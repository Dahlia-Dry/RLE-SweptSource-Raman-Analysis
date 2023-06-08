import sys
sys.path.append("..")
from gui_components import params
from time import sleep
from instrumental import Q_
from ctypes import cdll,c_long, c_ulong, c_uint32,byref,create_string_buffer,c_bool,c_char_p,c_int,c_int16,c_double, sizeof, c_voidp
import datetime

#Intialize ThorLabs Power Monitor
wavelength=800
try:
    from drivers.TLPM import TLPM
    pm = TLPM()
    deviceCount = c_uint32()
    pm.findRsrc(byref(deviceCount))
    print("devices found: " + str(deviceCount.value))
    resourceName = create_string_buffer(1024)
    for i in range(0, deviceCount.value):
        pm.getRsrcName(c_int(i), resourceName)
        print(c_char_p(resourceName.raw).value)
        break
    pm.open(resourceName, c_bool(True), c_bool(True))
    message = create_string_buffer(1024)
    pm.getCalibrationMsg(message)
    print(c_char_p(message.raw).value)

except:
    pm = None
    print('Could not open Thorlabs Power meter : {}'.format(sys.exc_info()))
else:
    print('Thorlabs Powermeter connected')

    pm.setWavelength(c_double(wavelength))
    print('Set wavelength to {} nm'.format(wavelength))

    print('Setting power auto range on')
    pm.setPowerAutoRange(c_int16(1))

    print('Set Analog Output slope to {} V/W'.format(params.pm_slope))
    pm.setAnalogOutputSlope(c_double(params.pm_slope))

    print('Setting input filter state to off for higher BW')
    pm.setInputFilterState(c_int16(0))

"""count = c_int16()
pm.getAvgTime(c_int16(0),byref(count))
print('COUNT',count)"""
while True:
    meas_power = c_double()
    pm.measPower(byref(meas_power))
    print('POWER',meas_power.value)
