# -*- coding: utf-8  -*-
"""
Driver for Newport Laser Diode Controllers

* Model 5005 Laser Diode Driver
"""

from . import LaserDiodeController
from .. import VisaMixin, SCPI_Facet

class Model5005(LaserDiodeController, VisaMixin):
    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = ('Newport', ['5005'])

    def _initialize(self):
        self._rsrc.read_termination = '\n'
        # *CLS, *RST resets current settings so don't
        # self.write('*CLS')
        print(self.query('*IDN?'))


    # current = SCPI_Facet('LAS:LDI', units='mA', convert=float) # Does not change current, inquiry sent to Newport
    output = SCPI_Facet('LAS:OUT', convert=int)

    # Tell list_instruments how to close this VISA resource properly
    @staticmethod
    def _close_resource(resource):
        output = 0 # Turns off laser
        resource.control_ren(False)  # Disable remote mode
