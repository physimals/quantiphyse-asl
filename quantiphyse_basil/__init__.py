"""
ASL Quantiphyse plugin

Author: Martin Craig <martin.craig@eng.ox.ac.uk>
Copyright (c) 2016-2017 University of Oxford, Martin Craig
"""
import os

from .widgets import AslPreprocWidget, AslBasilWidget, AslCalibWidget, AslMultiphaseWidget
from .oxasl_widgets import OxaslWidget
from .aslimage_widget import AslImageWidget
from .process import AslDataProcess, AslPreprocProcess, BasilProcess, AslMultiphaseProcess, OxaslProcess
from .tests import AslPreprocWidgetTest, MultiphaseProcessTest, OxaslProcessTest, OxaslWidgetTest

# Workaround ugly warning about wx
import logging
logging.getLogger("fsl.utils.platform").setLevel(logging.CRITICAL)

QP_MANIFEST = {
    "widgets" : [AslPreprocWidget, AslMultiphaseWidget, OxaslWidget],
    "processes" : [AslPreprocProcess, AslMultiphaseProcess, OxaslProcess],
    "fabber-dirs" : [os.path.dirname(__file__),],
    "qwidgets" : [AslImageWidget],
    "module-dirs" : ["deps",],
    "widget-tests" : [AslPreprocWidgetTest, OxaslWidgetTest],
    "process-tests" : [OxaslProcessTest, MultiphaseProcessTest,],
}
