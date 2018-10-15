"""
QP-BASIL - QWidgets for the Oxasl tool

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import

from PySide import QtGui

from quantiphyse.gui.options import OptionBox, ChoiceOption, NumericOption, BoolOption, DataOption, FileOption
from quantiphyse.gui.widgets import QpWidget, TitleWidget, Citation, RunBox
from quantiphyse.utils import QpException

from .aslimage_widget import AslImageWidget
from .process import OxaslProcess

from ._version import __version__

FAB_CITE_TITLE = "Variational Bayesian inference for a non-linear forward model"
FAB_CITE_AUTHOR = "Chappell MA, Groves AR, Whitcher B, Woolrich MW."
FAB_CITE_JOURNAL = "IEEE Transactions on Signal Processing 57(1):223-236, 2009."

class StructuralData(QtGui.QWidget):
    """
    OXASL processing options related to structural data
    """

    def __init__(self, ivm):
        QtGui.QWidget.__init__(self)
        self.ivm = ivm
        #self.grid = QtGui.QGridLayout()
        #self.setLayout(self.grid)

        #self.grid.addWidget(QtGui.QLabel("Structural data from"), 0, 0)
        #self.data_from = ChoiceOption(["Structural image", "FSL_ANAT output"], ["img", "fsl_anat"])
        #self.data_from.sig_changed.connect(self._data_from_changed)
        #self.grid.addWidget(self.data_from, 0, 1)

        #self.struc_img = DataOption(self.ivm, include_4d=False)
        #self.grid.addWidget(self.struc_img, 0, 2)
        #self.fslanat_dir = FileOption(dirs=True)
        
        #self.grid.addWidget(QtGui.QLabel("Segmentation"), 1, 0)
        #self.seg_from = ChoiceOption(["FSL FAST ", "FSL_ANAT output", "Manual"], ["fast", "fsl_anat", "manual"])
        #self.seg_from.sig_changed.connect(self._seg_from_changed)
        #self.grid.addWidget(self.seg_from, 1, 1)

        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        vbox.addWidget(self.optbox)
        vbox.addStretch(1)

        self.optbox.add("Structural data from", ChoiceOption(["Structural image", "FSL_ANAT output"], ["img", "fsl_anat"]), key="struc_src")
        self.optbox.option("struc_src").sig_changed.connect(self._data_from_changed)
        
        self.optbox.add("Structural image", DataOption(self.ivm, include_4d=False), key="struc")
        self.optbox.add("FSL_ANAT directory", FileOption(dirs=True), key="fslanat")
        self.optbox.set_visible("fslanat", False)

        #self.optbox.add("Segmentation", ChoiceOption(["FSL FAST ", "FSL_ANAT", "Manual"], ["fast", "fsl_anat", "manual"]), key="seg_src")
        #self.optbox.option("seg_src").sig_changed.connect(self._seg_from_changed)
        
        self.optbox.add("Override automatic segmentation")
        self.optbox.add("Brain image", DataOption(self.ivm, include_4d=False), key="struc_bet", checked=True)
        self.optbox.add("White matter", DataOption(self.ivm, include_4d=False), key="wmseg", checked=True)
        self.optbox.add("Grey matter", DataOption(self.ivm, include_4d=False), key="gmseg", checked=True)
        self.optbox.add("CSF", DataOption(self.ivm, include_4d=False), key="csfseg", checked=True)

    def _data_from_changed(self):
        struc_img = self.optbox.option("struc_src").value == "img"
        self.optbox.set_visible("struc", struc_img)
        self.optbox.set_visible("fslanat", not struc_img)
        
    def options(self):
        """ :return: Options as dictionary """
        return self.optbox.values()

class CalibrationOptions(QtGui.QWidget):
    """
    OXASL processing options related to calibration
    """

    def __init__(self, ivm):
        QtGui.QWidget.__init__(self)
        self.ivm = ivm
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        self.optbox.add("Calibration method", ChoiceOption(["Voxelwise", "Reference region"], ["voxelwise", "single"]), key="cmethod")
        self.optbox.option("cmethod").sig_changed.connect(self._calib_method_changed)
        self.optbox.add("Calibration image", DataOption(self.ivm), key="calib") 
        self.optbox.add("Sequence TR (s)", NumericOption(minval=0, maxval=20, default=3.2, step=0.1), key="tr")
        self.optbox.add("Calibration gain", NumericOption(minval=0, maxval=5, default=1, step=0.05), key="cgain")
        self.optbox.add("Inversion efficiency", NumericOption(minval=0, maxval=1, default=0.98, step=0.05), key="alpha")  
        vbox.addWidget(self.optbox)

        self.voxelwise_opts = OptionBox("Voxelwise calibration")
        self.voxelwise_opts.add("Tissue T1", NumericOption(minval=0, maxval=10, default=1.3, step=0.05), key="t1t")
        self.voxelwise_opts.add("Tissue partition coefficient", NumericOption(minval=0, maxval=5, default=0.9, step=0.05), key="pct")
        vbox.addWidget(self.voxelwise_opts)

        self.refregion_opts = OptionBox("Reference region calibration")
        # TODO switch T1/T2/PC defaults on tissue type
        self.refregion_opts.add("Reference type", ChoiceOption(["CSF", "WM", "GM", "Custom"]), key="tissref")
        #self.refregion_opts.option("tissref").sig_changed.connect(self._ref_tiss_changed)
        self.refregion_opts.add("Reference ROI", DataOption(self.ivm, rois=True, data=False), key="ref_mask")
        # TODO pick specific region of ROI
        self.refregion_opts.add("Reference T1 (s)", NumericOption(minval=0, maxval=10, default=4.3, step=0.1), key="t1r")
        self.refregion_opts.add("Reference T2 (ms)", NumericOption(minval=0, maxval=2000, default=750, step=50), key="t2r")
        self.refregion_opts.add("Reference partition coefficient (ms)", NumericOption(minval=0, maxval=5, default=1.15, step=0.05), key="pcr")
        self.refregion_opts.add("Sequence TE (ms)", NumericOption(minval=0, maxval=100, default=0, step=5), key="te")
        self.refregion_opts.add("Blood T1 (ms)", NumericOption(minval=0, maxval=2000, default=150, step=50), key="t1b")
        self.refregion_opts.setVisible(False)
        vbox.addWidget(self.refregion_opts)

        vbox.addStretch(1)

    def _calib_method_changed(self):
        voxelwise = self.optbox.option("cmethod").value == "voxelwise"
        self.voxelwise_opts.setVisible(voxelwise)
        self.refregion_opts.setVisible(not voxelwise)

    def options(self):
        """ :return: Options as dictionary """
        opts = self.optbox.values()
        if opts["cmethod"] == "voxelwise":
            opts.update(self.voxelwise_opts.values())
        else:
            opts.update(self.refregion_opts.values())

class PreprocOptions(QtGui.QWidget):
    """
    OXASL processing options related to corrections (motion, distortion etc)
    """

    def __init__(self):
        QtGui.QWidget.__init__(self)
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        vbox.addWidget(self.optbox)
        vbox.addStretch(1)

    def options(self):
        """ :return: Options as dictionary """
        return self.optbox.values()

class AnalysisOptions(QtGui.QWidget):
    """
    OXASL processing options related to model fitting analysis
    """

    def __init__(self):
        QtGui.QWidget.__init__(self)
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        self.optbox.add("White paper mode", BoolOption(), key="wp")
        self.optbox.add("Arterial Transit Time", NumericOption(minval=0, maxval=2.5, default=1.3), key="bat")
        self.optbox.add("T1 (s)", NumericOption(minval=0, maxval=3, default=1.3), key="t1")
        self.optbox.add("T1b (s)", NumericOption(minval=0, maxval=3, default=1.65), key="t1b")
        self.optbox.add("Spatial regularization", BoolOption(default=True), key="spatial")
        self.optbox.add("T1 value uncertainty", BoolOption(default=False), key="infert1")
        self.optbox.add("Macro vascular component", BoolOption(default=False), key="inferart")
        self.optbox.add("Fix label duration", BoolOption(default=True), key="fixbolus")
        self.optbox.add("Motion correction", BoolOption(default=False), key="mc")
        self.optbox.add("Partial volume correction", BoolOption(default=False), key="pvcorr")
        vbox.addWidget(self.optbox)
        vbox.addStretch(1)

    def options(self):
        """ :return: Options as dictionary """
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
        self.tabs.addTab(self.asldata, "ASL data")

        self.preproc = PreprocOptions()
        self.tabs.addTab(self.preproc, "Preprocessing")

        # Only add these if enabled in preprocessing
        # e.g. self.tabs.insertTab(self.tabs.indexOf(self.preproc)+1, self.veasl)
        # self.tabs.removeTab(self.tabs.indexOf(self.veasl))
        #self.veasl = VeaslOptions()
        #self.enable = EnableOptions()
        #self.deblur = DeblurOptions()

        self.structural = StructuralData(self.ivm)
        self.tabs.addTab(self.structural, "Structural data")

        self.calibration = CalibrationOptions(self.ivm)
        self.tabs.addTab(self.calibration, "Calibration")

        self.analysis = AnalysisOptions()
        self.tabs.addTab(self.analysis, "Analysis Options")

        runbox = RunBox(ivm=self.ivm, widget=self, title="Run processing", save_option=True)
        vbox.addWidget(runbox)
        vbox.addStretch(1)

    def _options(self):
        options = self.asldata.get_options()
        options.update(self.preproc.options())
        options.update(self.structural.options())
        options.update(self.calibration.options())
        options.update(self.analysis.options())

        #options["t1"] = str(self.t1.spin.value())
        #options["t1b"] = str(self.t1b.spin.value())
        #options["bat"] = str(self.bat.spin.value())
        #options["spatial"] = self.spatial_cb.isChecked()
       
        self.debug("oxasl options:")
        for item in options.items():
            self.debug("%s: %s" % item)
        
        return options

    def processes(self):
        return {"Oxasl" : self._options()}
