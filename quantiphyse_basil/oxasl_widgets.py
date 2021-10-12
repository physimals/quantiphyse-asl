"""
QP-BASIL - QWidgets for the Oxasl tool

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import

import numpy as np

from PySide2 import QtGui, QtCore, QtWidgets

from quantiphyse.gui.options import OptionBox, ChoiceOption, NumericOption, BoolOption, DataOption, FileOption, TextOption
from quantiphyse.gui.widgets import QpWidget, TitleWidget, Citation, RunWidget, MultiExpander
from quantiphyse.utils import get_plugins

from .aslimage_widget import AslImageWidget
from .veasl_widgets import VeslocsWidget, EncodingWidget, PriorsWidget, ClasslistWidget, veslocs_default

from ._version import __version__, __license__

FAB_CITE_TITLE = "Variational Bayesian inference for a non-linear forward model"
FAB_CITE_AUTHOR = "Chappell MA, Groves AR, Whitcher B, Woolrich MW."
FAB_CITE_JOURNAL = "IEEE Transactions on Signal Processing 57(1):223-236, 2009."

class OxaslOptionWidget(QtWidgets.QWidget):
    """
    Base class for a widget which provides options for OXASL
    """
    def __init__(self, ivm=None):
        QtWidgets.QWidget.__init__(self)
        self.ivm = ivm

        self.vbox = QtWidgets.QVBoxLayout()
        self.setLayout(self.vbox)

        if hasattr(self, "CITE"):
            self.vbox.addWidget(Citation(*self.CITE))
            
        self.optbox = OptionBox()
        self.vbox.addWidget(self.optbox)
        self._init_ui()
        self.vbox.addStretch(1)
        
    def options(self):
        """ 
        :return: Options as dictionary 
        """
        return self.optbox.values()

    def output(self):
        """
        :return: Dictionary of output items specific to this widget. The keys should be valid
                 quantiphyse names, and the values should be path-style identifiers in the output
                 workspace, e.g. ``enable/qms`` or ``veasl/veslocs``. Images will be added to the IVM,
                 other objects will be set as extras
        """
        return {}

    def postrun(self):
        """
        Called after run finished in case widget wants to display some of the output
        """
        pass

    def set_wp_mode(self, enabled):
        """
        Set whether the widget should display options in 'white paper mode'

        In white paper mode defaults are expected to follow the Alsop 2015
        consensus paper on ASL analysis although the user may explicitly
        override these defaults

        :param enabled: If True, white paper mode is enabled
        """
        pass

    def set_asldata_metadata(self, md):
        """
        Set the metadata defined for the base ASL data
        
        Widgets may modify defaults based on the ASL metadata

        :param md: Metadata as key/value mapping
        """
        pass

class StructuralData(OxaslOptionWidget):
    """
    OXASL processing options related to structural data
    """

    def _init_ui(self):
        self.optbox.add("Structural data from", ChoiceOption(["No structural data", "Structural image", "FSL_ANAT output"], [None, "img", "fsl_anat"]), key="struc_src")
        self.optbox.option("struc_src").sig_changed.connect(self._data_from_changed)
        self.optbox.add("Structural image", DataOption(self.ivm, include_4d=False, explicit=True), key="struc")
        self.optbox.add("FSL_ANAT directory", FileOption(dirs=True), key="fslanat")
        self.optbox.set_visible("fslanat", False)
        self.optbox.add("")
        self.optbox.add("<b>Override automatic segmentation</b>", key="override_label")
        self.optbox.add("Brain image", DataOption(self.ivm, include_4d=False, explicit=True), key="struc_bet", checked=True)
        self.optbox.add("White matter", DataOption(self.ivm, include_4d=False, explicit=True), key="wmseg", checked=True)
        self.optbox.add("Grey matter", DataOption(self.ivm, include_4d=False, explicit=True), key="gmseg", checked=True)
        self.optbox.add("CSF", DataOption(self.ivm, include_4d=False, explicit=True), key="csfseg", checked=True)
        self._data_from_changed()

    def _data_from_changed(self):
        data_from = self.optbox.option("struc_src").value
        self.optbox.set_visible("struc", data_from == "img")
        self.optbox.set_visible("fslanat", data_from == "fsl_anat")
        for opt in ("override_label", "struc_bet", "wmseg", "gmseg", "csfseg"):
            self.optbox.set_visible(opt, data_from is not None)

class CalibrationOptions(OxaslOptionWidget):
    """
    OXASL processing options related to calibration
    """

    def _init_ui(self):
        self.optbox.add("Calibration method", ChoiceOption(["None", "Voxelwise", "Reference region"], [None, "voxelwise", "single"]), key="calib_method")
        self.optbox.option("calib_method").sig_changed.connect(self._calib_method_changed)
        self.optbox.add("Calibration image", DataOption(self.ivm, explicit=True), key="calib") 
        self.optbox.add("Sequence TR (s)", NumericOption(minval=0, maxval=20, default=3.2, step=0.1, decimals=3), key="tr", checked=True)
        self.optbox.add("Sequence TE (ms)", NumericOption(minval=0, maxval=100, default=0, step=5, decimals=3), key="te", checked=True)
        self.optbox.add("Calibration gain", NumericOption(minval=0, maxval=5, default=1, step=0.05, decimals=3), key="calib_gain", checked=True)
        self.optbox.add("Inversion efficiency", NumericOption(minval=0, maxval=1, default=0.85, step=0.05, decimals=3), key="calib_alpha", checked=True)  
        
        self.voxelwise_opts = OptionBox("Voxelwise calibration")
        self.voxelwise_opts.add("Tissue T1", NumericOption(minval=0, maxval=10, default=1.3, step=0.05, decimals=3), key="t1t", checked=True)
        self.voxelwise_opts.add("Tissue partition coefficient", NumericOption(minval=0, maxval=5, default=0.9, step=0.05, decimals=3), key="pct", checked=True)
        self.vbox.addWidget(self.voxelwise_opts)

        self.refregion_opts = OptionBox("Reference region calibration")
        self.refregion_opts.add("Reference type", ChoiceOption(["CSF", "WM", "GM", "Custom"], ["csf", "wm", "gm", None]), key="tissref")
        self.refregion_opts.option("tissref").sig_changed.connect(self._ref_tiss_changed)
        self.refregion_opts.add("Custom reference ROI", DataOption(self.ivm, rois=True, data=False, explicit=True), key="refmask", checked=True)
        # TODO pick specific region of ROI
        self.refregion_opts.add("Reference T1 (s)", NumericOption(minval=0, maxval=10, default=4.3, step=0.1, decimals=3), key="t1r", checked=True)
        self.refregion_opts.add("Reference T2 (ms)", NumericOption(minval=0, maxval=2000, default=750, step=50, decimals=3), key="t2r", checked=True)
        self.refregion_opts.add("Reference partition coefficient (ms)", NumericOption(minval=0, maxval=5, default=1.15, step=0.05, decimals=3), key="pcr", checked=True)
        self.refregion_opts.add("Blood T2 (ms)", NumericOption(minval=0, maxval=2000, default=150, step=50, decimals=3), key="t2b", checked=True)
        self.refregion_opts.setVisible(False)
        self.vbox.addWidget(self.refregion_opts)

        self._calib_method_changed()

    def _calib_method_changed(self):
        method = self.optbox.option("calib_method").value
        self.voxelwise_opts.setVisible(method == "voxelwise")
        self.refregion_opts.setVisible(method == "single")
        for opt in ("calib", "tr", "te", "calib_gain", "calib_alpha"):
            self.optbox.set_visible(opt, method is not None)

    def _ref_tiss_changed(self):
        tissref = self.refregion_opts.option("tissref").value
        if tissref is not None:
            from oxasl.calib import tissue_defaults
            t1, t2, t2star, pc = tissue_defaults(tissref)
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

    def set_wp_mode(self, wp_enabled):
        if wp_enabled:
            self.optbox.option("calib_method").value = "voxelwise"

    def set_asldata_metadata(self, md):
        """
        Set the inversion efficiency default to 0.98 for PASL, 0.85 for CASL
        unless the checkbox is ticked in which case the user has modified it
        manually - so leave it alone
        """
        casl = md.get("casl", True)
        alpha = 0.85 if casl else 0.98
        if "calib_alpha" not in self.optbox.values():
            self.optbox.option("calib_alpha").value = alpha

class PreprocOptions(OxaslOptionWidget):
    """
    OXASL processing options related to corrections (motion, distortion etc)
    """
    sig_enable_tab = QtCore.Signal(str, bool)

    def _init_ui(self):
        self.optbox.add("Motion correction", BoolOption(default=True), key="mc")
        #opt = self.optbox.add("Deblurring", BoolOption(), key="deblur")
        #opt.sig_changed.connect(self._deblur_changed)
        opt = self.optbox.add("ENABLE volume selection", BoolOption(), key="use_enable")
        opt.sig_changed.connect(self._enable_changed)
        self.optbox.add("Distortion correction", ChoiceOption(["Fieldmap", "Phase encoding reversed calibration"], ["fmap", "cblip"]), key="distcorr", checked=True)
        self.optbox.option("distcorr").sig_changed.connect(self._distcorr_changed)
        self.optbox.add("Phase encode direction", ChoiceOption(["x", "y", "z", "-x", "-y", "-z"]), key="pedir")
        self.optbox.add("Echo spacing (ms)", NumericOption(minval=0, maxval=1, step=0.01, decimals=3), key="echospacing")

        self.fmap_opts = OptionBox("Fieldmap distortion correction")
        self.fmap_opts.add("Fieldmap image (rads)", DataOption(self.ivm, include_4d=False, explicit=True), key="fmap")
        self.fmap_opts.add("Fieldmap magnitude image (rads)", DataOption(self.ivm, include_4d=False, explicit=True), key="fmapmag")
        self.fmap_opts.add("Fieldmap magnitude brain image (rads)", DataOption(self.ivm, include_4d=False, explicit=True), key="fmapmagbrain")        
        self.vbox.addWidget(self.fmap_opts)

        self.cblip_opts = OptionBox("Phase-encoding reversed distortion correction")
        self.cblip_opts.add("Phase-encode reversed image", DataOption(self.ivm, include_4d=False, explicit=True), key="cblip")
        self.vbox.addWidget(self.cblip_opts)
        
        self._distcorr_changed()

    def _deblur_changed(self):
        self.sig_enable_tab.emit("deblur", self.optbox.option("deblur").value)

    def _enable_changed(self):
        self.sig_enable_tab.emit("enable", self.optbox.option("use_enable").value)

    def _distcorr_changed(self):
        enabled = self.optbox.option("distcorr").isEnabled()
        distcorr = self.optbox.option("distcorr").value
        self.fmap_opts.setVisible(enabled and distcorr == "fmap")
        self.cblip_opts.setVisible(enabled and distcorr == "cblip")
        self.optbox.set_visible("pedir", enabled)
        self.optbox.set_visible("echospacing", enabled)

    def options(self):
        """ :return: Options as dictionary """
        opts = self.optbox.values()
        
        if "echospacing" in opts:
            # Echo spacing needs to be passed in seconds
            opts["echospacing"] = opts["echospacing"] / 1000

        distcorr = opts.pop("distcorr", None)
        if distcorr == "fmap":
            opts.update(self.fmap_opts.values())
        elif distcorr == "cblip":
            opts.update(self.cblip_opts.values())
            
        return opts

class DistcorrOptions(OxaslOptionWidget):
    """
    OXASL processing options related to distortion correction
    """

    def _init_ui(self):
        self.optbox.add("Distortion correction type", ChoiceOption(["None", "Fieldmap", "CBLIP"], [None, "fmap", "cblip"]), key="distcorr_type")
        self.optbox.option("distcorr_type").sig_changed.connect(self._distcorr_type_changed)
        
    def _distcorr_type_changed(self):
        pass

class EnableOptions(OxaslOptionWidget):
    """
    OXASL processing options related to ENABLE preprocessing
    """

    CITE = (
        "Enhancement of automated blood flow estimates (ENABLE) from arterial spin-labeled MRI",
        "Shirzadi, Stefanovic, Chappell, Ramirez, Schwindt, Masellis, Black, Sandra, MacIntosh.",
        "Journal of Magnetic Resonance Imaging. . 10.1002/jmri.25807. 2017",
    )

    def __init__(self, ivm):
        self.qms_model = QtGui.QStandardItemModel()
        OxaslOptionWidget.__init__(self, ivm)

    def _init_ui(self):
        self.optbox.add("Minimum number of repeats per time point", NumericOption(intonly=True, default=3, minval=1, maxval=20), key="min_nvols")
        self.optbox.add("Custom grey matter ROI", DataOption(self.ivm, rois=True, data=False, explicit=True), checked=True, key="gm_roi")
        self.optbox.add("Custom noise ROI", DataOption(self.ivm, rois=True, data=False, explicit=True), checked=True, key="noise_roi")

        self.vbox.addWidget(QtWidgets.QLabel("Quality measures"))
        self.qms_table = QtWidgets.QTableView()
        self.qms_table.setModel(self.qms_model)
        self.vbox.addWidget(self.qms_table)

    def output(self):
        output = {
            "enable_results" : "enable/enable_results"
        }
        return output
    
    def postrun(self):
        # Clear the results table and repopulate it if we have results from the run
        self.qms_model.clear()
        self.qms_model.setColumnCount(5)
        self.qms_model.setHorizontalHeaderItem(0, QtGui.QStandardItem("TI"))
        self.qms_model.setHorizontalHeaderItem(1, QtGui.QStandardItem("Repeat"))
        self.qms_model.setHorizontalHeaderItem(2, QtGui.QStandardItem("CNR"))
        self.qms_model.setHorizontalHeaderItem(3, QtGui.QStandardItem("Quality"))
        self.qms_model.setHorizontalHeaderItem(4, QtGui.QStandardItem("Included"))

        results = self.ivm.extras.get("enable_results", None)
        if results is not None:
            df = results.df.sort_values(['ti_idx', 'rpt'])
            self.qms_model.setRowCount(len(df))
            for row, result in df.iterrows():
                for col, meas in enumerate(("ti", "rpt", "cnr", "qual", "selected")):
                    self.qms_model.setItem(row, col, QtGui.QStandardItem(str(result[meas])))

class DeblurOptions(OxaslOptionWidget):
    """
    OXASL processing options related to oxasl_deblur preprocessing
    """

    def _init_ui(self):
        pass

class VeaslOptions(OxaslOptionWidget):
    """
    OXASL processing options related to oxasl_deblur preprocessing
    """

    # FIXME this is not used at present
    CITE_OLD = (
        "A Fast Analysis Method for Non Invasive Imaging of Blood Flow in Individual Cerebral Arteries Using Vessel Encoded Arterial Spin Labelling Angiography.",
        "Chappell MA, Okell TW, Payne SJ, Jezzard P, Woolrich MW.",
        "Medical Image Analysis 16.4 (2012) 831-839",
    )

    CITE = (
        "Cerebral blood flow quantification using vessel-encoded arterial spin labelling",
        "Thomas W Okell, Michael A Chappell, Michael E Kelly, Peter Jezzard",
        "Journal of Cerebral Blood Flow and Metabolism (2013) 22, 1716-1724",
    )

    def __init__(self, ivm, data_widget):
        self.mcmc_options = ["num-jumps", "burnin", "sample-every"]
        self._data_widget = data_widget
        data_widget.sig_changed.connect(self._data_changed)
        OxaslOptionWidget.__init__(self, ivm)

    def _init_ui(self):
        nfpc = self.optbox.add("Sources per class", NumericOption(intonly=True, default=2, slider=False), key="nfpc")
        nfpc.sig_changed.connect(self._nfpc_changed)

        method = self.optbox.add("Inference method", ChoiceOption(choices=["MAP", "MCMC"]), key="method")
        method.sig_changed.connect(self._method_changed)

        self.optbox.add("Number of parameter jumps", NumericOption(intonly=True, slider=False, default=300), key="num-jumps")
        self.optbox.add("Number of 'burn in' jumps", NumericOption(intonly=True, slider=False, default=10), key="burnin")
        self.optbox.add("Number jumps per sample", NumericOption(intonly=True, slider=False, default=1), key="sample-every")

        #self.optbox.add("Modulation matrix", ChoiceOption(choices=["Default"]), key="modmat")
        inferloc = self.optbox.add("Infer vessel locations", ChoiceOption(choices=["Fixed positions", "Infer co-ordinates", "Infer rigid transformation"], return_values=["none", "xy", "rigid"], default="rigid"), key="infer_loc_initial")
        inferloc.sig_changed.connect(self._inferloc_changed)
        self.optbox.add("Infer vessel locations on mean data", BoolOption(default=True), key="init_loc")
        inferv = self.optbox.add("Infer flow velocity", BoolOption(), key="infer_v")
        inferv.sig_changed.connect(self._inferv_changed)
        self.optbox.add("Custom Inference ROI", DataOption(self.ivm, rois=True, data=False, explicit=True), checked=True, key="infer_mask")
        
        self._method_changed()

        # Encoding setup
        self.encoding = EncodingWidget()

        # Classes
        self.classlist = ClasslistWidget()

        # Vessel locations
        self.vessels = VeslocsWidget()
        self.vessels.sig_initial_changed.connect(self._vessels_changed)
        
        # Priors
        self.priors = PriorsWidget()

        self.vbox.addWidget(MultiExpander({"Encoding setup" : self.encoding, 
                                           "Class list" : self.classlist,
                                           "Vessels" : self.vessels,
                                           "Priors" : self.priors}))

        self.vessels.initial = veslocs_default
  
    def _data_changed(self):
        if self._data_widget.md["iaf"] == "ve":
            data = self._data_widget.data
            if data is not None:
                self.encoding.nenc = self._data_widget.md.get("nenc", 8)

    def _method_changed(self):
        mcmc = self.optbox.option("method").value == "MCMC"
        for opt in self.mcmc_options:
            self.optbox.set_visible(opt, mcmc)

    def _nfpc_changed(self):
        self.classlist.generate_classes(len(self.vessels.initial[0]), self.optbox.option("nfpc").value)

    def _vessels_changed(self):
        self.classlist.generate_classes(len(self.vessels.initial[0]), self.optbox.option("nfpc").value)
        self.encoding.veslocs = self.vessels.initial

    def _inferloc_changed(self):
        val = self.optbox.values()["infer_loc"]
        self.priors.set_infer_transform(val == "rigid")
        self.optbox.set_visible("init_loc", val != "none")

    def _inferv_changed(self):
        self.priors.set_infer_v(self.optbox.values()["infer_v"])
      
    def options(self):
        options = self.optbox.values()
        options.update(self.priors.options())
        options["veslocs"] = self.vessels.initial
        options["encdef"] = self.encoding.mac
        options["imlist"] = self.encoding.imlist
        if self.optbox.option("method").value != "MCMC":
            for opt in self.mcmc_options:
                options.pop(opt, None)
        return options

    def output(self):
        output = {}
        if self._data_widget.data is not None:
            plds = self._data_widget.md.get("plds", self._data_widget.md.get("tis", []))
            for idx in range(1, len(plds)+1):
                output["veasl_veslocs_pld%i" % idx] = "veasl/pld%i/veslocs" % idx
                output["veasl_pis_pld%i" % idx] = "veasl/pld%i/pis" % idx
        return output

    def postrun(self):
        if self._data_widget.data is not None:
            veslocs, pis = [], []
            plds = self._data_widget.md.get("plds", self._data_widget.md.get("tis", []))
            for idx in range(1, len(plds)+1):
                if "veasl_veslocs_pld%i" % idx in self.ivm.extras:
                    veslocs.append(self.ivm.extras["veasl_veslocs_pld%i" % idx].arr)
                if "veasl_pis_pld%i" % idx in self.ivm.extras:
                    pis.append(self.ivm.extras["veasl_pis_pld%i" % idx].arr)

            if veslocs:
                self.vessels.inferred = veslocs[0]
            if pis:
                self.classlist.inferred_pis = np.array(pis[0]).T

class AnalysisOptions(OxaslOptionWidget):
    """
    OXASL processing options related to model fitting analysis
    """

    def _init_ui(self):
        self._batdefault = 1.3
        self.optbox.add("<b>Model fitting options</b>")
        self.optbox.add("Custom ROI", DataOption(self.ivm, data=False, rois=True, explicit=True), key="roi", checked=True)
        self.optbox.add("Spatial regularization", BoolOption(default=True), key="spatial")
        self.optbox.add("Fix label duration", BoolOption(default=False, invert=True), key="infertau")
        self.optbox.add("Fix arterial transit time", BoolOption(default=True, invert=True), key="inferbat")
        self.optbox.add("T1 value uncertainty", BoolOption(default=False), key="infert1")
        self.optbox.add("Macro vascular component", BoolOption(default=True), key="inferart")
        self.optbox.add("Partial volume correction", BoolOption(default=False), key="pvcorr")
        self.optbox.add("")
        self.optbox.add("<b>Default parameters</b>")
        self.optbox.add("Arterial Transit Time", NumericOption(minval=0, maxval=2.5, default=self._batdefault, decimals=3), key="bat", checked=True)
        self.optbox.add("T1 (s)", NumericOption(minval=0, maxval=3, default=1.3, decimals=3), key="t1", checked=True)
        self.optbox.add("T1b (s)", NumericOption(minval=0, maxval=3, default=1.65, decimals=3), key="t1b", checked=True)
        self.optbox.add("")
        self.optbox.add("<b>White paper mode</b>  (defaults from Alsop, 2015 consensus paper)")
        self.optbox.add("Enable white paper mode", BoolOption(), key="wp")
        
    def set_wp_mode(self, enabled):
        """
        In white paper mode BAT=0, T1=T1b=1.65 no inference of BAT or ART
        """
        if enabled:
            self.optbox.set_checked("bat", False)
            self.optbox.set_checked("t1", False)
            self.optbox.set_checked("t1b", False)
            
        self.optbox.option("infertau").value = False
        self.optbox.option("inferbat").value = not enabled
        self.optbox.option("infert1").value = False
        self.optbox.option("inferart").value = not enabled
        self.optbox.option("pvcorr").value = False
        self.optbox.option("bat").value = 0 if enabled else 1.3
        self.optbox.option("t1").value = 1.65 if enabled else 1.3
        self.optbox.option("t1b").value = 1.65

    def set_asldata_metadata(self, md):
        """ 
        Set the BAT default to 0.7 for PASL, 1.3 for CASL unless it is already zero
        (which probably means we are in WP mode)
        """
        casl = md.get("casl", True)
        self._batdefault = 1.3 if casl else 0.7
        current = self.optbox.option("bat").value
        self.optbox.option("bat").value = 0 if current == 0 else self._batdefault

class OutputOptions(OxaslOptionWidget):
    """
    OXASL processing options related to output
    """

    def _init_ui(self):
        self.optbox.add("<b>Default outputs</b>")
        self.optbox.add("Prefix for output data names", TextOption(), key="output-prefix", checked=True)
        self.optbox.add("Output in native (ASL) space", BoolOption(default=True), key="output_native")
        self.optbox.add("Output in structural space", BoolOption(), key="output_struc")
        self.optbox.add("Output in standard (MNI) space", BoolOption(), key="output_mni")
        self.optbox.add("")
        self.optbox.add("<b>Additional outputs</b>")
        self.optbox.add("Output parameter variance maps", BoolOption(), key="output_var")
        self.optbox.add("Output mask", BoolOption(default=True), key="save_mask")
        self.optbox.add("Output calibration data", BoolOption(), key="save_calib")
        self.optbox.add("Output corrected input data", BoolOption(), key="save_corrected")
        self.optbox.add("Output registration data", BoolOption(), key="save_reg")
        self.optbox.add("Output structural segmentation", BoolOption(), key="save_struc")
        self.optbox.add("Output model fitting data", BoolOption(), key="save_basil")
        self.optbox.add("")
        self.optbox.add("<b>Summary report</b>")
        self.optbox.add("Save HTML report", FileOption(dirs=True), key="report", checked=True)

class OxaslWidget(QpWidget):
    """
    Widget to do ASL data processing
    """
    def __init__(self, **kwargs):
        QpWidget.__init__(self, name="ASL data processing", icon="asl.png", group="ASL", desc="Complete data processing for ASL data", version=__version__, license=__license__, **kwargs)
        
    def init_ui(self):
        vbox = QtWidgets.QVBoxLayout()
        self.setLayout(vbox)
        
        title = TitleWidget(self, help="asl", subtitle="Data processing for Arterial Spin Labelling MRI")
        vbox.addWidget(title)
              
        cite = Citation(FAB_CITE_TITLE, FAB_CITE_AUTHOR, FAB_CITE_JOURNAL)
        vbox.addWidget(cite)

        self.tabs = QtWidgets.QTabWidget()
        vbox.addWidget(self.tabs)

        self.asldata = AslImageWidget(self.ivm, parent=self)
        self.asldata.sig_changed.connect(self._data_changed)
        self.tabs.addTab(self.asldata, "ASL data")

        self.preproc = PreprocOptions(self.ivm)
        self.preproc.sig_enable_tab.connect(self._enable_tab)
        self.tabs.addTab(self.preproc, "Corrections")

        # Only add these if appropriate
        self._optional_tabs = {
            "veasl" :  VeaslOptions(self.ivm, self.asldata),
            "enable" : EnableOptions(self.ivm),
            "deblur" : DeblurOptions(),
        }

        self.structural = StructuralData(self.ivm)
        self.tabs.addTab(self.structural, "Structural data")

        self.calibration = CalibrationOptions(self.ivm)
        self.tabs.addTab(self.calibration, "Calibration")

        self.analysis = AnalysisOptions(self.ivm)
        self.analysis.optbox.option("wp").sig_changed.connect(self._wp_changed)
        self.tabs.addTab(self.analysis, "Analysis")

        self.output = OutputOptions()
        self.tabs.addTab(self.output, "Output")

        runbox = RunWidget(self, title="Run processing", save_option=True)
        runbox.sig_postrun.connect(self._postrun)
        vbox.addWidget(runbox)
        vbox.addStretch(1)

        fsldir_qwidgets = get_plugins("qwidgets", "FslDirWidget")
        if len(fsldir_qwidgets) > 0:
            fsldir = fsldir_qwidgets[0]()
            vbox.addWidget(fsldir)
            #fsldir.sig_changed.connect(self._fsldir_changed)
            #self._fsldir_changed(fsldir.fsldir)

    def _data_changed(self):
        self._enable_tab("veasl", self.asldata.md["iaf"] == "ve")
        for tab in self._enabled_tabs():
            tab.set_asldata_metadata(self.asldata.md)

    def _enable_tab(self, name, enable):
        widget = self._optional_tabs[name]
        self.tabs.removeTab(self.tabs.indexOf(widget))
        if enable:
            self.tabs.insertTab(self.tabs.indexOf(self.preproc)+1, widget, name.title())

    def _enabled_tabs(self):
        tabs = [self.preproc, self.structural, self.calibration, self.analysis, self.output]
        for tab in self._optional_tabs.values():
            if self.tabs.indexOf(tab) >= 0:
                tabs.append(tab)
        return tabs

    def _options(self):
        options = self.asldata.get_options()
        output = {}

        for tab in self._enabled_tabs():
            options.update(tab.options())
            output.update(tab.output())

        self.debug("oxasl options:")
        for key, value in options.items():
            self.debug("%s (%s): %s" % (key, type(value), value))

        self.debug("oxasl output:")
        for item in output.items():
            self.debug("%s: %s" % item)
        
        if output:
            options["output"] = output

        return options

    def _postrun(self):
        """
        Called after run has finished - some widgets like to display some of the outputs
        """
        tabs = self._enabled_tabs()
        for tab in tabs:
            tab.postrun()

    def _wp_changed(self):
        """
        White paper mode is special and needs to be passed to all widgets so they can
        update defaults accordingly
        """
        for tab in self._enabled_tabs():
            tab.set_wp_mode(self.analysis.optbox.option("wp").value)

    def processes(self):
        """ 
        :return: Specification of process and current options
        """
        return {"Oxasl" : self._options()}
