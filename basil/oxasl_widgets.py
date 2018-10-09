"""
QP-BASIL - QWidgets for the Oxasl tool

Copyright (c) 2013-2018 University of Oxford
"""

from __future__ import division, unicode_literals, absolute_import

from PySide import QtGui

from quantiphyse.gui.options import OptionBox, ChoiceOption as Choice, NumericOption as Number, BoolOption, DataOption, FileOption

class StructuralData(QtGui.QWidget):
    """
    OXASL processing options related to structural data
    """

    def __init__(self, ivm):
        QtGui.QWidget.__init__(self)
        self.ivm = ivm
        self.grid = QtGui.QGridLayout()
        self.setLayout(self.grid)

        self.grid.addWidget(QtGui.QLabel("Structural data from"), 0, 0)
        self.data_from = Choice(["Structural image", "FSL_ANAT output"], ["img", "fsl_anat"])
        self.data_from.sig_changed.connect(self._data_from_changed)
        self.grid.addWidget(self.data_from, 0, 1)
        self.struc_img = DataOption(self.ivm, include_4d=False)
        self.grid.addWidget(self.struc_img, 0, 2)
        self.fslanat_dir = FileOption(dirs=True)
        
        self.grid.setRowStretch(1, 1)

    def _data_from_changed(self):
        if self.data_from.value == "img":
            self.grid.addWidget(self.struc_img, 0, 2)
        else:
            self.grid.addWidget(self.fslanat_dir, 0, 2)

    def options(self):
        """ :return: Options as dictionary """
        return {
            "struc" : self.struc_img.value,
        }

class CalibrationOptions(QtGui.QWidget):
    """
    OXASL processing options related to calibration
    """

    def __init__(self):
        QtGui.QWidget.__init__(self)
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        vbox.addWidget(self.optbox)
        vbox.addStretch(1)

    def options(self):
        """ :return: Options as dictionary """
        return self.optbox.values()

class CorrectionOptions(QtGui.QWidget):
    """
    OXASL processing options related to corrections (motion, distortion etc)
    """

    def __init__(self):
        QtGui.QWidget.__init__(self)
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        vbox.addWidget(self.optbox)
        vbox.addStretch(1)

    def options(self):
        """ :return: Options as dictionary """
        return self.optbox.values()

class AnalysisOptions(QtGui.QWidget):
    """
    OXASL processing options related to model fitting analysis
    """

    def __init__(self):
        QtGui.QWidget.__init__(self)
        vbox = QtGui.QVBoxLayout()
        self.setLayout(vbox)

        self.optbox = OptionBox()
        self.optbox.add("White paper mode", BoolOption(), key="wp")
        self.optbox.add("Arterial Transit Time", Number(minval=0, maxval=2.5, default=1.3), key="bat")
        self.optbox.add("T1 (s)", Number(minval=0, maxval=3, default=1.3), key="t1")
        self.optbox.add("T1b (s)", Number(minval=0, maxval=3, default=1.65), key="t1b")
        self.optbox.add("Spatial regularization", BoolOption(default=True), key="spatial")
        self.optbox.add("T1 value uncertainty", BoolOption(default=False), key="infert1")
        self.optbox.add("Macro vascular component", BoolOption(default=False), key="inferart")
        self.optbox.add("Fix label duration", BoolOption(default=True), key="fixbolus")
        self.optbox.add("Motion correction", BoolOption(default=False), key="mc")
        self.optbox.add("Partial volume correction", BoolOption(default=False), key="pvcorr")
        vbox.addWidget(self.optbox)
        vbox.addStretch(1)

    def options(self):
        """ :return: Options as dictionary """
        return self.optbox.values()
