# -*- coding: utf-8  -*-
"""
Driver for ILX Lightwave PowerMeter

* OMM-6810B
"""

from . import PowerMeter
from .. import VisaMixin, SCPI_Facet
from ... import Q_


class OMM_6810B(PowerMeter, VisaMixin):
    """ILX Lightwave OMM-6810B power meter"""
    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = ('ILX Lightwave', ['6810B'])

    def _initialize(self):
        self._rsrc.read_termination = '\n'
        # Set power mode to Linear and Watts
        self.write('POWER:MODE LIN')

        # Set measurement rate to slow
        self.write('RATE SLOW')

    def close(self):
        self._rsrc.control_ren(False)  # Disable remote mode

    # Tell list_instruments how to close this VISA resource properly
    @staticmethod
    def _close_resource(resource):
        resource.control_ren(False)  # Disable remote mode

    # power = SCPI_Facet('POW', units='W', readonly=True, type=float,
    #                         doc="Measured Power")
    # Not using SCPI_Facet because the value gets stuck when auto ranging
    def power(self):
        # Turn on auto ranging mode - auto ranging must be off for the power meter to update values
        # self.write('POWER:AUTO 1')
        # self.write('POWER:AUTO 0')

        return Q_(float(self.query('POW?')), units='W')

    wavelength = SCPI_Facet('WAVE', units='nm', type=float,
                            doc="Input signal wavelength")

    auto_range = SCPI_Facet('POWER:AUTO', convert=int, value={False:0, True:1},
                            doc="Whether auto-ranging is enabled")

    # Methods for setting averaging filter speed
    def set_slow_filter(self):
        """Set the averaging filter to slow mode

        The slow filter uses a 16-measurement running average.
        """
        self.write('RATE SLOW')

    def set_medium_filter(self):
        """Set the averaging filter to medium mode

        The medium filter uses a 4-measurement running average.
        """
        self.write('RATE MED')

    def set_no_filter(self):
        """Set the averaging filter to fast mode, i.e. no averaging"""
        self.write('RATE FAST')

    def get_filter(self):
        """Queries the filter mode setting"""
        return self.query('RATE?')
