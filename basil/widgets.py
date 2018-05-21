"""
QP-BASIL - Quantiphyse widgets for processing for ASL data

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import, print_function

from PySide import QtCore, QtGui

from quantiphyse.gui.widgets import QpWidget, RoiCombo, OverlayCombo, Citation, TitleWidget, ChoiceOption, NumericOption, OrderList, OrderListButtons, NumberGrid, RunBox
from quantiphyse.utils import debug, warn
from quantiphyse.utils.exceptions import QpException

from .process import AslDataProcess, AslPreprocProcess, BasilProcess, AslCalibProcess, AslMultiphaseProcess

from ._version import __version__
from .oxasl import AslImage
from .oxasl.calib import get_tissue_defaults

ORDER_LABELS = {
    "r" : ("Repeat ", "R", "Repeats"), 
    "t" : ("TI ", "TI", "TIs/PLDs"),
    "p" : (("Label", "Control"), ("L", "C"), "Label-Control pairs"),
    "P" : (("Control", "Label"), ("C", "L"), "Control-Label pairs"),
    "m" : ("Phase ", "Ph", "Phases"),
}

TIMING_LABELS = {
    True : "PLDs",
    False : "TIs",
}

DEFAULT_STRUC = {
    "order" : "prt", 
    "tis" : [1.5,], 
    "taus" : [1.4,], 
    "casl" : True
}

def auto_repeats(data, struc):
    if data is None: 
        return [1,]
    
    nvols = data.nvols
    nrpts = float(nvols) / len(struc["tis"])
    if "p" in struc["order"].lower():
        ntc = 2
    elif "m" in struc["order"].lower():
        if "phases" in struc:
            ntc = len(struc["phases"])
        elif "nphases" in struc:
            ntc = struc["nphases"]
        else:
            ntc = 1
    else: 
        ntc = 1
    nrpts /= ntc
    rpts = [int(nrpts),] * len(struc["tis"])
    missing = data.nvols - ntc*sum(rpts)
    for idx in range(missing):
        rpts[idx] += 1
    return rpts

class StrucView(object):
    sig_struc_changed = QtCore.Signal(object)

    def set_data(self, data):
        pass

class AslDataPreview(QtGui.QWidget, StrucView):
    """
    Visual preview of the structure of an ASL data set
    """
    def __init__(self, struc, grid, ypos):
        QtGui.QWidget.__init__(self)
        self.set_struc(struc)
        self.hfactor = 0.95
        self.vfactor = 0.95
        self.cols = {
            "r" : (128, 128, 255, 128), 
            "t" : (255, 128, 128, 128), 
            "P" : (128, 255, 128, 128),
            "p" : (128, 255, 128, 128),
            "m" : (128, 255, 128, 128),
        }
        grid.addWidget(self, ypos, 0, 1, 3)
    
    def set_struc(self, struc):
        """ Set the data order, e.g. 'prt' = TC pairs, repeats, TIs/PLDs"""
        self.struc = struc
        self.order = struc.get("order", "prt")
        self.num = {
            "t" : len(struc.get("tis", [1.0] * 3)), 
            "r" : struc.get("rpts", [struc.get("nrpts", 3)])[0],
            "m" : len(struc.get("phases", [1] * struc.get("nphases", 8))),
            "p" : 2,
            "P" : 2,
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
            self.struc = self.ivm.data[data_name].metadata.get("AslData", None)
            if self.struc is None:
                self.text.setText("You need to define the structure of your ASL data first\nSee the 'ASL Structure' widget")
                self.icon.setPixmap(self.warn_icon.pixmap(32, 32))
                self.setStyleSheet(
                    """QWidget { background-color: orange; color: black; padding: 5px 5px 5px 5px;}""")
            else:
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

class NumPhases(NumericOption, StrucView):
    def __init__(self, struc, grid, ypos):
        NumericOption.__init__(self, "Number of Phases (evenly spaced)", grid, ypos, default=8, intonly=True, minval=2)
        self.set_struc(struc)
        self.sig_changed.connect(self._changed)
    
    def set_struc(self, struc):
        self.struc = struc
        order = self.struc["order"]
        # Phase list only visible in multiphase mode
        self.label.setVisible("m" in order)
        self.spin.setVisible("m" in order)
        if "m" in order:
            self.spin.setValue(self.struc.get("nphases", 8))
                    
    def _changed(self):
        self.struc["nphases"] = self.spin.value()
        self.sig_struc_changed.emit(self)

class DataOrdering(QtCore.QObject, StrucView):
    def __init__(self, struc, grid, ypos):
        QtCore.QObject.__init__(self)
        grid.addWidget(QtGui.QLabel("Data grouping\n(top = outermost)"), ypos, 0, alignment=QtCore.Qt.AlignTop)
        self.group_list = OrderList()
        grid.addWidget(self.group_list, ypos, 1)
        self.list_btns = OrderListButtons(self.group_list)
        grid.addLayout(self.list_btns, ypos, 2)

        # Have to set items after adding to grid or sizing doesn't work right
        self.set_struc(struc)
        self.group_list.sig_changed.connect(self._changed)
    
    def set_struc(self, struc):
        self.struc = struc
        order = self.struc["order"]
        self.group_list.setItems([ORDER_LABELS[g][2] for g in order[::-1]])
                     
    def _changed(self):
        order = ""
        for item in self.group_list.items():
            code = [k for k, v in ORDER_LABELS.items() if v[2] == item][0]
            order += code

        self.struc["order"] = order[::-1]
        self.sig_struc_changed.emit(self)

class LabelType(ChoiceOption, StrucView):

    def __init__(self, struc, grid, ypos):
        ChoiceOption.__init__(self, "Data format", grid, ypos, choices=["Label-control pairs", "Control-Label pairs", "Already subtracted", "Multiphase"])
        self.set_struc(struc)
        self.sig_changed.connect(self._changed)
    
    def set_struc(self, struc):
        self.struc = struc
        order = self.struc["order"]
        if "p" in order:
            self.combo.setCurrentIndex(0)
        elif "P" in order:
            self.combo.setCurrentIndex(1)
        elif "m" in order:
            self.combo.setCurrentIndex(3)
        else:
            self.combo.setCurrentIndex(2)
                      
    def _changed(self):
        order = self.struc["order"]
        idx = self.combo.currentIndex()

        char = ["p", "P", "", "m"][idx]
        order = order.replace("p", char).replace("P", char).replace("m", char)
        if char != "" and char not in order:
            order = char + order
        if char == "m":
            self.struc["nphases"] = 8

        self.struc["order"] = order
        self.sig_struc_changed.emit(self)

class Labelling(ChoiceOption, StrucView):

    def __init__(self, struc, grid, ypos):
        ChoiceOption.__init__(self, "Labelling", grid, ypos, choices=["cASL/pcASL", "pASL"])
        self.set_struc(struc)
        self.combo.currentIndexChanged.connect(self._changed)
    
    def set_struc(self, struc):
        self.struc = struc
        self.combo.setCurrentIndex(1-int(self.struc.get("casl", True)))
                      
    def _changed(self):
        self.struc["casl"] = self.combo.currentIndex() == 0
        self.sig_struc_changed.emit(self)

class Readout(ChoiceOption, StrucView):

    def __init__(self, struc, grid, ypos):
        ChoiceOption.__init__(self, "Readout", grid, ypos, choices=["3D (e.g. GRASE)", "2D (e.g. EPI)"])
        self.set_struc(struc)
        self.combo.currentIndexChanged.connect(self._changed)
    
    def set_struc(self, struc):
        self.struc = struc
        readout_2d = "slicedt" in self.struc
        self.combo.setCurrentIndex(int(readout_2d))
                      
    def _changed(self):
        if self.combo.currentIndex() == 0:
            self.struc.pop("slicedt", None)
        else:
            self.struc["slicedt"] = None
        
        self.sig_struc_changed.emit(self)

class SliceTime(NumericOption, StrucView):

    def __init__(self, struc, grid, ypos):
        NumericOption.__init__(self, "Time per slice (ms)", grid, ypos, default=10, decimals=2)
        self.set_struc(struc)
        self.spin.valueChanged.connect(self._changed)
    
    def set_struc(self, struc):
        self.struc = struc
        readout_2d = "slicedt" in self.struc
        self.label.setVisible(readout_2d)
        self.spin.setVisible(readout_2d)
        if readout_2d:
            slicedt = self.struc["slicedt"]
            if slicedt is None:
                slicedt = 0.01
            self.spin.setValue(slicedt*1000) # s->ms
            
    def _changed(self):
        self.struc["slicedt"] = self.spin.value() / 1000 # ms->s
        self.sig_struc_changed.emit(self)

class Multiband(QtCore.QObject, StrucView):

    def __init__(self, struc, grid, ypos):
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

        self.set_struc(struc)
        self.slices_per_band.valueChanged.connect(self._changed)
        self.cb.stateChanged.connect(self._changed)
    
    def set_struc(self, struc):
        self.struc = struc
        readout_2d = "slicedt" in self.struc
        multiband = "sliceband" in self.struc
        self.cb.setVisible(readout_2d)
        self.cb.setChecked(multiband)
        self.slices_per_band.setVisible(readout_2d)
        self.slices_per_band_lbl.setVisible(readout_2d)
        self.slices_per_band.setEnabled(multiband)
        if multiband: 
            self.slices_per_band.setValue(self.struc["sliceband"])
            
    def _changed(self):
        self.slices_per_band.setEnabled(self.cb.isChecked())
        if self.cb.isChecked():
            self.struc["sliceband"] = self.slices_per_band.value()
        else:
            self.struc.pop("sliceband", None)
        self.sig_struc_changed.emit(self)

class RepeatsChoice(ChoiceOption, StrucView):

    def __init__(self, struc, grid, ypos):
        ChoiceOption.__init__(self, "Repeats", grid, ypos, choices=["Fixed", "Variable"])

        self.set_struc(struc)
        self.set_data(None)
        self.sig_changed.connect(self._changed)
    
    def set_data(self, data):
        self.data = data
        self._changed()

    def set_struc(self, struc):
        self.struc = struc
        rpts = self.struc.get("rpts", None)
        var_rpts = rpts is not None and min(rpts) != max(rpts)
        self.combo.setCurrentIndex(int(var_rpts))

    def _changed(self):
        repeats = auto_repeats(self.data, self.struc)
        fixed_repeats = self.combo.currentIndex() == 0
        if fixed_repeats:
            self.struc.pop("rpts", None)
            if min(repeats) == max(repeats):
                self.struc["nrpts"] = repeats[0]
        else:
            self.struc.pop("nrpts", None)
            if "rpts" not in self.struc:
                self.struc["rpts"] = repeats
        self.sig_struc_changed.emit(self)
        
class AslParamsGrid(NumberGrid, StrucView):
    """ 
    Grid which displays TIs, taus and optionally variable repeats 
    """

    def __init__(self, struc, grid, ypos):
        self.tau_header = "Bolus durations"
        self.rpt_header = "Repeats"

        NumberGrid.__init__(self, [[1.0], [1.0], [1]],
                            row_headers=self._headers(True, True),
                            expandable=(True, False), 
                            fix_height=True)

        grid.addWidget(self, ypos, 0, 1, 3)
        self.set_struc(struc)
        self.set_data(None)
        self.sig_changed.connect(self._changed)
    
    def set_data(self, data):
        self.data = data
    
    def set_struc(self, struc):
        self.struc = struc

        rpts = self.struc.get("rpts", None)
        var_rpts = rpts is not None

        grid_values = [self.struc["tis"], self.struc["taus"]]
        if var_rpts:
            grid_values.append(rpts)

        casl = self.struc.get("casl", True)
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

        self.struc["tis"] = values[0]
        self.struc["taus"] = values[1]

        try:
            if len(values) > 2:
                self.struc["rpts"] = [int(v) for v in values[2]]
            else:
                # May need to recalculate fixed repeats
                repeats = auto_repeats(self.data, self.struc)
                self.struc.pop("nrpts", None)
                if min(repeats) == max(repeats):
                    self.struc["nrpts"] = repeats[0]
        except ValueError:
            # Repeats are not integers - FIXME silently ignored
            pass
            
        self.sig_struc_changed.emit(self)

class AslStrucWidget(QtGui.QWidget):
    """
    QWidget which allows an ASL structure to be described
    """
    def __init__(self, ivm, parent=None, **kwargs):
        QtGui.QWidget.__init__(self, parent)
        self.ivm = ivm
        self.default_struc = kwargs.get("default_struc", DEFAULT_STRUC)

        self.updating_ui = False
        self.process = AslDataProcess(self.ivm)
        self.struc = dict(self.default_struc)
        
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
            view = view_class(self.struc, grid, ypos=idx+2)
            view.sig_struc_changed.connect(self._struc_changed)
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
        """ Set the name of the data item whose structure is being displayed """
        if name not in self.ivm.data:
            raise QpException("Data not found: %s" % name)
        else:
            idx = self.data_combo.findText(name)
            self.data_combo.setCurrentIndex(idx)

    def set_struct(self, struct):
        self.struct = struct
        self._update_ui()
        self._save_structure()

    def _update_ui(self, ignore=()):
        """ 
        Update user interface from the structure 
        """
        # Hack to avoid processing signals while updating UI
        self.updating_ui = True
        try:
            for view in self.views:
                if view not in ignore:
                    view.set_struc(self.struc)
        finally:
            self.updating_ui = False

    def _struc_changed(self, sender):
        debug("struc changed", sender)
        debug(self.struc)
        if self.updating_ui: return
        self._update_ui(ignore=[sender])
        self._save_structure()

    def _data_changed(self):
        """
        New data selected - load any previously defined structure, and validate it 
        """
        data = self.ivm.data.get(self.data_combo.currentText(), None)
        if data is not None:
            self._load_structure(data.name)
            self._validate()
            for view in self.views:
                view.set_data(data)
        
    def _load_structure(self, data_name):
        """ 
        Load previously defined structure information, if any
        """
        if data_name in self.ivm.data:
            self.struc = self.ivm.data[data_name].metadata.get("AslData", None)
            if self.struc is not None:
                debug("Existing structure for", data_name)
                debug(self.struc)
            else:
                # Use defaults below
                debug("Using default structure")
                self.struc = dict(self.default_struc)
                self._save_structure()
            self._update_ui()

    def _save_structure(self):
        """
        Set the structure on the dataset using AslDataProcess
        """
        if self._validate():
            self.process.run(self.get_options())
            debug("Saved: ", self.struc)

    def _validate(self):
        """
        Validate data against specified TIs, etc
        """
        try:
            data = self.ivm.data.get(self.data_combo.currentText(), None)
            if data is not None:
                AslImage(data.name, data=data.raw(), 
                         rpts=self.struc.get("rpts", None), 
                         tis=self.struc.get("tis", None),
                         order=self.struc.get("order", None), 
                         nphases=self.struc.get("nphases", None))
                self.warn_label.setVisible(False)
                return True
            return False
        except RuntimeError, e:
            self.warn_label.setText(str(e))
            self.warn_label.setVisible(True)
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
        QpWidget.__init__(self, name="ASL Structure", icon="asl.png", group="ASL", desc="Define the structure of an ASL dataset", **kwargs)
        self.process = AslDataProcess(self.ivm)
        
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
        QpWidget.__init__(self, name="ASL Preprocess", icon="asl.png", group="ASL", desc="Basic preprocessing on ASL data", **kwargs)
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
        # Label-control differencing only if data contains LC or CL pairs
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
            t1, t2, t2star, pc = get_tissue_defaults(ref_type)
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

        default_struc = dict(DEFAULT_STRUC)
        default_struc["order"] = "mrt"
        default_struc["nphases"] = 8
        self.struc_widget = AslStrucWidget(self.ivm, ignore_views=[RepeatsChoice, Readout, Labelling, SliceTime, Multiband, AslParamsGrid], default_struc=default_struc)
        self.struc_widget.data_combo.currentIndexChanged.connect(self._data_changed)
        self.tabs.addTab(self.struc_widget, "Data Structure")

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
        data_name = self.struc_widget.data_combo.currentText()
        if data_name in self.ivm.data:
            struc = self.ivm.data[data_name].metadata.get("AslData", None)
            if struc is not None and "m" not in struc["order"]:
                struc["order"] = "mrt"
                self.struc_widget.set_struct(struc)

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
        options = self.struc_widget.get_options()
        options["roi"] = self.roi.currentText()
        options["biascorr"] = self.biascorr_cb.isChecked()
        if options["biascorr"]:
            options["n-supervoxels"] = self.num_sv.value()
            options["sigma"] = self.sigma.value()
            options["compactness"] = self.compactness.value()
            options["keep-temp"] = self.verbose_cb.isChecked()
            
        for item in options.items():
            debug("%s: %s" % item)
        
        return options
