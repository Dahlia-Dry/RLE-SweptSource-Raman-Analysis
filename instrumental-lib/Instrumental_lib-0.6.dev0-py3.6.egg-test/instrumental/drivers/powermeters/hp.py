# -*- coding: utf-8  -*-
"""
Driver module for HP Lightwave power meters. Supports:

* HP Lightwave8153A
Usage Example:
from instrumental.drivers.powermeters.hp import HP_8153A
pm = HP_8153A(visa_address='GPIB0::15::INSTR')
pm.identify()
pm.close()

"""

from . import PowerMeter
from .. import VisaMixin, SCPI_Facet
from ... import Q_


class HP_8153A(PowerMeter, VisaMixin):
    """HP Lightwave 8153A power meter"""
    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = ('HP Lightwave', ['8153A'])

    def _initialize(self):
        self._rsrc.read_termination = '\n'
        self._rsrc.timeout = 20000 # ms timeout

        # initialize internal Variables
        self.tap_channel = 1
        self.rec_channel = 2
        self.int_time = 0.05 # seconds

        # Set units to W
        self.write("SENS1:POW:UNIT 1")
        self.write("SENS2:POW:UNIT 1")
        # self.write("SENS%d:CHAN1:POW:UNIT 1" % self.rec_channel)

        # Automatic power range
        self.write("SENS1:POW:RANG:AUTO 1" )
        self.write("SENS2:POW:RANG:AUTO 1" )
        # self.write("SENS%d:CHAN1:POW:RANG:AUTO 1" % self.rec_channel)

        # Set integration time
        # self.write("SENS2:POW:ATIME %.3fS" % self.int_time)
        # self.write("SENS%d:CHAN1:POW:ATIME %.3fS" % (self.rec_channel, self.int_time))

        # Do not measure continuously
        self.write("INIT1:CONT 0")
        self.write("INIT2:CONT 0")
        # self.write("INIT%d:CHAN1:CONT 0" % self.rec_channel)

    def identify(self):
        print(self.query('*IDN?'))

    def close(self):
        self._rsrc.control_ren(False)  # Disable remote mode

    # Tell list_instruments how to close this VISA resource properly
    @staticmethod
    def _close_resource(resource):
        self._rsrc.control_ren(False)  # Disable remote mode

    # power = SCPI_Facet('POW', units='W', readonly=True, type=float,
    #                         doc="Measured Power")
    # Not using SCPI_Facet because the value gets stuck when auto ranging
    def power(self, channel=2):
        if channel in [1,2]:
            self.write("INIT{}:IMM".format(channel))
            try:
                meas_power = max(0.0, float(self.query('FETC{}:POW?'.format(channel))))
            except ValueError:
                meas_power = 0.0

            return Q_(meas_power, units='W')

        else:
            print("channel {} not available. select 1 or 2".format(channel))
            return Q_(0, 'W')

    wavelength2 = SCPI_Facet('SENS2:POW:WAVE', units='m', type=float,
                            doc="Input signal wavelength")

    auto_range2 = SCPI_Facet('SENS2:POW:RANG:AUTO', convert=int, value={False:0, True:1},
                            doc="Whether auto-ranging is enabled")

    integration_time2 = SCPI_Facet('SENS2:POW:ATIME', units='s', type=float,
                            doc="Measurement integration time in seconds 20ms to 3600s available")

    wavelength1 = SCPI_Facet('SENS1:POW:WAVE', units='m', type=float,
                            doc="Input signal wavelength")

    auto_range1 = SCPI_Facet('SENS1:POW:RANG:AUTO', convert=int, value={False:0, True:1},
                            doc="Whether auto-ranging is enabled")

    integration_time1 = SCPI_Facet('SENS1:POW:ATIME', units='s', type=float,
                            doc="Measurement integration time in seconds 20ms to 3600s available")
