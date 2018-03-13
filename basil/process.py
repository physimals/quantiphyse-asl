import yaml

from quantiphyse.utils import warn, debug, get_plugins
from quantiphyse.utils.exceptions import QpException

from quantiphyse.analysis import BackgroundProcess, Process

from .asl.image import AslImage

USE_CMDLINE = False

class AslProcess(Process):

    def __init__(self, ivm, **kwargs):
        Process.__init__(self, ivm, **kwargs)
        self.default_struc = {"order" : "prt", "tis" : [1.5,], "taus" : [1.4,], "casl" : True}
        self.struc = None

    def get_asldata(self, options):
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

        # Create AslImage object, this will fail if structure information is 
        # insufficient or inconsistent
        data = self.ivm.data[data_name]
        img = AslImage(data.name, data=data.std(),
                       tis=self.struc.get("tis", None), 
                       rpts=self.struc.get("rpts", None), 
                       order=self.struc.get("order", None))
                       
        # On success, set structure metadata so other widgets/processes can use it
        struc_str = yaml.dump(self.struc)
        self.ivm.add_extra("ASL_STRUCTURE_" + data_name, struc_str)
        return img

class AslDataProcess(AslProcess):
    """
    Process which merely records the structure of an ASL dataset
    """
    PROCESS_NAME = "AslData"

    def __init__(self, ivm, **kwargs):
        AslProcess.__init__(self, ivm, **kwargs)

    def run(self, options):
        self.get_asldata(options)
        self.status = Process.SUCCEEDED

class AslPreprocProcess(AslProcess):
    """
    ASL preprocessing process
    """
    PROCESS_NAME = "AslPreproc"

    def __init__(self, ivm, **kwargs):
        AslProcess.__init__(self, ivm, **kwargs)
        
    def run(self, options):
        img = self.get_asldata(options)

        if options.pop("sub", False):
            img = img.diff()

        new_order = options.pop("reorder", None)
        if new_order is not None:
            img = img.reorder(new_order)

        output_name = options.pop("output-name", img.iname + "_preproc")
        self.ivm.add_data(img.data(), name=output_name)
        new_struc = dict(self.struc)
        new_struc["data"] = output_name
        new_struc["order"] = img.order

        debug("New structure is")
        debug(str(new_struc))
        AslDataProcess(self.ivm).run(new_struc)

        self.status = Process.SUCCEEDED

class BasilProcess(BackgroundProcess):
    """
    Currently a direct wrapper around the Fabber process. We would like to subclass
    it but this is not straightforward because the Fabber process class is loaded
    from a plugin.
    """
    def __init__(self, ivm, **kwargs):
        try:
            self.fabber = get_plugins("processes", "FabberProcess")[0](ivm)
        except Exception, e:
            warn(str(e))
            raise QpException("Fabber core library not found.\n\n You must install Fabber to use this widget")

        BackgroundProcess.__init__(self, ivm, self.fabber.fn, **kwargs)

    def run(self, options):
        data_name = options.pop("data", None)
        if data_name is None:
            if self.ivm.main is None:
                raise QpException("No data loaded")
            else:
                data_name = self.ivm.main.name

        if data_name not in self.ivm.data:
            raise QpException("Data not found: %s" % data_name)

        # Get information about the structure of the data. This should have been
        # created by the ASL Data widget, but the user might not realize that
        # they needed to do this
        struc_str = self.ivm.extras.get("ASL_STRUCTURE_" + data_name, None)
        if struc_str is None:
            raise QpException("You need to define the structure of your ASL data first")
        else:
            struc = yaml.load(struc_str)

        data = self.ivm.data[data_name]
        img = AslImage(data.name, data=data.std(), 
                       tis=struc["tis"], rpts=struc.get("rpts", None), order=struc["order"])
        img = img.diff().reorder("rt")
        self.ivm.add_data(img.data(), name=img.iname)
        options["data"] = img.iname

        # Taus are relevant only for CASL labelling
        # For taus/repeats try to use a single value where possible
        if struc["casl"]:
            options["casl"] = ""
            taus = struc["taus"]
            if min(taus) == max(taus):
                options["tau"] = str(taus[0])
            else:
                for idx, tau in enumerate(taus):
                    options["tau%i" % (idx+1)] = str(tau)
        
        if min(img.rpts) == max(img.rpts):
            options["repeats"] = str(img.rpts[0])
        else:
            for idx, rpt in enumerate(img.rpts):
                options["rpt%i" % (idx+1)] = str(rpt)

        # For CASL obtain TI by adding PLD to tau
        for idx, ti in enumerate(img.tis):
            if struc["casl"]:
                ti += taus[idx]
            options["ti%i" % (idx+1)] = str(ti)

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
        
