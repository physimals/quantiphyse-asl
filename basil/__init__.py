"""
ASL Quantiphyse plugin

Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""
from quantiphyse.utils import get_local_shlib

from .widgets import AslStrucCheck, AslDataWidget, AslPreprocWidget, AslBasilWidget
from .process import AslDataProcess, AslPreprocProcess

QP_MANIFEST = {
    "widgets" : [AslPreprocWidget, AslBasilWidget],
    "fabber-libs" : [get_local_shlib("fabber_models_asl", __file__)],
    "asl-widgets" : [AslStrucCheck],
}
