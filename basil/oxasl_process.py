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

from six import StringIO

from quantiphyse.data import DataGrid, NumpyData, QpData
from quantiphyse.utils import QpException
from quantiphyse.utils.cmdline import OutputStreamMonitor, LogProcess

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
    wsp = Workspace(log=StringIO(), **options)

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

def wsp_to_dict(wsp):
    from fsl.data.image import Image
    from oxasl import Workspace, AslImage
    ret = dict(vars(wsp))
    for key in ret.keys():
        value = ret[key] 
        if isinstance(value, AslImage):
            ret[key] = aslimage_to_qpdata(value)
        elif isinstance(value, Image):
            ret[key] = fslimage_to_qpdata(value)
        elif isinstance(value, Workspace):
            ret[key] = wsp_to_dict(value)
        elif key in ("log", "fsllog", "report") or key[0] == "_":
            ret.pop(key)
    print(ret)
    return ret

def qp_oxasl(worker_id, queue, asldata, options):
    try:
        from fsl.data.image import Image
        from oxasl import Workspace, AslImage
        from oxasl.oxford_asl import oxasl

        for key, value in options.items():
            if isinstance(value, QpData):
                options[key] = qpdata_to_fslimage(value)

        output_monitor = OutputStreamMonitor(queue)
        wsp = Workspace(log=output_monitor)
        wsp.asldata, _ = qpdata_to_aslimage(asldata)

        oxasl(wsp)

        print("done")
        ret = wsp_to_dict(wsp)
        return worker_id, True, ret
    except:
        import sys, traceback
        traceback.print_exc()
        return worker_id, False, sys.exc_info()[1]

class OxaslProcess(LogProcess):
    """
    Process which runs the Python version of oxford_asl
    """
    PROCESS_NAME = "Oxasl"

    def __init__(self, ivm, **kwargs):
        LogProcess.__init__(self, ivm, worker_fn=qp_oxasl, **kwargs)

    def run(self, options):
 
        self.data = self.get_data(options)
        options["mask"] = self.get_roi(options, self.data.grid)

        self.expected_steps = [
            ("Pre-processing", "Pre-processing"),
            #("Registering", "Initial ASL->Structural registration"),
            (".*initial fit", "Initial model fitting"),
            (".*fit on full", "Model fitting to full data"),    
            #("segmentation", "Segmenting structural image"),
            #("BBR registration", "Final ASL->Structural registration"),
        ]
        self.current_step = 0
        self.start_bg([self.data, options])

    def finished(self, worker_output):
        """ Called when process finishes """
        print("finished")
        ret = worker_output[0]
        print(ret)
        self.ivm.add(ret["native"]["perfusion"], name="perfusion")
        print("finished")
