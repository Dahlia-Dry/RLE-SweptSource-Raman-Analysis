# -*- coding: utf-8  -*-
"""
Driver for Keithley 2400 Sourcemeter on GPIB communication

Usage Example:
from instrumental.drivers.sourcemeasureunit.keithley import Keithley_2400
smu = Keithley_2400(visa_address='GPIB0::15::INSTR')
smu.identify()
smu.close()
"""

from . import SourceMeasureUnit
from .. import VisaMixin
from ... import Q_

class KeithleySMU(SourceMeasureUnit, VisaMixin):
    _DEFAULT_CURRENT_COMPLIANCE = 0.001 # in A
    _VISA_TIMEOUT = 10000 # in ms

    def _initialize(self):
        self.write("*RST")
        # time.sleep(1.0)

        # Increase timeout
        self._rsrc.timeout = KeithleySMU._VISA_TIMEOUT
        self._rsrc.read_termination = '\n'
        self._rsrc.write_termination = '\n'

        # initialize variables
        self._voltage = Q_(0.0, 'V') # V
        self._compliance = Q_(KeithleySMU._DEFAULT_CURRENT_COMPLIANCE, 'A')

        # initialize instrument
        self.write("*RST")

        # set voltage source settings
        self.write(':SOUR:FUNC VOLT')
        self.write(':SOUR:SWE:RANG AUTO')
        self.write(':SOUR:VOLT:LEV:AMPL 0.0')

        # set current sense settings
        self.write(':SENS:CURR:PROT {}'.format(KeithleySMU._DEFAULT_CURRENT_COMPLIANCE))
        self.write(':SENS:FUNC "CURR"')
        self.write(':SENS:CURR:RANG:AUTO 1')
        self.write(':SENS:CURR:NPLC 10') # set integration to maximum power line cycles

        self.write(':OUTP ON')

    def identify(self):
        print(self.query('*IDN?'))

    def set_integration_time(self, time=1.0):
        """
        Sets the integration time in power-line cycles (16.67 ms)
        :param time: float, 0.01 to 10, 1.0 is default
        :return:
        """
        if isinstance(time, str):
            if time == 'short':
                self.write(':SENS:CURR:NPLC 0.01')
            elif time == 'med' or time=='medium':
                self.write(':SENS:CURR:NPLC 1.0')
            elif time == 'long':
                self.write(':SENS:CURR:NPLC 10')
            else:
                print('KeithleySMU: Specified integration time {} is not correct.'.format(time))
                return
        elif isinstance(time, float):
            if time<0.01 or time>10:
                print('KeithleySMU: Specified integration time is not correct. Input 0.01 to 10 power cycles.')
                return
            else:
                self.write(':SENS:CURR:NPLC {:.2f}'.format(time))
        else:
            print('KeithleySMU: Unsupported type {} for integration time'.format(type(time)))

    def set_voltage(self, voltage):
        """
        Sets the voltage to the specified value, voltage should be Q_ type
        :return:
        """
        print('Setting Keithley SMU voltage to {:.4f}'.format(voltage))

        self.write(':SOUR:VOLT:LEV:AMPL {:.5E}'.format(voltage.to('V').magnitude))

        self._voltage = voltage

    def set_current_compliance(self, compliance):
        """
        :param compliance: In Q_ type
        :return:
        """
        self._compliance = compliance
        self.write(':SENS:CURR:PROT {:.5E}'.format(compliance.to('A').magnitude))

    def measure_current(self):
        """
        Measure the current through the device
        :return: The current in A
        """
        try:
            current = Q_(float(self.query(':READ?').split(',')[1]), 'A')
        except ValueError:
            current = Q_(0.0, 'A')

        return current

    # Tell list_instruments how to close this VISA resource properly
    @staticmethod
    def _close_resource(resource):
        self.write(':OUTP OFF')

        resource.control_ren(False)  # Disable remote mode

# Models
class Keithley_2400(KeithleySMU):
    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = ('Keithley', ['2400'])
