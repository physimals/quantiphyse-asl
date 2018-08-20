"""
QP-BASIL - Quantiphyse processes for ASL data

These processes use the ``oxasl`` and `fslpyt` python libraries which involves
the following key mappings between Quantiphyse concepts and 
oxasl concepts.

 - ``quantiphyse.data.QpData`` <-> ``fsl.data.image.Image``

Quantiphyse data objects can be transformed to and from ``fslpy`` Image objects.

 - Quantiphyse process options -> oxasl.Workspace

Process options are used to set standard attributes on the ``oxasl.Workspace`` object.
In addition, Quantiphyse options which represent data names are transformed into 
``fsl.data.image.Image`` objects.

 - ``oxasl.AslImage`` <-> ``quantiphyse.data.QpData`` plus ``AslData`` metadata

Additional information stored in the ``oxasl.AslImage`` structure is handled
in quantiphyse using the metadata extensions.

Copyright (c) 2013-2018 University of Oxford
"""

from StringIO import StringIO

from quantiphyse.data import DataGrid, NumpyData
from quantiphyse.utils import get_plugins, QpException
from quantiphyse.utils.batch import Script
from quantiphyse.processes import Process

from .multiphase_template import BIASCORR_MC_YAML, BASIC_YAML, DELETE_TEMP

def qpdata_to_fslimage(qpd):
    """ Convert QpData to fsl.data.image.Image"""
    from oxasl.data.image import Image
    return Image(qpd.raw(), name=qpd.name, xform=qpd.grid.affine)

def fslimage_to_qpdata(img, name=None):
    """ Convert fsl.data.image.Image to QpData """
    if not name: name = img.name
    return NumpyData(img.data, grid=DataGrid(img.shape[:3], img.voxToWorldMat), name=name)

def qpdata_to_aslimage(qpd, options):
    """ Convert QpData to oxasl.AslImage using stored metadata where available """

    # Get already defined structure if there is one. Override it with
    # specified structure options
    struc = qpd.metadata.get("AslData", {})
        
    for opt in ["order", "rpts", "taus", "casl", "tis", "plds", "nphases"]:
        val = options.pop(opt, None)
        if val is not None:
            struc[opt] = val
        else:
            struc.pop(opt, None)

    # Create AslImage object, this will fail if structure information is 
    # insufficient or inconsistent
    from oxasl import AslImage
    asldata = AslImage(qpd.raw(), name=qpd.name,
                       tis=struc.get("tis", None),
                       plds=struc.get("plds", None), 
                       rpts=struc.get("rpts", None), 
                       order=struc.get("order", None),
                       nphases=struc.get("nphases", None))
                    
    # On success, set structure metadata so other widgets/processes can use it
    qpd.metadata["AslData"] = struc
    return asldata

def aslimage_to_qpdata(qpd):
    """ Convert oxasl.AslImage to QpData storing additional information as metadata """
    pass

def workspace_from_options(options):
    """ Create an oxasl.Workspace object from process options """
    pass

class AslProcess(Process):
    """ 
    Base class for processes which use ASL data 
    """

    def __init__(self, ivm, **kwargs):
        super(AslProcess, self).__init__(ivm, **kwargs)
        self.struc = None
        self.asldata = None
        self.grid = None

    def get_asldata(self, options):
        """ 
        Get the main data set and construct an AslData instance from it 
        """
        data = self.get_data(options)

        self.asldata = qpdata_to_aslimage(data, options)
        self.struc = data.metadata["AslData"]
        self.grid = data.grid

class AslDataProcess(AslProcess):
    """
    Process which merely records the structure of an ASL dataset
    """
    PROCESS_NAME = "AslData"

    def run(self, options):
        """ Run the process """
        self.get_asldata(options)

class AslPreprocProcess(AslProcess):
    """
    ASL preprocessing process
    """
    PROCESS_NAME = "AslPreproc"

    def run(self, options):
        """ Run the process """
        from oxasl import AslImage, basil, calib
        from fsl.data.image import Image

        self.get_asldata(options)

        if options.pop("diff", False):
            self.asldata = self.asldata.diff()

        new_order = options.pop("reorder", None)
        if new_order is not None:
            self.asldata = self.asldata.reorder(new_order)

        if options.pop("mean", False):
            self.asldata = self.asldata.mean_across_repeats()
        elif options.pop("pwi", False):
            self.asldata = self.asldata.perf_weighted()

        output_name = options.pop("output-name", self.asldata.name + "_preproc")
        self.ivm.add_data(self.asldata[:], name=output_name, grid=self.grid, make_current=True)

        if isinstance(self.asldata, AslImage):
            new_struc = dict(self.struc)
            for opt in ["rpts", "tis", "taus", "order", "casl", "plds"]:
                if hasattr(self.asldata, opt):
                    new_struc[opt] = getattr(self.asldata, opt)

            self.debug("New structure is")
            self.debug(str(new_struc))
            self.ivm.data[output_name].metadata["AslData"] = new_struc

class BasilProcess(AslProcess):
    """
    Process which runs the multi-step Basil ASL model fitting method
    """
    PROCESS_NAME = "Basil"

    def __init__(self, ivm, **kwargs):
        try:
            self.fabber = get_plugins("processes", class_name="FabberProcess")[0](ivm)
            self.fabber.sig_finished.connect(self._fabber_finished)
            self.fabber.sig_progress.connect(self._fabber_progress)
        except Exception as exc:
            self.warn(str(exc))
            raise QpException("Fabber core library not found.\n\n You must install Fabber to use this widget")

        self.steps = []
        self.step_num = 0
        super(BasilProcess, self).__init__(ivm, **kwargs)

    def run(self, options):
        """ Run the process """
        from oxasl import Workspace, AslImage, basil, calib
        from fsl.data.image import Image
 
        self.get_asldata(options)
        self.asldata = self.asldata.diff().reorder("rt")

        # FIXME Necesssary for pre-processed data and dummy ROI to be in the IVM
        self.ivm.add_data(self.asldata[:], name=self.asldata.name, grid=self.grid)
        roi = self.get_roi(options, self.grid)
        if roi.name not in self.ivm.rois:
            self.ivm.add_roi(roi)

        # Take copy of options and clear out remainder, to avoid 'unconsumed options' 
        # warnings. This does risk genuinely unrecognized options going unnoticed
        # (although there will be warnings in the Fabber log)
        basil_options = dict(options)
        for key in options.keys():
            options.pop(key)

        # Convert image options into fsl.Image objects, also check they exist in the IVM
        # Names and descriptions of options which are images
        images = {
            "t1im": "T1 map", 
            "pwm" : "White matter PV map",
            "pgm" : "Grey matter PV map",
        }
        
        basil_options["mask"] = Image(roi.raw(), name=roi.name)
        for opt in images:
            if opt in basil_options:
                data_name = basil_options.pop(opt)
                data = self.ivm.data.get(data_name, self.ivm.rois.get(data_name, None))
                if data is not None:
                    basil_options[opt] = Image(data.resample(self.grid).raw(), name=data.name)
                else:
                    raise QpException("Data not found: %s" % data_name)

        # Taus are relevant only for CASL labelling
        # Try to use a single value where possible
        if self.struc["casl"]:
            basil_options["casl"] = ""
            taus = self.struc["taus"]
            if min(taus) == max(taus):
                basil_options["tau"] = taus[0]
            else:
                for idx, tau in enumerate(taus):
                    basil_options["tau%i" % (idx+1)] = tau

        # For CASL obtain TI by adding PLD to tau
        for idx, tival in enumerate(self.asldata.tis):
            if self.struc["casl"]:
                tival += taus[idx]
            basil_options["ti%i" % (idx+1)] = tival

        self.debug("Basil options: ")
        self.debug(basil_options)
        logbuf = StringIO()
        wsp = Workspace(log=logbuf, **basil_options)
        self.steps = basil.basil_steps(wsp, self.asldata)

        self.log = logbuf.getvalue()
        self.step_num = 0
        self.status = Process.RUNNING
        self._next_step()

    def cancel(self):
        """ Cancel the underlying fabber process """
        self.fabber.cancel()

    def output_data_items(self):
        """ :return: list of data items output by the process """
        return ["perfusion", "arrival", "aCBV", "duration", "perfusion_std", "arrival_std", "aCBV_std", "duration_std"]
        
    def _next_step(self):
        if self.status != self.RUNNING:
            return
        
        if self.step_num < len(self.steps):
            step = self.steps[self.step_num]
            self.step_num += 1
            self.debug("Basil: starting step %i" % self.step_num)
            self._start_fabber(step)
        else:
            self.debug("Basil: All steps complete")
            self.log += "COMPLETE\n"
            self.status = Process.SUCCEEDED
            self.steps = []
            self.step_num = 0
            if "finalMVN" in self.ivm.data:
                self.ivm.delete_data("finalMVN")
            self.sig_finished.emit(self.status, self.log, self.exception)
            self.ivm.set_current_data("perfusion")

    def _start_fabber(self, step):
        self.sig_step.emit(step.desc)

        options = dict(step.options)
        options["model-group"] = "asl"
        options["data"] = options["data"].name
        options["roi"] = options.pop("mask").name
        if self.step_num == len(self.steps):
            # Final step - save stuff we're interested in
            options["save-mean"] = ""
            options["save-std"] = ""
            options["save-model-fit"] = ""
        else:
            # Just save the MVN so we can continue from it
            options["save-mvn"] = ""

        # Rename output data to match oxford_asl
        options["output-rename"] = {
            "mean_ftiss" : "perfusion",
            "mean_delttiss" : "arrival",
            "mean_fblood" : "aCBV",
            "mean_tau" : "duration",
            "std_ftiss" : "perfusion_std",
            "std_delttiss" : "arrival_std",
            "std_fblood" : "aCBV_std",
            "std_tau" : "duration_std",
        }

        if self.step_num > 1:
            options["continue-from-mvn"] = "finalMVN"

        self.debug("Basil: Fabber options")
        for k in sorted(options.keys()):
            self.debug("%s=%s (%s)" % (k, str(options[k]), type(options[k])))

        self.log += step.desc + "\n\n"
        self.fabber.execute(options)

    def _fabber_finished(self, status, log, exception):
        if self.status != self.RUNNING:
            return

        self.log += log + "\n\n"
        if status == Process.SUCCEEDED:
            self.debug("Basil: completed step %i" % self.step_num)
            self._next_step()
        else:
            self.debug("Basil: Fabber failed on step %i" % self.step_num)
            self.log += "CANCELLED\n"
            self.status = status
            self.sig_finished.emit(self.status, self.log, exception)
            
    def _fabber_progress(self, complete):
        self.debug("Basil: Fabber progress: %f", complete)
        if self.status == self.RUNNING:
            # emit sig_progress scaling by number of steps
            self.sig_progress.emit((self.step_num - 1 + complete)/len(self.steps))

class AslMultiphaseProcess(Script):
    """
    Process for carrying out multiphase pre-process modelling
    """

    PROCESS_NAME = "AslMultiphase"

    def __init__(self, ivm, **kwargs):
        Script.__init__(self, ivm, **kwargs)
        self._orig_roi = None

    def run(self, options):
        """ Run the process"""
        data = self.get_data(options)
        
        if options.pop("biascorr", True):
            template = BIASCORR_MC_YAML
            if not options.pop("keep-temp", False):
                template += DELETE_TEMP
        else:
            template = BASIC_YAML

        self._orig_roi = options.pop("roi", None)
        template_params = {
            "data" : data.name,
            "roi" : self._orig_roi,
            "nph" : options.pop("nphases"),
            "sigma" : options.pop("sigma", 0),
            "n_supervoxels" : options.pop("n-supervoxels", 8),
            "compactness" : options.pop("compactness", 0.01),
        }
        
        options["yaml"] = template % template_params
        Script.run(self, options)

    def finished(self):
        """ Called when process finishes """
        self.ivm.set_current_roi(self._orig_roi)
        self.ivm.set_current_data("mean_mag")

class AslCalibProcess(Process):
    """
    ASL calibration process
    """
    PROCESS_NAME = "AslCalib"

    def run(self, options):
        """ Run the process """
        from oxasl import Workspace, calib
        from fsl.data.image import Image

        data = self.get_data(options)
        img = Image(data.raw(), name=data.name)

        roi = self.get_roi(options, data.grid)
        options["mask"] = Image(roi.raw(), name=roi.name)

        calib_name = options.pop("calib-data")
        if calib_name not in self.ivm.data:
            raise QpException("Calibration data not found: %s" % calib_name)
        else:
            calib_img = Image(self.ivm.data[calib_name].resample(data.grid).raw(), name=calib_name)

        ref_roi_name = options.pop("ref-roi", None)
        if ref_roi_name is not None:
            if ref_roi_name not in self.ivm.rois:
                raise QpException("Reference ROI not found: %s" % calib_name)
            else:
                options["ref_mask"] = Image(self.ivm.rois[ref_roi_name].resample(data.grid).raw(), name=ref_roi_name)
        
        options["calib_method"] = options.pop("method", None)
        output_name = options.pop("output-name", data.name + "_calib")

        logbuf = StringIO()
        wsp = Workspace(log=logbuf, **options)
        wsp.calib = calib_img
        ## FIXME variance mode
        calibrated = calib.calibrate(wsp, img)
        self.log = logbuf.getvalue()
        self.ivm.add_data(name=output_name, data=calibrated.data, grid=data.grid, make_current=True)
        
