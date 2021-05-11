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

 - ``oxasl.AslImage`` <-> ``quantiphyse.data.QpData`` with ``AslData`` metadata

Additional information stored in the ``oxasl.AslImage`` structure is handled
in quantiphyse using the metadata extensions.

Copyright (c) 2013-2018 University of Oxford
"""
import sys
import traceback
import tempfile
import shutil
import os
import glob

import six
import pandas as pd

from quantiphyse.data import DataGrid, NumpyData, QpData, load
from quantiphyse.data.extras import MatrixExtra, DataFrameExtra
from quantiphyse.utils import get_plugins, QpException, load_matrix
from quantiphyse.utils.batch import Script
from quantiphyse.processes import Process
from quantiphyse.utils.cmdline import OutputStreamMonitor, LogProcess

from .multiphase_template import BIASCORR_MC_YAML, BASIC_YAML, DELETE_TEMP

METADATA_ATTRS = ["iaf", "ibf", "order", "tis", "plds", "rpts", "taus", "tau", "bolus", "casl", "nphases", "nenc", "slicedt", "sliceband"]

def qpdata_to_fslimage(qpd, grid=None):
    """ 
    Convert QpData to fsl.data.image.Image
    """
    from fsl.data.image import Image
    if grid is None:
        return Image(qpd.raw(), name=qpd.name, xform=qpd.grid.affine)
    else:
        return Image(qpd.resample(grid), name=qpd.name, xform=grid.affine)
        
def fslimage_to_qpdata(img, name=None):
    """ Convert fsl.data.image.Image to QpData """
    if not name: name = img.name
    return NumpyData(img.data, grid=DataGrid(img.shape[:3], img.voxToWorldMat), name=name)

def qpdata_to_aslimage(qpd, options=None, metadata=None, grid=None):
    """ 
    Convert QpData to oxasl.AslImage using stored metadata where available 
    """

    # If metadata is not provided, get the existing metadata
    if metadata is None:
        metadata = qpd.metadata.get("AslData", {})
    
    # If options are provided, use them to override existing metadata
    if options:
        for opt in METADATA_ATTRS:
            val = options.pop(opt, None)
            if val is not None:
                metadata[opt] = val
            else:
                metadata.pop(opt, None)

    # Create AslImage object, this will fail if metadat is insufficient or inconsistent
    from oxasl import AslImage
    if grid is None:
        aslimage = AslImage(qpd.raw(), name=qpd.name, xform=qpd.grid.affine, **metadata)
    else:
        aslimage = AslImage(qpd.resample(grid), name=qpd.name, xform=grid.affine, **metadata)
                    
    return aslimage, metadata

def aslimage_to_metadata(aslimage):
    """
    Get metadata from an AslImage

    :return: Metadata as a dictionary
    """
    metadata = {}
    for opt in METADATA_ATTRS:
        if opt == "tis" and aslimage.have_plds:
            # Write PLDs only for PLD data sets
            continue
        if hasattr(aslimage, opt):
            val = getattr(aslimage, opt)
            if val is not None:
                metadata[opt] = val
    return metadata

def aslimage_to_qpdata(aslimage):
    """ 
    Convert oxasl.AslImage to QpData storing additional information as metadata 
    """
    qpd = fslimage_to_qpdata(aslimage)
    metadata = aslimage_to_metadata(aslimage)
    qpd.metadata["AslData"] = metadata
    return qpd

def workspace_from_options(options, images, grid, ivm):
    """ 
    Create an oxasl.Workspace object from process options 
    """
    from oxasl import Workspace
    wsp = Workspace(log=six.StringIO(), **options)

    for key in images:
        if key in options:
            data_name = options[key]
            data = ivm.data.get(data_name, None)
            if data is not None:
                setattr(wsp, key, qpdata_to_fslimage(data, grid=grid))
            else:
                raise QpException("Data not found: %s" % data_name)

    # Clear out options otherwise they will generate warnings. 
    # We have to hope that the process will warn us about unused options
    for key in options.keys():
        options.pop(key)

    return wsp

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
        self.data = self.get_data(options)
        self.asldata, self.struc = qpdata_to_aslimage(self.data, options)
        # Set the metadata on the data
        self.data.metadata["AslData"] = self.struc
        self.grid = self.data.grid

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
        """ 
        Run preprocessing steps and add the output to the IVM
        """
        from oxasl import AslImage

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

        if isinstance(self.asldata, AslImage):
            qpd = aslimage_to_qpdata(self.asldata)
        else:
            qpd = fslimage_to_qpdata(self.asldata)

        output_name = options.pop("output-name", self.asldata.name + "_preproc")
        self.ivm.add(qpd, name=output_name, make_current=True)

class BasilProcess(AslProcess):
    """
    Process which runs the multi-step Basil ASL model fitting method
    """
    PROCESS_NAME = "Basil"

    OUTPUT_RENAME = {
        "mean_ftiss" : "perfusion",
        "mean_delttiss" : "arrival",
        "mean_fblood" : "aCBV",
        "mean_tau" : "duration",
        "std_ftiss" : "perfusion_std",
        "std_delttiss" : "arrival_std",
        "std_fblood" : "aCBV_std",
        "std_tau" : "duration_std",
    }

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
        from oxasl import basil
 
        self.get_asldata(options)
        self.asldata = self.asldata.diff().reorder("rt")
        self.ivm.add(self.asldata.data, grid=self.grid, name=self.asldata.name)
        roi = self.get_roi(options, self.grid)
        if roi.name not in self.ivm.rois:
            self.ivm.add(roi)

        self.debug("Basil options: ")
        self.debug(options)

        wsp = workspace_from_options(options, images=["t1im", "pwm", "pgm"], grid=self.grid, ivm=self.ivm)
        wsp.asldata = self.asldata
        wsp.mask = qpdata_to_fslimage(roi)

        self.steps = basil.basil_steps(wsp, self.asldata)
        self.log(wsp.log.getvalue())
        self.step_num = 0
        self.status = Process.RUNNING
        self._next_step()

    def cancel(self):
        """ Cancel the underlying fabber process """
        self.fabber.cancel()

    def output_data_items(self):
        """ :return: list of data items output by the process """
        return self.OUTPUT_RENAME.values()
        
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
            self.log("COMPLETE\n")
            self.status = Process.SUCCEEDED
            self.steps = []
            self.step_num = 0
            if "finalMVN" in self.ivm.data:
                self.ivm.delete("finalMVN")
            self.sig_finished.emit(self.status, self.get_log(), self.exception)
            self.ivm.set_current_data("perfusion")

    #def fabber(options, output=LOAD, ref_nii=None, progress=None, **kwargs):
    def _start_fabber(self, step):
        from fsl.data.image import Image
        self.sig_step.emit(step.desc)

        options = dict(step.options)
        options["model-group"] = "asl"
        for key in options.keys():
            val = options[key]
            if isinstance(val, Image):
                if key == "mask":
                    options["roi"] = val.name
                    options.pop(key)
                else:
                    options[key] = val.name
        
        if self.step_num == len(self.steps):
            # Final step - save stuff we're interested in
            options["save-mean"] = True
            options["save-std"] = True
            options["save-model-fit"] = True
        else:
            # Just save the MVN so we can continue from it
            options["save-mvn"] = True

        # Rename output data to match oxford_asl
        options["output-rename"] = self.OUTPUT_RENAME

        if self.step_num > 1:
            options["continue-from-mvn"] = "finalMVN"

        self.debug("Basil: Fabber options")
        for k in sorted(options.keys()):
            self.debug("%s=%s (%s)" % (k, str(options[k]), type(options[k])))

        self.log(step.desc + "\n\n")
        self.fabber.execute(options)

    def _fabber_finished(self, status, log, exception):
        if self.status != self.RUNNING:
            return

        self.log(log + "\n\n")
        if status == Process.SUCCEEDED:
            self.debug("Basil: completed step %i" % self.step_num)
            self._next_step()
        else:
            self.debug("Basil: Fabber failed on step %i" % self.step_num)
            self.log("CANCELLED\n")
            self.status = status
            self.sig_finished.emit(self.status, self.get_log(), exception)
            
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

        self._orig_roi = options.pop("roi", "")
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

    def finished(self, _):
        """ Called when process finishes """
        if self._orig_roi:
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

        logbuf = six.StringIO()
        wsp = Workspace(log=logbuf, **options)
        wsp.calib = calib_img
        ## FIXME variance mode
        calibrated = calib.calibrate(wsp, img)
        self.log(logbuf.getvalue())
        self.ivm.add(name=output_name, data=calibrated.data, grid=data.grid, make_current=True)

def qp_oxasl(worker_id, queue, fsldir, fsldevdir, asldata, options):
    """
    Worker function for asynchronous oxasl run

    Note that images are passed as QpData because it's pickleable
    but need to be converted to fsl.data.image.Image
    """
    try:
        from oxasl import Workspace
        from oxasl.oxford_asl import oxasl
        options["fabber_dirs"] = get_plugins("fabber-dirs")

        if "FSLOUTPUTTYPE" not in os.environ:
            os.environ["FSLOUTPUTTYPE"] = "NIFTI_GZ"
        if fsldir:
            os.environ["FSLDIR"] = fsldir
        if fsldevdir:
            os.environ["FSLDEVDIR"] = fsldevdir

        for key, value in options.items():
            if isinstance(value, QpData):
                options[key] = qpdata_to_fslimage(value)
        options["asldata"], _ = qpdata_to_aslimage(asldata)

        output_monitor = OutputStreamMonitor(queue)
        wsp = Workspace(log=output_monitor, **options)
        oxasl(wsp)

        return worker_id, True, {}
    except:
        traceback.print_exc()
        return worker_id, False, sys.exc_info()[1]

class OxaslProcess(LogProcess):
    """
    Process which runs the Python version of oxford_asl
    """
    PROCESS_NAME = "Oxasl"

    IMAGE_OPTIONS = [
        "struc", "calib", "cref", "cblip", "infer_mask",
        "fmap", "fmapmag", "fmapmagbrain", "gm_roi", "noise_roi",
        "wmseg", "gmseg", "csfseg", "refmask"
    ]

    def __init__(self, ivm, **kwargs):
        LogProcess.__init__(self, ivm, worker_fn=qp_oxasl, **kwargs)
        self._expected_output = {}
        self._tempdir = None
        self._output_data_items = []

    def _get_asldata(self, options):
        data = self.get_data(options)
        asldata, md = qpdata_to_aslimage(data, options)
        data.metadata["AslData"] = md
        return data

    def run(self, options):
        """
        Run oxasl pipeline asynchronously
        """
        self.data = self._get_asldata(options)

        # Create a temporary directory to store working data - this makes it
        # easy to retrieve afterwards and reduces memory usage. Note that
        # this is deleted in the `finished` method which is guaranteed to
        # be called.
        self._tempdir = tempfile.mkdtemp("qp_oxasl")

        # Set up basic options
        self._reportdir = options.pop("report", None)
        self._expected_output = options.pop("output", {})
        self._output_prefix = options.pop("output-prefix", "")
        self._pvcorr = options.get("pvcorr", False)

        oxasl_options = {
            "debug" : self.debug_enabled(),
            "savedir" : self._tempdir,
            "save_report" : self._reportdir is not None,
        }
        if "roi" in options:
            oxasl_options["mask"] = self.get_roi(options, self.data.grid)

        # For options which are images set the value to the actual QpData object
        #
        # FIXME this is not great... We are assuming we know what 
        # options are actually images. Could the widgets themselves tell us?
        for key in list(options.keys()):
            if key in self.IMAGE_OPTIONS:
                data_name = options.pop(key)
                if data_name:
                    oxasl_options[key] = self.ivm.data[data_name]

        # Copy all other options are remove them from the dictionary
        # to avoid any warnings about unused options
        for key in list(options.keys()):
            value = options.pop(key)
            if value is not None:
                oxasl_options[key] = value
                
        self.expected_steps = [
            ("Pre-processing", "Pre-processing"),
            #("Registering", "Initial ASL->Structural registration"),
            (".*initial fit", "Initial model fitting"),
            (".*fit on full", "Model fitting to full data"),    
            #("segmentation", "Segmenting structural image"),
            #("BBR registration", "Final ASL->Structural registration"),
        ]
        self.current_step = 0
        # Pass FSLDIR and FSLDEVDIR to the process as it will not necessarily
        # inherit the environment and these might be configured by the user
        fsldir, fsldevdir = None, None
        if "FSLDIR" in os.environ:
            fsldir = os.environ["FSLDIR"]
        if "FSLDEVDIR" in os.environ:
            fsldevdir = os.environ["FSLDEVDIR"]
        self._output_data_items = []
        self.start_bg([fsldir, fsldevdir, self.data, oxasl_options])

    def finished(self, worker_output):
        try:
            self.debug("OXASL finished\n")
            self.debug("Expected output: %s", self._expected_output)

            # Load expected output
            for name, path in self._expected_output.items():
                self._load_expected_output(self._tempdir, path, name)

            # Load 'default' output
            if self._pvcorr:
                self._load_default_output(os.path.join(self._tempdir, "output_pvcorr"))
            else:
                self._load_default_output(os.path.join(self._tempdir, "output"))
            self._load_default_output(os.path.join(self._tempdir, "corrected"), suffix="_corr")
            self._load_default_output(os.path.join(self._tempdir, "structural"), suffix="_struc")
            self._load_default_output(os.path.join(self._tempdir, "calibration"), suffix="_calib")
            self._load_default_output(os.path.join(self._tempdir, "basil"), suffix="_fitting")
            self._load_default_output(os.path.join(self._tempdir, "reg"), suffix="_reg")

            # Copy report and open if required
            if self._reportdir:
                input_dir = os.path.join(self._tempdir, "report")
                output_dir = os.path.abspath(os.path.join(self._reportdir, "oxasl_report"))
                if os.path.exists(input_dir):
                    if os.path.exists(output_dir):
                        if os.path.isdir(output_dir):
                            shutil.rmtree(output_dir)
                        else:
                            os.remove(output_dir)
                    shutil.copytree(input_dir, output_dir)
                    indexurl = "file://" + os.path.join(output_dir, "index.html")

                    import webbrowser
                    webbrowser.open(indexurl, new=0, autoraise=True)
                else:
                    self.warn("HTML report was requested but sphinx was not available")
        finally:
            if self._tempdir:
                if not self.debug_enabled():
                    shutil.rmtree(self._tempdir)
                else:
                    self.warn("Debug mode enabled - temporary output is in %s" % self._tempdir)
                self.tempdir = None

    def output_data_items(self):
        return self._output_data_items

    def _load_expected_output(self, outdir, path, name):
        path = os.path.join(outdir, path + ".*")
        self.debug("Looking for item: %s", path)
        matches = glob.glob(path)
        for fname in matches:
            self.debug("Found: %s", fname)
            # FIXME could be roi?
            self._load(fname, name)

    def _load_default_output(self, outdir, suffix=""):
        """ 
        Recursively load output images into the IVM. 
        """
        self.debug("output from: %s", outdir)
        files = glob.glob(os.path.join(outdir, "*"))
        for fname in files:
            self.debug("found %s", fname)
            name = os.path.basename(fname).split(".", 1)[0]
            if os.path.isdir(fname):
                self._load_default_output(fname, suffix + "_" + name)
            else:
                is_roi = "mask" in name
                self.debug("trying to load %s", fname)
                self._load(fname, name + suffix, is_roi)

    def _load(self, fname, name, is_roi=False):
        try:
            extension = ""
            parts = fname.split(".", 1)
            if len(parts) > 1: 
                extension = parts[1]
            self.debug("Loading: %s (%s)", fname, extension)
            if extension == 'mat':
                mat, _rows, _cols = load_matrix(fname)
                extra = MatrixExtra(name, mat)
                self.ivm.add_extra(name, extra)
            elif extension == 'csv':
                df = pd.read_csv(fname)
                extra = DataFrameExtra(name, df)
                self.ivm.add_extra(name, extra)
            elif extension in ('nii', 'nii.gz'):
                self.debug("Nifti data")
                qpdata = load(fname)
                # Remember this is from a temporary file so need to copy the actual data
                qpdata = NumpyData(qpdata.raw(), grid=qpdata.grid, name=self._output_prefix + name, roi=is_roi)
                self._output_data_items.append(name)
                self.ivm.add(qpdata)
        except:
            self.warn("Failed to load: %s", fname)
            traceback.print_exc()
