"""
Quantiphyse - oxasl.Workspace implementation for Quantiphyse

Copyright (c) 2013-2018 University of Oxford
"""
from fsl.data.image import Image

from oxasl import Workspace

from quantiphyse.data import NumpyData, DataGrid

def qpdata_to_fslimage(qpd, grid=None):
    """ 
    Convert QpData to fsl.data.image.Image
    """
    if grid is None:
        return Image(qpd.raw(), name=qpd.name, xform=qpd.grid.affine)
    else:
        return Image(qpd.resample(grid), name=qpd.name, xform=grid.affine)
        
def fslimage_to_qpdata(img, name=None):
    """ Convert fsl.data.image.Image to QpData """
    if not name: name = img.name
    return NumpyData(img.data, grid=DataGrid(img.shape[:3], img.voxToWorldMat), name=name)

class QpWorkspace(Workspace):
    """
    Workspace which is able to return images from an IVM

    The idea here is to bridge the oxasl.Workspace with the
    Quantiphyse IVM. When we request images from the workspace,
    they may be returned from the IVM.

    Note that not any old image will be returned, e.g. if the
    workspace contains an image called 't1' this might cause
    problems if it was returned as the workspace attribute 't1'.
    So we only return images if they are in a predefined dictionary
    set at construction which maps attribute names to IVM image names.

    Images are returned as fsl.data.Image objects as expected by
    oxasl FIXME not yet.
    """

    def __init__(self, ivm, images=None, *args, **kwargs):
        """
        :param ivm: ImageVolumeManagement containing image data
        :param images: Dictionary mapping workspace attribute names
                       to the IVM data names that should be returned
        """
        Workspace.__init__(self, *args, **kwargs)
        if images:
            for attrname, ivm_name in images.items():
                if ivm_name in self.ivm.data:
                    setattr(self, attrname, qpdata_to_fslimage(self.ivm.data[name]))
                    
    def __getstate__(self): return self.__dict__
    def __setstate__(self, d): self.__dict__.update(d)