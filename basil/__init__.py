"""
ASL Quantiphyse plugin

Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""
from quantiphyse.utils import get_local_shlib

from .widgets import AslPreprocWidget, AslBasilWidget, AslCalibWidget, AslMultiphaseWidget
from .oxasl_widgets import OxaslWidget
from .aslimage_widget import AslImageWidget
from .process import AslDataProcess, AslPreprocProcess, BasilProcess, AslMultiphaseProcess, OxaslProcess
from .tests import AslPreprocWidgetTest, MultiphaseProcessTest, BasilProcessTest

QP_MANIFEST = {
    "widgets" : [AslPreprocWidget, AslBasilWidget, AslCalibWidget, AslMultiphaseWidget, OxaslWidget],
    "fabber-libs" : [get_local_shlib("fabber_models_asl", __file__)],
    "module-dirs" : ["deps",],
    "asl-widgets" : [AslImageWidget],
    "processes" : [BasilProcess, AslMultiphaseProcess, OxaslProcess],
    "widget-tests" : [AslPreprocWidgetTest],
    "process-tests" : [MultiphaseProcessTest, BasilProcessTest],
}
