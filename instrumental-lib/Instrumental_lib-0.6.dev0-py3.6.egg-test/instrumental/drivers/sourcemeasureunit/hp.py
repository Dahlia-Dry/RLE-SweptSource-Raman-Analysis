# -*- coding: utf-8  -*-
"""
Driver for HP 4156C on GPIB communication

Usage Example:
from instrumental.drivers.sourcemeasureunit.hp import HP_4156C
smu = HP_4156C(visa_address='GPIB0::17::INSTR')
smu.identify()
smu.close()
"""

from . import SourceMeasureUnit
from .. import VisaMixin
from ... import Q_

class HpSMU(SourceMeasureUnit, VisaMixin):
    _NUM_OF_CHANNELS = 4
    _DEFAULT_CURRENT_COMPLIANCE = 0.001 # in A
    _VISA_TIMEOUT = 10000

    def _initialize(self):
        # self._rsrc.read_termination = '\r'
        # self._rsrc.write_termination = '\n'
        # *CLS, *RST resets current settings so don't
        # self.write('*CLS')

        # Increase timeout
        self._rsrc.timeout = HpSMU._VISA_TIMEOUT

        # initialize variables
        self._channel = 1
        self._voltage = Q_(0.0, 'V') # V
        self._compliance = Q_(HpSMU._DEFAULT_CURRENT_COMPLIANCE, 'A')

        # initialize instrument
        self.write("*RST")
        # Initialize channels 1~4
        for ch_index in range(HpSMU._NUM_OF_CHANNELS):
            self.initialize_channel(ch_index+1)

    def identify(self):
        print(self.query('*IDN?'))

    def set_channel(self, channel):
        if channel >0 and channel <= HpSMU._NUM_OF_CHANNELS:
            self._channel = channel
            self.write("CN %d" % channel)
        else:
            print('HpSemiParamAnalyzer: Invalid channel')

    def set_integration_time(self, time):
        """
        Sets the integration time
        :param time: String, eiher 'short', 'med'. or 'long'
        :return:
        """
        if time == 'short':
            mode = 1
        elif time == 'med' or time=='medium':
            mode = 2
        elif time == 'long':
            mode = 3
        else:
            print('Specified integration time is not correct.')
            return

        self.write("SLI " + str(mode))

    def set_voltage(self, voltage):
        """
        Sets the voltage to the specified value, voltage should be Q_ type
        :return:
        """
        print('Setting HP SMU channel {} voltage to {:.4f}'.format(self._channel, voltage))
        self.write("DV {},12,{:.5E},{:.4f}".format(self._channel, voltage.to('V').magnitude,
                                                  self._compliance.to('A').magnitude))
        self._voltage = voltage

    def initialize_channel(self, channel):
        """
        Initializes the current channel
        :return: None
        """

        self._channel = channel

        self.write("US")
        self.write("FMT 2")
        self.write("AV 1")
        self.write("CM 0")
        self.write("SLI 1") # short integration time
        # self.sparam.write("FL 0")
        self.write("CN %d" % channel)
        self.write("DV 2,11,0," + str(self._compliance.to('A').magnitude))

        self.set_voltage(Q_(0.0, 'V'))

    def set_current_compliance(self, compliance):
        """
        :param compliance: In Q_ type
        :return:
        """
        self._compliance = compliance

    def measure_current(self):
        """
        Measure the current through the device
        :return: The current in A
        """
        try:
            current = Q_(float(self.query("TI? %d,0" % self._channel)), 'A')
        except ValueError:
            current = Q_(0.0, 'A')

        return current

    # Tell list_instruments how to close this VISA resource properly
    @staticmethod
    def _close_resource(resource):

        self.write("CL")
        self.write(":PAGE")

        resource.control_ren(False)  # Disable remote mode

# Models
class HP_4156C(HpSMU):
    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = ('HEWLETT-PACKARD', ['4156C'])
