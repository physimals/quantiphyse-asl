"""
QP-BASIL - Quantiphyse widgets for processing for ASL data

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import


from PySide2 import QtGui, QtCore, QtWidgets

from quantiphyse.gui.widgets import QpWidget, RoiCombo, OverlayCombo, Citation, TitleWidget, ChoiceOption, NumericOption, RunBox
from quantiphyse.utils import QpException

from .aslimage_widget import AslImageWidget
from .process import AslPreprocProcess, BasilProcess, AslCalibProcess, AslMultiphaseProcess

from ._version import __version__, __license__

# Default metadata for the multiphase widget
DEFAULT_MULTIPHASE_METADATA = {
    "iaf" : "mp",
    "order" : "lrt", 
    "nphases" : 8,
    "tis" : [1.5,], 
    "taus" : [1.4,], 
    "casl" : True
}

class AslPreprocWidget(QpWidget):
    """
    Widget which lets you do basic preprocessing on ASL data
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="ASL Preprocess", icon="asl.png", group="ASL", desc="Basic preprocessing on ASL data", version=__version__, license=__license__, **kwargs)
        self.process = AslPreprocProcess(self.ivm)
        self.output_name_edited = False

    def init_ui(self):
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)

        title = TitleWidget(self, help="asl", subtitle="Basic preprocessing of ASL data")
        vbox.addWidget(title)
              
        self.aslimage_widget = AslImageWidget(self.ivm, parent=self)
        self.aslimage_widget.data_combo.currentIndexChanged.connect(self._data_changed)
        vbox.addWidget(self.aslimage_widget)

        preproc_box = QtWidgets.QGroupBox("Preprocessing Options")
        grid = QtWidgets.QGridLayout()
        preproc_box.setLayout(grid)

        self.sub_cb = QtWidgets.QCheckBox("Label-control subtraction")
        self.sub_cb.stateChanged.connect(self._guess_output_name)
        grid.addWidget(self.sub_cb, 4, 0)
        
        self.reorder_cb = QtWidgets.QCheckBox("Reordering")
        grid.addWidget(self.reorder_cb, 5, 0)
        self.new_order = QtWidgets.QLineEdit()
        self.new_order.setEnabled(False)
        self.reorder_cb.stateChanged.connect(self.new_order.setEnabled)
        self.reorder_cb.stateChanged.connect(self._guess_output_name)
        grid.addWidget(self.new_order, 5, 1)
        
        self.mean_cb = QtWidgets.QCheckBox("Average data")
        grid.addWidget(self.mean_cb, 6, 0)
        self.mean_combo = QtWidgets.QComboBox()
        self.mean_combo.addItem("Mean across repeats")
        self.mean_combo.addItem("Perfusion-weighted image")
        grid.addWidget(self.mean_combo, 6, 1)
        self.mean_cb.stateChanged.connect(self.mean_combo.setEnabled)
        self.mean_cb.stateChanged.connect(self._guess_output_name)
        
        grid.addWidget(QtWidgets.QLabel("Output name"), 7, 0)
        self.output_name = QtWidgets.QLineEdit()
        self.output_name.editingFinished.connect(self._output_name_changed)
        grid.addWidget(self.output_name, 7, 1)
        
        self.run_btn = QtWidgets.QPushButton("Run")
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
        pairs = self.aslimage_widget.aslimage is not None and self.aslimage_widget.aslimage.iaf in ("tc", "ct")
        self.sub_cb.setEnabled(pairs)
        if not pairs: self.sub_cb.setChecked(False)

    def _guess_output_name(self):
        data_name = self.aslimage_widget.data_combo.currentText()
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
        options = self.aslimage_widget.get_options()
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
        QpWidget.__init__(self, name="ASL Model fitting", icon="asl.png", group="ASL", desc="Bayesian model fitting on ASL data", version=__version__, license=__license__, **kwargs)
        
    def init_ui(self):
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)

        try:
            self.process = BasilProcess(self.ivm)
        except QpException as e:
            self.process = None
            vbox.addWidget(QtWidgets.QLabel(str(e)))
            return
        
        title = TitleWidget(self, help="asl", subtitle="Bayesian Modelling for Arterial Spin Labelling MRI")
        vbox.addWidget(title)
              
        cite = Citation(FAB_CITE_TITLE, FAB_CITE_AUTHOR, FAB_CITE_JOURNAL)
        vbox.addWidget(cite)

        self.tabs = QtWidgets.QTabWidget()
        vbox.addWidget(self.tabs)

        self.aslimage_widget = AslImageWidget(self.ivm, parent=self)
        self.aslimage_widget.data_combo.currentIndexChanged.connect(self._data_changed)
        self.tabs.addTab(self.aslimage_widget, "Data Structure")

        analysis_tab = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout()
        analysis_tab.setLayout(grid)

        #grid.addWidget(QtWidgets.QLabel("Output name"), 0, 0)
        #self.output_name_edit = QtWidgets.QLineEdit()
        #grid.addWidget(self.output_name_edit, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Mask"), 1, 0)
        self.roi_combo = RoiCombo(self.ivm)
        grid.addWidget(self.roi_combo, 1, 1)

        self.bat = NumericOption("Bolus arrival time (s)", grid, ypos=2, xpos=0, default=1.3, decimals=2)
        self.t1 = NumericOption("T1 (s)", grid, ypos=2, xpos=3, default=1.3, decimals=2)
        self.t1b = NumericOption("T1b (s)", grid, ypos=3, xpos=3, default=1.65, decimals=2)

        self.spatial_cb = QtWidgets.QCheckBox("Spatial regularization")
        grid.addWidget(self.spatial_cb, 4, 0, 1, 2)
        self.fixtau_cb = QtWidgets.QCheckBox("Fix bolus duration")
        grid.addWidget(self.fixtau_cb, 4, 2, 1, 2)
        self.t1_cb = QtWidgets.QCheckBox("Allow uncertainty in T1 values")
        grid.addWidget(self.t1_cb, 5, 0, 1, 2)
        #self.pvc_cb = QtWidgets.QCheckBox("Partial volume correction")
        #grid.addWidget(self.pvc_cb, 5, 2, 1, 2)
        self.mv_cb = QtWidgets.QCheckBox("Include macro vascular component")
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
        options = self.aslimage_widget.get_options()
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
        QpWidget.__init__(self, name="ASL Calibration", icon="asl.png", group="ASL", desc="Calibration of fitted ASL data", version=__version__, license=__license__, **kwargs)
        
    def init_ui(self):
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        title = TitleWidget(self, help="asl", subtitle="ASL calibration")
        vbox.addWidget(title)
              
        self.data_box = QtWidgets.QGroupBox("Data to calibrate")
        grid = QtWidgets.QGridLayout()
        grid.addWidget(QtWidgets.QLabel("Data"), 0, 0)
        self.data = OverlayCombo(self.ivm)
        grid.addWidget(self.data, 0, 1)
        self.data_type = ChoiceOption("Data type", grid, ypos=1, choices=["Perfusion", "Perfusion variance"])
        self.data_box.setLayout(grid)

        grid.addWidget(QtWidgets.QLabel("Data ROI"), 2, 0)
        self.roi = RoiCombo(self.ivm)
        grid.addWidget(self.roi, 2, 1)

        self.calib_method = ChoiceOption("Calibration method", grid, ypos=3, choices=["Voxelwise", "Reference region"])
        vbox.addWidget(self.data_box)
        # TODO calibrate multiple data sets

        calib_box = QtWidgets.QGroupBox("Calibration Data")
        grid = QtWidgets.QGridLayout()
        calib_box.setLayout(grid)

        grid.addWidget(QtWidgets.QLabel("Calibration image"), 0, 0)
        self.calib_img = OverlayCombo(self.ivm)
        grid.addWidget(self.calib_img, 0, 1)

        self.tr = NumericOption("Sequence TR (s)", grid, ypos=1, minval=0, maxval=20, default=3.2, step=0.1)
        self.gain = NumericOption("Calibration gain", grid, ypos=3, minval=0, maxval=5, default=1, step=0.05)
        self.alpha = NumericOption("Inversion efficiency", grid, ypos=4, minval=0, maxval=1, default=0.98, step=0.05)
        self.calib_method.combo.currentIndexChanged.connect(self._calib_method_changed)
        
        vbox.addWidget(calib_box)

        self.voxelwise_box = QtWidgets.QGroupBox("Voxelwise calibration")
        grid = QtWidgets.QGridLayout()
        self.t1t = NumericOption("Tissue T1", grid, ypos=0, minval=0, maxval=10, default=1.3, step=0.05)
        self.pct = NumericOption("Tissue partition coefficient", grid, ypos=1, minval=0, maxval=5, default=0.9, step=0.05)
        self.voxelwise_box.setLayout(grid)
        vbox.addWidget(self.voxelwise_box)

        self.refregion_box = QtWidgets.QGroupBox("Reference region calibration")
        # TODO switch T1/T2/PC defaults on tissue type
        grid = QtWidgets.QGridLayout()
        self.refregion_box.setLayout(grid)
        self.ref_type = ChoiceOption("Reference type", grid, ypos=0, choices=["CSF", "WM", "GM", "Custom"])
        self.ref_type.combo.currentIndexChanged.connect(self._ref_tiss_changed)

        grid.addWidget(QtWidgets.QLabel("Reference ROI"), 1, 0)
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
        QpWidget.__init__(self, name="Multiphase ASL", icon="asl.png", group="ASL", desc="Bayesian Modelling for Multiphase Arterial Spin Labelling MRI", version=__version__, license=__license__, **kwargs)
        
    def init_ui(self):
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)

        try:
            self.process = BasilProcess(self.ivm)
        except QpException as e:
            self.process = None
            vbox.addWidget(QtWidgets.QLabel(str(e)))
            return
        
        title = TitleWidget(self, help="asl", subtitle="Bayesian pre-processing for Multiphase Arterial Spin Labelling MRI")
        vbox.addWidget(title)
              
        cite = Citation(FAB_CITE_TITLE, FAB_CITE_AUTHOR, FAB_CITE_JOURNAL)
        vbox.addWidget(cite)

        self.tabs = QtWidgets.QTabWidget()
        vbox.addWidget(self.tabs)

        self.aslimage_widget = AslImageWidget(self.ivm, default_metadata=DEFAULT_MULTIPHASE_METADATA)
        self.aslimage_widget.sig_changed.connect(self._aslimage_changed)
        self.tabs.addTab(self.aslimage_widget, "ASL data")

        analysis_tab = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout()
        analysis_tab.setLayout(grid)

        #grid.addWidget(QtWidgets.QLabel("Output name"), 0, 0)
        #self.output_name_edit = QtWidgets.QLineEdit()
        #grid.addWidget(self.output_name_edit, 0, 1)
        grid.addWidget(QtWidgets.QLabel("Mask"), 1, 0)
        self.roi = RoiCombo(self.ivm)
        grid.addWidget(self.roi, 1, 1)

        self.biascorr_cb = QtWidgets.QCheckBox("Apply bias correction")
        self.biascorr_cb.setChecked(True)
        self.biascorr_cb.stateChanged.connect(self._biascorr_changed)
        grid.addWidget(self.biascorr_cb, 2, 0)

        self.num_sv = NumericOption("Number of supervoxels", grid, ypos=3, intonly=True, minval=1, default=8)
        self.sigma = NumericOption("Supervoxel pre-smoothing (mm)", grid, ypos=4, minval=0, default=0.5, decimals=1, step=0.1)
        self.compactness = NumericOption("Supervoxel compactness", grid, ypos=5, minval=0, default=0.1, decimals=2, step=0.05)
        self.verbose_cb = QtWidgets.QCheckBox("Keep interim results")
        grid.addWidget(self.verbose_cb, 6, 0)

        grid.setRowStretch(7, 1)
        self.tabs.addTab(analysis_tab, "Analysis Options")

        self.runbox = RunBox(self.get_process, self.get_options, title="Run Multiphase modelling", save_option=True)
        vbox.addWidget(self.runbox)
        vbox.addStretch(1)

    def activate(self):
        self._aslimage_changed()

    def _aslimage_changed(self):
        if self.aslimage_widget.valid and self.aslimage_widget.data is not None and self.aslimage_widget.md.get("iaf", "") != "mp":
            self.aslimage_widget.warn_label.warn("This widget is only for use with multiphase data")
            self.aslimage_widget.warn_label.setVisible(True)
            self.runbox.setEnabled(False)
        else:
            self.runbox.setEnabled(self.aslimage_widget.valid)

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
        options = self.aslimage_widget.get_options()
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
