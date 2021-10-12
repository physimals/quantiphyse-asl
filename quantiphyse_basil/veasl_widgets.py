"""
Quantiphyse - Vessel Encoded ASL widgets

Copyright (c) 2016-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import, print_function

import traceback

import numpy as np

from PySide2 import QtGui, QtCore, QtWidgets

import pyqtgraph as pg

from quantiphyse.gui.widgets import NumberGrid
from quantiphyse.gui.options import OptionBox, NumericOption

# TODO allow drag/drop XY only file

veslocs_default = np.array([
    [1.0000000e+01, -1.0000000e+01, 1.0000000e+01, -1.0000000e+01,],
    [1.0000000e+01, 1.0000000e+01, -1.0000000e+01, -1.0000000e+01,],
], dtype=np.float)   

class EncodingWidget(QtWidgets.QWidget):
    """
    Widget which displays the encoding setup in MAC and TWO forms and keeps the two in sync
    """

    def __init__(self, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, *args, **kwargs)
        self._veslocs = None
        self._nenc = 0
        self._updating = False
        self.imlist = None

        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)

        hbox = QtWidgets.QHBoxLayout()
        self.auto_combo = QtWidgets.QComboBox()
        self.auto_combo.addItem("Automatic (vessels are RC, LC, RV, LV brain arteries)")
        self.auto_combo.addItem("Custom")
        self.auto_combo.currentIndexChanged.connect(self._auto_changed)
        hbox.addWidget(self.auto_combo)

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("TWO specification")
        self.mode_combo.addItem("MAC specification")
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        hbox.addWidget(self.mode_combo)
        vbox.addLayout(hbox)

        self.warning = QtWidgets.QLabel()
        self.warning.setVisible(False)
        vbox.addWidget(self.warning)

        self.two_mtx = NumberGrid([[0, 0, 0, 0]], col_headers=["\u03b8 (\u00b0)", "Image type", "vA", "vB"], expandable=(False, True), fix_height=True)
        self.two_mtx.sig_changed.connect(self._two_changed)
        vbox.addWidget(self.two_mtx)

        self.mac_mtx = NumberGrid([[0], [0], [0], [0]], row_headers=["CX", "CY", "\u03b8 (\u00b0)", "D"], expandable=(True, False), fix_height=True)
        self.mac_mtx.sig_changed.connect(self._mac_changed)
        vbox.addWidget(self.mac_mtx)

        self._mode_changed(0)

    @property
    def mac(self):
        return np.array(self.mac_mtx.values())

    @property
    def two(self):
        return np.array(self.two_mtx.values())
        
    @property
    def veslocs(self):
        return self._veslocs
    
    @veslocs.setter
    def veslocs(self, veslocs):
        self._veslocs = np.array(veslocs)
        self._autogen()
        
    @property
    def nenc(self):
        return self._nenc
    
    @nenc.setter
    def nenc(self, nenc):
        self._nenc = nenc
        self._autogen()
        
    def _auto_changed(self):
        self._autogen()
        
    def _mode_changed(self, idx):
        self.two_mtx.setVisible(idx == 0)
        self.mac_mtx.setVisible(idx == 1)


    def _warn(self, warning):
        if warning:
            self.warning.setText(warning)
            self.warning.setVisible(True)
        else:
            self.warning.setVisible(False)

    def _autogen(self):
        if self.veslocs is not None and self.auto_combo.currentIndex() == 0:
            try:
                nenc = self._nenc
                if nenc == 0:
                    # Default if data is not loaded
                    nenc = 8

                from oxasl_ve import veslocs_to_enc
                two = veslocs_to_enc(self.veslocs[:2, :], nenc)
                self.two_mtx.setValues(two)
                self._warn("")
            except ValueError as exc:
                self._warn(str(exc))
            except Exception as exc:
                print(exc)
            except:
                import traceback
                traceback.print_exc()
        
    def _two_changed(self):
        """
        Update MAC matrix to match TWO matrix
        """
        if not self._updating: 
            try:
                from oxasl_ve import two_to_mac
                self._updating = True
                two = np.array(self.two_mtx.values())
                mac, self.imlist = two_to_mac(two)
                self.mac_mtx.setValues(mac)
            finally:
                self._updating = False

    def _mac_changed(self):
        """ 
        Convert MAC format encoding into TWO format

        This is an inverse of _two_changed done with remarkably little understanding.
        It seems to assume that 'reverse cycles' occur in odd numbered images which 
        seems unreasonable, but I can't see an obvious way to detect this otherwise
        """
        if not self._updating: 
            try:
                from oxasl_ve import mac_to_two
                self._updating = True
                mac = np.array(self.mac_mtx.values())
                two, self.imlist = mac_to_two(mac)
                self.two_mtx.setValues(two)
            finally:
                self._updating = False

class PriorsWidget(QtWidgets.QWidget):
    """
    Widget providing priors options
    """

    def __init__(self, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, *args, **kwargs)
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        self.optbox.add("Prior standard deviation on co-ordinates", NumericOption(minval=0, maxval=2, default=1), key="xy-std")
        self.optbox.add("(distance units defined by encoding setup)")
        self.optbox.add("Prior mean for flow velocity", NumericOption(minval=0, maxval=1, default=0.3), key="v-mean")
        self.optbox.add("Prior standard deviation for flow velocity", NumericOption(minval=0, maxval=0.1, decimals=3, default=0.01), key="v-std")
        self.optbox.add("Prior mean for rotation angle (\u00b0)", NumericOption(minval=0, maxval=5, default=1.2), key="rot-std")
        vbox.addWidget(self.optbox)

    def set_infer_v(self, infer_v):
        """ Set whether flow velocity should be inferred - enables modification of prior"""
        self.optbox.option("v-mean").setEnabled(infer_v)
        self.optbox.option("v-std").setEnabled(infer_v)
    
    def set_infer_transform(self, infer_trans):
        """ Set whether vessel locations are inferred by transformation - enables modification of prior for rotation angle"""
        self.optbox.option("rot-std").setEnabled(infer_trans)

    def options(self):
        """ :return: options as dictionary """
        return self.optbox.values()

class VeslocsWidget(QtWidgets.QWidget):
    """
    Widget for setting initial vessel locations and viewing inferred locations
    """

    sig_initial_changed = QtCore.Signal(object)

    def __init__(self, *args, **kwargs):
        QtWidgets.QWidget.__init__(self, *args, **kwargs)

        grid = QtWidgets.QGridLayout()
        self.setLayout(grid)

        grid.addWidget(QtWidgets.QLabel("Initial"), 0, 0)
        self.vessels_initial = NumberGrid([[], []], row_headers=["X", "Y"], expandable=(True, False), fix_height=True)
        self.vessels_initial.sig_changed.connect(self._initial_vessels_changed)
        grid.addWidget(self.vessels_initial, 1, 0)

        grid.addWidget(QtWidgets.QLabel("Inferred"), 2, 0)
        self.vessels_inferred = NumberGrid([[], []], row_headers=["X", "Y"], expandable=(True, False), fix_height=True)
        self.vessels_inferred.sig_changed.connect(self._inferred_vessels_changed)
        grid.addWidget(self.vessels_inferred, 3, 0) 

        # Vessel locations plot
        plot_win = pg.GraphicsLayoutWidget()
        plot_win.setBackground(background=None)
        plot_win.setFixedSize(200, 200)

        self.vessel_plot = plot_win.addPlot(lockAspect=True)
        self.vessel_plot.showAxis('right')
        self.vessel_plot.showAxis('top')
        grid.addWidget(plot_win, 0, 1, 5, 1)
   
    @property
    def initial(self):
        return np.array(self.vessels_initial.values())

    @initial.setter
    def initial(self, locs):
        self.vessels_initial.setValues(locs, validate=False, row_headers=["X", "Y"])

    @property
    def inferred(self):
        return self.vessels_inferred.values()

    @inferred.setter
    def inferred(self, locs):
        self.vessels_inferred.setValues(locs, validate=False, row_headers=["X", "Y"])
        
    def _initial_vessels_changed(self):
        try:
            vessel_data = self.vessels_initial.values()
            self.vessels_inferred.setValues(vessel_data, validate=False, row_headers=["X", "Y"])
            self._update_vessel_plot()
            self.sig_initial_changed.emit(vessel_data)
        except ValueError:
            traceback.print_exc() # FIXME need to handle ValueError

    def _inferred_vessels_changed(self):
        self._update_vessel_plot()

    def _update_vessel_plot(self):
        try:
            # Plot vessel locations on graph
            veslocs = self.vessels_initial.values()
            veslocs_inferred = self.vessels_inferred.values()
            self.vessel_plot.clear()
            self.vessel_plot.plot(veslocs[0], veslocs[1], 
                                pen=None, symbolBrush=(50, 50, 255), symbolPen='k', symbolSize=10.0)
            self.vessel_plot.plot(veslocs_inferred[0], veslocs_inferred[1], 
                                pen=None, symbolBrush=(255, 50, 50), symbolPen='k', symbolSize=10.0)
            self.vessel_plot.autoRange()
        except ValueError:
            traceback.print_exc() # FIXME need to handle ValueError

class ClasslistWidget(NumberGrid):
    """
    Widget which displays the class list and inferred proportions
    """

    def __init__(self):
        NumberGrid.__init__(self, [[], [], [], [], []], expandable=(False, False), fix_height=True)
        self.generate_classes(4, 2)
    
    def generate_classes(self, num_sources, nfpc):
        """
        Reset the class list for a given number of sources and number of sources per class
        """
        classes = self._make_classlist(num_sources, nfpc)
        self.num_sources = num_sources
        self._update(classes)
        
    @property
    def classes(self):
        return [row[:self.num_sources] for row in self.values()]

    @property
    def inferred_pis(self):
        return [row[self.num_sources+1:] for row in self.values()]

    @inferred_pis.setter
    def inferred_pis(self, pis):
        classes = self.classes
        if len(pis) != len(classes):
            raise ValueError("Number of inferred PIs must match number of classes")
        self._update(classes, pis)
    
    def _update(self, classes, inferred_pis=None):
        if inferred_pis is None:
            inferred_pis = [[],] * len(classes)
            num_plds = 0
        else:
            num_plds = len(inferred_pis[0])

        new_values = [c + [1/float(len(classes)),] + list(pi) for c, pi in zip(classes, inferred_pis)]
        row_headers = ["Class %i" % (i+1) for i in range(len(classes))]
        col_headers = ["Vessel %i" % (i+1) for i in range(len(classes[0]))] + \
                      ["Initial Proportions",] + \
                      ["PLD %i Proportions" % (i+1) for i in range(num_plds)]

        self.setValues(new_values, validate=False, col_headers=col_headers, row_headers=row_headers)

    def _make_classlist(self, nsources, nfpc):
        """
        Generate the class list with specified number of sources per class
        A rather crude approach is used which will be fine so long as nsources
        is not too big. We generate all combinations of sources and just select
        those where the total number of sources is correct

        The equivalent code was 70 lines of c++ :-)
        """
        classlist = [c for c in self._all_combinations(nsources) if sum(c) == nfpc]
        # add class with no flows in FIXME not in Matlab - should we do thi?
        # classlist += [0,] * nsources
        return classlist

    def _all_combinations(self, nsources):
        if nsources == 0:
            yield []
        else:
            for c in self._all_combinations(nsources-1):
                yield [0,] + c
                yield [1,] + c
