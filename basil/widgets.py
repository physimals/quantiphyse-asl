"""
QP-BASIL - Quantiphyse widgets for processing for ASL data

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import, print_function

import yaml
from PySide import QtCore, QtGui

from quantiphyse.gui.widgets import QpWidget, RoiCombo, OverlayCombo, Citation, TitleWidget, ChoiceOption, NumericOption, OrderList, OrderListButtons, NumberGrid, RunBox
from quantiphyse.utils import debug, warn
from quantiphyse.utils.exceptions import QpException

from .process import AslDataProcess, AslPreprocProcess, BasilProcess

from ._version import __version__
from .oxasl import AslImage

ORDER_LABELS = {
    "r" : ("Repeat ", "R", "Repeats"), 
    "t" : ("TI ", "TI", "TIs/PLDs"),
    "p" : (("Tag", "Control"), ("T", "C"), "TC pairs"),
    "P" : (("Control", "Tag"), ("C", "T"), "CT pairs"),
    "m" : ("Phase", "Ph", "Phases"),
}

TIMING_LABELS = {
    True : "PLDs",
    False : "TIs",
}

class AslDataPreview(QtGui.QWidget):
    """
    Visual preview of the structure of an ASL data set
    """
    def __init__(self, order, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.set_order(order)
        self.hfactor = 0.95
        self.vfactor = 0.95
        self.cols = {
            "r" : (128, 128, 255, 128), 
            "t" : (255, 128, 128, 128), 
            "P" : (128, 255, 128, 128),
            "p" : (128, 255, 128, 128),
            "m" : (128, 255, 128, 128),
        }
        
    
    def set_order(self, order):
        """ Set the data order, e.g. 'prt' = TC pairs, repeats, TIs/PLDs"""
        self.order = order
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

    def _get_label(self, code, short):
        labels = ORDER_LABELS[code]
        if short: return labels[1]
        return labels[0]
        
    def _draw_groups(self, p, groups, ox, oy, width, height, cont=False):
        if not groups: return
        else:
            small = width < 150 # Heuristic
            group = groups[0]
            label = self._get_label(group, small)
            col = self.cols[group]
            if cont:
                p.fillRect(ox, oy, width-1, height-1, QtGui.QBrush(QtGui.QColor(*col)))
                p.drawText(ox, oy, width-1, height, QtCore.Qt.AlignHCenter, "...")
                self._draw_groups(p, groups[1:], ox, oy+height, width, height, cont=True)
            elif group in ("p", "P"):
                w = width/2
                for c in range(2):
                    p.fillRect(ox+c*w, oy, w-1, height-1, QtGui.QBrush(QtGui.QColor(*col)))
                    p.drawText(ox+c*w, oy, w-1, height, QtCore.Qt.AlignHCenter, label[c])
                    self._draw_groups(p, groups[1:], ox+c*w, oy+height, w, height)
            else:
                w = 2*width/5
                for c in range(2):
                    p.fillRect(ox+c*w, oy, w-1, height-1, QtGui.QBrush(QtGui.QColor(*col)))
                    p.drawText(ox+c*w, oy, w-1, height, QtCore.Qt.AlignHCenter, label + str(c+1))
                    self._draw_groups(p, groups[1:], ox+c*w, oy+height, w, height)
                self._draw_groups(p, groups, ox+2*w, oy, w/2, height, cont=True)

class AslStrucCheck(QtGui.QWidget):
    """
    Widget which checks that structure information is available for an ASL data set
    """

    def __init__(self, ivm):
        QtGui.QWidget.__init__(self)
        self.ivm = ivm
        self.struc = None
        hbox = QtGui.QHBoxLayout()
        hbox.setSpacing(0)
        self.setLayout(hbox)

        self.ok_icon = QtGui.QIcon.fromTheme("dialog-information")
        self.warn_icon = QtGui.QIcon.fromTheme("dialog-error")
        self.icon = QtGui.QLabel()
        hbox.addWidget(self.icon)

        self.text = QtGui.QLabel()
        self.text.setWordWrap(True)
        hbox.addWidget(self.text)
        hbox.setStretchFactor(self.text, 2)

        self.set_data_name(None)
        
    def _order_readable(self, order):
        return ", ".join([ORDER_LABELS[c][2] for c in order])

    def set_data_name(self, data_name):
        """ Set the name of the data item whose structure is being checked """
        if data_name not in self.ivm.data:
            self.setVisible(False)
        else:
            self.setVisible(True)
            struc = self.ivm.extras.get("ASL_STRUCTURE_" + data_name, None)
            if struc is None:
                self.text.setText("You need to define the structure of your ASL data first\nSee the 'ASL Structure' widget")
                self.icon.setPixmap(self.warn_icon.pixmap(32, 32))
                self.setStyleSheet(
                    """QWidget { background-color: orange; color: black; padding: 5px 5px 5px 5px;}""")
            else:
                self.struc = yaml.load(struc)
                casl = self.struc.get("casl", True)
                text = "Asl structure found - "
                text += "Order: %s\n" % self._order_readable(self.struc.get("order", ""))
                if casl:
                    text += "Labelling: CASL/pCASL\n"
                else:
                    text += "Labelling: PASL\n"
                text += "%s: %s\n" % (TIMING_LABELS[casl], self.struc.get("tis", []))
                if "rpts" in self.struc:
                    text += "Repeats: %s\n" % self.struc["rpts"]

                self.text.setText(text)
                self.icon.setPixmap(self.ok_icon.pixmap(32, 32))
                self.setStyleSheet(
                    """QWidget { background-color: green; color: black; padding: 5px 5px 5px 5px;}""")

class AslParamsGrid(NumberGrid):
    """ Grid which displays TIs, taus and optionally variable repeats """
    def __init__(self, tis, rpts, taus):
        self.fixed_repeats = True
        self.casl = True
        self.tau_header = "Bolus durations"
        self.rpt_header = "Repeats"
        NumberGrid.__init__(self, [tis, rpts, taus], 
                            row_headers=self._headers(),
                            expandable=(True, False), 
                            fix_height=True)
    
    def set_fixed_repeats(self, fixed_repeats):
        """ Set whether repeats should be considered fixed """
        self.fixed_repeats = fixed_repeats
        vals = self.values()
        if fixed_repeats:
            self.setValues(vals[:2], validate=False)
        elif len(vals) == 2:
            vals.append([0,] * len(vals[0]))
            self.setValues(vals, validate=False, row_headers=self._headers())

    def set_labelling(self, casl):
        """ Set whether labelling is CASL/pCASL or PASL """
        self.casl = casl
        self._model.setVerticalHeaderLabels(self._headers())

    def tis(self):
        """ Return TI values """
        return self.values()[0]

    def taus(self):
        """ Return bolus durations """
        return self.values()[1]

    def rpts(self):
        """ Return repeats or None if fixed """
        if self.fixed_repeats:
            return None
        return self.values()[2]

    def _headers(self):
        headers = []
        headers.append(TIMING_LABELS[self.casl])
        headers.append(self.tau_header)
        if not self.fixed_repeats: headers.append(self.rpt_header)
        return headers

class AslStrucWidget(QtGui.QWidget):
    """
    QWidget which allows an ASL structure to be described
    """
    def __init__(self, ivm, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ivm = ivm
        self.groups = {
            "p" : "Tag-Control pairs", 
            "P" : "Control-Tag pairs", 
            "m" : "Phases", 
            "r" : "Repeats", 
            "t" : "TIs"
        }

        self.updating_ui = False
        self.process = AslDataProcess(self.ivm)
        self.struc = dict(self.process.default_struc)
        
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        grid = QtGui.QGridLayout()

        grid.addWidget(QtGui.QLabel("ASL data"), 0, 0)
        self.data_combo = OverlayCombo(self.ivm)
        self.data_combo.currentIndexChanged.connect(self._data_changed)
        grid.addWidget(self.data_combo, 0, 1)

        self.tc_combo = ChoiceOption("Data format", grid, ypos=1, choices=["Tag-control pairs", "Control-Tag pairs", "Already subtracted", "Multiphase"])
        self.tc_combo.sig_changed.connect(self._tc_changed)

        self.rpt_combo = ChoiceOption("Repeats", grid, ypos=2, choices=["Fixed", "Variable"])
        self.rpt_combo.sig_changed.connect(self._rpt_changed)

        self.nphases = NumericOption("Number of Phases (evenly spaced)", grid, ypos=3, default=8, intonly=True, minval=2)
        self.nphases.label.setVisible(False)
        self.nphases.spin.setVisible(False)
        self.nphases.spin.valueChanged.connect(self._nphases_changed)

        grid.addWidget(QtGui.QLabel("Data grouping\n(top = innermost)"), 4, 0, alignment=QtCore.Qt.AlignTop)
        self.group_list = OrderList()
        grid.addWidget(self.group_list, 4, 1)
        self.list_btns = OrderListButtons(self.group_list)
        grid.addLayout(self.list_btns, 4, 2)
        # Have to set items after adding to grid or sizing doesn't work right
        self.group_list.sig_changed.connect(self._group_list_changed)

        grid.addWidget(QtGui.QLabel("Data order preview"), 5, 0)
        self.data_preview = AslDataPreview(self.struc["order"])
        grid.addWidget(self.data_preview, 6, 0, 1, 3)
        
        self.lbl_combo = ChoiceOption("Labelling", grid, ypos=7, choices=["cASL/pcASL", "pASL"])
        self.lbl_combo.combo.currentIndexChanged.connect(self._labelling_changed)

        self.readout_combo = ChoiceOption("Readout", grid, ypos=8, choices=["3D (e.g. GRASE)", "2D (e.g. EPI)"])
        self.readout_combo.combo.currentIndexChanged.connect(self._readout_changed)

        self.slice_time = NumericOption("Time per slice (ms)", grid, ypos=9, default=10, decimals=2)
        self.slice_time.spin.valueChanged.connect(self._slice_time_changed)

        self.mb_cb = QtGui.QCheckBox("Multiband")
        self.mb_cb.stateChanged.connect(self._mb_changed)
        grid.addWidget(self.mb_cb, 10, 0)

        hbox = QtGui.QHBoxLayout()
        self.slices_per_band = QtGui.QSpinBox()
        self.slices_per_band.setMinimum(1)
        self.slices_per_band.setValue(5)
        hbox.addWidget(self.slices_per_band)
        self.slices_per_band.valueChanged.connect(self._sliceband_changed)
        self.slices_per_band_lbl = QtGui.QLabel("slices per band")
        hbox.addWidget(self.slices_per_band_lbl)
        grid.addLayout(hbox, 10, 1)
    
        # Code below is for specific multiple phases
        #self.phases_lbl = QtGui.QLabel("Phases (\N{DEGREE SIGN})")
        #grid.addWidget(self.phases_lbl, 3, 0)
        #self.phases_lbl.setVisible(False)
        #self.phases = NumberList([float(x)*360/8 for x in range(8)])
        #grid.addWidget(self.phases, 3, 1)
        #self.phases.setVisible(False)

        self.params_grid = AslParamsGrid(self.struc["tis"], [1,], self.struc["taus"])
        self.params_grid.sig_changed.connect(self._params_grid_changed)
        grid.addWidget(self.params_grid, 11, 0, 1, 3)
        
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
        """ Set the name of the data item whose structure is being displayed """
        if name not in self.ivm.data:
            raise QpException("Data not found: %s" % name)
        else:
            idx = self.data_combo.findText(name)
            self.data_combo.setCurrentIndex(idx)

    def _readout_changed(self):
        if self.readout_combo.combo.currentIndex() == 0:
            self.struc.pop("slicedt", None)
        else:
            self.struc["slicedt"] = self.slice_time.spin.value() / 1000 # ms-s
        self._update_ui(ignore=[self.readout_combo])
        self.save_structure()

    def _slice_time_changed(self):
        self.struc["slicedt"] = self.slice_time.spin.value() / 1000 # ms-s
        self._update_ui(ignore=[self.slice_time])
        self.save_structure()

    def _mb_changed(self):
        if self.mb_cb.isChecked():
            self.struc["sliceband"] = self.slices_per_band.value()
        else:
            self.struc.pop("sliceband", None)
        self._update_ui(ignore=[self.mb_cb])
        self.save_structure()

    def _sliceband_changed(self):
        self.struc["sliceband"] = self.slices_per_band.value()
        self._update_ui(ignore=[self.slices_per_band])
        self.save_structure()

    def _nphases_changed(self):
        self.struc["nphases"] = self.nphases.spin.value()
        self._update_ui(ignore=[self.nphases])
        self.save_structure()

    def _update_ui(self, ignore=()):
        """ 
        Update user interface from the structure 
        """
        # Hack to avoid processing signals while updating UI
        self.updating_ui = True
        try:
            # Get the order and use it to select the right contents and grouping
            order = self.struc["order"]
            if self.tc_combo not in ignore:
                if "p" in order:
                    self.tc_combo.combo.setCurrentIndex(0)
                elif "P" in order:
                    self.tc_combo.combo.setCurrentIndex(1)
                elif "m" in order:
                    self.tc_combo.combo.setCurrentIndex(3)
                else:
                    self.tc_combo.combo.setCurrentIndex(2)

            # Phase list only visible in multiphase mode
            if self.nphases not in ignore:
                self.nphases.label.setVisible("m" in order)
                self.nphases.spin.setVisible("m" in order)
                if "m" in order:
                    self.nphases.spin.setValue(self.struc.get("nphases", 8))

            if self.group_list not in ignore:
                self.group_list.setItems([self.groups[g] for g in order])
                self.data_preview.set_order(order)
            
            # Repeats
            var_rpts = "rpts" in self.struc

            if self.params_grid not in ignore:
                grid_values = [self.struc["tis"], self.struc["taus"]]
                if var_rpts:
                    grid_values.append(self.struc["rpts"])
                self.params_grid.set_fixed_repeats(not var_rpts)
                self.params_grid.set_labelling(self.struc["casl"])
                self.params_grid.setValues(grid_values)
            
            if self.rpt_combo not in ignore:
                self.rpt_combo.combo.setCurrentIndex(int(var_rpts))

            if self.lbl_combo not in ignore:
                self.lbl_combo.combo.setCurrentIndex(1-int(self.struc.get("casl", True)))

            # Readout
            slice_time = self.struc.get("slicedt", None)
            slices_per_band = self.struc.get("sliceband", None)
            readout_2d = slice_time is not None
            multiband = slices_per_band is not None
            if self.readout_combo not in ignore:
                self.readout_combo.combo.setCurrentIndex(int(readout_2d))

            if self.slice_time not in ignore:
                self.slice_time.label.setVisible(readout_2d)
                self.slice_time.spin.setVisible(readout_2d)
                if readout_2d: self.slice_time.spin.setValue(slice_time*1000) # s->ms
            
            if self.mb_cb not in ignore:
                self.mb_cb.setVisible(readout_2d)
                self.mb_cb.setChecked(multiband)

            if self.slices_per_band not in ignore:
                self.slices_per_band.setVisible(readout_2d)
                self.slices_per_band_lbl.setVisible(readout_2d)
                self.slices_per_band.setEnabled(multiband)
                if multiband: self.slices_per_band.setValue(slices_per_band)

            if self.slices_per_band not in ignore:
                self.slices_per_band.setEnabled(multiband)
                if slices_per_band is not None:
                    self.slices_per_band.setValue(slices_per_band)

        finally:
            self.updating_ui = False

    def _get_auto_repeats(self):
        data = self.ivm.data.get(self.data_combo.currentText(), None)
        if data is None: return 1

        nvols = data.nvols
        nrpts = nvols / len(self.struc["tis"])
        if "p" in self.struc["order"].lower():
            nrpts /= 2
        elif "m" in self.struc["order"].lower():
            nrpts /= self.nphases.value()
        return nrpts

    def _rpt_changed(self):
        if self.updating_ui: return
        fixed = self.rpt_combo.combo.currentIndex() == 0
        if fixed:
            self.struc.pop("rpts", None)
        else:
            self.struc["rpts"] = [self._get_auto_repeats(),] * len(self.struc["tis"])

        self._update_ui(ignore=[self.rpt_combo])
        self.save_structure()

    def _labelling_changed(self):
        """
        Labelling method (CASL/PASL) changed
        """
        self.struc["casl"] = self.lbl_combo.combo.currentIndex() == 0
        self._update_ui(ignore=[self.lbl_combo])
        self.save_structure()

    def _tc_changed(self):
        """ 
        Data contents (TC pairs, multiphase, subtracted, etc) changed - this can affect the order
        """
        if self.updating_ui: return

        order = self.struc["order"]
        idx = self.tc_combo.combo.currentIndex()

        chars = {0 : "p", 1 : "P", 2: "", 3: "m"}
        char = chars[idx]
        order = order.replace("p", char).replace("P", char).replace("m", char)
        if char != "" and char not in order:
            order = char + order

        self.struc["order"] = order
        if "m" in order:
            self.struc["nphases"] = self.nphases.spin.value()
        else:
            self.struc.pop("nphases", None)

        self._update_ui(ignore=[self.tc_combo])
        self.save_structure()

    def _group_list_changed(self):
        """ Grouping list changed - modify the order """
        if self.updating_ui: return

        order = ""
        for item in self.group_list.items():
            code = [k for k, v in self.groups.items() if v == item][0]
            order += code
        self.struc["order"] = order
        self._update_ui(ignore=[self.group_list])
        self.save_structure()

    def _params_grid_changed(self):
        if self.updating_ui: return

        try:
            tis = self.params_grid.tis()
            taus = self.params_grid.taus()
            rpts = self.params_grid.rpts()
        except ValueError:
            # Non-numeric values - don't change anything
            return

        self.struc["tis"] = tis
        self.struc["taus"] = taus
        if rpts is not None:
            # We have variable repeats
            self.struc["rpts"] = rpts

        self._update_ui(ignore=[self.params_grid])
        self.save_structure()

    def _data_changed(self):
        """
        New data selected - load any previously defined structure, and validate it 
        """
        data = self.ivm.data.get(self.data_combo.currentText(), None)
        if data is not None:
            self.load_structure(data.name)
            self.validate()
        
    def load_structure(self, data_name):
        """ 
        Load previously defined structure information, if any
        """
        asl_datastruct = self.ivm.extras.get("ASL_STRUCTURE_" + data_name, None)
        if asl_datastruct is not None:
            self.struc = yaml.load(asl_datastruct)
            debug("Existing structure for", data_name)
            debug(self.struc)
        else:
            # Use defaults below
            debug("Using default structure")
            self.struc = dict(self.process.default_struc)
            self.save_structure()
        self._update_ui()

    def save_structure(self):
        """
        Set the structure on the dataset using AslDataProcess
        """
        debug("save", self.struc)
        if self.validate():
            self.process.run(self.get_options())
            debug("Saved: ", self.struc)

    def validate(self):
        """
        Validate data against specified TIs, etc
        """
        try:
            data = self.ivm.data.get(self.data_combo.currentText(), None)
            if data is not None:
                debug("Validate: ", self.params_grid.tis(), self.params_grid.rpts(), self.params_grid.taus(), self.struc["order"])
                AslImage(data.name, data=data.raw(), 
                         rpts=self.params_grid.rpts(), 
                         tis=self.params_grid.tis(), 
                         order=self.struc["order"], 
                         nphases=self.struc.get("nphases", None))
                self.warn_label.setVisible(False)
                return True
            return False
        except RuntimeError, e:
            self.warn_label.setText(str(e))
            self.warn_label.setVisible(True)
            warn(e)
            return False

    def get_options(self):
        """ Get batch options """
        options = {
            "data" : self.data_combo.currentText(),
        }
        options.update(self.struc)
        return options

class AslDataWidget(QpWidget):
    """
    Widget which lets you define the structure of an ASL dataset
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="ASL Structure", icon="asl", group="ASL", desc="Define the structure of an ASL dataset", **kwargs)
        self.groups = {
            "p" : "Tag-Control pairs", 
            "P" : "Control-Tag pairs", 
            "m" : "Phases", 
            "r" : "Repeats", 
            "t" : "TIs"
        }
        self.process = AslDataProcess(self.ivm)
        self.updating_ui = False
        self.struc = dict(self.process.default_struc)
        
    def init_ui(self):
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        title = TitleWidget(self, help="asl_struc", subtitle="Define the structure of an ASL dataset %s" % __version__)
        vbox.addWidget(title)

        self.struc_widget = AslStrucWidget(self.ivm, parent=self)
        vbox.addWidget(self.struc_widget)

        vbox.addStretch(1)
        
    def batch_options(self):
        return "AslData", self.struc_widget.get_options()

    def get_process(self):
        return self.struc_widget.process
    
    def get_options(self):
        return self.struc_widget.get_options()

class AslPreprocWidget(QpWidget):
    """
    Widget which lets you do basic preprocessing on ASL data
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="ASL Preprocess", icon="asl", group="ASL", desc="Basic preprocessing on ASL data", **kwargs)
        self.process = AslPreprocProcess(self.ivm)
        self.output_name_edited = False

    def init_ui(self):
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        title = TitleWidget(self, help="asl", subtitle="Basic preprocessing of ASL data %s" % __version__)
        vbox.addWidget(title)
              
        self.struc_widget = AslStrucWidget(self.ivm, parent=self)
        self.struc_widget.data_combo.currentIndexChanged.connect(self._data_changed)
        vbox.addWidget(self.struc_widget)

        grid = QtGui.QGridLayout()

        self.sub_cb = QtGui.QCheckBox("Tag-control subtraction")
        self.sub_cb.stateChanged.connect(self._guess_output_name)
        grid.addWidget(self.sub_cb, 4, 0)
        
        self.reorder_cb = QtGui.QCheckBox("Reordering")
        grid.addWidget(self.reorder_cb, 5, 0)
        self.new_order = QtGui.QLineEdit()
        self.new_order.setEnabled(False)
        self.reorder_cb.stateChanged.connect(self.new_order.setEnabled)
        self.reorder_cb.stateChanged.connect(self._guess_output_name)
        grid.addWidget(self.new_order, 5, 1)
        
        self.mean_cb = QtGui.QCheckBox("Mean across repeats")
        grid.addWidget(self.mean_cb, 6, 0)
        self.mean_cb.stateChanged.connect(self._guess_output_name)

        #self.smooth_cb = QtGui.QCheckBox("Smoothing")
        #grid.addWidget(self.smooth_cb, 6, 0)
        
        grid.addWidget(QtGui.QLabel("Output name"), 7, 0)
        self.output_name = QtGui.QLineEdit()
        self.output_name.editingFinished.connect(self._output_name_changed)
        grid.addWidget(self.output_name, 7, 1)
        
        self.run_btn = QtGui.QPushButton("Run")
        self.run_btn.clicked.connect(self.run)
        grid.addWidget(self.run_btn, 8, 0)

        grid.setColumnStretch(2, 1)
        vbox.addLayout(grid)
        vbox.addStretch(1)
        self.output_name_edited = False

    def activate(self):
        self._data_changed()
        
    def _output_name_changed(self):
        self.output_name_edited = True

    def _data_changed(self):
        self.output_name_edited = False
        self._guess_output_name()
        # Tag-control differencing only if data contains TC or CT pairs
        print(self.struc_widget.struc["order"])
        pairs = "p" in self.struc_widget.struc["order"].lower()
        self.sub_cb.setEnabled(pairs)
        if not pairs: self.sub_cb.setChecked(False)

    def _guess_output_name(self):
        data_name = self.struc_widget.data_combo.currentText()
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
        options = self.struc_widget.get_options()
        options["diff"] = self.sub_cb.isChecked()
        options["mean"] = self.mean_cb.isChecked()
        options["output-name"] = self.output_name.text()
        if self.reorder_cb.isChecked(): 
            options["reorder"] = self.new_order.text()
        #if self.smooth_cb.isChecked(): 
        #    # FIXME sigma
        #    options["smooth"] = True
        return options

    def run(self):
        self.process.run(self.get_options())
        self.struc_widget.set_data_name(self.output_name.text())
         
FAB_CITE_TITLE = "Variational Bayesian inference for a non-linear forward model"
FAB_CITE_AUTHOR = "Chappell MA, Groves AR, Whitcher B, Woolrich MW."
FAB_CITE_JOURNAL = "IEEE Transactions on Signal Processing 57(1):223-236, 2009."

class AslBasilWidget(QpWidget):
    """
    Widget to do model fitting on ASL data
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="ASL Model fitting", icon="asl", group="ASL", desc="Bayesian model fitting on ASL data", **kwargs)
        
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

        self.struc_widget = AslStrucWidget(self.ivm, parent=self)
        self.struc_widget.data_combo.currentIndexChanged.connect(self._data_changed)
        self.tabs.addTab(self.struc_widget, "Data Structure")

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
        options = self.struc_widget.get_options()
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
            debug("%s: %s" % item)
        
        return options

    def run(self):
        self.process.run(self.get_options())

class AslCalibWidget(QpWidget):
    """
    Widget to do calibration on ASL data
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="ASL Calibration", icon="asl", group="ASL", desc="Calibration of fitted ASL data", **kwargs)
        
    def init_ui(self):
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)
        
        title = TitleWidget(self, help="asl", subtitle="ASL calibration v%s" % __version__)
        vbox.addWidget(title)
              
        calib_box = QtGui.QGroupBox("Calibration")
        grid = QtGui.QGridLayout()
        calib_box.setLayout(grid)

        self.calib_method = ChoiceOption("Calibration method", grid, ypos=0, choices=["Voxelwise", "Reference region"])
        self.calib_method.combo.currentIndexChanged.connect(self._calib_method_changed)
        
        grid.addWidget(QtGui.QLabel("Calibration image"), 1, 0)
        self.calib_img = OverlayCombo(self.ivm)
        grid.addWidget(self.calib_img, 1, 1)

        self.tr = NumericOption("Sequence TR (s)", grid, ypos=2, minval=0, maxval=20, default=6, step=0.1)
        self.gain = NumericOption("Calibration gain", grid, ypos=3, minval=0, maxval=5, default=1, step=0.05)

        grid.addWidget(QtGui.QLabel("Mask"), 1, 0)
        self.roi_combo = RoiCombo(self.ivm)
        grid.addWidget(self.roi_combo, 1, 1)

        vbox.addWidget(calib_box)

        self.voxelwise_box = QtGui.QGroupBox("Voxelwise calibration")
        grid = QtGui.QGridLayout()
        self.voxelwise_box.setLayout(grid)
        self.alpha = NumericOption("Inversion efficiency", grid, ypos=0, minval=0, maxval=1, default=0.98, step=0.05)
        vbox.addWidget(self.voxelwise_box)

        self.refregion_box = QtGui.QGroupBox("Reference region calibration")
        grid = QtGui.QGridLayout()
        self.refregion_box.setLayout(grid)
        self.ref_type = ChoiceOption("Reference type", grid, ypos=0, choices=["CSF", "WM", "GM", "None"])

        grid.addWidget(QtGui.QLabel("ROI"), 1, 0)
        self.ref_roi = RoiCombo(self.ivm)
        grid.addWidget(self.ref_roi, 1, 1)
        # TODO pick specific region of ROI

        self.ref_t1 = NumericOption("Reference T1 (s)", grid, ypos=2, minval=0, maxval=10, default=4.3, step=0.1)
        self.te = NumericOption("Sequence TE (ms)", grid, ypos=3, minval=0, maxval=100, default=0, step=5)
        self.ref_t2 = NumericOption("Reference T2 (ms)", grid, ypos=4, minval=0, maxval=2000, default=750, step=50)
        self.t1b = NumericOption("Blood T1 (s)", grid, ypos=5, minval=0, maxval=2000, default=150, step=50)
        # TODO sensitivity correction

        self.refregion_box.setVisible(False)
        vbox.addWidget(self.refregion_box)

        self.data_box = QtGui.QGroupBox("Data to calibrate")
        grid = QtGui.QGridLayout()
        grid.addWidget(QtGui.QLabel("Data"), 0, 0)
        self.data = OverlayCombo(self.ivm)
        grid.addWidget(self.data, 0, 1)
        self.data_type = ChoiceOption("Data type", grid, ypos=1, choices=["Perfusion", "Perfusion variance"])
        self.data_box.setLayout(grid)
        vbox.addWidget(self.data_box)
        # TODO calibrate multiple data sets

        runbox = RunBox(self.get_process, self.get_options, title="Run calibration", save_option=True)
        vbox.addWidget(runbox)
        vbox.addStretch(1)
        
    def get_process(self):
        return None

    def get_options(self):
        return None

    def _calib_method_changed(self, idx):
        self.voxelwise_box.setVisible(idx == 0)
        self.refregion_box.setVisible(idx == 1)