"""
QP-BASIL - QWidget which displays and edits the metadata for ASL data

The metadata includes data ordering/structure and acquisition parameters

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import

from PySide import QtCore, QtGui

from quantiphyse.gui.widgets import OverlayCombo, ChoiceOption, NumericOption, OrderList, OrderListButtons, NumberGrid
from quantiphyse.utils import LogSource, QpException

from .process import  qpdata_to_aslimage

from ._version import __version__

ORDER_LABELS = {
    "r" : ("Repeat ", "R", "Repeats"), 
    "t" : ("TI ", "TI", "TIs/PLDs"),
    "l" : {
        "tc" : (("Label", "Control"), ("L", "C"), "Label-Control pairs"),
        "ct" : (("Control", "Label"), ("C", "L"), "Control-Label pairs"),
        "mp" : ("Phase ", "Ph", "Phases"),
        "ve" : ("Encoding", "Enc", "Encoding cycles"),
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
    "order" : "rt", 
    "tis" : [1.5,], 
    "taus" : [1.4,], 
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
        
        Sets the attributes ``data``, ``md`` and calls ``update()``

        :param data: QpData object 
        """
        self.data = data
        self.md = metadata

        # Make sure we always have some basic defaults
        if "tis" not in self.md and "plds" not in self.md: self.md["tis"] = [1.5]
        if "taus" not in self.md: self.md["taus"] = [1.4]
        if "iaf" not in self.md: self.md["iaf"] = "diff"
        if "order" not in self.md:
            if self.md["iaf"] == "diff": 
                self.md["order"] = "rt"
            else:
                self.md["order"] = "lrt"

        self.update()

    def update(self):
        """
        Override to update the view when the data object changes
        """
        pass

    def _get_num_label_vols(self):
        iaf = self.md.get("iaf", "tc")
        if iaf in ("tc", "ct"):
            return 2
        elif iaf == "diff":
            return 1
        elif iaf == "mp":
            return self.md.get("nphases", 8)
        elif iaf == "ve":
            return self.md.get("nenc", 8)

    def _get_auto_repeats(self):
        if self.data is None: 
            return [1,]
        
        nvols = self.data.nvols
        ntis = len(self.md.get("tis", [1.5]))
        nrpts = float(nvols) / ntis
        ntc = self._get_num_label_vols()
        
        nrpts /= ntc
        rpts = [max(1, int(nrpts)),] * ntis
        missing = sum(rpts) * ntc
        for idx in range(min(0, missing)):
            rpts[idx] += 1
        return rpts

class DataStructure(QtGui.QWidget, AslMetadataView):
    """
    Visual preview of the structure of an ASL data set
    """
    def __init__(self, grid, ypos):
        QtGui.QWidget.__init__(self)
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

    def update(self):
        self.order = self.md.get("order", "lrt")
        self.num = {
            "t" : len(self.md.get("tis", [1])),
            # This is for display purposes only so good enough for variable repeats
            "r" : self.md.get("nrpts", self._get_auto_repeats()[0]),
            "l" : self._get_num_label_vols()
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

class NumPhases(NumericOption, AslMetadataView):
    """
    Displays/Sets the number of phases for a multiphase data set
    """

    def __init__(self, grid, ypos):
        NumericOption.__init__(self, "Number of Phases (evenly spaced)", grid, ypos, default=8, intonly=True, minval=2)
        AslMetadataView.__init__(self)
        self.sig_changed.connect(self._changed)
    
    def update(self):
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

class DataOrdering(QtCore.QObject, AslMetadataView):
    """
    Displays the current ordering of elements in the ASL data (e.g. TIs, repeats) and 
    allows the order to be modified by dragging them around
    """
    def __init__(self, grid, ypos):
        QtCore.QObject.__init__(self)
        AslMetadataView.__init__(self)
        grid.addWidget(QtGui.QLabel("Data grouping\n(top = outermost)"), ypos, 0, alignment=QtCore.Qt.AlignTop)
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

    def update(self):
        order = self.md.get("order", "lrt")
        self.group_list.setItems([self._get_label(g) for g in order[::-1]])
                     
    def _changed(self):
        order = ""
        for item in self.group_list.items():
            code = [char for char in ('t', 'r', 'l') if self._get_label(char) == item][0]
            order += code

        self.md["order"] = order[::-1]
        self.sig_md_changed.emit(self)

class LabelType(ChoiceOption, AslMetadataView):
    """
    Menu to display/set the type of labelling images present
    """

    def __init__(self, grid, ypos):
        self._indexes = ["tc", "ct", "diff", "mp"]
        ChoiceOption.__init__(self, "Data format", grid, ypos, choices=["Label-control pairs", "Control-Label pairs", "Already subtracted", "Multiphase"])
        AslMetadataView.__init__(self)
        self.sig_changed.connect(self._changed)
    
    def update(self):
        iaf = self.md.get("iaf", "tc")
        self.combo.setCurrentIndex(self._indexes.index(iaf))
        
    def _changed(self):
        iaf = self._indexes[self.combo.currentIndex()]
        self.md["iaf"] = iaf
        if iaf == "diff":
            self.md["order"] = self.md["order"].replace("l", "")
        elif "l" not in self.md["order"]:
            self.md["order"] = "l" + self.md["order"]

        if iaf == "mp" and "nphases" not in self.md:
            self.md["nphases"] = 8
            
        self.sig_md_changed.emit(self)

class Labelling(ChoiceOption, AslMetadataView):
    """
    Menu to select CASL/PCASL vs PASL labelling
    """

    def __init__(self, grid, ypos):
        ChoiceOption.__init__(self, "Labelling", grid, ypos, choices=["cASL/pcASL", "pASL"])
        AslMetadataView.__init__(self)
        self.combo.currentIndexChanged.connect(self._changed)
    
    def update(self):
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
    
    def update(self):
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
    
    def update(self):
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
        self.cb = QtGui.QCheckBox("Multiband")
        grid.addWidget(self.cb, ypos, 0)
        hbox = QtGui.QHBoxLayout()
        self.slices_per_band = QtGui.QSpinBox()
        self.slices_per_band.setMinimum(1)
        self.slices_per_band.setValue(5)
        hbox.addWidget(self.slices_per_band)
        self.slices_per_band_lbl = QtGui.QLabel("slices per band")
        hbox.addWidget(self.slices_per_band_lbl)
        grid.addLayout(hbox, ypos, 1)

        self.slices_per_band.valueChanged.connect(self._changed)
        self.cb.stateChanged.connect(self._changed)
        AslMetadataView.__init__(self)
    
    def update(self):
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
    
    def update(self):
        rpts = self.md.get("rpts", None)
        var_rpts = rpts is not None and min(rpts) != max(rpts)
        self.combo.setCurrentIndex(int(var_rpts))

    def _changed(self):
        fixed_repeats = self.combo.currentIndex() == 0
        if fixed_repeats:
            self.md.pop("rpts", None)
            self.md.pop("nrpts", None)
        else:
            self.md.pop("nrpts", None)
            if "rpts" not in self.md:
                self.md["rpts"] = self._get_auto_repeats()
        self.sig_md_changed.emit(self)
        
class AslParamsGrid(NumberGrid, AslMetadataView):
    """ 
    Grid which displays TIs, taus and optionally variable repeats 
    """

    def __init__(self, grid, ypos):
        self.tau_header = "Bolus durations"
        self.rpt_header = "Repeats"

        NumberGrid.__init__(self, [[1.0], [1.0], [1]],
                            row_headers=self._headers(True, True),
                            expandable=(True, False), 
                            fix_height=True)

        grid.addWidget(self, ypos, 0, 1, 3)
        self.sig_changed.connect(self._changed)
        AslMetadataView.__init__(self)
    
    def update(self):
        rpts = self.md.get("rpts", None)
        var_rpts = rpts is not None

        grid_values = [self.md.get("tis", [1.5]), self.md.get("taus", [1.8])]
        if var_rpts:
            grid_values.append(rpts)

        casl = self.md.get("casl", True)
        self._model.setVerticalHeaderLabels(self._headers(casl, var_rpts))
        self.setValues(grid_values, validate=False)

    def _headers(self, casl, rpts):
        headers = []
        headers.append(TIMING_LABELS[casl])
        headers.append(self.tau_header)
        if rpts: headers.append(self.rpt_header)
        return headers

    def _changed(self):
        try:
            values = self.values()
        except ValueError:
            # Non-numeric values - don't change anything
            return

        self.md["tis"] = values[0]
        self.md["taus"] = values[1]

        try:
            if len(values) > 2:
                self.md["rpts"] = [int(v) for v in values[2]]
        except ValueError:
            # Repeats are not integers - FIXME silently ignored
            pass
            
        self.sig_md_changed.emit(self)

class AslImageWidget(QtGui.QWidget, LogSource):
    """
    QWidget which allows an ASL data set to be described

    This is intended to be embedded into a QpWidget which supports processing of ASL data
    """

    # Signal emitted when the data or metadata is changed
    sig_changed = QtCore.Signal()

    def __init__(self, ivm, parent=None, **kwargs):
        LogSource.__init__(self)
        QtGui.QWidget.__init__(self, parent)
        self.ivm = ivm
        self.data = None
        self.default_md = kwargs.get("default_metadata", DEFAULT_METADATA)
        self.md = dict(self.default_md)
        self.aslimage = None
        self.valid = True
        
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        grid = QtGui.QGridLayout()

        grid.addWidget(QtGui.QLabel("ASL data"), 0, 0)
        self.data_combo = OverlayCombo(self.ivm)
        self.data_combo.currentIndexChanged.connect(self._data_changed)
        grid.addWidget(self.data_combo, 0, 1)

        view_classes = [LabelType, RepeatsChoice, NumPhases, DataOrdering, DataStructure,
                        Labelling, Readout, SliceTime, Multiband, AslParamsGrid]

        self.views = []
        for idx, view_class in enumerate(view_classes):
            if view_class in kwargs.get("ignore_views", ()): 
                continue
            view = view_class(grid, ypos=idx+2)
            view.set_data(self.data, self.md)
            view.sig_md_changed.connect(self._metadata_changed)
            self.views.append(view)

        #grid.addWidget(QtGui.QLabel("Data order preview"), 5, 0)
       
        # Code below is for specific multiple phases
        #self.phases_lbl = QtGui.QLabel("Phases (\N{DEGREE SIGN})")
        #grid.addWidget(self.phases_lbl, 3, 0)
        #self.phases_lbl.setVisible(False)
        #self.phases = NumberList([float(x)*360/8 for x in range(8)])
        #grid.addWidget(self.phases, 3, 1)
        #self.phases.setVisible(False)

        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)
        
        vbox.addLayout(grid)
        
        self.warn_label = QtGui.QLabel("")
        self.warn_label.setStyleSheet(
            """QLabel { background-color: orange; color: black; border: 1px solid gray;
                        border-radius: 2px; padding: 10px 10px 10px 10px;}""")
        self.warn_label.setVisible(False)
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
        if self.data is not None:
            self.md = self.data.metadata.get("AslData", dict(self.default_md))
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
        if self.valid:
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
            self.warn_label.setVisible(False)
            self.valid = True
        except RuntimeError, e:
            self.debug("Failed: %s", str(e))
            self.aslimage = None
            self.warn_label.setText(str(e))
            self.warn_label.setVisible(True)
            self.valid = False

    def get_options(self):
        """ Get batch options """
        options = {}
        if self.data is not None:
            options["data"] = self.data.name
            options.update(self.md)
        return options
