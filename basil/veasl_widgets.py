"""
Quantiphyse - Vessel Encoded ASL widgets

Copyright (c) 2016-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import, print_function

import math

import numpy as np
from PySide import QtCore, QtGui
import pyqtgraph as pg

from quantiphyse.gui.widgets import NumberGrid
from quantiphyse.gui.options import OptionBox, NumericOption

# TODO allow drag/drop XY only file

veslocs_default = np.array([
    [1.0000000e+01, -1.0000000e+01, 1.0000000e+01, -1.0000000e+01,],
    [1.0000000e+01, 1.0000000e+01, -1.0000000e+01, -1.0000000e+01,],
    [0.3, 0.3, 0.3, 0.3,],
], dtype=np.float)   

class EncodingWidget(QtGui.QWidget):
    """
    Widget which displays the encoding setup in MAC and TWO forms and keeps the two in sync
    """

    def __init__(self, *args, **kwargs):
        QtGui.QWidget.__init__(self, *args, **kwargs)
        self.veslocs = None
        self.imlist = None
        self.nvols = 0
        self.updating = False

        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        hbox = QtGui.QHBoxLayout()
        self.auto_combo = QtGui.QComboBox()
        self.auto_combo.addItem("Automatic (vessels are RC, LC, RV, LV brain arteries)")
        self.auto_combo.addItem("Custom")
        self.auto_combo.currentIndexChanged.connect(self._auto_changed)
        hbox.addWidget(self.auto_combo)

        self.mode_combo = QtGui.QComboBox()
        self.mode_combo.addItem("TWO specification")
        self.mode_combo.addItem("MAC specification")
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        hbox.addWidget(self.mode_combo)
        vbox.addLayout(hbox)

        self.warning = QtGui.QLabel()
        self.warning.setVisible(False)
        vbox.addWidget(self.warning)

        self.two_mtx = NumberGrid([[0, 0, 0, 0]], col_headers=["\u03b8 (\u00b0)", "Image type", "vA", "vB"], expandable=(False, True), fix_height=True)
        self.two_mtx.sig_changed.connect(self._two_changed)
        vbox.addWidget(self.two_mtx)

        self.mac_mtx = NumberGrid([[0], [0], [0], [0]], row_headers=["CX", "CY", "\u03b8 (\u00b0)", "D"], expandable=(True, False), fix_height=True)
        self.mac_mtx.sig_changed.connect(self._mac_changed)
        vbox.addWidget(self.mac_mtx)

        self._mode_changed(0)

    def _auto_changed(self):
        self._autogen()
        
    def _mode_changed(self, idx):
        self.two_mtx.setVisible(idx == 0)
        self.mac_mtx.setVisible(idx == 1)

    def set_nvols(self, nvols):
        """
        Set the total number of tag/control and encoded volumes
        """
        self.nvols = nvols
        self._autogen()

    def set_veslocs(self, veslocs):
        """
        Set the initial vessel locations.
        
        If enabled, this automatically generates an encoding matrix from initial vessel locations
        with either 6 or 8 encoding images
        """
        self.veslocs = np.array(veslocs)
        self._autogen()

    def _warn(self, warning):
        if warning:
            self.warning.setText(warning)
            self.warning.setVisible(True)
        else:
            self.warning.setVisible(False)

    def _autogen(self):
        auto_mode = self.auto_combo.currentIndex()
        if auto_mode == 1:
            # Auto-generation disabled
            return

        self._warn("")
        nvols = self.nvols
        if nvols == 0:
            # Default if data is not loaded
            nvols = 8
            
        if self.veslocs is None:
            # No vessels defined
            return

        if nvols not in (6, 8):
            self._warn("Auto-generation of encoding matrix only supported for 6 or 8 encoding cycles")
            return

        num_vessels = self.veslocs.shape[1]
        if num_vessels != 4:
            self._warn("Auto-generation of encoding matrix only supported with 4 inferred vessels")
            return

        lr1, lr2 = self.veslocs[0, 0], self.veslocs[0, 1]
        ap1, ap2 = np.mean(self.veslocs[1, :2]), np.mean(self.veslocs[1, 2:])
        two = [
            [0, 0, 0, 0],
            [0, 1, 0, 0],
            [90, 2, lr1, lr2],
            [90, 3, lr1, lr2],
            [0, 2, ap1, ap2],
            [0, 3, ap1, ap2],
        ]
        if nvols == 8:
            # Vector from RC to LV
            LV_minus_RC = self.veslocs[:2, 3] - self.veslocs[:2, 0]

            # Want to tag RC and LV simultaneously - gradient angle required
            # is acos[normalised(LV - RC).x]
            tag_rad = math.acos(LV_minus_RC[0] / np.linalg.norm(LV_minus_RC))
            tag_deg = math.degrees(tag_rad)

            # Unit vector in gradient direction
            G = [math.sin(tag_rad), math.cos(tag_rad)]

            # Calculate distance from isocentre to each vessel
            # Dot product of location with gradient unit vector
            isodist = [sum(self.veslocs[:2, v] * G) for v in range(num_vessels)]
            vA = (isodist[0] + isodist[3])/2
            vB = vA + (abs(vA -isodist[1]) + abs(vA - isodist[2]))/2
            two += [
                [tag_deg, 2, vA, vB],
                [tag_deg, 3, vA, vB],
            ]

        self.two_mtx.setValues(two)

    def _update_imlist(self):
        """
        Update the imlist from the TWO encoding matrix 
        """
        two = np.array(self.two_mtx.values())
        self.imlist = two[:, 1] - 1
        inc = 1
        for i in range(len(self.imlist)):
            if self.imlist[i] > 0:
                self.imlist[i] = inc
                inc += 1
        
    def _two_changed(self):
        """
        Update MAC matrix to match TWO matrix
        """
        if self.updating: return

        self._update_imlist()
        two = np.array(self.two_mtx.values())

        # Encoding cycles - second column
        enccyc = two[:, 1] > 1

        # angles TWO measures angle from AP anti-clock, MAC from LR clock
        th = -two[:, 0][enccyc] + 90
        # MAC uses 180 rotation to indicate reversal of modulation function, thus it
        # is important which of vA or Vb is lower, as for TWO this would reverse
        # the modulation function
        th[two[enccyc, 2] > two[enccyc, 3]] = th[two[enccyc, 2] > two[enccyc, 3]] + 180

        # scales
        D = np.abs(two[enccyc, 2] - two[enccyc, 3]) / 2

        # centres
        thtsp = two[enccyc, 0] * 3.14159265 / 180
        conline = np.mean(two[enccyc, 2:4], 1)

        cx = conline * np.sin(thtsp)
        cy = conline * np.cos(thtsp)

        # reverse cycles
        # these are cycles where the tagging of vessels is reversed, Tom does this
        # by shifting the phase of the moudlation function. So this is NOT 180
        # rotation in my convention, but a shift in the encoding centre
        revcyc = two[enccyc, 1] > 2
        cx[revcyc] = (conline[revcyc] + 2*D[revcyc]) * np.sin(thtsp[revcyc])
        cy[revcyc] = (conline[revcyc] + 2*D[revcyc]) * np.cos(thtsp[revcyc])

        mac = [cx, cy, th, D]
        self.updating = True
        try:
            self.mac_mtx.setValues(mac)
        finally:
            self.updating = False

    def _mac_changed(self):
        """ 
        Convert MAC format encoding into TWO format

        This is an inverse of _two_changed done with remarkably little understanding.
        It seems to assume that 'reverse cycles' occur in odd numbered images which 
        seems unreasonable, but I can't see an obvious way to detect this otherwise
        """
        if self.updating: return
        mac = np.array(self.mac_mtx.values())

        imlist = np.array(self.imlist) + 1
        for idx, imcode in enumerate(self.imlist):
            if imcode > 0:
                imlist[idx] = 2 + (imlist[idx] % 2)

        th = np.zeros(len(imlist))
        th_mac = np.zeros(len(imlist))
        va = np.zeros(len(imlist))
        vb = np.zeros(len(imlist))
        cx = np.zeros(len(imlist))
        cy = np.zeros(len(imlist))
        d = np.zeros(len(imlist))
    
        cx[imlist > 1] = mac[0, :]
        cy[imlist > 1] = mac[1, :]
        d[imlist > 1] = mac[3, :]
        th[imlist > 1] = mac[2, :]
        th_mac[imlist > 1] = mac[2, :]

        # Angles
        #
        # MAC uses 180 rotation to indicate reversal of modulation function, thus it
        # is important which of vA or Vb is lower, as for TWO this would reverse
        # the modulation function
        # TWO measures angle from AP anti-clock, MAC from LR clock
        rev_mod = th > 180
        th[rev_mod] = th[rev_mod] - 180
        th[imlist > 1] = -th[imlist > 1] + 90

        # Scales and centres
        for idx, itype in enumerate(imlist):
            if itype > 1:
                s = np.sin(th[idx] * 3.14159265 / 180)
                c = np.cos(th[idx] * 3.14159265 / 180)
                if np.abs(s) > np.abs(c):
                    vb[idx] = cx[idx] / s + d[idx]
                    va[idx] = cx[idx] / s - d[idx]
                else:
                    vb[idx] = cy[idx] / c + d[idx]
                    va[idx] = cy[idx] / c - d[idx]

            if itype == 3:
                vb[idx] = vb[idx] - 2*d[idx]
                va[idx] = va[idx] - 2*d[idx]
        
            if th_mac[idx] > 180:
                va[idx], vb[idx] = vb[idx], va[idx]

        two = np.column_stack((th, imlist, va, vb))
        self.updating = True
        try:
            self.two_mtx.setValues(two)
            self._update_imlist()
        finally:
            self.updating = False

class PriorsWidget(QtGui.QWidget):
    """
    Widget providing priors options
    """

    def __init__(self, *args, **kwargs):
        QtGui.QWidget.__init__(self, *args, **kwargs)
        vbox = QtGui.QVBoxLayout()
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

class VeslocsWidget(QtGui.QWidget):
    """
    Widget for setting initial vessel locations and viewing inferred locations
    """

    sig_initial_changed = QtCore.Signal(object)

    def __init__(self, *args, **kwargs):
        QtGui.QWidget.__init__(self, *args, **kwargs)

        grid = QtGui.QGridLayout()
        self.setLayout(grid)

        grid.addWidget(QtGui.QLabel("Initial"), 0, 0)
        self.vessels_initial = NumberGrid([[], [], []], row_headers=["X", "Y", "v"], expandable=(True, False), fix_height=True)
        self.vessels_initial.sig_changed.connect(self._initial_vessels_changed)
        grid.addWidget(self.vessels_initial, 1, 0)

        grid.addWidget(QtGui.QLabel("Inferred"), 2, 0)
        self.vessels_inferred = NumberGrid([[], [], []], row_headers=["X", "Y", "v"], expandable=(True, False), fix_height=True)
        self.vessels_inferred.sig_changed.connect(self._inferred_vessels_changed)
        grid.addWidget(self.vessels_inferred, 3, 0) 

        # Vessel locations plot
        plot_win = pg.GraphicsLayoutWidget()
        plot_win.setBackground(background=None)
        #sizePolicy = QtGui.QSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Preferred)
        #sizePolicy.setHeightForWidth(True)
        #plot_win.setSizePolicy(sizePolicy)
        plot_win.setFixedSize(200, 200)

        self.vessel_plot = plot_win.addPlot(lockAspect=True)
        self.vessel_plot.showAxis('right')
        self.vessel_plot.showAxis('top')
        grid.addWidget(plot_win, 0, 1, 5, 1)
   
    def _initial_vessels_changed(self):
        vessel_data = self.vessels_initial.values()
        if len(vessel_data) == 2:
            vessel_data.append([0.3,] * len(vessel_data[0]))
            self.vessels_initial.setValues(vessel_data, validate=False, row_headers=["X", "Y", "v"])
        self.vessels_inferred.setValues(vessel_data, validate=False, row_headers=["X", "Y", "v"])
        self._update_vessel_plot()
        self.sig_initial_changed.emit(vessel_data)

    def _inferred_vessels_changed(self):
        self._update_vessel_plot()

    def _update_vessel_plot(self):
        """ Plot vessel locations on graph """
        veslocs = self.vessels_initial.values()
        veslocs_inferred = self.vessels_inferred.values()
        self.vessel_plot.clear()
        self.vessel_plot.plot(veslocs[0], veslocs[1], 
                              pen=None, symbolBrush=(50, 50, 255), symbolPen='k', symbolSize=10.0)
        self.vessel_plot.plot(veslocs_inferred[0], veslocs_inferred[1], 
                              pen=None, symbolBrush=(255, 50, 50), symbolPen='k', symbolSize=10.0)
        self.vessel_plot.autoRange()

class ClasslistWidget(NumberGrid):
    """
    Widget which displays the class list and inferred proportions
    """

    def __init__(self):
        NumberGrid.__init__(self, [[], [], [], [], []], expandable=(False, False), fix_height=True)
    
    def update(self, num_sources, nfpc):
        """
        Update the class list for a given number of sources and number of sources per class
        """
        classes = self._make_classlist(num_sources, nfpc)
        if not classes:
            return
        if len(self.values()) == len(classes):
            pis = [row[-1] for row in self.values()]
        else:
            # Number of sources has changed so current PIs are invalid
            pis = [1/float(len(classes)),] * len(classes)
        classes = [c + [pi,] for c, pi in zip(classes, pis)]
        row_headers = ["Class %i" % (i+1) for i in range(len(classes))]
        col_headers = ["Vessel %i" % (i+1) for i in range(num_sources)] + ["Proportion",]
        self.setValues(classes, validate=False, col_headers=col_headers, row_headers=row_headers)

    def set_pis(self, pis):
        """
        Set the inferred proportions of each class
        """
        current_values = self.values()
        if len(current_values) != len(pis):
            raise ValueError("Number of PIs must match number of classes")
        num_sources = len(current_values[0]) - 1
        new_values = [[c[0], c[1], pi] for c, pi in zip(current_values, pis)]
        row_headers = ["Class %i" % (i+1) for i in range(len(current_values))]
        col_headers = ["Vessel %i" % (i+1) for i in range(num_sources)] + ["Proportion",]
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
