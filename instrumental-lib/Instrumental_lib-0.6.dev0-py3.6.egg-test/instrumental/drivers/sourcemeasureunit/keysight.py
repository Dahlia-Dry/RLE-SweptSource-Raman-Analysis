# -*- coding: utf-8  -*-
"""
Driver for Keysight B2902A sourcemeter on GPIB communication

Usage Example:
from instrumental.drivers.sourcemeasureunit.keysight import B2902A
smu = B2902A(visa_address='USB0::0x0957::0x8C18::MY51141236::INSTR')
smu.identify()
smu.close()
"""

from . import SourceMeasureUnit
from .. import VisaMixin
from ... import Q_

class B2902A(SourceMeasureUnit, VisaMixin):
    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = ('Keysight', ['B2902A'])

    _DEFAULT_CURRENT_COMPLIANCE = 0.001 # in A
    _DEFAULT_VOLTAGE_COMPLIANCE = 50 # in V
    _VISA_TIMEOUT = 10000 # in ms

    def _initialize(self):
        self.write("*RST")
        # time.sleep(1.0)

        # Increase timeout
        self._rsrc.timeout = B2902A._VISA_TIMEOUT
        self._rsrc.read_termination = '\n'
        self._rsrc.write_termination = '\n'

        # initialize variables
        self._voltage = Q_(0.0, 'V') # V
        self._current = Q_(0.0, 'A') # A
        self._cur_compliance = Q_(B2902A._DEFAULT_CURRENT_COMPLIANCE, 'A')
        self._volt_compliance =Q_(B2902A._DEFAULT_VOLTAGE_COMPLIANCE, 'V')
        self._mode = "VOLT"
        self._is_on = "ON"

        # initialize instrument
        self.write("*RST")

        # set voltage source settings
        self.write(':SOUR:FUNC VOLT')
        self.write(':SOUR:SWE:RANG AUTO')
        self.write(':SOUR:VOLT:LEV:AMPL 0.0')

        # set current sense settings
        self.write(':SENS:CURR:PROT {}'.format(B2902A._DEFAULT_CURRENT_COMPLIANCE))
        self.write(':SENS:FUNC:MODE CURR')
        self.write(':SENS:CURR:RANG:AUTO 1')
        self.write(':SENS:CURR:NPLC 10') # set integration to maximum power line cycles

        self.write(':OUTP ON')

    def identify(self):
        print(self.query('*IDN?'))

    def set_mode(self, mode):
        """
        :param mode: Either VOLT or CURR
        :return:
        """
        if not (mode == 'VOLT' or mode == 'CURR'):
            print('Source meter mode not correct. NO action taken')
            return

        self.write((":SOUR:FUNC:MODE %s" % mode))
        self.write(':SENS:{}:RANG:AUTO 1'.format(mode))
        self._mode = mode


    def set_integration_time(self, time=1.0):
        """
        Sets the integration time in power-line cycles (16.67 ms)
        :param time: float, 0.01 to 10, 1.0 is default
        :return:
        """
        if isinstance(time, str):
            if time == 'short':
                self.write(':SENS:%s:NPLC 0.01' % self._mode)
            elif time == 'med' or time=='medium':
                self.write(':SENS:%s:NPLC 1.0' % self._mode)
            elif time == 'long':
                self.write(':SENS:%s:NPLC 10' % self._mode)
            else:
                print('KeysightSMU: Specified integration time {} is not correct.'.format(time))
                return
        elif isinstance(time, float):
            if time<8E-6 or time>2.0:
                print('KeysightSMU: Specified integration time is not correct. Input 0.01 to 10 power cycles.')
                return
            else:
                self.write(':SENS:{}:APER {:.2f}'.format(self._mode, time))
        else:
            print('KeysightSMU: Unsupported type {} for integration time'.format(type(time)))

    def set_voltage_compliance(self, v_comp):
        self.write((":SENS:VOLT:PROT %.4E" % v_comp))
        self.write(":OUTP:PROT ON")
        self._volt_compliance = Q_(v_comp, 'V')

    def set_current_compliance(self, i_comp):
        self.write((":SENS:CURR:PROT %.4E" % i_comp))
        self.write(":OUTP:PROT ON")
        self._cur_compliance = Q_(i_comp, 'A')

    def set_voltage(self, voltage):
        """
        Sets the specified voltage
        :param voltage: Q_( , 'A')
        :return:
        """
        if not (self._mode == 'VOLT'):
            self.set_output("OFF")
            self.set_mode('VOLT')
            time.sleep(0.1)

        if self._is_on == "OFF":
            self.set_output("ON")

        self.write(":SOUR1:VOLT %.4E" % voltage.to('V').magnitude)

        self._voltage = voltage

    def set_current(self, current):
        """
        Sets the specified current
        :param current: Q_( , 'A')
        :return:
        """
        if not (self._mode == 'CURR'):
            self.set_output("OFF")
            self.set_mode('CURR')
            time.sleep(0.1)

        self.write(":SOUR1:CURR %.4E" % current.to('A').magnitude)

        if self._is_on == "OFF":
            self.set_output("ON")
        self._current = current

    def measure_current(self):
        self.write(":FORM:ELEM:SENS CURR")
        return Q_(float(self.query(":MEAS?")), 'A')

    def measure_voltage(self):
        self.write(":FORM:ELEM:SENS VOLT")
        return Q_(float(self.query(":MEAS?")), 'V')

    def measure_resistance(self):
        self.write(":FORM:ELEM:SENS RES")
        return Q_(float(self.query(":MEAS?")), 'ohm')

    def set_output(self, output):
        if not (output == 'ON' or output == 'OFF'):
            print('Source meter output not correct. specify ON or OFF')
            return

        self.write(":OUTP %s" % output)
        self._is_on = output

    # Tell list_instruments how to close this VISA resource properly
    @staticmethod
    def _close_resource(resource):
        self.write(':OUTP OFF')

        resource.control_ren(False)  # Disable remote mode
