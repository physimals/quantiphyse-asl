"""
QP-BASIL - Quantiphyse processes for ASL data

Copyright (c) 2013-2018 University of Oxford
"""

import time
from StringIO import StringIO

import yaml

from quantiphyse.utils import warn, debug, get_plugins, QpException
from quantiphyse.utils.batch import Script, BatchScriptCase
from quantiphyse.processes import Process

from .oxasl import AslImage, fsl, basil, calib

USE_CMDLINE = False

class AslProcess(Process):
    """ 
    Base class for processes which use ASL data 
    """

    def __init__(self, ivm, **kwargs):
        super(AslProcess, self).__init__(ivm, **kwargs)
        self.default_struc = {"order" : "prt", "tis" : [1.5,], "taus" : [1.4,], "casl" : True}
        self.struc = None
        self.asldata = None

    def get_asldata(self, options):
        """ 
        Get the main data set and construct an AslData instance from it 
        """
        data = self.get_data(options)

        # Get already defined structure if there is one. Override it with
        # specified structure options
        struc_str = self.ivm.extras.get("ASL_STRUCTURE_" + data.name, None)
        if struc_str is not None:
            self.struc = yaml.load(struc_str)
        else:
            self.struc = {}
            
        for opt in ["order", "rpts", "taus", "casl", "tis", "plds", "nphases"]:
            v = options.pop(opt, None)
            if v is not None:
                self.struc[opt] = v
            else:
                self.struc.pop(opt, None)

        # Create AslImage object, this will fail if structure information is 
        # insufficient or inconsistent
        data = self.ivm.data[data.name]
        self.asldata = AslImage(data.name, data=data.raw(),
                                tis=self.struc.get("tis", None),
                                plds=self.struc.get("plds", None), 
                                rpts=self.struc.get("rpts", None), 
                                order=self.struc.get("order", None),
                                nphases=self.struc.get("nphases", None))
        self.grid = data.grid
                       
        # On success, set structure metadata so other widgets/processes can use it
        struc_str = yaml.dump(self.struc)
        self.ivm.add_extra("ASL_STRUCTURE_" + data.name, struc_str)

class AslDataProcess(AslProcess):
    """
    Process which merely records the structure of an ASL dataset
    """
    PROCESS_NAME = "AslData"

    def run(self, options):
        self.get_asldata(options)

class AslPreprocProcess(AslProcess):
    """
    ASL preprocessing process
    """
    PROCESS_NAME = "AslPreproc"

    def run(self, options):
        self.get_asldata(options)

        if options.pop("diff", False):
            self.asldata = self.asldata.diff()

        new_order = options.pop("reorder", None)
        if new_order is not None:
            self.asldata = self.asldata.reorder(new_order)

        if options.pop("mean", False):
            self.asldata = self.asldata.mean_across_repeats()

        output_name = options.pop("output-name", self.asldata.iname + "_preproc")
        self.ivm.add_data(self.asldata.data(), name=output_name, grid=self.grid, make_current=True)
        new_struc = dict(self.struc)
        for opt in ["rpts", "tis", "taus", "order", "casl", "plds"]:
            if hasattr(self.asldata, opt):
                new_struc[opt] = getattr(self.asldata, opt)

        debug("New structure is")
        debug(str(new_struc))
        struc_str = yaml.dump(new_struc)
        self.ivm.add_extra("ASL_STRUCTURE_" + output_name, struc_str)

class BasilProcess(AslProcess):
    """
    """
    PROCESS_NAME = "Basil"

    def __init__(self, ivm, **kwargs):
        try:
            self.fabber = get_plugins("processes", class_name="FabberProcess")[0](ivm)
            self.fabber.sig_finished.connect(self._fabber_finished)
            self.fabber.sig_progress.connect(self._fabber_progress)
        except Exception, e:
            warn(str(e))
            raise QpException("Fabber core library not found.\n\n You must install Fabber to use this widget")

        self.steps = []
        self.step_num = 0
        super(BasilProcess, self).__init__(ivm, **kwargs)

    def run(self, options):
        self.get_asldata(options)
        self.asldata = self.asldata.diff().reorder("rt")
        roi = self.get_roi(options, self.grid)
        if roi.name not in self.ivm.rois:
            # FIXME Necesssary for dummy ROI to be in the IVM
            self.ivm.add_roi(roi)

        # FIXME temporary
        self.ivm.add_data(self.asldata.data(), name=self.asldata.iname, grid=self.grid)
        
        # Convert image options into fsl.Image objects, als check they exist in the IVM
        # Names and descriptions of options which are images
        images = {
            "t1im": "T1 map", 
            "pwm" : "White matter PV map", 
            "pgm" : "Grey matter PV map",
        }
        options["asldata"] = self.asldata
        options["mask"] = fsl.Image(roi.name, data=roi.raw(), role="Mask")
        for opt, role in images.items():
            if opt in options:
                data = self.ivm.data.get(options[opt], self.ivm.rois.get(options[opt], None))
                if data is not None:
                    options[opt] = fsl.Image(data.name, data=data.resample(self.grid).raw(), role=role)
                    #options[opt] = data.resample(self.grid).raw()
                else:
                    raise QpException("Data not found: %s" % options[opt])

        # Taus are relevant only for CASL labelling
        # Try to use a single value where possible
        if self.struc["casl"]:
            options["casl"] = ""
            taus = self.struc["taus"]
            if min(taus) == max(taus):
                options["tau"] = taus[0]
            else:
                for idx, tau in enumerate(taus):
                    options["tau%i" % (idx+1)] = tau

        # For CASL obtain TI by adding PLD to tau
        for idx, ti in enumerate(self.asldata.tis):
            if self.struc["casl"]:
                ti += taus[idx]
            options["ti%i" % (idx+1)] = ti

        debug("Basil options: ")
        debug(options)
        logbuf = StringIO()
        self.steps = basil.get_steps(log=logbuf, **options)
        self.log = logbuf.getvalue()
        self.step_num = 0
        self.status = Process.RUNNING
        self._next_step()

    def cancel(self):
        self.fabber.cancel()
        
    def _next_step(self):
        if self.status != self.RUNNING:
            return
        
        if self.step_num < len(self.steps):
            step = self.steps[self.step_num]
            self.step_num += 1
            debug("Basil: starting step %i" % self.step_num)
            self._start_fabber(*step)
        else:
            debug("Basil: All steps complete")
            self.log += "COMPLETE\n"
            self.status = Process.SUCCEEDED
            self.steps = []
            self.step_num = 0
            if "finalMVN" in self.ivm.data:
                self.ivm.delete_data("finalMVN")
            self.sig_finished.emit(self.status, self.log, self.exception)
            self.ivm.set_current_data("perfusion")

    def _start_fabber(self, step, step_desc, infile, mask, options, prev_step=None):
        self.sig_step.emit(step_desc)

        options = dict(options)
        options["model-group"] = "asl"
        options["data"] = infile.iname
        options["roi"] = mask.iname
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

        if prev_step is not None:
            step_desc += " - init with STEP %i" % prev_step
            options["continue-from-mvn"] = "finalMVN"

        debug("Basil: Fabber options")
        for k in sorted(options.keys()):
            debug("%s=%s (%s)" % (k, str(options[k]), type(options[k])))

        self.log += step_desc + "\n\n"
        self.fabber.execute(options)

    def _fabber_finished(self, status, log, exception):
        if self.status != self.RUNNING:
            return

        self.log += log + "\n\n"
        if status == Process.SUCCEEDED:
            debug("Basil: completed step %i" % self.step_num)
            self._next_step()
        else:
            debug("Basil: Fabber failed on step %i" % self.step_num)
            self.log += "CANCELLED\n"
            self.status = status
            self.sig_finished.emit(self.status, self.log, exception)
            
    def _fabber_progress(self, complete):
        debug("Basil: Fabber progress: %f", complete)
        if self.status == self.RUNNING:
            # emit sig_progress scaling by number of steps
            self.sig_progress.emit((self.step_num - 1 + complete)/len(self.steps))
        
class MacroProcess(Process):

    def __init__(self, ivm, yaml_code=None, **kwargs):
        super(MacroProcess, self).__init__(ivm, **kwargs)
        if yaml_code is not None:
            self.set_script(yaml_code)

    def set_script(self, yaml_code):
        self.script = Script(ivm=self.ivm, code=yaml_code)
        self.script.sig_start_process.connect(self._start_process)
        self.script.sig_done_process.connect(self._done_process)
        self.script.sig_progress.connect(self._progress)
        self.script.sig_finished.connect(self._done_script)

    def run(self, _):
        self.status = Process.RUNNING
        self.script.run()

    def cancel(self):
        self.script.cancel()
        
    def _start_process(self, process, params):
        self.start = time.time()
        self.log += "Running %s\n\n" % process.proc_id
        for key, value in params.items():
            debug("      %s=%s" % (key, str(value)))
                
    def _done_process(self, process, _):
        self.log += process.log
        end = time.time()

        if process.status == Process.SUCCEEDED:
            self.log += "\nDONE (%.1fs)\n" % (end - self.start)
        else:
            self.log += "\nFAILED: %i\n" % process.status
            self.status = process.status
            self.exception = process.exception
            self.sig_finished.emit(self.status, self.log, self.exception)

    def _progress(self, complete):
        debug("Progress: %f", complete)
        if self.status == self.RUNNING:
            # emit sig_progress scaling by number of steps
            self.sig_progress.emit(complete)

    def _done_script(self, status, log, exception):
        if self.status == Process.RUNNING:
            self.log += "Script finished\n"
            self.status = Process.SUCCEEDED
            self.sig_finished.emit(self.status, self.log, self.exception)
        
from .multiphase_template import BIASCORR_MC_YAML, BASIC_YAML, DELETE_TEMP

class AslMultiphaseProcess(MacroProcess):

    PROCESS_NAME = "AslMultiphase"

    def __init__(self, ivm, **kwargs):
        MacroProcess.__init__(self, ivm, BIASCORR_MC_YAML, **kwargs)

    def run(self, options):
        data = self.get_data(options)
        
        biascorr = options.pop("biascorr", True)
        if biascorr:
            template = BIASCORR_MC_YAML
            if not options.pop("keep-temp", False):
                template += DELETE_TEMP
            self.set_script(template)
        else:
            self.set_script(BASIC_YAML)

        roi = options.pop("roi", None)
        nphases = options.pop("nphases")
        case_params = {
            "Fabber" : {
                "data" : data.name,
                "roi" : roi,
                "nph" : nphases,
            },
            "Supervoxels" : {
                "roi" : roi,
                "sigma" : options.pop("sigma", 0),
                "n-supervoxels" : options.pop("n-supervoxels", 8),
                "compactness" : options.pop("compactness", 0.01),
            },
            "MeanValues_MCCORR" : {
                "data" : data.name,
            },
            "Fabber_MCCORR" : {
                "roi" : roi,
                "nph" : nphases,
            },
        }
        case = BatchScriptCase("MultiphaseCase", case_params)
        self.script.cases = [case, ]
        self.status = Process.RUNNING
        self.script.run()

class AslCalibProcess(Process):
    """
    ASL calibration process
    """
    PROCESS_NAME = "AslCalib"

    def run(self, options):
        data = self.get_data(options)
        img = fsl.Image(data.name, data=data.raw())

        roi = self.get_roi(options, data.grid)
        roi_img = fsl.Image(roi.name, data=roi.raw())

        calib_name = options.pop("calib-data")
        if calib_name not in self.ivm.data:
            raise QpException("Calibration data not found: %s" % calib_name)
        else:
            calib_img = fsl.Image(calib_name, data=self.ivm.data[calib_name].resample(data.grid).raw())

        ref_roi_name = options.pop("ref-roi", None)
        if ref_roi_name is not None:
            if ref_roi_name not in self.ivm.rois:
                raise QpException("Reference ROI not found: %s" % calib_name)
            else:
                ref_roi_img = fsl.Image(ref_roi_name, data=self.ivm.rois[ref_roi_name].resample(data.grid).raw())
        else:
            ref_roi_img = None

        method = options.pop("method", None)
        output_name = options.pop("output-name", data.name + "_calib")

        logbuf = StringIO()
        calibrated = calib(img, calib_img, method, output_name=output_name, brain_mask=roi_img, ref_mask=ref_roi_img, log=logbuf, **options)
        self.log = logbuf.getvalue()
        self.ivm.add_data(name=calibrated.iname, data=calibrated.data(), grid=data.grid, make_current=True)
        