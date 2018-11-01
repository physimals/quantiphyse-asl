"""
QP-BASIL - QWidgets for the Oxasl tool

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import

import numpy as np

from PySide import QtGui, QtCore

from quantiphyse.gui.options import OptionBox, ChoiceOption, NumericOption, BoolOption, DataOption, FileOption
from quantiphyse.gui.widgets import QpWidget, TitleWidget, Citation, RunBox, MultiExpander
from quantiphyse.utils import QpException

from .aslimage_widget import AslImageWidget
from .process import OxaslProcess
from .veasl_widgets import VeslocsWidget, EncodingWidget, PriorsWidget, ClasslistWidget, veslocs_default

from ._version import __version__

FAB_CITE_TITLE = "Variational Bayesian inference for a non-linear forward model"
FAB_CITE_AUTHOR = "Chappell MA, Groves AR, Whitcher B, Woolrich MW."
FAB_CITE_JOURNAL = "IEEE Transactions on Signal Processing 57(1):223-236, 2009."

class OxaslOptionWidget(QtGui.QWidget):
    def __init__(self, ivm=None):
        QtGui.QWidget.__init__(self)
        self.ivm = ivm

        self.vbox = QtGui.QVBoxLayout()
        self.setLayout(self.vbox)

        if hasattr(self, "cite"):
            self.vbox.addWidget(Citation(*self.cite))
            
        self.optbox = OptionBox()
        self.vbox.addWidget(self.optbox)
        self.init_ui()
        self.vbox.addStretch(1)
        
    def options(self):
        """ :return: Options as dictionary """
        return self.optbox.values()

class StructuralData(OxaslOptionWidget):
    """
    OXASL processing options related to structural data
    """

    def init_ui(self):
        self.optbox.add("Structural data from", ChoiceOption(["No structural data", "Structural image", "FSL_ANAT output"], [None, "img", "fsl_anat"]), key="struc_src")
        self.optbox.option("struc_src").sig_changed.connect(self._data_from_changed)
        
        self.optbox.add("Structural image", DataOption(self.ivm, include_4d=False), key="struc")
        self.optbox.add("FSL_ANAT directory", FileOption(dirs=True), key="fslanat")
        self.optbox.set_visible("fslanat", False)
        
        self.optbox.add("Override automatic segmentation")
        self.optbox.add("Brain image", DataOption(self.ivm, include_4d=False), key="struc_bet", checked=True)
        self.optbox.add("White matter", DataOption(self.ivm, include_4d=False), key="wmseg", checked=True)
        self.optbox.add("Grey matter", DataOption(self.ivm, include_4d=False), key="gmseg", checked=True)
        self.optbox.add("CSF", DataOption(self.ivm, include_4d=False), key="csfseg", checked=True)

    def _data_from_changed(self):
        data_from = self.optbox.option("struc_src").value
        self.optbox.set_visible("struc", data_from == "img")
        self.optbox.set_visible("fslanat", data_from == "fsl_anat")
        for opt in ("struc_bet", "wmset", "gmseg", "csfseg"):
            self.optbox.set_visible(opt, data_from is not None)

class CalibrationOptions(OxaslOptionWidget):
    """
    OXASL processing options related to calibration
    """

    def init_ui(self):
        self.optbox.add("Calibration method", ChoiceOption(["None", "Voxelwise", "Reference region"], [None, "voxelwise", "single"]), key="calib_method")
        self.optbox.option("calib_method").sig_changed.connect(self._calib_method_changed)
        self.optbox.add("Calibration image", DataOption(self.ivm), key="calib") 
        self.optbox.add("Sequence TR (s)", NumericOption(minval=0, maxval=20, default=3.2, step=0.1), key="tr")
        self.optbox.add("Sequence TE (ms)", NumericOption(minval=0, maxval=100, default=0, step=5), key="te")
        self.optbox.add("Calibration gain", NumericOption(minval=0, maxval=5, default=1, step=0.05), key="cgain")
        self.optbox.add("Inversion efficiency", NumericOption(minval=0, maxval=1, default=0.98, step=0.05), key="alpha")  
        
        self.voxelwise_opts = OptionBox("Voxelwise calibration")
        self.voxelwise_opts.add("Tissue T1", NumericOption(minval=0, maxval=10, default=1.3, step=0.05), key="t1t")
        self.voxelwise_opts.add("Tissue partition coefficient", NumericOption(minval=0, maxval=5, default=0.9, step=0.05), key="pct")
        self.vbox.addWidget(self.voxelwise_opts)

        self.refregion_opts = OptionBox("Reference region calibration")
        self.refregion_opts.add("Reference type", ChoiceOption(["CSF", "WM", "GM", "Custom"]), key="tissref")
        self.refregion_opts.option("tissref").sig_changed.connect(self._ref_tiss_changed)
        self.refregion_opts.add("Reference ROI", DataOption(self.ivm, rois=True, data=False), key="ref_mask")
        # TODO pick specific region of ROI
        self.refregion_opts.add("Reference T1 (s)", NumericOption(minval=0, maxval=10, default=4.3, step=0.1), key="t1r")
        self.refregion_opts.add("Reference T2 (ms)", NumericOption(minval=0, maxval=2000, default=750, step=50), key="t2r")
        self.refregion_opts.add("Reference partition coefficient (ms)", NumericOption(minval=0, maxval=5, default=1.15, step=0.05), key="pcr")
        self.refregion_opts.add("Blood T2 (ms)", NumericOption(minval=0, maxval=2000, default=150, step=50), key="t2b")
        self.refregion_opts.setVisible(False)
        self.vbox.addWidget(self.refregion_opts)

        self._calib_method_changed()

    def _calib_method_changed(self):
        method = self.optbox.option("calib_method").value
        self.voxelwise_opts.setVisible(method == "voxelwise")
        self.refregion_opts.setVisible(method == "single")
        for opt in ("calib", "tr", "te", "cgain", "alpha"):
            self.optbox.set_visible(opt, method is not None)

    def _ref_tiss_changed(self):
        ref_type = self.ref_type.combo.currentText()
        if ref_type != "Custom":
            from oxasl.calib import tissue_defaults
            t1, t2, t2star, pc = tissue_defaults(ref_type)
            self.refregion_opts.option("t1r").value = t1
            self.refregion_opts.option("t2r").value = t2
            self.refregion_opts.option("pcr").value = pc
        else:
            # Do nothing - user must choose their own values
            pass

    def options(self):
        """ :return: Options as dictionary """
        opts = self.optbox.values()
        method = self.optbox.option("calib_method").value
        if method == "voxelwise":
            opts.update(self.voxelwise_opts.values())
        elif method == "single":
            opts.update(self.refregion_opts.values())
        return opts

class PreprocOptions(OxaslOptionWidget):
    """
    OXASL processing options related to corrections (motion, distortion etc)
    """
    sig_enable_tab = QtCore.Signal(str, bool)

    def init_ui(self):
        self.optbox.add("Motion correction", BoolOption(default=True), key="mc")
        opt = self.optbox.add("Deblurring", BoolOption(), key="deblur")
        opt.sig_changed.connect(self._deblur_changed)
        opt = self.optbox.add("ENABLE volume selection", BoolOption(), key="enable")
        opt.sig_changed.connect(self._enable_changed)
        self.optbox.add("Distortion correction", ChoiceOption(["Fieldmap", "Phase encoding reversed calibration"], ["fmap", "cblip"]), key="distcorr", checked=True)
        self.optbox.option("distcorr").sig_changed.connect(self._distcorr_changed)
        self.optbox.add("Phase encode direction", ChoiceOption(["x", "y", "z", "-x", "-y", "-z"]), key="pedir")
        self.optbox.add("Echo spacing", NumericOption(minval=0, maxval=1, step=0.01), key="echospacing")

        self.fmap_opts = OptionBox("Fieldmap distortion correction")
        self.fmap_opts.add("Fieldmap image (rads)", DataOption(self.ivm, include_4d=False), key="fmap")
        self.fmap_opts.add("Fieldmap magnitude image (rads)", DataOption(self.ivm, include_4d=False), key="fmapmag")
        self.fmap_opts.add("Fieldmap magnitude brain image (rads)", DataOption(self.ivm, include_4d=False), key="fmapmagbrain")        
        self.vbox.addWidget(self.fmap_opts)

        self.cblip_opts = OptionBox("Phase-encoding reversed distortion correction")
        self.cblip_opts.add("Phase-encode reversed image", DataOption(self.ivm, include_4d=False), key="cblip")
        self.vbox.addWidget(self.cblip_opts)
        
        self._distcorr_changed()

    def _deblur_changed(self):
        self.sig_enable_tab.emit("deblur", self.optbox.option("deblur").value)

    def _enable_changed(self):
        self.sig_enable_tab.emit("enable", self.optbox.option("enable").value)

    def _distcorr_changed(self):
        enabled = self.optbox.option("distcorr").isEnabled()
        distcorr =  self.optbox.option("distcorr").value
        self.fmap_opts.setVisible(enabled and distcorr == "fmap")
        self.cblip_opts.setVisible(enabled and distcorr == "cblip")
        self.optbox.set_visible("pedir", enabled)
        self.optbox.set_visible("echospacing", enabled)

    def options(self):
        """ :return: Options as dictionary """
        return self.optbox.values()

class DistcorrOptions(OxaslOptionWidget):
    """
    OXASL processing options related to distortion correction
    """

    def init_ui(self):
        self.optbox.add("Distortion correction type", ChoiceOption(["None", "Fieldmap", "CBLIP"], [None, "fmap", "cblip"]), key="distcorr_type")
        self.optbox.option("distcorr_type").sig_changed.connect(self._distcorr_type_changed)
        
    def _distcorr_type_changed(self):
        pass

class EnableOptions(OxaslOptionWidget):
    """
    OXASL processing options related to ENABLE preprocessing
    """

    def init_ui(self):
        pass
        
class DeblurOptions(OxaslOptionWidget):
    """
    OXASL processing options related to oxasl_deblur preprocessing
    """

    def init_ui(self):
        pass
        
class VeaslOptions(OxaslOptionWidget):
    """
    OXASL processing options related to oxasl_deblur preprocessing
    """

    cite = (
        "A Fast Analysis Method for Non Invasive Imaging of Blood Flow in Individual Cerebral Arteries Using Vessel Encoded Arterial Spin Labelling Angiography.",
        "Chappell MA, Okell TW, Payne SJ, Jezzard P, Woolrich MW.",
        "Medical Image Analysis 16.4 (2012) 831-839",
    )

    # FIXME this is not used at present
    cite_multipld = (
        "Cerebral blood flow quantification using vessel-encoded arterial spin labelling",
        "Thomas W Okell, Michael A Chappell, Michael E Kelly, Peter Jezzard",
        "Journal of Cerebral Blood Flow and Metabolism (2013) 22, 1716-1724",
    )

    def __init__(self, ivm, data_widget):
        OxaslOptionWidget.__init__(self, ivm)
        self._data_widget = data_widget
        data_widget.sig_changed.connect(self._data_changed)

    def init_ui(self):
        auto_roi_btn = QtGui.QPushButton("Auto generate")
        self.optbox.add("Inference ROI", DataOption(self.ivm, rois=True, data=False), auto_roi_btn, key="roi")
        auto_roi_btn.clicked.connect(self._autogen_roi)
        
        nfpc = self.optbox.add("Sources per class", NumericOption(intonly=True, default=2, slider=False), key="nfpc")
        nfpc.sig_changed.connect(self._nfpc_changed)

        method = self.optbox.add("Inference method", ChoiceOption(choices=["MAP", "MCMC"]), key="method")
        method.sig_changed.connect(self._method_changed)

        self.optbox.add("Number of parameter jumps", NumericOption(intonly=True, slider=False, default=300), key="num-jumps")
        self.optbox.add("Number of 'burn in' jumps", NumericOption(intonly=True, slider=False, default=10), key="burnin")
        self.optbox.add("Number jumps per sample", NumericOption(intonly=True, slider=False, default=1), key="sample-every")
        self.mcmc_options = ["num-jumps", "burnin", "sample-every"]

        #self.optbox.add("Modulation matrix", ChoiceOption(choices=["Default"]), key="modmat")
        inferloc = self.optbox.add("Infer vessel locations", ChoiceOption(choices=["Fixed positions", "Infer co-ordinates", "Infer rigid transformation"], return_values=["none", "xy", "rigid"]), key="infer_loc")
        inferloc.sig_changed.connect(self._inferloc_changed)
        inferv = self.optbox.add("Infer flow velocity", BoolOption(), key="infer_v")
        inferv.sig_changed.connect(self._inferv_changed)
        self._method_changed()

        # Encoding setup
        self.enc_mtx = EncodingWidget()

        # Classes
        self.class_mtx = ClasslistWidget()

        # Vessel locations
        self.vessels = VeslocsWidget()
        self.vessels.sig_initial_changed.connect(self._vessels_changed)
        
        # Priors
        self.priors = PriorsWidget()

        self.vbox.addWidget(MultiExpander({"Encoding setup" : self.enc_mtx, 
                                           "Class list" : self.class_mtx,
                                           "Vessels" : self.vessels,
                                           "Priors" : self.priors}))

        self.vessels.vessels_initial.setValues(veslocs_default)
  
    def _data_changed(self):
        if self._data_widget.md["iaf"] == "mp":
            data = self._data_widget.data
            if data is not None:
                nvols = data.nvols
                self.enc_mtx.set_nvols(nvols)

    def _autogen_roi(self):
        data = self._data_widget.data
        if data is None:
            raise QpException("Need data to autogenerate mask")
        if data.ndim != 4:
            raise QpException("Data must be 4D")
            
        frac = 0.5 # DEFAULT
        imlist = list(self.enc_mtx.imlist)
        tag_idx = imlist.index(-1)
        ctl_idx = imlist.index(0)
        diffdata = np.abs(data.raw()[:, :, :, tag_idx] - data.raw()[:, :, :, ctl_idx])
        thresh = np.percentile(diffdata, 99) * frac
        roi = (diffdata > thresh).astype(np.int)
        self.ivm.add(roi, name="VEASL_AUTOGEN", grid=data.grid, make_current=True)
        self.optbox.option("roi").value = "VEASL_AUTOGEN"

    def _method_changed(self):
        mcmc = self.optbox.option("method").value == "MCMC"
        for opt in self.mcmc_options:
            self.optbox.set_visible(opt, mcmc)

    def _nfpc_changed(self):
        self.class_mtx.update(len(self.vessels.vessels_initial.values()[0]), self.optbox.option("nfpc").value)

    def _vessels_changed(self):
        self.class_mtx.update(len(self.vessels.vessels_initial.values()[0]), self.optbox.option("nfpc").value)
        self.enc_mtx.set_veslocs(self.vessels.vessels_initial.values())

    def _inferloc_changed(self):
        self.priors.set_infer_transform(self.optbox.values()["infer_loc"] == "rigid")

    def _inferv_changed(self):
        self.priors.set_infer_v(self.optbox.values()["infer_v"])
      
    def options(self):
        options = self.optbox.values()
        options.update(self.priors.options())
        options["vesloc"] = self.vessels.vessels_initial.values() 
        options["encdef"] = self.enc_mtx.mac_mtx.values()
        options["imlist"] = self.enc_mtx.imlist
        if options["method"] != "MCMC":
            for opt in self.mcmc_options:
                options.pop(opt, None)
        return options

class AnalysisOptions(OxaslOptionWidget):
    """
    OXASL processing options related to model fitting analysis
    """

    def init_ui(self):
        self.optbox.add("White paper mode", BoolOption(), key="wp")
        self.optbox.option("wp").sig_changed.connect(self._wp_changed)
        self.optbox.add("Default parameters")
        self.optbox.add("Arterial Transit Time", NumericOption(minval=0, maxval=2.5, default=1.3), key="bat")
        self.optbox.add("T1 (s)", NumericOption(minval=0, maxval=3, default=1.3), key="t1")
        self.optbox.add("T1b (s)", NumericOption(minval=0, maxval=3, default=1.65), key="t1b")
        self.optbox.add("Model fitting options")
        self.optbox.add("Spatial regularization", BoolOption(default=True), key="spatial")
        self.optbox.add("Fix label duration", BoolOption(default=True), key="fixbolus")
        self.optbox.add("T1 value uncertainty", BoolOption(default=False), key="infert1")
        self.optbox.add("Macro vascular component", BoolOption(default=False), key="inferart")
        self.optbox.add("Partial volume correction", BoolOption(default=False), key="pvcorr")
        
    def _wp_changed(self):
        pass

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
        self.asldata.sig_changed.connect(self._data_changed)
        self.tabs.addTab(self.asldata, "ASL data")

        self.preproc = PreprocOptions(self.ivm)
        self.preproc.sig_enable_tab.connect(self._enable_tab)
        self.tabs.addTab(self.preproc, "Preprocessing")

        # Only add these if enabled in preprocessing
        self._optional_tabs = {
            "veasl" :  VeaslOptions(self.ivm, self.asldata),
            "enable" : EnableOptions(),
            "deblur" : DeblurOptions(),
        }
        self._enable_tab("veasl", True)

        self.structural = StructuralData(self.ivm)
        self.tabs.addTab(self.structural, "Structural data")

        self.calibration = CalibrationOptions(self.ivm)
        self.tabs.addTab(self.calibration, "Calibration")

        self.analysis = AnalysisOptions()
        self.tabs.addTab(self.analysis, "Analysis Options")

        runbox = RunBox(ivm=self.ivm, widget=self, title="Run processing", save_option=True)
        vbox.addWidget(runbox)
        vbox.addStretch(1)

    def _data_changed(self):
        self._enable_tab("veasl", self.asldata.md["iaf"] == "mp")

    def _enable_tab(self, name, enable):
        widget = self._optional_tabs[name]
        self.tabs.removeTab(self.tabs.indexOf(widget))
        if enable:
            self.tabs.insertTab(self.tabs.indexOf(self.preproc)+1, widget, name.title())

    def _options(self):
        options = self.asldata.get_options()
        options.update(self.preproc.options())
        options.update(self.structural.options())
        options.update(self.calibration.options())
        options.update(self.analysis.options())
       
        for widget in self._optional_tabs.values():
            if self.tabs.indexOf(widget) >= 0:
                options.update(widget.options())

        self.debug("oxasl options:")
        for item in options.items():
            self.debug("%s: %s" % item)
        
        return options

    def processes(self):
        return {"Oxasl" : self._options()}
