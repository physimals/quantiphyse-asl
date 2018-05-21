"""
ASL Quantiphyse plugin

Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""
from quantiphyse.utils import get_local_shlib

from .widgets import AslStrucCheck, AslStrucWidget, AslDataWidget, AslPreprocWidget, AslBasilWidget, AslCalibWidget, AslMultiphaseWidget
from .process import AslDataProcess, AslPreprocProcess, BasilProcess, AslMultiphaseProcess
from .tests import AslPreprocWidgetTest, MultiphaseProcessTest, BasilProcessTest

QP_MANIFEST = {
    "widgets" : [AslPreprocWidget, AslBasilWidget, AslCalibWidget, AslMultiphaseWidget],
    "fabber-libs" : [get_local_shlib("fabber_models_asl", __file__)],
    "asl-widgets" : [AslStrucCheck, AslStrucWidget],
    "processes" : [BasilProcess, AslMultiphaseProcess],
    "widget-tests" : [AslPreprocWidgetTest],
    "process-tests" : [MultiphaseProcessTest, BasilProcessTest],
}
