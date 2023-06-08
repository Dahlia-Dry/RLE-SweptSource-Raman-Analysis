# -*- coding: utf-8  -*-
"""
Driver for IDQuantique ID120 SPAD Module on RS232 communication

Usage Example:
from instrumental.drivers.spad.id120 import ID120
spad = ID120(visa_address='USB0::0x1DDC::0x0330::002008::INSTR')
spad.identify()
spad.close()
"""

from . import SPAD
from .. import VisaMixin, SCPI_Facet
from ... import Q_

class ID120(SPAD, VisaMixin):
    """ IDQuantique ID120 SPAD """
    _INST_PARAMS_ = ['visa_address']
    _INST_VISA_INFO_ = ('IDQuantique', ['ID120'])

    def _initialize(self):
        self._rsrc.read_termination = '\n'
        self._rsrc.timeout = 20000 # ms timeout

        self.info()


    def identify(self):
        print(self.query('*IDN?'))

    def info(self):
        print('Querying capabilities of the device:')
        print("THRESHOLD:CAPABILITY? "+self.query("THRESHOLD:CAPABILITY?"))
        print("DEADTIME:CAPABILITY? "+self.query("DEADTIME:CAPABILITY?"))
        print("BIAS:CAPABILITY? "+self.query("BIAS:CAPABILITY?"))
        print("COUNTERS:INTEGRATION_TIME_CAPABILITY? "+self.query("COUNTERS:INTEGRATION_TIME_CAPABILITY?"))
        print("REG:TEMP_SET_POINT_CAPABILITY? "+self.query("REG:TEMP_SET_POINT_CAPABILITY?"))
        # print(" "+self.query(""))

        print('Printing device information for ID120')
        print("INFO:PRODUCT_NAME? "+self.query("INFO:PRODUCT_NAME?"))
        print("INFO:PRODUCT_DEVELOPMENT_NAME? "+self.query("INFO:PRODUCT_DEVELOPMENT_NAME?"))
        print("INFO:PRODUCT_DESCRIPTION? "+self.query("INFO:PRODUCT_DESCRIPTION?"))
        print("INFO:PRODUCT_SERIAL_NUMBER? "+self.query("INFO:PRODUCT_SERIAL_NUMBER?"))
        print("INFO:PRODUCT_TYPE? "+self.query("INFO:PRODUCT_TYPE?"))
        print("INFO:PRODUCT_REVISION? "+self.query("INFO:PRODUCT_REVISION?"))
        print("INFO:APD_TYPE? "+self.query("INFO:APD_TYPE?"))
        print("INFO:BOARD_REVISION? "+self.query("INFO:BOARD_REVISION?"))
        print("INFO:BOARD_SERIAL_NUMBER? "+self.query("INFO:BOARD_SERIAL_NUMBER?"))
        print("INFO:VENDOR_NAME? "+self.query("INFO:VENDOR_NAME?"))
        print("INFO:MANUFACTURER_NAME? "+self.query("INFO:MANUFACTURER_NAME?"))
        print("INFO:MANUFACTURING_DATE? "+self.query("INFO:MANUFACTURING_DATE?"))
        print("INFO:OUTPUT1_STANDARD? "+self.query("INFO:OUTPUT1_STANDARD?"))
        print("INFO:OUTPUT2_STANDARD? "+self.query("INFO:OUTPUT2_STANDARD?"))
        print("INFO:FIRMWARE_VERSION? "+self.query("INFO:FIRMWARE_VERSION?"))
        print("INFO:CONTENT_INTEGRITY? "+self.query("INFO:CONTENT_INTEGRITY?"))
        print("INFO:BIAS_BREAKDOWN_VOLTAGE? "+self.query("INFO:BIAS_BREAKDOWN_VOLTAGE?"))

    def set_outputs(self, channel, polarity):
        if not channel in [1,2]:
            print('Channel must be 1 or 2')
            return

        if not polarity in ['POSITIVE', 'NEGATIVE']:
            print('polarity must be POSITIVE or NEGATIVE')
            return

        self.write("OUTPUT{}:POLARITY {}".format(channel, polarity))

    def get_outputs(self, channel):
        if not channel in [1,2]:
            print('Channel must be 1 or 2')
            return

        print(self.query("OUTPUT{}:POLARITY?".format(channel)))

    threshold = SCPI_Facet('THRESHOLD:VOLTAGE', type=float, convert=int, units='microvolt', limits=[0, 1047000, 500],
                            doc="Count threshold voltage")

    deadtime = SCPI_Facet('DEADTIME:TIME', type=float, convert=int, units='microsecond', limits=[40, 1000000, 40],
                            doc="Dead time")

    bias = SCPI_Facet('BIAS:VOLTAGE', type=float, convert=int, units='microvolt', limits=[0, 250000000, 80000],
                            doc="Bias voltage")
    bias_error = SCPI_Facet('BIAS:ERROR_STATUS', type=bool, convert=str, value={True: "TRUE", False: "FALSE"}, readonly=True,
                            doc="Bias voltage error status")

    integration_time = SCPI_Facet('COUNTERS:INTEGRATION_TIME', type=float, convert=int, units='millisecond', limits=[200, 100000, 200],
                            doc="Integration time")

    # pint has an error where millidegC gets converted to milliK https://github.com/hgrecco/pint/issues/1381
    set_temp = SCPI_Facet('REG:TEMP_SET_POINT', type=float, convert=int, units='millidegC', limits=[-50000, -10000, 1000],
                            doc="Temperature set point")
    temp = SCPI_Facet('REG:MEASURED_TEMP', type=float, convert=int, units='millidegC', readonly=True,
                            doc="Measured Temperature")

    run = SCPI_Facet('REG:RUN', type=bool, convert=str, value={True:"TRUE", False:"FALSE"},
                            doc="Run status")

    state = SCPI_Facet('REG:STATE', type=str, readonly=True,
                            doc="SPAD state")

    freq = SCPI_Facet('COUNTERS:DETECTION_FREQ', type=float, convert=int, units='Hz', readonly=True,
                            doc="Detected frequency")
    count = SCPI_Facet('COUNTERS:DETECTION_COUNT', type=float, convert=int, units='dimensionless', readonly=True,
                            doc="Detected counts")

    # Tell list_instruments how to close this VISA resource properly
    @staticmethod
    def _close_resource(resource):
        pass
