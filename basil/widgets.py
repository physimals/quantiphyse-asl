"""
QP-BASIL - Quantiphyse widgets for processing for ASL data

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import

from PySide import QtCore, QtGui

from quantiphyse.gui.widgets import QpWidget, RoiCombo, OverlayCombo, Citation, TitleWidget, ChoiceOption, NumericOption, OrderList, OrderListButtons, NumberGrid, RunBox
from quantiphyse.gui.options import OptionBox, ChoiceOption as Choice, NumericOption as Number, BoolOption, DataOption, FileOption
from quantiphyse.utils import LogSource, QpException

from .process import AslPreprocProcess, BasilProcess, AslCalibProcess, AslMultiphaseProcess, OxaslProcess, qpdata_to_aslimage

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

DEFAULT_METADATA = {
    "iaf" : "tc",
    "order" : "lrt", 
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

    def set_data(self, data):
        """
        Sets the data whose ASL metadata is to be displayed
        
        Sets the attributes ``data``, ``md`` and calls ``update()``

        :param data: QpData object 
        """
        self.data = data
        if self.data is not None:
            self.md = dict(data.metadata.get("AslData", {}))
            # Make sure we always have some basic defaults
            if "tis" not in self.md and "plds" not in self.md: self.md["tis"] = [1.5]
            if "taus" not in self.md: self.md["taus"] = [1.4]
            if "iaf" not in self.md: self.md["iaf"] = "diff"
            if "order" not in self.md:
                if self.md["iaf"] == "diff": 
                    self.md["order"] = "rt"
                else:
                    self.md["order"] = "lrt"
        else:
            self.md = {}

        self.update()

    def update(self):
        """
        Override to update the view when the data object changes
        """
        pass

    def get_num_label_vols(self):
        iaf = self.md.get("iaf", "tc")
        if iaf in ("tc", "ct"):
            return 2
        elif iaf == "diff":
            return 1
        elif iaf == "mp":
            return self.md.get("nphases", 8)
        elif iaf == "ve":
            return self.md.get("nenc", 8)

    def get_auto_repeats(self):
        if self.data is None: 
            return [1,]
        
        nvols = self.data.nvols
        ntis = len(self.md.get("tis", [1.5]))
        nrpts = float(nvols) / ntis
        ntc = self.get_num_label_vols()
        
        nrpts /= ntc
        rpts = [max(1, int(nrpts)),] * ntis
        missing = sum(rpts) * ntc
        for idx in range(min(0, missing)):
            rpts[idx] += 1
        return rpts

class AslDataPreview(QtGui.QWidget, AslMetadataView):
    """
    Visual preview of the structure of an ASL data set
    """
    def __init__(self, data, grid, ypos):
        QtGui.QWidget.__init__(self)
        self.set_data(data)
        self.hfactor = 0.95
        self.vfactor = 0.95
        self.cols = {
            "r" : (128, 128, 255, 128), 
            "t" : (255, 128, 128, 128), 
            "l" : (128, 255, 128, 128),
        }
        grid.addWidget(self, ypos, 0, 1, 3)

    def update(self):
        self.order = self.md.get("order", "lrt")
        self.num = {
            "t" : len(self.md.get("tis", [1.4,])),
            "r" : self.md.get("rpts", [self.md.get("nrpts", 3),])[0], # FIXME variable repeats won't work
            "l" : self.get_num_label_vols()
        }
        self.repaint()
        self.setFixedHeight((self.fontMetrics().height() + 2)*len(self.order))

    def paintEvent(self, _):
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
    def __init__(self, data, grid, ypos):
        NumericOption.__init__(self, "Number of Phases (evenly spaced)", grid, ypos, default=8, intonly=True, minval=2)
        self.set_data(data)
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
    def __init__(self, data, grid, ypos):
        QtCore.QObject.__init__(self)
        grid.addWidget(QtGui.QLabel("Data grouping\n(top = outermost)"), ypos, 0, alignment=QtCore.Qt.AlignTop)
        self.group_list = OrderList()
        grid.addWidget(self.group_list, ypos, 1)
        self.list_btns = OrderListButtons(self.group_list)
        grid.addLayout(self.list_btns, ypos, 2)

        # Have to set items after adding to grid or sizing doesn't work right
        self.set_data(data)
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

    def __init__(self, data, grid, ypos):
        ChoiceOption.__init__(self, "Data format", grid, ypos, choices=["Label-control pairs", "Control-Label pairs", "Already subtracted", "Multiphase"])
        self._indexes = ["tc", "ct", "diff", "mp"]
        self.set_data(data)
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
        self.sig_md_changed.emit(self)

class Labelling(ChoiceOption, AslMetadataView):

    def __init__(self, data, grid, ypos):
        ChoiceOption.__init__(self, "Labelling", grid, ypos, choices=["cASL/pcASL", "pASL"])
        self.set_data(data)
        self.combo.currentIndexChanged.connect(self._changed)
    
    def update(self):
        self.combo.setCurrentIndex(1-int(self.md.get("casl", True)))
                      
    def _changed(self):
        self.md["casl"] = self.combo.currentIndex() == 0
        self.sig_md_changed.emit(self)

class Readout(ChoiceOption, AslMetadataView):

    def __init__(self, data, grid, ypos):
        ChoiceOption.__init__(self, "Readout", grid, ypos, choices=["3D (e.g. GRASE)", "2D (e.g. EPI)"])
        self.set_data(data)
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

    def __init__(self, data, grid, ypos):
        NumericOption.__init__(self, "Time per slice (ms)", grid, ypos, default=10, decimals=2)
        self.set_data(data)
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

    def __init__(self, data, grid, ypos):
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

        self.set_data(data)
        self.slices_per_band.valueChanged.connect(self._changed)
        self.cb.stateChanged.connect(self._changed)
    
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

    def __init__(self, data, grid, ypos):
        ChoiceOption.__init__(self, "Repeats", grid, ypos, choices=["Fixed", "Variable"])

        self.set_data(data)
        self.sig_changed.connect(self._changed)
    
    def update(self):
        rpts = self.md.get("rpts", None)
        var_rpts = rpts is not None and min(rpts) != max(rpts)
        self.combo.setCurrentIndex(int(var_rpts))

    def _changed(self):
        auto_repeats = self.get_auto_repeats()
        fixed_repeats = self.combo.currentIndex() == 0
        if fixed_repeats:
            self.md.pop("rpts", None)
            if min(auto_repeats) == max(auto_repeats):
                self.md["nrpts"] = auto_repeats[0]
        else:
            self.md.pop("nrpts", None)
            if "rpts" not in self.md:
                self.md["rpts"] = auto_repeats
        self.sig_md_changed.emit(self)
        
class AslParamsGrid(NumberGrid, AslMetadataView):
    """ 
    Grid which displays TIs, taus and optionally variable repeats 
    """

    def __init__(self, data, grid, ypos):
        self.tau_header = "Bolus durations"
        self.rpt_header = "Repeats"

        NumberGrid.__init__(self, [[1.0], [1.0], [1]],
                            row_headers=self._headers(True, True),
                            expandable=(True, False), 
                            fix_height=True)

        grid.addWidget(self, ypos, 0, 1, 3)
        self.set_data(data)
        self.sig_changed.connect(self._changed)
    
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
            else:
                # May need to recalculate fixed repeats
                repeats = self.get_auto_repeats()
                self.md.pop("nrpts", None)
                if min(repeats) == max(repeats):
                    self.md["nrpts"] = repeats[0]
        except ValueError:
            # Repeats are not integers - FIXME silently ignored
            pass
            
        self.sig_md_changed.emit(self)

class AslImageWidget(QtGui.QWidget, LogSource):
    """
    QWidget which allows an ASL data set to be described

    This is intended to be embedded into a QpWidget which supports processing of ASL data
    """
    def __init__(self, ivm, parent=None, **kwargs):
        LogSource.__init__(self)
        QtGui.QWidget.__init__(self, parent)
        self.ivm = ivm
        self.data = None
        self.aslimage = None
        self.updating_ui = False
        
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        grid = QtGui.QGridLayout()

        grid.addWidget(QtGui.QLabel("ASL data"), 0, 0)
        self.data_combo = OverlayCombo(self.ivm)
        self.data_combo.currentIndexChanged.connect(self._data_changed)
        grid.addWidget(self.data_combo, 0, 1)

        view_classes = [LabelType, RepeatsChoice, NumPhases, DataOrdering, AslDataPreview,
                        Labelling, Readout, SliceTime, Multiband, AslParamsGrid]

        self.views = []
        for idx, view_class in enumerate(view_classes):
            if view_class in kwargs.get("ignore_views", ()): 
                continue
            view = view_class(None, grid, ypos=idx+2)
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
            for view in self.views:
                view.set_data(self.data)
            self._validate(self.data.metadata.get("AslData", {}))

    def _metadata_changed(self, sender):
        """
        A view has changed the metadata

        FIXME the process of updating the views can elicit additional
        metadata changes
        """
        self.debug("Metadata changed %s", sender)
        if self.data is not None:
            self.debug("Current metadata: %s", self.data.metadata.get("AslData", {}))
        self.debug("New metadata: %s", sender.md)
        self._validate(sender.md)
        self._save_metadata(sender.md)

    def _update_ui(self, ignore=()):
        """ 
        Update user interface from the current metadata 
        """
        # Hack to avoid processing signals while updating UI
        #if self.updating_ui: return
        #self.updating_ui = True
        try:
            for view in self.views:
                if view not in ignore:
                    view.set_data(self.data)
        finally:
            self.updating_ui = False

    def _save_metadata(self, md):
        """
        Set the metadata on the dataset
        """
        if self.data is not None:
            current_md = self.data.metadata.get("AslData", {})
            self.debug("Save: Current metadata: %s", self.data.metadata.get("AslData", {}))
            if md != current_md:
                self.debug("Different!")
                self.data.metadata["AslData"] = dict(md)
                self.debug("Saved: %s ", md)
                self._update_ui()

    def _validate(self, md):
        """
        Validate data against specified TIs, etc
        """
        try:
            if md and self.data is not None:
                self.debug("Validating against metadata: %s", str(md))
                self.aslimage, md = qpdata_to_aslimage(self.data, metadata=md)
            self.warn_label.setVisible(False)
        except RuntimeError, e:
            self.debug("Failed: %s", str(e))
            self.aslimage = None
            self.warn_label.setText(str(e))
            self.warn_label.setVisible(True)

    def get_options(self):
        """ Get batch options """
        options = {}
        if self.data is not None:
            options["data"] = self.data.name
            options.update(self.data.metadata["AslData"])
        return options

class AslPreprocWidget(QpWidget):
    """
    Widget which lets you do basic preprocessing on ASL data
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="ASL Preprocess", icon="asl.png", group="ASL", desc="Basic preprocessing on ASL data", **kwargs)
        self.process = AslPreprocProcess(self.ivm)
        self.output_name_edited = False

    def init_ui(self):
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        title = TitleWidget(self, help="asl", subtitle="Basic preprocessing of ASL data %s" % __version__)
        vbox.addWidget(title)
              
        self.asldata_widget = AslImageWidget(self.ivm, parent=self)
        self.asldata_widget.data_combo.currentIndexChanged.connect(self._data_changed)
        vbox.addWidget(self.asldata_widget)

        preproc_box = QtGui.QGroupBox("Preprocessing Options")
        grid = QtGui.QGridLayout()
        preproc_box.setLayout(grid)

        self.sub_cb = QtGui.QCheckBox("Label-control subtraction")
        self.sub_cb.stateChanged.connect(self._guess_output_name)
        grid.addWidget(self.sub_cb, 4, 0)
        
        self.reorder_cb = QtGui.QCheckBox("Reordering")
        grid.addWidget(self.reorder_cb, 5, 0)
        self.new_order = QtGui.QLineEdit()
        self.new_order.setEnabled(False)
        self.reorder_cb.stateChanged.connect(self.new_order.setEnabled)
        self.reorder_cb.stateChanged.connect(self._guess_output_name)
        grid.addWidget(self.new_order, 5, 1)
        
        self.mean_cb = QtGui.QCheckBox("Average data")
        grid.addWidget(self.mean_cb, 6, 0)
        self.mean_combo = QtGui.QComboBox()
        self.mean_combo.addItem("Mean across repeats")
        self.mean_combo.addItem("Perfusion-weighted image")
        grid.addWidget(self.mean_combo, 6, 1)
        self.mean_cb.stateChanged.connect(self.mean_combo.setEnabled)
        self.mean_cb.stateChanged.connect(self._guess_output_name)
        
        grid.addWidget(QtGui.QLabel("Output name"), 7, 0)
        self.output_name = QtGui.QLineEdit()
        self.output_name.editingFinished.connect(self._output_name_changed)
        grid.addWidget(self.output_name, 7, 1)
        
        self.run_btn = QtGui.QPushButton("Run")
        self.run_btn.clicked.connect(self.run)
        grid.addWidget(self.run_btn, 8, 0)

        grid.setColumnStretch(2, 1)
        vbox.addWidget(preproc_box)
        vbox.addStretch(1)
        self.output_name_edited = False

    def activate(self):
        self._data_changed()
        
    def _output_name_changed(self):
        self.output_name_edited = True

    def _data_changed(self):
        self.output_name_edited = False
        self._guess_output_name()
        # Label-control differencing only if data contains LC or CL pairs
        pairs = self.asldata_widget.aslimage is not None and self.asldata_widget.aslimage.iaf in ("tc", "ct")
        self.sub_cb.setEnabled(pairs)
        if not pairs: self.sub_cb.setChecked(False)

    def _guess_output_name(self):
        data_name = self.asldata_widget.data_combo.currentText()
        if data_name != "" and not self.output_name_edited:
            if self.sub_cb.isChecked():
                data_name += "_diff"
            if self.reorder_cb.isChecked():
                data_name += "_reorder"
            if self.mean_cb.isChecked():
                data_name += "_mean"
            self.output_name.setText(data_name)

    def batch_options(self):
        return "AslPreproc", self.get_options()

    def get_process(self):
        return self.process

    def get_options(self):
        options = self.asldata_widget.get_options()
        options["diff"] = self.sub_cb.isChecked()
        options["mean"] = self.mean_cb.isChecked() and self.mean_combo.currentIndex() == 0
        options["pwi"] = self.mean_cb.isChecked() and self.mean_combo.currentIndex() == 1
        options["output-name"] = self.output_name.text()
        if self.reorder_cb.isChecked(): 
            options["reorder"] = self.new_order.text()
        return options

    def run(self):
        self.process.run(self.get_options())
         
FAB_CITE_TITLE = "Variational Bayesian inference for a non-linear forward model"
FAB_CITE_AUTHOR = "Chappell MA, Groves AR, Whitcher B, Woolrich MW."
FAB_CITE_JOURNAL = "IEEE Transactions on Signal Processing 57(1):223-236, 2009."

class AslBasilWidget(QpWidget):
    """
    Widget to do model fitting on ASL data
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="ASL Model fitting", icon="asl.png", group="ASL", desc="Bayesian model fitting on ASL data", **kwargs)
        
    def init_ui(self):
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        try:
            self.process = BasilProcess(self.ivm)
        except QpException, e:
            self.process = None
            vbox.addWidget(QtGui.QLabel(str(e)))
            return
        
        title = TitleWidget(self, help="asl", subtitle="Bayesian Modelling for Arterial Spin Labelling MRI %s" % __version__)
        vbox.addWidget(title)
              
        cite = Citation(FAB_CITE_TITLE, FAB_CITE_AUTHOR, FAB_CITE_JOURNAL)
        vbox.addWidget(cite)

        self.tabs = QtGui.QTabWidget()
        vbox.addWidget(self.tabs)

        self.asldata_widget = AslImageWidget(self.ivm, parent=self)
        self.asldata_widget.data_combo.currentIndexChanged.connect(self._data_changed)
        self.tabs.addTab(self.asldata_widget, "Data Structure")

        analysis_tab = QtGui.QWidget()
        grid = QtGui.QGridLayout()
        analysis_tab.setLayout(grid)

        #grid.addWidget(QtGui.QLabel("Output name"), 0, 0)
        #self.output_name_edit = QtGui.QLineEdit()
        #grid.addWidget(self.output_name_edit, 0, 1)
        grid.addWidget(QtGui.QLabel("Mask"), 1, 0)
        self.roi_combo = RoiCombo(self.ivm)
        grid.addWidget(self.roi_combo, 1, 1)

        self.bat = NumericOption("Bolus arrival time (s)", grid, ypos=2, xpos=0, default=1.3, decimals=2)
        self.t1 = NumericOption("T1 (s)", grid, ypos=2, xpos=3, default=1.3, decimals=2)
        self.t1b = NumericOption("T1b (s)", grid, ypos=3, xpos=3, default=1.65, decimals=2)

        self.spatial_cb = QtGui.QCheckBox("Spatial regularization")
        grid.addWidget(self.spatial_cb, 4, 0, 1, 2)
        self.fixtau_cb = QtGui.QCheckBox("Fix bolus duration")
        grid.addWidget(self.fixtau_cb, 4, 2, 1, 2)
        self.t1_cb = QtGui.QCheckBox("Allow uncertainty in T1 values")
        grid.addWidget(self.t1_cb, 5, 0, 1, 2)
        #self.pvc_cb = QtGui.QCheckBox("Partial volume correction")
        #grid.addWidget(self.pvc_cb, 5, 2, 1, 2)
        self.mv_cb = QtGui.QCheckBox("Include macro vascular component")
        grid.addWidget(self.mv_cb, 6, 0, 1, 2)

        grid.setRowStretch(7, 1)
        self.tabs.addTab(analysis_tab, "Analysis Options")

        runbox = RunBox(self.get_process, self.get_options, title="Run ASL modelling", save_option=True)
        vbox.addWidget(runbox)
        vbox.addStretch(1)

    def activate(self):
        self._data_changed()

    def _data_changed(self):
        pass

    def batch_options(self):
        return "Basil", self.get_options()

    def get_process(self):
        return self.process

    def _infer(self, options, param, selected):
        options["infer%s" % param] = selected

    def get_options(self):
        # General defaults
        options = self.asldata_widget.get_options()
        options["t1"] = str(self.t1.spin.value())
        options["t1b"] = str(self.t1b.spin.value())
        options["bat"] = str(self.bat.spin.value())
        options["spatial"] = self.spatial_cb.isChecked()
        
        # FIXME batsd

        self._infer(options, "tiss", True)
        self._infer(options, "t1", self.t1_cb.isChecked())
        self._infer(options, "art", self.mv_cb.isChecked())
        self._infer(options, "tau", not self.fixtau_cb.isChecked())
       
        for item in options.items():
            self.debug("%s: %s" % item)
        
        return options

class AslCalibWidget(QpWidget):
    """
    Widget to do calibration on ASL data
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="ASL Calibration", icon="asl.png", group="ASL", desc="Calibration of fitted ASL data", **kwargs)
        
    def init_ui(self):
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)
        
        title = TitleWidget(self, help="asl", subtitle="ASL calibration v%s" % __version__)
        vbox.addWidget(title)
              
        self.data_box = QtGui.QGroupBox("Data to calibrate")
        grid = QtGui.QGridLayout()
        grid.addWidget(QtGui.QLabel("Data"), 0, 0)
        self.data = OverlayCombo(self.ivm)
        grid.addWidget(self.data, 0, 1)
        self.data_type = ChoiceOption("Data type", grid, ypos=1, choices=["Perfusion", "Perfusion variance"])
        self.data_box.setLayout(grid)

        grid.addWidget(QtGui.QLabel("Data ROI"), 2, 0)
        self.roi = RoiCombo(self.ivm)
        grid.addWidget(self.roi, 2, 1)

        self.calib_method = ChoiceOption("Calibration method", grid, ypos=3, choices=["Voxelwise", "Reference region"])
        vbox.addWidget(self.data_box)
        # TODO calibrate multiple data sets

        calib_box = QtGui.QGroupBox("Calibration Data")
        grid = QtGui.QGridLayout()
        calib_box.setLayout(grid)

        grid.addWidget(QtGui.QLabel("Calibration image"), 0, 0)
        self.calib_img = OverlayCombo(self.ivm)
        grid.addWidget(self.calib_img, 0, 1)

        self.tr = NumericOption("Sequence TR (s)", grid, ypos=1, minval=0, maxval=20, default=3.2, step=0.1)
        self.gain = NumericOption("Calibration gain", grid, ypos=3, minval=0, maxval=5, default=1, step=0.05)
        self.alpha = NumericOption("Inversion efficiency", grid, ypos=4, minval=0, maxval=1, default=0.98, step=0.05)
        self.calib_method.combo.currentIndexChanged.connect(self._calib_method_changed)
        
        vbox.addWidget(calib_box)

        self.voxelwise_box = QtGui.QGroupBox("Voxelwise calibration")
        grid = QtGui.QGridLayout()
        self.t1t = NumericOption("Tissue T1", grid, ypos=0, minval=0, maxval=10, default=1.3, step=0.05)
        self.pct = NumericOption("Tissue partition coefficient", grid, ypos=1, minval=0, maxval=5, default=0.9, step=0.05)
        self.voxelwise_box.setLayout(grid)
        vbox.addWidget(self.voxelwise_box)

        self.refregion_box = QtGui.QGroupBox("Reference region calibration")
        # TODO switch T1/T2/PC defaults on tissue type
        grid = QtGui.QGridLayout()
        self.refregion_box.setLayout(grid)
        self.ref_type = ChoiceOption("Reference type", grid, ypos=0, choices=["CSF", "WM", "GM", "Custom"])
        self.ref_type.combo.currentIndexChanged.connect(self._ref_tiss_changed)

        grid.addWidget(QtGui.QLabel("Reference ROI"), 1, 0)
        self.ref_roi = RoiCombo(self.ivm)
        grid.addWidget(self.ref_roi, 1, 1)
        # TODO pick specific region of ROI

        self.ref_t1 = NumericOption("Reference T1 (s)", grid, ypos=2, minval=0, maxval=10, default=4.3, step=0.1)
        self.ref_t2 = NumericOption("Reference T2 (ms)", grid, ypos=3, minval=0, maxval=2000, default=750, step=50)
        self.ref_pc = NumericOption("Reference partition coefficient (ms)", grid, ypos=4, minval=0, maxval=5, default=1.15, step=0.05)
        self.te = NumericOption("Sequence TE (ms)", grid, ypos=5, minval=0, maxval=100, default=0, step=5)
        self.t1b = NumericOption("Blood T1 (s)", grid, ypos=6, minval=0, maxval=2000, default=150, step=50)
        # TODO sensitivity correction

        self.refregion_box.setVisible(False)
        vbox.addWidget(self.refregion_box)

        runbox = RunBox(self.get_process, self.get_options, title="Run calibration", save_option=True)
        vbox.addWidget(runbox)
        vbox.addStretch(1)
        
    def _ref_tiss_changed(self):
        ref_type = self.ref_type.combo.currentText()
        if ref_type != "Custom":
            from oxasl.calib import tissue_defaults
            t1, t2, t2star, pc = tissue_defaults(ref_type)
            self.ref_t1.spin.setValue(t1)
            self.ref_t2.spin.setValue(t2)
            self.ref_pc.spin.setValue(pc)   
        else:
            # Do nothing - user must choose their own values
            pass

    def batch_options(self):
        return "AslCalib", self.get_options()
    
    def get_process(self):
        return AslCalibProcess(self.ivm)

    def get_options(self):
        options = {
            "data" : self.data.currentText(),
            "roi" : self.roi.currentText(),
            "calib-data" : self.calib_img.currentText(),
            "multiplier" : 6000,
            "alpha" : self.alpha.value(),
            "gain" : self.gain.value(),
            "tr" : self.tr.value(),
            "var" : self.data_type.combo.currentIndex() == 1
        }
        if self.calib_method.combo.currentIndex() == 0:
            options.update({
                "method" : "voxelwise",
                "t1t" : self.t1t.value(),
                "pct" : self.pct.value(),
                "edgecorr" : True,
            })
        else:
            options.update({
                "method" : "refregion",
                "tissref" : self.ref_type.combo.currentText(),
                "ref-roi" : self.ref_roi.currentText(),
                "t1r" : self.ref_t1.value(),
                "t2r" : self.ref_t2.value(),
                "pcr" : self.ref_pc.value(),
                "te" : self.te.value(),
                "t1b" : self.t1b.value(),
            })
        return options

    def _calib_method_changed(self, idx):
        self.voxelwise_box.setVisible(idx == 0)
        self.refregion_box.setVisible(idx == 1)

class AslMultiphaseWidget(QpWidget):
    """
    Widget to do multiphase model fitting on ASL data
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="Multiphase ASL", icon="asl.png", group="ASL", desc="Bayesian Modelling for Multiphase Arterial Spin Labelling MRI", **kwargs)
        
    def init_ui(self):
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        try:
            self.process = BasilProcess(self.ivm)
        except QpException, e:
            self.process = None
            vbox.addWidget(QtGui.QLabel(str(e)))
            return
        
        title = TitleWidget(self, help="asl", subtitle="Bayesian pre-processing for Multiphase Arterial Spin Labelling MRI %s" % __version__)
        vbox.addWidget(title)
              
        cite = Citation(FAB_CITE_TITLE, FAB_CITE_AUTHOR, FAB_CITE_JOURNAL)
        vbox.addWidget(cite)

        self.tabs = QtGui.QTabWidget()
        vbox.addWidget(self.tabs)

        default_metadata = dict(DEFAULT_METADATA)
        default_metadata["iaf"] = "mp"
        default_metadata["order"] = "lrt"
        default_metadata["nphases"] = 8
        self.asldata_widget = AslImageWidget(self.ivm, ignore_views=[RepeatsChoice, Readout, Labelling, SliceTime, Multiband, AslParamsGrid], default_metadata=default_metadata)
        self.asldata_widget.data_combo.currentIndexChanged.connect(self._data_changed)
        self.tabs.addTab(self.asldata_widget, "ASL data")

        analysis_tab = QtGui.QWidget()
        grid = QtGui.QGridLayout()
        analysis_tab.setLayout(grid)

        #grid.addWidget(QtGui.QLabel("Output name"), 0, 0)
        #self.output_name_edit = QtGui.QLineEdit()
        #grid.addWidget(self.output_name_edit, 0, 1)
        grid.addWidget(QtGui.QLabel("Mask"), 1, 0)
        self.roi = RoiCombo(self.ivm)
        grid.addWidget(self.roi, 1, 1)

        self.biascorr_cb = QtGui.QCheckBox("Apply bias correction")
        self.biascorr_cb.setChecked(True)
        self.biascorr_cb.stateChanged.connect(self._biascorr_changed)
        grid.addWidget(self.biascorr_cb, 2, 0)

        self.num_sv = NumericOption("Number of supervoxels", grid, ypos=3, intonly=True, minval=1, default=8)
        self.sigma = NumericOption("Supervoxel pre-smoothing (mm)", grid, ypos=4, minval=0, default=0.5, decimals=1, step=0.1)
        self.compactness = NumericOption("Supervoxel compactness", grid, ypos=5, minval=0, default=0.1, decimals=2, step=0.05)
        self.verbose_cb = QtGui.QCheckBox("Keep interim results")
        grid.addWidget(self.verbose_cb, 6, 0)

        grid.setRowStretch(7, 1)
        self.tabs.addTab(analysis_tab, "Analysis Options")

        runbox = RunBox(self.get_process, self.get_options, title="Run Multiphase modelling", save_option=True)
        vbox.addWidget(runbox)
        vbox.addStretch(1)

    def activate(self):
        self._data_changed()

    def _data_changed(self):
        # Change data order to multiphase if it isn't already
        # FIXME not sure we want to do this!
        pass

    def _biascorr_changed(self):
        biascorr = self.biascorr_cb.isChecked()
        self.num_sv.spin.setVisible(biascorr)
        self.sigma.spin.setVisible(biascorr)
        self.compactness.spin.setVisible(biascorr)
        self.num_sv.label.setVisible(biascorr)
        self.sigma.label.setVisible(biascorr)
        self.compactness.label.setVisible(biascorr)
        self.verbose_cb.setVisible(biascorr)

    def batch_options(self):
        return "AslMultiphase", self.get_options()

    def get_process(self):
        return AslMultiphaseProcess(self.ivm)

    def _infer(self, options, param, selected):
        options["infer%s" % param] = selected

    def get_options(self):
        # General defaults
        options = self.asldata_widget.get_options()
        options["roi"] = self.roi.currentText()
        options["biascorr"] = self.biascorr_cb.isChecked()
        if options["biascorr"]:
            options["n-supervoxels"] = self.num_sv.value()
            options["sigma"] = self.sigma.value()
            options["compactness"] = self.compactness.value()
            options["keep-temp"] = self.verbose_cb.isChecked()
            
        for item in options.items():
            self.debug("%s: %s" % item)
        
        return options

class StructuralData(QtGui.QWidget):

    def __init__(self, ivm):
        QtGui.QWidget.__init__(self)
        self.ivm = ivm
        self.grid = QtGui.QGridLayout()
        self.setLayout(self.grid)

        self.grid.addWidget(QtGui.QLabel("Structural data from"), 0, 0)
        self.data_from = Choice(["Structural image", "FSL_ANAT output"], ["img", "fsl_anat"])
        self.data_from.sig_changed.connect(self._data_from_changed)
        self.grid.addWidget(self.data_from, 0, 1)
        self.struc_img = DataOption(self.ivm, include_4d=False)
        self.grid.addWidget(self.struc_img, 0, 2)
        self.fslanat_dir = FileOption(dirs=True)
        
        self.grid.setRowStretch(1, 1)

    def _data_from_changed(self):
        if self.data_from.value == "img":
            self.grid.addWidget(self.struc_img, 0, 2)
        else:
            self.grid.addWidget(self.fslanat_dir, 0, 2)

    def options(self):
        return {
            "struc" : self.struc_img.value,
        }

class CalibrationOptions(QtGui.QWidget):

    def __init__(self):
        QtGui.QWidget.__init__(self)
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        vbox.addWidget(self.optbox)
        vbox.addStretch(1)

    def options(self):
        return self.optbox.values()

class CorrectionOptions(QtGui.QWidget):

    def __init__(self):
        QtGui.QWidget.__init__(self)
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        vbox.addWidget(self.optbox)
        vbox.addStretch(1)

    def options(self):
        return self.optbox.values()

class AnalysisOptions(QtGui.QWidget):

    def __init__(self):
        QtGui.QWidget.__init__(self)
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        self.optbox.add("White paper mode", BoolOption(), key="wp")
        self.optbox.add("Arterial Transit Time", Number(minval=0, maxval=2.5, default=1.3), key="bat")
        self.optbox.add("T1 (s)", Number(minval=0, maxval=3, default=1.3), key="t1")
        self.optbox.add("T1b (s)", Number(minval=0, maxval=3, default=1.65), key="t1b")
        self.optbox.add("Spatial regularization", BoolOption(default=True), key="spatial")
        self.optbox.add("T1 value uncertainty", BoolOption(default=False), key="infert1")
        self.optbox.add("Macro vascular component", BoolOption(default=False), key="inferart")
        self.optbox.add("Fix label duration", BoolOption(default=True), key="fixbolus")
        self.optbox.add("Motion correction", BoolOption(default=False), key="mc")
        self.optbox.add("Partial volume correction", BoolOption(default=False), key="pvcorr")
        vbox.addWidget(self.optbox)
        vbox.addStretch(1)

    def options(self):
        return self.optbox.values()

class OxaslWidget(QpWidget):
    """
    Widget to do ASL data processing
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="ASL data processing", icon="asl.png", group="ASL", desc="Complete data processing for ASL data", **kwargs)
        
    def init_ui(self):
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        try:
            self.process = OxaslProcess(self.ivm)
        except QpException, e:
            self.process = None
            vbox.addWidget(QtGui.QLabel(str(e)))
            return
        
        title = TitleWidget(self, help="asl", subtitle="Data processing for Arterial Spin Labelling MRI %s" % __version__)
        vbox.addWidget(title)
              
        cite = Citation(FAB_CITE_TITLE, FAB_CITE_AUTHOR, FAB_CITE_JOURNAL)
        vbox.addWidget(cite)

        self.tabs = QtGui.QTabWidget()
        vbox.addWidget(self.tabs)

        self.asldata = AslImageWidget(self.ivm, parent=self)
        self.asldata.data_combo.currentIndexChanged.connect(self._data_changed)
        self.tabs.addTab(self.asldata, "ASL data")

        self.structural = StructuralData(self.ivm)
        self.tabs.addTab(self.structural, "Structural data")

        self.calibration = CalibrationOptions()
        self.tabs.addTab(self.calibration, "Calibration")

        self.corrections = CorrectionOptions()
        self.tabs.addTab(self.corrections, "Corrections")

        self.analysis = AnalysisOptions()
        self.tabs.addTab(self.analysis, "Analysis Options")

        runbox = RunBox(self.get_process, self.get_options, title="Run processing", save_option=True)
        vbox.addWidget(runbox)
        vbox.addStretch(1)

    def activate(self):
        self._data_changed()

    def _data_changed(self):
        pass

    def batch_options(self):
        return "Oxasl", self.get_options()

    def get_process(self):
        return self.process

    def _infer(self, options, param, selected):
        options["infer%s" % param] = selected

    def get_options(self):
        # General defaults
        options = self.asldata.get_options()
        options.update(self.structural.options())
        options.update(self.analysis.options())

        #options["t1"] = str(self.t1.spin.value())
        #options["t1b"] = str(self.t1b.spin.value())
        #options["bat"] = str(self.bat.spin.value())
        #options["spatial"] = self.spatial_cb.isChecked()
        
        # FIXME batsd

        #self._infer(options, "tiss", True)
        #self._infer(options, "t1", self.t1_cb.isChecked())
        #self._infer(options, "art", self.mv_cb.isChecked())
        #self._infer(options, "tau", not self.fixtau_cb.isChecked())
       
        for item in options.items():
            self.debug("%s: %s" % item)
        
        return options
