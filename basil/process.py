"""
QP-BASIL - Quantiphyse processes for ASL data

Copyright (c) 2013-2018 University of Oxford
"""

import yaml

from quantiphyse.utils import warn, debug, get_plugins
from quantiphyse.utils.exceptions import QpException

from quantiphyse.analysis import BackgroundProcess, Process

from .asl.image import AslImage

USE_CMDLINE = False

class AslProcess(Process):
    """ Base class for processes which use ASL data """

    def __init__(self, ivm, **kwargs):
        super(AslProcess, self).__init__(ivm, **kwargs)
        self.default_struc = {"order" : "prt", "tis" : [1.5,], "taus" : [1.4,], "casl" : True}
        self.struc = None
        self.asldata = None

    def get_asldata(self, options):
        """ Get the data structure and construct an AslData instance from it """
        data_name = options.pop("data", None)
        if data_name is None:
            if self.ivm.main is None:
                raise QpException("No data loaded")
            else:
                data_name = self.ivm.main.name

        if data_name not in self.ivm.data:
            raise QpException("Data not found: %s" % data_name)

        # Get already defined structure if there is one. Override it with
        # specified structure options
        struc_str = self.ivm.extras.get("ASL_STRUCTURE_" + data_name, None)
        if struc_str is not None:
            self.struc = yaml.load(struc_str)
        else:
            self.struc = {}
            
        for opt in ["rpts", "tis", "taus", "order", "casl", "plds"]:
            v = options.pop(opt, None)
            if v is not None:
                self.struc[opt] = v
            else:
                self.struc.pop(opt, None)

        # Create AslImage object, this will fail if structure information is 
        # insufficient or inconsistent
        data = self.ivm.data[data_name]
        self.asldata = AslImage(data.name, data=data.std(),
                                tis=self.struc.get("tis", self.struc.get("plds", None)), 
                                rpts=self.struc.get("rpts", None), 
                                order=self.struc.get("order", None))
                       
        # On success, set structure metadata so other widgets/processes can use it
        struc_str = yaml.dump(self.struc)
        self.ivm.add_extra("ASL_STRUCTURE_" + data_name, struc_str)

class AslDataProcess(AslProcess):
    """
    Process which merely records the structure of an ASL dataset
    """
    PROCESS_NAME = "AslData"

    def run(self, options):
        self.get_asldata(options)
        self.status = Process.SUCCEEDED

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
        self.ivm.add_data(self.asldata.data(), name=output_name)
        new_struc = dict(self.struc)
        for opt in ["rpts", "tis", "taus", "order", "casl", "plds"]:
            if hasattr(self.asldata, opt):
                new_struc[opt] = getattr(self.asldata, opt)

        debug("New structure is")
        debug(str(new_struc))
        struc_str = yaml.dump(self.struc)
        self.ivm.add_extra("ASL_STRUCTURE_" + output_name, struc_str)

        self.status = Process.SUCCEEDED

class BasilProcess(BackgroundProcess, AslProcess):
    """
    Currently a direct wrapper around the Fabber process. We would like to subclass
    it but this is not straightforward because the Fabber process class is loaded
    from a plugin.
    """
    def __init__(self, ivm, **kwargs):
        try:
            self.fabber = get_plugins("processes", class_name="FabberProcess")[0](ivm)
        except Exception, e:
            warn(str(e))
            raise QpException("Fabber core library not found.\n\n You must install Fabber to use this widget")

        kwargs["fn"] = self.fabber.fn
        super(BasilProcess, self).__init__(ivm, **kwargs)
        #AslProcess.__init__(self, ivm, self.fabber.fn, **kwargs)
        #BackgroundProcess.__init__(self, ivm, self.fabber.fn, **kwargs)

    def run(self, options):
        self.get_asldata(options)

        self.asldata = self.asldata.diff().reorder("rt")
        self.ivm.add_data(self.asldata.data(), name=self.asldata.iname)
        options["data"] = self.asldata.iname

        # Taus are relevant only for CASL labelling
        # For taus/repeats try to use a single value where possible
        if self.struc["casl"]:
            options["casl"] = ""
            taus = self.struc["taus"]
            if min(taus) == max(taus):
                options["tau"] = str(taus[0])
            else:
                for idx, tau in enumerate(taus):
                    options["tau%i" % (idx+1)] = str(tau)
        
        if min(self.asldata.rpts) == max(self.asldata.rpts):
            options["repeats"] = str(self.asldata.rpts[0])
        else:
            for idx, rpt in enumerate(self.asldata.rpts):
                options["rpt%i" % (idx+1)] = str(rpt)

        # For CASL obtain TI by adding PLD to tau
        for idx, ti in enumerate(self.asldata.tis):
            if self.struc["casl"]:
                ti += taus[idx]
            options["ti%i" % (idx+1)] = str(ti)

        # Rename output data to match oxford_asl
        options["output-rename"] = {
            "mean_ftiss" : "perfusion",
            "mean_deltiss" : "arrival",
            "mean_fblood" : "aCBV",
            "std_ftiss" : "perfusion_std",
            "std_deltiss" : "arrival_std",
            "std_fblood" : "aCBV_std",
        }
        self.fabber.sig_finished.connect(self.finished)
        self.fabber.sig_progress.connect(self.update_progress)
        self.fabber.run(options)

    def cancel(self):
        self.fabber.cancel()

    def update_progress(self, *args, **kwargs):
        self.sig_progress.emit(*args, **kwargs)
        
    def finished(self, *args, **kwargs):
        self.status = self.fabber.status
        self.log = self.fabber.log
        self.sig_finished.emit(*args, **kwargs)
        
