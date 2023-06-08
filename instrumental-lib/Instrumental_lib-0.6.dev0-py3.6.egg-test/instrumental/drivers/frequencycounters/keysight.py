
from . import FrequencyCounter
from .. import Facet,SCPI_Facet,VisaMixin
from ... import Q_

class FC53220A(FrequencyCounter, VisaMixin):
    """
    A Keysight 53220A series frequency counter

    Usage Example:
        from instrumental.drivers.frequencycounters.keysight import FC53220A
        fc = FC53220A(visa_address='USB0::0x0957::0x1807::MY50009613::INSTR')
        fc.identify()
        fc.close()
    """
    _INST_PARAMS_ = ['visa_address']

    def _initialize(self, timeout=60000):
        self.channel = 1
        self.resource.read_termination = '\n'
        self._rsrc.timeout = timeout # ms timeout
        self.write('*RST') # Reset to default settings

    def identify(self):
        print(self.query('*IDN?'))

    def frequency(self):
        """The measured frequency"""
        frequency_Hz = float(self.query('MEAS:FREQ?'))

        return Q_(frequency_Hz, 'Hz')

    def period(self):
        """The measured period"""
        period_s = float(self.query('MEAS:PER?'))

        return Q_(period_s, 's')

    def single_period(self, num_counts = 1):
        """Time between triggering events"""
        print('Single period measurement for {} counts'.format(num_counts))
        self.write('SAMP:COUN {}'.format(num_counts))
        self.write('INIT:IMM')
        # self.write('*WAI')
        time_list = self.query('FETC?') # Read instrument
        singleperiod_s = list(np.float_(time_list.split(","))) # Converts the output string to a float list

        # return Q_(singleperiod_s, 's')
        return singleperiod_s

    def set_mode_totalize(self, integration_time= 1.0):
        self.write('CONF:TOT:TIM {}'.format(integration_time))

    def set_mode_single_period(self, num_counts=100):
        self.write('CONF:SPER') # Configure instrument for single period measurement
        self.write('SAMP:COUN {}'.format(num_counts)) # Collect num_counts counts (for each trigger)
        self.timeout = round(float(num_counts), 3) # round to 1ms


    Vthreshold = SCPI_Facet('INP1:LEV', units='V', convert=float, doc="Threshold voltage")
    slope = SCPI_Facet('INP1:SLOP', convert=str, doc="Triggering slope") # "NEG" or "POS"
    coupling = SCPI_Facet('INP1:COUP', convert=str, doc="Input coupling") # "DC" or "AC"
    impedance = SCPI_Facet('INP1:IMP', units='ohm', convert=float, doc="Input impedance") # 50 or 1e6
    display = SCPI_Facet('DISP', convert=str, doc="Display state") # 'ON' or 'OFF'
    timeout = SCPI_Facet('SYST:TIM', convert=str, doc="Measurement timeout in sec") # min 0.01, max 2000, steps 0.001

    temp = SCPI_Facet('SYST:TEMP', units='degC', convert=float, readonly=True,
                        doc="Temperature of system in deg C")
