# -*- coding: utf-8  -*-
"""
Driver for Custom PCB board for interfacing a single parameter analyzer to a 12 point microprobe
PCB design and Arduino Sketch available:
https://github.com/jhwnkim/designs-opto-nanofluidics/tree/master/PCB/Probecard-interface
"""

from . import RelayController
from .. import VisaMixin, SCPI_Facet

class ProbecardInterface(RelayController, VisaMixin):
    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = ('MIT POE GROUP', ['Probecard-interface'])

    def _initialize(self):
        self._rsrc.read_termination = '\r'
        self._rsrc.write_termination = '\n'
        # *CLS, *RST resets current settings so don't
        # self.write('*CLS')

    def identify(self):
        print(self.query('*IDN?'))

    channel = SCPI_Facet(':ROUTE:OPEN', convert=int)
    polarity = SCPI_Facet(':ROUTE:POLARITY', convert=int)

    lamp = SCPI_Facet(':LAMP:OUT', convert=int)

    # Tell list_instruments how to close this VISA resource properly
    @staticmethod
    def _close_resource(resource):
        channel = 0 # Close all channels
        lamp = 0 # Turns off lamp
        resource.control_ren(False)  # Disable remote mode
