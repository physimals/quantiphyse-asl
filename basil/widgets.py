"""
Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""

from __future__ import division, unicode_literals, absolute_import, print_function

import sys
import os
import time
import traceback
import re
import tempfile
import math

import yaml
import numpy as np
from PySide import QtCore, QtGui

from quantiphyse.gui.widgets import QpWidget, OverlayCombo, RoiCombo, Citation, TitleWidget, ChoiceOption, NumericOption, NumberList, LoadNumbers, OrderList, OrderListButtons, NumericGrid, RunBox, NumberGrid
from quantiphyse.gui.dialogs import TextViewerDialog, error_dialog, GridEditDialog
from quantiphyse.utils import debug, warn, text_to_matrix
from quantiphyse.utils.exceptions import QpException

from .process import AslDataProcess, AslPreprocProcess, BasilProcess

from ._version import __version__
from .asl.image import AslImage

ORDER_LABELS = {
    "r" : ("Repeat ", "R", "Repeats"), 
    "t" : ("TI " , "TI", "TIs/PLDs"),
    "p" : (("Tag", "Control"), ("T", "C"), "TC pairs"),
    "P" : (("Control", "Tag"), ("C", "T"), "CT pairs"),
    "m" : ("Phase", "Ph", "Phases"),
}

TIMING_LABELS = {
    True : "PLDs",
    False : "TIs",
}

class AslDataPreview(QtGui.QWidget):
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
        
        self.setFixedHeight(self.fontMetrics().height()*4)
    
    def set_order(self, order):
        self.order = order
        self.repaint()

    def get_label(self, code, short):
        labels = ORDER_LABELS[code]
        if short: return labels[1]
        else: return labels[0]
        
    def draw_groups(self, p, groups, ox, oy, width, height, cont=False):
        if len(groups) == 0: return
        else:
            small = width < 150 # Heuristic
            group = groups[0]
            label = self.get_label(group, small)
            col = self.cols[group]
            if cont:
                p.fillRect(ox, oy, width-1, height-1, QtGui.QBrush(QtGui.QColor(*col)))
                p.drawText(ox, oy, width-1, height, QtCore.Qt.AlignHCenter, "...")
                self.draw_groups(p, groups[1:], ox, oy+height, width, height, cont=True)
            elif group in ("p", "P"):
                w = width/2
                for c in range(2):
                    p.fillRect(ox+c*w, oy, w-1, height-1, QtGui.QBrush(QtGui.QColor(*col)))
                    p.drawText(ox+c*w, oy, w-1, height, QtCore.Qt.AlignHCenter, label[c])
                    self.draw_groups(p, groups[1:], ox+c*w, oy+height, w, height)
            else:
                w = 2*width/5
                for c in range(2):
                    p.fillRect(ox+c*w, oy, w-1, height-1, QtGui.QBrush(QtGui.QColor(*col)))
                    p.drawText(ox+c*w, oy, w-1, height, QtCore.Qt.AlignHCenter, label + str(c+1))
                    self.draw_groups(p, groups[1:], ox+c*w, oy+height, w, height)
                self.draw_groups(p, groups, ox+2*w, oy, w/2, height, cont=True)

    def paintEvent(self, ev):
        h, w = self.height(), self.width()
        group_height = h*self.vfactor / len(self.order)
        group_width = self.hfactor*w
        ox = w*(1-self.hfactor)/2
        oy = h*(1-self.vfactor)/2
        p = QtGui.QPainter(self)
#        p.begin()
        self.draw_groups(p, self.order[::-1], ox, oy, group_width, group_height)
 #       p.end()

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
        if data_name not in self.ivm.data:
            self.setVisible(False)
        else:
            self.setVisible(True)
            struc = self.ivm.extras.get("ASL_STRUCTURE_" + data_name, None)
            debug("AslStrucCheck: ", struc)
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

class AslParamsGrid(NumericGrid):
    def __init__(self, tis, rpts, taus):
        self.fixed_repeats = True
        self.casl = True
        self.tau_header = "Bolus durations"
        self.rpt_header = "Repeats"
        NumericGrid.__init__(self, [tis, rpts, taus], 
                            row_headers=self.headers(),
                            expandable=(True, False), 
                            fix_height=True)
    
    def set_fixed_repeats(self, fixed_repeats):
        self.fixed_repeats = fixed_repeats
        vals = self.values()
        if fixed_repeats:
            self.setValues(vals[:2], validate=False)
        elif len(vals) == 2:
            vals.append([0,] * len(vals[0]))
            self.setValues(vals, validate=False, row_headers=self.headers())

    def set_labelling(self, casl):
        self.casl = casl
        self.setVerticalHeaderLabels(self.headers())

    def tis(self):
        return self.values()[0]

    def taus(self):
        return self.values()[1]

    def rpts(self):
        if not self.fixed_repeats:
            return self.values()[2]
        else:
            return None

    def headers(self):
        headers = []
        if self.casl: headers.append("PLDs")
        else: headers.append("TIs")
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
        #self.process = AslDataProcess(self.ivm)
        self.updating_ui = False
        self.process = AslDataProcess(self.ivm)
        self.struc = dict(self.process.default_struc)
        
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        grid = QtGui.QGridLayout()

        grid.addWidget(QtGui.QLabel("ASL data"), 0, 0)
        self.data_combo = OverlayCombo(self.ivm)
        self.data_combo.currentIndexChanged.connect(self.data_changed)
        grid.addWidget(self.data_combo, 0, 1)

        self.tc_combo = ChoiceOption("Data format", grid, ypos=1, choices=["Tag-control pairs", "Control-Tag pairs", "Already subtracted", "Multiphase"])
        self.tc_combo.sig_changed.connect(self.tc_changed)

        self.rpt_combo = ChoiceOption("Repeats", grid, ypos=2, choices=["Fixed", "Variable"])
        self.rpt_combo.sig_changed.connect(self.rpt_changed)
        self.rpt_spin = QtGui.QSpinBox()
        self.rpt_spin.setValue(1)
        self.rpt_spin.setMinimum(1)
        grid.addWidget(self.rpt_spin, 2, 2)

        grid.addWidget(QtGui.QLabel("Data grouping\n(top = outermost)"), 4, 0, alignment=QtCore.Qt.AlignTop)
        self.group_list = OrderList()
        grid.addWidget(self.group_list, 4, 1)
        self.list_btns = OrderListButtons(self.group_list)
        grid.addLayout(self.list_btns, 4, 2)
        # Have to set items after adding to grid or sizing doesn't work right
        self.group_list.sig_changed.connect(self.group_list_changed)

        grid.addWidget(QtGui.QLabel("Data order preview"), 5, 0)
        self.data_preview = AslDataPreview(self.struc["order"])
        grid.addWidget(self.data_preview, 6, 0, 1, 3)
        
        self.lbl_combo = ChoiceOption("Labelling", grid, ypos=7, choices=["cASL/pcASL", "pASL"])
        self.lbl_combo.combo.currentIndexChanged.connect(self.labelling_changed)

        self.nphases = NumericOption("Number of Phases (evenly spaced)",  grid, ypos=2, default=8, intonly=True, minval=2)
        self.nphases.label.setVisible(False)
        self.nphases.spin.setVisible(False)

        # Code below is for specific multiple phases
        #self.phases_lbl = QtGui.QLabel("Phases (\N{DEGREE SIGN})")
        #grid.addWidget(self.phases_lbl, 1, 0)
        #self.phases_lbl.setVisible(False)
        #self.phases = NumberList([float(x)*360/8 for x in range(8)])
        #grid.addWidget(self.phases, 1, 1)
        #self.phases.setVisible(False)

        self.params_grid = AslParamsGrid(self.struc["tis"], [1,], self.struc["taus"])
        self.params_grid.sig_changed.connect(self.params_grid_changed)
        grid.addWidget(self.params_grid, 8, 0, 1, 3)
        
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

        self.update_ui()
        self.data_changed()
        
    def set_data_name(self, name):
        if name not in self.ivm.data:
            raise QpException("Data not found: %s" % name)
        else:
            idx = self.data_combo.findText(name)
            self.data_combo.setCurrentIndex(idx)

    def update_ui(self):
        """ 
        Update user interface from the structure 
        """
        # Hack to avoid processing signals while updating UI
        self.updating_ui = True
        try:
            # Get the order and use it to select the right contents and grouping
            order = self.struc["order"]
            if "p" in order:
                self.tc_combo.combo.setCurrentIndex(0)
            elif "P" in order:
                self.tc_combo.combo.setCurrentIndex(1)
            elif "m" in order:
                self.tc_combo.combo.setCurrentIndex(3)
            else:
                self.tc_combo.combo.setCurrentIndex(2)

            # Phase list only visible in multiphase mode
            self.nphases.label.setVisible("m" in order)
            self.nphases.spin.setVisible("m" in order)

            self.group_list.setItems([self.groups[g] for g in order])
            self.data_preview.set_order(order)
            
            # Update TIs and repeats
            tis = self.struc["tis"]
            taus = self.struc["taus"]
            grid_values = [tis, taus]

            # Repeats can be set automatically    
            data = self.ivm.data.get(self.data_combo.currentText(), None)
            if data is None:
                nrpts = 1
            else:
                nvols = data.nvols
                nrpts = nvols / len(tis)
                if "p" in order or "P" in order:
                    nrpts /= 2
            debug("Auto repeats is: ",nrpts)
            var_rpts = "rpts" in self.struc
            if var_rpts:
                rpts = self.struc["rpts"]
                grid_values.append(rpts)

            self.rpt_spin.setValue(nrpts)
            self.rpt_spin.setVisible(not var_rpts)
            self.rpt_combo.combo.setCurrentIndex(int(var_rpts))
            self.params_grid.set_fixed_repeats(not var_rpts)
            self.params_grid.setValues(grid_values)
        finally:
            self.updating_ui = False

    def rpt_changed(self):
        if self.updating_ui: return
        fixed =  self.rpt_combo.combo.currentIndex() == 0
        if fixed:
            self.struc.pop("rpts")
        else:
            self.struc["rpts"] = [self.rpt_spin.value(),] * len(self.struc["tis"])

        self.update_ui()

    def labelling_changed(self):
        """
        Labelling method (CASL/PASL) changed
        """
        if self.updating_ui: return
        self.struc["casl"] = self.lbl_combo.combo.currentIndex() == 0
        self.params_grid.set_labelling(self.struc["casl"])
        self.save_structure()

    def tc_changed(self):
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

        debug("Contents combo changed: ", idx, order)
        self.struc["order"] = order
        self.update_ui()
        self.save_structure()

    def group_list_changed(self):
        """ Grouping list changed - modify the order """
        if self.updating_ui: return

        order = ""
        for item in self.group_list.items():
            code = [k for k, v in self.groups.items() if v == item][0]
            debug(item, code)
            order += code
        debug("Group list changed: ", order)
        self.struc["order"] = order
        self.update_ui()
        self.save_structure()

    def params_grid_changed(self):
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

        self.save_structure()

    def data_changed(self):
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
        self.update_ui()

    def save_structure(self):
        """
        Set the structure on the dataset using AslDataProcess
        """
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
                AslImage(data.name, data=data.std(), rpts=self.params_grid.rpts(), tis=self.params_grid.tis(), order=self.struc["order"])
                self.warn_label.setVisible(False)
                return True
            else:
                return False
        except RuntimeError, e:
            self.warn_label.setText(str(e))
            self.warn_label.setVisible(True)
            warn(e)
            return False

    def get_options(self):
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
        QpWidget.__init__(self, name="ASL Structure", icon="asl",  group="ASL", desc="Define the structure of an ASL dataset", **kwargs)
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
        QpWidget.__init__(self, name="ASL Preproc", icon="asl",  group="ASL", desc="Basic preprocessing on ASL data", **kwargs)
        self.process = AslPreprocProcess(self.ivm)

    def init_ui(self):
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        title = TitleWidget(self, help="asl", subtitle="Basic preprocessing of ASL data %s" % __version__)
        vbox.addWidget(title)
              
        self.struc_widget = AslStrucWidget(self.ivm, parent=self)
        vbox.addWidget(self.struc_widget)

        self.struc_check = AslStrucCheck(self.ivm)
        vbox.addWidget(self.struc_check)

        grid = QtGui.QGridLayout()

        self.sub_cb = QtGui.QCheckBox("Tag-control subtraction")
        self.sub_cb.stateChanged.connect(self.guess_output_name)
        grid.addWidget(self.sub_cb, 4, 0)
        
        self.reorder_cb = QtGui.QCheckBox("Reordering")
        grid.addWidget(self.reorder_cb, 5, 0)
        self.new_order = QtGui.QLineEdit()
        self.reorder_cb.stateChanged.connect(self.new_order.setEnabled)
        self.reorder_cb.stateChanged.connect(self.guess_output_name)
        grid.addWidget(self.new_order, 5, 1)
        
        #self.smooth_cb = QtGui.QCheckBox("Smoothing")
        #grid.addWidget(self.smooth_cb, 6, 0)
        
        grid.addWidget(QtGui.QLabel("Output name"), 7, 0)
        self.output_name = QtGui.QLineEdit()
        self.output_name.editingFinished.connect(self.output_name_changed)
        grid.addWidget(self.output_name, 7, 1)
        
        self.run_btn = QtGui.QPushButton("Run")
        self.run_btn.clicked.connect(self.run)
        grid.addWidget(self.run_btn, 8, 0)

        grid.setColumnStretch(2, 1)
        vbox.addLayout(grid)
        vbox.addStretch(1)
        self.output_name_edited = False

    def activate(self):
        self.data_changed()

    def deactivate(self):
        pass
        
    def output_name_changed(self):
        self.output_name_edited = True

    def data_changed(self):
        self.struc_check.set_data_name(self.struc_widget.data_combo.currentText())
        self.output_name_edited = False
        self.guess_output_name()

    def guess_output_name(self):
        data_name = self.struc_widget.data_combo.currentText()
        if data_name != "" and not self.output_name_edited:
            if self.sub_cb.isChecked():
                data_name += "_sub"
            if self.reorder_cb.isChecked():
                data_name += "_reorder"
            self.output_name.setText(data_name)

    def batch_options(self):
        return "AslPreproc", self.get_options()

    def get_process(self):
        return self.process

    def get_options(self):
        options = self.struc_widget.get_options()
        options["sub"] = self.sub_cb.isChecked()
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

        # FIXME add multiband readout options?
        grid = QtGui.QGridLayout()

        grid.addWidget(QtGui.QLabel("ASL data"), 0, 0)
        self.data_combo = OverlayCombo(self.ivm)
        self.data_combo.currentIndexChanged.connect(self.data_changed)
        grid.addWidget(self.data_combo, 0, 1)

        self.struc_check = AslStrucCheck(self.ivm)
        grid.addWidget(self.struc_check, 1, 0, 1, 3)
        vbox.addLayout(grid)

        grid = QtGui.QGridLayout()
        self.bat = NumericOption("Bolus arrival time (s)", grid, ypos=0, xpos=0, default=1.3, decimals=2)
        self.ie = NumericOption("Inversion efficiency", grid, ypos=1, xpos=0, default=0.85, decimals=2)
        self.t1 = NumericOption("T1 (s)", grid, ypos=0, xpos=2, default=1.3, decimals=2)
        self.t1b = NumericOption("T1b (s)", grid, ypos=1, xpos=2, default=1.65, decimals=2)

        self.spatial_cb = QtGui.QCheckBox("Spatial regularization")
        grid.addWidget(self.spatial_cb, 4, 0, 1, 2)
        self.t1_cb = QtGui.QCheckBox("Allow uncertainty in T1 values")
        grid.addWidget(self.t1_cb, 5, 0, 1, 2)
        self.mv_cb = QtGui.QCheckBox("Include macro vascular component")
        grid.addWidget(self.mv_cb, 6, 0, 1, 2)
        self.fixtau_cb = QtGui.QCheckBox("Fix bolus duration")
        grid.addWidget(self.fixtau_cb, 4, 2, 1, 2)
        #self.pvc_cb = QtGui.QCheckBox("Partial volume correction")
        #grid.addWidget(self.pvc_cb, 5, 2, 1, 2)
        vbox.addLayout(grid)

        self.runbox = RunBox(self.get_process, self.get_options, title="Run ASL modelling", save_option=True)
        vbox.addWidget(self.runbox)
        vbox.addStretch(1)

    def activate(self):
        self.data_changed()

    def data_changed(self):
        if self.process is not None:
            self.struc_check.set_data_name(self.data_combo.currentText())

    def batch_options(self):
        return "Basil", self.get_options()

    def get_process(self):
        return self.process

    def _infer(self, options, param, selected):
        if selected:
            options["infer%s" % param] = ""
            options["inc%s" % param] = ""
        else:
            options.pop("infer%s" % param, None)
            options.pop("inc%s" % param, None)

    def get_options(self):
        # General defaults
        options = {}
        options["data"] = self.data_combo.currentText()
        options["model-group"] = "asl"
        options["save-mean"] = ""
        options["save-model-fit"] = ""
        options["noise"] = "white"
        options["max-iterations"] = "20"
        options["model"] = "aslrest"
        options["t1"] = str(self.t1.spin.value())
        options["t1b"] = str(self.t1b.spin.value())
        options["bat"] = str(self.bat.spin.value())

        # FIXME inversion efficiency?
        # FIXME batsd

        # Analysis options
        if self.spatial_cb.isChecked():
            options["method"] = "spatialvb"
        else:
            options["method"] = "vb"

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
        pass
