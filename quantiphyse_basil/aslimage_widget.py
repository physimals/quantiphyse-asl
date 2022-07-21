"""
QP-BASIL - QWidget which displays and edits the metadata for ASL data

The metadata includes data ordering/structure and acquisition parameters

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import
import itertools
import traceback

import numpy as np
import scipy

from PySide2 import QtGui, QtCore, QtWidgets

from quantiphyse.gui.widgets import OverlayCombo, ChoiceOption, NumericOption, OrderList, OrderListButtons, WarningBox
import quantiphyse.gui.options as opt
from quantiphyse.utils import LogSource, QpException

from .process import  qpdata_to_aslimage, fslimage_to_qpdata

from ._version import __version__

ORDER_LABELS = {
    "r" : ("Repeat ", "R", "Repeats"), 
    "t" : ("TI ", "TI", "TIs/PLDs"),
    "l" : {
        "tc" : (("Label", "Control"), ("L", "C"), "Label-Control pairs"),
        "ct" : (("Control", "Label"), ("C", "L"), "Control-Label pairs"),
        "mp" : ("Phase ", "Ph", "Phases"),
        "ve" : ("Encoding ", "Enc", "Encoding cycles"),
        "diff" : ("", "", ""),
    }
}

TIMING_LABELS = {
    True : "PLDs",
    False : "TIs",
}

"""
Default metadata which should work for any data file
"""
DEFAULT_METADATA = {
    "iaf" : "diff",
    "ibf" : "tis", 
    "tis" : [1.5,], 
    "taus" : [1.8,], 
    "casl" : True
}

class AslMetadataView(object):
    """
    Objects which displays and potentially changes ASL metadata
    """

    # Signal emitted when this view changes the metadata
    sig_md_changed = QtCore.Signal(object)

    def __init__(self):
        self.data = None
        self.md = dict(DEFAULT_METADATA)

    def set_data(self, data, metadata):
        """
        Sets the data whose ASL metadata is to be displayed
        
        Sets the attributes ``data``, ``md`` and calls ``_update()``

        :param data: QpData object 
        """
        self.data = data
        self.md = metadata

        # Make sure we always have some basic defaults
        if "tis" not in self.md and "plds" not in self.md: self.md["tis"] = [1.5]
        if "taus" not in self.md: self.md["taus"] = [1.4]
        if "iaf" not in self.md: self.md["iaf"] = "diff"
        if "order" not in self.md and "ibf" not in self.md:
            self.md["ibf"] = "rpt"
        self._update()

    def _update(self):
        """
        Override to update the view when the data object changes
        """
        pass

def get_num_label_vols(md):
    """
    Get the number of volumes used for labelling - e.g. 2 for tag-control pair data
    """
    iaf = md.get("iaf", "tc")
    if iaf in ("tc", "ct"):
        return 2
    elif iaf == "diff":
        return 1
    elif iaf == "mp":
        return md.get("nphases", 8)
    elif iaf == "ve":
        return md.get("nenc", 8)

def get_auto_repeats(md, data):
    """
    Guess a set of repeats values for each TI which are consistent with the data size
    
    In the case where the data is consistent with fixed repeats this will always
    return fixed repeats
    """
    if data is None: 
        return [1,]
    
    nvols = data.nvols
    ntis = len(md.get("tis", md.get("plds", [1.5])))
    nrpts = float(nvols) / ntis
    ntc = get_num_label_vols(md)
    
    nrpts /= ntc
    rpts = [max(1, int(nrpts)),] * ntis
    missing = sum(rpts) * ntc
    for idx in range(min(0, missing)):
        rpts[idx] += 1
    return rpts

def get_order_string(md):
    """
    Get the effective ordering string for a set of metadata
    """
    from oxasl.image import data_order
    _, order, _ = data_order(md.get("iaf", None), md.get("ibf", None), md.get("order", None))
    return order

class DataStructure(QtWidgets.QWidget, AslMetadataView):
    """
    Visual preview of the structure of an ASL data set
    """
    def __init__(self, grid, ypos):
        QtWidgets.QWidget.__init__(self)
        AslMetadataView.__init__(self)
        self.hfactor = 0.95
        self.vfactor = 0.95
        self.cols = {
            "r" : (128, 128, 255, 128), 
            "t" : (255, 128, 128, 128), 
            "l" : (128, 255, 128, 128),
        }
        self.order = "lrt"
        self.num = {"t" : 1, "r" : 3, "l" : 2}
        grid.addWidget(self, ypos, 0, 1, 3)

    def _update(self):
        self.order = get_order_string(self.md)
        self.num = {
            "t" : len(self.md.get("tis", self.md.get("plds", [1]))),
            # This is for display purposes only so good enough for variable repeats
            "r" : self.md.get("nrpts", get_auto_repeats(self.md, self.data)[0]),
            "l" : get_num_label_vols(self.md)
        }
        self.repaint()
        self.setFixedHeight((self.fontMetrics().height() + 2)*len(self.order))

    def paintEvent(self, _):
        """
        Re-draw the structure diagram
        """
        h, w = self.height(), self.width()
        group_height = h*self.vfactor / len(self.order)
        group_width = self.hfactor*w
        ox = w*(1-self.hfactor)/2
        oy = h*(1-self.vfactor)/2
        p = QtGui.QPainter(self)
        self._draw_groups(p, self.order[::-1], ox, oy, group_width, group_height)

    def _get_label(self, code, num, short):
        labels = ORDER_LABELS[code]
        if isinstance(labels, dict):
            labels = labels[self.md.get("iaf", "tc")]
        label = labels[int(short)]
        if isinstance(label, tuple):
            return label[num]
        else:
            return label + str(num+1)
        
    def _draw_groups(self, p, groups, ox, oy, width, height, cont=False):
        if not groups: return
        else:
            small = width < 150 # Heuristic
            group = groups[0]
            col = self.cols[group]
            if cont:
                p.fillRect(ox, oy, width-1, height-1, QtGui.QBrush(QtGui.QColor(*col)))
                p.drawText(ox, oy, width-1, height, QtCore.Qt.AlignHCenter, "...")
                self._draw_groups(p, groups[1:], ox, oy+height, width, height, cont=True)
            else:
                num = self.num[group]
                # Half the width of a normal box (full with of ellipsis box)
                w = width/min(2*num, 5)

                # Draw first box
                label = self._get_label(group, 0, small)
                p.fillRect(ox, oy, 2*w-1, height-1, QtGui.QBrush(QtGui.QColor(*col)))
                p.drawText(ox, oy, 2*w-1, height, QtCore.Qt.AlignHCenter, label)
                self._draw_groups(p, groups[1:], ox, oy+height, 2*w, height)
                ox += 2*w
                
                # Draw ellipsis if required
                if num > 2:
                    self._draw_groups(p, groups, ox, oy, w, height, cont=True)
                    ox += w

                # Draw last box if required
                if num > 1:
                    label = self._get_label(group, num-1, small)
                    p.fillRect(ox, oy, 2*w-1, height-1, QtGui.QBrush(QtGui.QColor(*col)))
                    p.drawText(ox, oy, 2*w-1, height, QtCore.Qt.AlignHCenter, label)
                    self._draw_groups(p, groups[1:], ox, oy+height, 2*w, height)

class SignalPreview(QtWidgets.QWidget, LogSource):
    """
    Visual preview of the signal expected from an ASL data set
    """
    HFACTOR = 0.95
    VFACTOR = 0.95

    def __init__(self):
        LogSource.__init__(self)
        QtWidgets.QWidget.__init__(self)
        self._order = "lrt"
        self._num = {"l" : 2, "r" : 1, "t" : 1}
        self._md = None
        self._data = None
        self.mean_signal = None
        self.fitted_signal = None
        self.cost = None
        self.setFixedHeight(50)

    @property
    def md(self):
        """ Metadata dictionary"""
        return self._md

    @md.setter
    def md(self, md):
        self._md = md
        self._update()

    @property
    def data(self):
        """ QpData object containing actual ASL data"""
        return self._data

    @data.setter
    def data(self, data):
        self._data = data
        self._update()

    def _update(self):
        if self._data is not None and self._md is not None:
            self._order = get_order_string(self._md)
            self._num = {
                "t" : len(self._md.get("tis", self.md.get("plds", [1]))),
                "r" : self._md.get("nrpts", get_auto_repeats(self._md, self._data)[0]),
                "l" : get_num_label_vols(self._md)
            }
            self._get_mean_signal()
            self._get_fitted_signal()
            self.repaint()

    def paintEvent(self, _):
        """
        Re-draw the structure diagram
        """
        h, w = self.height(), self.width()
        ox = w*(1-self.HFACTOR)/2
        oy = h*(1-self.VFACTOR)/2
        p = QtGui.QPainter(self)
        p.drawLine(0, h-1, 0, 0)
        p.drawLine(0, h-1, w-1, h-1)
        if self._data is not None:
            self._draw_signal(self.fitted_signal, p, ox, oy, w*self.HFACTOR, h*self.VFACTOR, col=QtCore.Qt.red)
            self._draw_signal(self.mean_signal, p, ox, oy, w*self.HFACTOR, h*self.VFACTOR, col=QtCore.Qt.green)

    def _get_mean_signal(self):
        if self._data is not None:
            rawdata = self._data.raw()
            voxel_range = np.nanmax(rawdata, axis=-1) - np.nanmin(rawdata, axis=-1)
            good_signal = np.percentile(voxel_range, 99)
            good_signals = rawdata[voxel_range >= good_signal]
            self.mean_signal = np.mean(good_signals, axis=0)

    def _draw_signal(self, sig, p, ox, oy, w, h, col):
        sigmin, sigmax = np.min(sig), np.max(sig)
        sigrange = sigmax - sigmin
        if sigrange == 0:
            yvals = [oy + 0.5*h for _ in sig]
        else:
            yvals = [oy + (1-float(val-sigmin)/sigrange)*h for val in sig]

        path = QtGui.QPainterPath(QtCore.QPointF(ox, yvals[0])) 
        pen = QtGui.QPen(QtGui.QBrush(col), 2, QtCore.Qt.SolidLine)
        p.setPen(pen)
        npts = len(yvals)
        for idx, yval in enumerate(yvals):
            x, y = ox+w*float(idx)/npts, yval
            path.lineTo(x, y)
        p.drawPath(path)

    def _get_fitted_signal(self):
        sigmin, sigmax = np.min(self.mean_signal), np.max(self.mean_signal)
        sigrange = sigmax - sigmin
        if sigrange == 0:
            sigrange = 1
        initial = sigrange * np.arange(self._num["t"])[::-1] + sigmin
        try:
            result = scipy.optimize.least_squares(self._sigdiff, initial)
            self.fitted_signal = self._tdep_to_signal(result.x)
            self.cost = result.cost
        except Exception as exc:
            self.warn("Error optimizing least squares: %s" % exc)
            self.warn("Initial values provided: %s" % initial)
            self.fitted_signal = initial
            self.cost = 0

    def _tdep_to_signal(self, tdep):
        vals = []
        for char in self._order[::-1]:
            vals.append(range(self._num[char]))
        t_idx = self._order[::-1].index('t')
        return np.array([tdep[items[t_idx]] for items in itertools.product(*vals)])

    def _sigdiff(self, tdep):
        signal = self._tdep_to_signal(tdep)
        if len(signal) >= len(self.mean_signal):
            return self.mean_signal - signal[:len(self.mean_signal)]
        else:
            return self.mean_signal - (list(signal) + [0,] * (len(self.mean_signal) - len(signal)))

class SignalView(QtCore.QObject, AslMetadataView):
    """
    Shows a preview of the actual mean ASL signal and the predicted signal
    based on the data structure specified
    """

    def __init__(self, grid, ypos):
        QtCore.QObject.__init__(self)
        AslMetadataView.__init__(self)
        self.preview = SignalPreview()
        label = QtWidgets.QLabel("Signal fit\nGreen=data\nRed=prediction")
        label.setWordWrap(True)
        grid.addWidget(label, ypos, 0, alignment=QtCore.Qt.AlignTop)
        grid.addWidget(self.preview, ypos, 1, 1, 2)

    def _update(self):
        self.preview.md = self.md
        if self.data is not None:
            self.preview.data = self.data

class NumPhases(NumericOption, AslMetadataView):
    """
    Displays/Sets the number of phases for a multiphase data set
    """

    def __init__(self, grid, ypos):
        NumericOption.__init__(self, "Number of Phases (evenly spaced)", grid, ypos, default=8, intonly=True, minval=2)
        AslMetadataView.__init__(self)
        self.sig_changed.connect(self._changed)
    
    def _update(self):
        # Phase list only visible in multiphase mode
        multiphase = self.md.get("iaf", "") == "mp"
        self.label.setVisible(multiphase)
        self.spin.setVisible(multiphase)
        if multiphase:
            self.spin.setValue(self.md.get("nphases", 8))
            if "nphases" not in self.md:
                self._changed()

    def _changed(self):
        if self.spin.isVisible():
            self.md["nphases"] = self.spin.value()
        else:
            self.md.pop("nphases", None)
        self.sig_md_changed.emit(self)

class NumEncodings(NumericOption, AslMetadataView):
    """
    Displays/Sets the number of encoding cycles for a VE data set
    """

    def __init__(self, grid, ypos):
        NumericOption.__init__(self, "Number of encoding cycles", grid, ypos, default=8, intonly=True, minval=2)
        AslMetadataView.__init__(self)
        self.sig_changed.connect(self._changed)
    
    def _update(self):
        # Only visible for vessel encoded data
        ve = self.md.get("iaf", "") == "ve"
        self.label.setVisible(ve)
        self.spin.setVisible(ve)
        if ve:
            self.spin.setValue(self.md.get("nenc", 8))
            if "nenc" not in self.md:
                self._changed()

    def _changed(self):
        if self.spin.isVisible():
            self.md["nenc"] = self.spin.value()
        else:
            self.md.pop("nenc", None)
        self.sig_md_changed.emit(self)

class DataOrdering(QtCore.QObject, AslMetadataView):
    """
    Displays the current ordering of elements in the ASL data (e.g. TIs, repeats) and 
    allows the order to be modified by dragging them around
    """
    def __init__(self, grid, ypos):
        QtCore.QObject.__init__(self)
        AslMetadataView.__init__(self)
        grid.addWidget(QtWidgets.QLabel("Data grouping"), ypos, 0, alignment=QtCore.Qt.AlignTop)
        self.group_list = OrderList()
        grid.addWidget(self.group_list, ypos, 1)
        self.list_btns = OrderListButtons(self.group_list)
        grid.addLayout(self.list_btns, ypos, 2)
        self.group_list.sig_changed.connect(self._changed)
    
    def _get_label(self, order_char):
        labels = ORDER_LABELS[order_char]
        if isinstance(labels, dict):
            labels = labels[self.md.get("iaf", "tc")]
        return labels[2]

    def _update(self):
        order = self.md.get("order", "lrt")
        self.group_list.setItems([self._get_label(g) for g in order[::-1]])

    def _changed(self):
        order = ""
        for item in self.group_list.items():
            code = [char for char in ('t', 'r', 'l') if self._get_label(char) == item][0]
            order += code

        self.md["order"] = order[::-1]
        self.sig_md_changed.emit(self)

class BlockFormat(QtCore.QObject, AslMetadataView):
    """
    Menu to display/set the block format
    """

    def __init__(self, grid, ypos):
        QtCore.QObject.__init__(self)
        AslMetadataView.__init__(self)
        grid.addWidget(QtWidgets.QLabel("Data grouped by"), ypos, 0)
        hbox = QtWidgets.QHBoxLayout()
        self.choice = opt.ChoiceOption(["TIs", "Repeats", "Custom"], ["tis", "rpt", "custom"])
        hbox.addWidget(self.choice)
        self.order_edit = QtWidgets.QLineEdit()
        hbox.addWidget(self.order_edit)
        self.order_edit.setVisible(False)
        grid.addLayout(hbox, ypos, 1)
        self.detect_btn = QtWidgets.QPushButton("Auto detect")
        grid.addWidget(self.detect_btn, ypos, 2)

        self.choice.sig_changed.connect(self._changed)
        self.order_edit.editingFinished.connect(self._changed)
        self.detect_btn.clicked.connect(self._autodetect)
    
    def _update(self):
        if "order" in self.md:
            ibf = "custom"
        else:
            ibf = self.md.get("ibf", "custom")
        self.choice.value = ibf

        order = get_order_string(self.md)
        self.order_edit.setText(order)
        self.order_edit.setVisible(ibf == "custom")
        self.detect_btn.setEnabled(self.data is not None)

    def _changed(self):
        ibf = self.choice.value
        if ibf == "custom":
            self.md.pop("ibf", None)
            self.md["order"] = self.order_edit.text()
        else:
            self.md["ibf"] = ibf
            self.md.pop("order", None)
            
        self.sig_md_changed.emit(self)

    def _autodetect(self):
        fitter = SignalPreview()
        fitter.data = self.data
        order = get_order_string(self.md)
        trial_md = dict(self.md)
        trial_md.pop("ibf", None)
        best, best_order = 1e9, order
        for trial in itertools.permutations(order):
            trial = "".join(trial)
            trial_md["order"] = trial
            fitter.md = trial_md
            #self.debug("autodetect: %s, %f" % (trial, fitter.cost))
            if fitter.cost < best:
                best = fitter.cost
                best_order = trial
        if best_order.endswith("rt"):
            self.md["ibf"] = "tis"
            self.md.pop("order", None)
        elif best_order.endswith("tr"):
            self.md["ibf"] = "rpt"
            self.md.pop("order", None)
        else:
            self.md.pop("ibf", None)
            self.md["order"] = best_order

        self.sig_md_changed.emit(self)
        
class LabelType(ChoiceOption, AslMetadataView):
    """
    Menu to display/set the type of labelling images present
    """

    def __init__(self, grid, ypos):
        self._indexes = ["tc", "ct", "diff", "ve", "mp"]
        ChoiceOption.__init__(self, "Data format", grid, ypos, choices=["Label-control pairs", "Control-Label pairs", "Already subtracted", "Vessel encoded", "Multiphase"])
        self.pwi_btn = QtWidgets.QPushButton("Generate PWI")
        self.pwi_btn.setToolTip("Generate a perfusion-weighted image by performing label-control subtraction and averaging")
        self.pwi_btn.clicked.connect(self._pwi)
        grid.addWidget(self.pwi_btn, ypos, 2)
        AslMetadataView.__init__(self)
        self.sig_changed.connect(self._changed)
    
    def _update(self):
        iaf = self.md.get("iaf", "tc")
        self.combo.setCurrentIndex(self._indexes.index(iaf))
        self.pwi_btn.setEnabled(iaf in ("tc", "ct"))

    def _changed(self):
        iaf = self._indexes[self.combo.currentIndex()]
        self.md["iaf"] = iaf
        if "order" in self.md:
            if iaf == "diff":
                self.md["order"] = self.md["order"].replace("l", "")
            elif "l" not in self.md["order"]:
                self.md["order"] = "l" + self.md["order"]

        if iaf == "mp":
            if "nphases" not in self.md:
                self.md["nphases"] = 8
        else:
            self.md.pop("nphases", None)
            
        if iaf == "ve":
            if "nenc" not in self.md:
                self.md["nenc"] = 8
        else:
            self.md.pop("nenc", None)

        self.sig_md_changed.emit(self)

    def _pwi(self):
        try:
            aslimage, _ = qpdata_to_aslimage(self.data, metadata=self.md)
            pwi = aslimage.perf_weighted()
            qpd = fslimage_to_qpdata(pwi, name=self.data.name + "_pwi")
            self.ivm.add(qpd, name=qpd.name, make_current=True)
        except:
            # FIXME ignore but button should not be enabled if 
            # metadata is inconsistent!
            traceback.print_exc()

class Labelling(ChoiceOption, AslMetadataView):
    """
    Menu to select CASL/PCASL vs PASL labelling
    """

    def __init__(self, grid, ypos):
        ChoiceOption.__init__(self, "Labelling", grid, ypos, choices=["cASL/pcASL", "pASL"])
        AslMetadataView.__init__(self)
        self.combo.currentIndexChanged.connect(self._changed)
    
    def _update(self):
        self.combo.setCurrentIndex(1-int(self.md.get("casl", True)))
                      
    def _changed(self):
        self.md["casl"] = self.combo.currentIndex() == 0
        self.sig_md_changed.emit(self)

class Readout(ChoiceOption, AslMetadataView):
    """
    Display/set 2D/3D readout options
    """

    def __init__(self, grid, ypos):
        ChoiceOption.__init__(self, "Readout", grid, ypos, choices=["3D (e.g. GRASE)", "2D (e.g. EPI)"])
        AslMetadataView.__init__(self)
        self.combo.currentIndexChanged.connect(self._changed)
    
    def _update(self):
        readout_2d = "slicedt" in self.md
        self.combo.setCurrentIndex(int(readout_2d))
                      
    def _changed(self):
        if self.combo.currentIndex() == 0:
            self.md.pop("slicedt", None)
        else:
            self.md["slicedt"] = None
        self.sig_md_changed.emit(self)

class SliceTime(NumericOption, AslMetadataView):
    """
    Display set slice time for 2D readout
    """

    def __init__(self, grid, ypos):
        NumericOption.__init__(self, "Time per slice (ms)", grid, ypos, default=10, decimals=2)
        AslMetadataView.__init__(self)
        self.spin.valueChanged.connect(self._changed)
    
    def _update(self):
        readout_2d = "slicedt" in self.md
        self.label.setVisible(readout_2d)
        self.spin.setVisible(readout_2d)
        if readout_2d:
            slicedt = self.md["slicedt"]
            if slicedt is None:
                slicedt = 0.01
            self.spin.setValue(slicedt*1000) # s->ms
            
    def _changed(self):
        self.md["slicedt"] = self.spin.value() / 1000 # ms->s
        self.sig_md_changed.emit(self)

class Multiband(QtCore.QObject, AslMetadataView):
    """
    Display/set slices per band for multiband readout
    """

    def __init__(self, grid, ypos):
        QtCore.QObject.__init__(self)
        self.cb = QtWidgets.QCheckBox("Multiband")
        grid.addWidget(self.cb, ypos, 0)
        hbox = QtWidgets.QHBoxLayout()
        self.slices_per_band = QtWidgets.QSpinBox()
        self.slices_per_band.setMinimum(1)
        self.slices_per_band.setValue(5)
        hbox.addWidget(self.slices_per_band)
        self.slices_per_band_lbl = QtWidgets.QLabel("slices per band")
        hbox.addWidget(self.slices_per_band_lbl)
        grid.addLayout(hbox, ypos, 1)

        self.slices_per_band.valueChanged.connect(self._changed)
        self.cb.stateChanged.connect(self._changed)
        AslMetadataView.__init__(self)
    
    def _update(self):
        readout_2d = "slicedt" in self.md
        multiband = "sliceband" in self.md
        self.cb.setVisible(readout_2d)
        self.cb.setChecked(multiband)
        self.slices_per_band.setVisible(readout_2d)
        self.slices_per_band_lbl.setVisible(readout_2d)
        self.slices_per_band.setEnabled(multiband)
        if multiband: 
            self.slices_per_band.setValue(self.md["sliceband"])
            
    def _changed(self):
        self.slices_per_band.setEnabled(self.cb.isChecked())
        if self.cb.isChecked():
            self.md["sliceband"] = self.slices_per_band.value()
        else:
            self.md.pop("sliceband", None)
        self.sig_md_changed.emit(self)

class RepeatsChoice(ChoiceOption, AslMetadataView):
    """
    Display set choice between fixed and variable repeats
    """

    def __init__(self, grid, ypos):
        ChoiceOption.__init__(self, "Repeats", grid, ypos, choices=["Fixed", "Variable"])
        AslMetadataView.__init__(self)
        self.sig_changed.connect(self._changed)
    
    def _update(self):
        ntis = len(self.md.get("tis", self.md.get("plds", 1)))
        self.combo.setVisible(ntis > 1)
        self.label.setVisible(ntis > 1)
        rpts = self.md.get("rpts", None)
        var_rpts = rpts is not None and len(rpts) > 1
        self.combo.setCurrentIndex(int(var_rpts))

    def _changed(self):
        fixed_repeats = self.combo.currentIndex() == 0
        if fixed_repeats:
            self.md.pop("rpts", None)
            self.md.pop("nrpts", None)
        else:
            self.md.pop("nrpts", None)
            if "rpts" not in self.md:
                self.md["rpts"] = get_auto_repeats(self.md, self.data)
        self.sig_md_changed.emit(self)
        
class Times(QtCore.QObject, AslMetadataView):
    """ 
    Displays TIs/PLDs, taus and optionally variable repeats 
    """
    def __init__(self, grid, ypos):
        QtCore.QObject.__init__(self)
        self._label = QtWidgets.QLabel(TIMING_LABELS[True])
        self._edit = QtWidgets.QLineEdit()
        self._edit.editingFinished.connect(self._edit_changed)
        grid.addWidget(self._label, ypos, 0)
        grid.addWidget(self._edit, ypos, 1)
        AslMetadataView.__init__(self)

    def _update(self):
        if self.md.get("casl", True):
            times = self.md.get("plds", [0.25])
        else:
            times = self.md.get("tis", [1.5])
        self._label.setText(TIMING_LABELS[self.md.get("casl", True)])
        self._edit.setText(", ".join([str(v) for v in times]))
        
    def _edit_changed(self):
        try:
            text = self._edit.text().replace(",", " ")
            times = [float(v) for v in text.split()]
            if self.md.get("casl", True):
                self.md["plds"] = times
                self.md.pop("tis", None)
            else:
                self.md["tis"] = times
                self.md.pop("plds", None)
            self._edit.setText(" ".join([str(v) for v in times]))
            self._edit.setStyleSheet("")
        except ValueError:
            # Colour edit red but don't change anything
            self._edit.setStyleSheet("QLineEdit {background-color: red}")
        self.sig_md_changed.emit(self)

class BolusDurations(QtCore.QObject, AslMetadataView):
    """ 
    Displays bolus durations (taus)
    """
    def __init__(self, grid, ypos):
        QtCore.QObject.__init__(self)
        self._label = QtWidgets.QLabel("Bolus duration (s)")
        self._edit = QtWidgets.QLineEdit()
        self._edit.editingFinished.connect(self._edit_changed)
        grid.addWidget(self._label, ypos, 0)
        grid.addWidget(self._edit, ypos, 1)
        AslMetadataView.__init__(self)

    def _update(self):
        taus = self.md.get("taus", [1.8,])
        self._edit.setText(", ".join([str(v) for v in taus]))
        
    def _edit_changed(self):
        try:
            text = self._edit.text().replace(",", " ")
            taus = [float(v) for v in text.split()]
            self.md["taus"] = taus
            self._edit.setText(" ".join([str(v) for v in taus]))
            self._edit.setStyleSheet("")
        except ValueError:
            # Colour edit red but don't change anything
            self._edit.setStyleSheet("QLineEdit {background-color: red}")
        self.sig_md_changed.emit(self)

class VariableRepeats(QtCore.QObject, AslMetadataView):
    """ 
    Displays variable repeats if enabled
    """
    def __init__(self, grid, ypos):
        QtCore.QObject.__init__(self)
        self._label = QtWidgets.QLabel("Repeats")
        self._edit = QtWidgets.QLineEdit()
        self._edit.editingFinished.connect(self._edit_changed)
        grid.addWidget(self._label, ypos, 0)
        grid.addWidget(self._edit, ypos, 1)
        AslMetadataView.__init__(self)

    def _update(self):
        rpts = self.md.get("rpts", None)
        var_rpts = rpts is not None
        self._label.setVisible(var_rpts)
        self._edit.setVisible(var_rpts)
        if var_rpts:
            self._edit.setText(", ".join([str(v) for v in rpts]))
        
    def _edit_changed(self):
        try:
            text = self._edit.text().replace(",", " ")
            rpts = [int(v) for v in text.split()]
            self.md["rpts"] = rpts
            self._edit.setText(" ".join([str(v) for v in rpts]))
            self._edit.setStyleSheet("")
        except ValueError:
            # Colour edit red but don't change anything
            self._edit.setStyleSheet("QLineEdit {background-color: red}")
        self.sig_md_changed.emit(self)

class AslImageWidget(QtWidgets.QWidget, LogSource):
    """
    QWidget which allows an ASL data set to be described

    This is intended to be embedded into a QpWidget which supports processing of ASL data
    """

    # Signal emitted when the data or metadata is changed
    sig_changed = QtCore.Signal()

    def __init__(self, ivm, parent=None, **kwargs):
        LogSource.__init__(self)
        QtWidgets.QWidget.__init__(self, parent)
        self.ivm = ivm
        self.data = None
        self.default_md = kwargs.get("default_metadata", DEFAULT_METADATA)
        self.md = dict(self.default_md)
        self.aslimage = None
        self.valid = True
        
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)

        grid = QtWidgets.QGridLayout()

        grid.addWidget(QtWidgets.QLabel("ASL data"), 0, 0)
        self.data_combo = OverlayCombo(self.ivm)
        self.data_combo.currentIndexChanged.connect(self._data_changed)
        grid.addWidget(self.data_combo, 0, 1)

        view_classes = [LabelType, RepeatsChoice, NumPhases, NumEncodings,
                        BlockFormat, DataStructure, SignalView,
                        Labelling, Readout, SliceTime, Multiband, Times,
                        BolusDurations, VariableRepeats]

        self.views = []
        for idx, view_class in enumerate(view_classes):
            if view_class in kwargs.get("ignore_views", ()): 
                continue
            view = view_class(grid, ypos=idx+2)
            view.ivm = self.ivm
            view.sig_md_changed.connect(self._metadata_changed)
            self.views.append(view)

        #grid.addWidget(QtWidgets.QLabel("Data order preview"), 5, 0)
       
        # Code below is for specific multiple phases
        #self.phases_lbl = QtWidgets.QLabel("Phases (\N{DEGREE SIGN})")
        #grid.addWidget(self.phases_lbl, 3, 0)
        #self.phases_lbl.setVisible(False)
        #self.phases = NumberList([float(x)*360/8 for x in range(8)])
        #grid.addWidget(self.phases, 3, 1)
        #self.phases.setVisible(False)

        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)
        grid.setRowStretch(len(view_classes)+2, 1)
        
        self.grid = grid
        vbox.addLayout(grid)
        
        self.warn_label = WarningBox()
        vbox.addWidget(self.warn_label)

        self._update_ui()
        self._data_changed()
        
    def set_data_name(self, name):
        """ Set the name of the data item being displayed """
        if name not in self.ivm.data:
            raise QpException("Data not found: %s" % name)
        else:
            idx = self.data_combo.findText(name)
            self.data_combo.setCurrentIndex(idx)

    def _data_changed(self):
        """
        New data selected - load any previously defined metadata, and validate it 
        """
        self.data = self.ivm.data.get(self.data_combo.currentText(), None)
        for idx in range(self.grid.count()):
            if idx > 1:
                w = self.grid.itemAt(idx).widget()
                if w is not None:
                    w.setEnabled(self.data is not None)

        if self.data is not None:
            self.md = self.data.metadata.get("AslData", None)
            if self.md is None:
                self.md = dict(self.default_md)
                if self.data.nvols % 2 == 0:
                    # Even number of volumes - guess TC pairs
                    # FIXME don't need block format for single TI
                    self.md["iaf"] = "tc"
                    self.md["ibf"] = "tis"
            for view in self.views:
                view.set_data(self.data, self.md)
            self._validate_metadata()
            self.sig_changed.emit()

    def _metadata_changed(self, sender):
        """
        Called when a view has changed the metadata
        """
        self.debug("Metadata changed %s", sender)
        if self.data is not None:
            self.debug("Current metadata: %s", self.md)
        self.debug("New metadata: %s", sender.md)
        self.md = sender.md
        self._validate_metadata()
        self._save_metadata()
        self.sig_changed.emit()

    def _save_metadata(self):
        """
        Set the metadata on the dataset
        """
        if self.data is not None:
            current_md = self.data.metadata.get("AslData", {})
            self.debug("Save: Current metadata: %s", current_md)
            if self.md != current_md:
                self.debug("Different!")
                self.data.metadata["AslData"] = dict(self.md)
                self.debug("Saved: %s ", self.md)
                self._update_ui()

    def _update_ui(self, ignore=()):
        """ 
        Update user interface from the current metadata 
        """
        try:
            for view in self.views:
                if view not in ignore:
                    view.set_data(self.data, self.md)
        finally:
            self.updating_ui = False

    def _validate_metadata(self):
        """
        Validate data against specified TIs, etc
        """
        try:
            if self.md and self.data is not None:
                self.debug("Validating metadata: %s", str(self.md))
                self.aslimage, _ = qpdata_to_aslimage(self.data, metadata=self.md)
            self.warn_label.clear()
            self.valid = True
        except ValueError as e:
            self.debug("Failed: %s", str(e))
            self.aslimage = None
            self.warn_label.warn(str(e))
            self.valid = False

    def get_options(self):
        """ Get batch options """
        options = {}
        if self.data is not None:
            options["data"] = self.data.name
            options.update(self.md)
        return options
