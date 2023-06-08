import sys
sys.path.append("..")
from gui_components import params
from time import sleep
from instrumental import Q_
from ctypes import cdll,c_long, c_ulong, c_uint32,byref,create_string_buffer,c_bool,c_char_p,c_int,c_int16,c_double, sizeof, c_voidp
import datetime
# Initialize Superlum laser
try:
    from drivers.superlum import Superlum

    laser = Superlum(port='COM8', verbose=False)
    laser.connect()
except:
    print('Error connecting to Superlum {}'.format(sys.exc_info()))
    laser = None
else:
    print('Connected to Superlum through serial port {}'.format(laser.port))
    laser.set_mode(mode='T') # single tone mode
    laser.verbose = True
    laser.get_status()
    laser.verbose = False
    wavelength = laser.get_wavelength()
# #Intialize ThorLabs Power Monitor
# wavelength=800
# try:
#     from drivers.TLPM import TLPM
#     pm = TLPM()
#     deviceCount = c_uint32()
#     pm.findRsrc(byref(deviceCount))
#     print("devices found: " + str(deviceCount.value))
#     resourceName = create_string_buffer(1024)
#     for i in range(0, deviceCount.value):
#         pm.getRsrcName(c_int(i), resourceName)
#         print(c_char_p(resourceName.raw).value)
#         break
#     pm.open(resourceName, c_bool(True), c_bool(True))
#     message = create_string_buffer(1024)
#     pm.getCalibrationMsg(message)
#     print(c_char_p(message.raw).value)

# except:
#     pm = None
#     print('Could not open Thorlabs Power meter : {}'.format(sys.exc_info()))
# else:
#     print('Thorlabs Powermeter connected')

#     pm.setWavelength(c_double(wavelength))
#     print('Set wavelength to {} nm'.format(wavelength))

#     print('Setting power auto range on')
#     pm.setPowerAutoRange(c_int16(1))

#     print('Set Analog Output slope to {} V/W'.format(params.pm_slope))
#     pm.setAnalogOutputSlope(c_double(params.pm_slope))

#     print('Setting input filter state to off for higher BW')
#     pm.setInputFilterState(c_int16(0))
# #Initialize SPADs
# spads=[]
# for address in params.spad_addresses:
#     print('ATTEMPTING TO CONNECT TO ', address)
#     try:
#         from instrumental.drivers.spad.id120 import ID120
#         spads.append(ID120(visa_address=address))
#     except:
#         print('ID120 SPAD unavailable: {}'.format(sys.exc_info()))
#         break
#     else:
#         print('SPAD connected, setting parameters')
#         spads[-1].bias = Q_(int(params.spad_bias*1e6), 'uV')
#         spads[-1].threshold = Q_(int(params.spad_threshold*1e6), 'uV')
#         spads[-1].run = True
#         spads[-1].integration_time=Q_(2000,'ms')
# exp_before=datetime.datetime.now()

# m = spads[-1].count.magnitude
# exp_after=datetime.datetime.now()
# timedelta = (exp_after-exp_before).total_seconds()
# print('integration time:',spads[-1].integration_time)
# print('photon count: ',m)
# print('time:',timedelta)
# print('temp',spads[-1].temp)
# #Initialize Switch
# # Test DICON optical switch connection

# from drivers.dicon import DiConOpticalSwitch

# switch = DiConOpticalSwitch(port='COM7', verbose=True)
# print('Opened serial port to DiCon Switch')
# if switch.identify() > 0:
#     # Test channel switch
#     switch.set_channel(int(0))
#     sleep(0.5)
#     print('channel on {}'.format(switch.get_channel()))
# else:
#     print('No reply from DiCon switch module, check connection between serial cable and switch')

#     switch.close()
#     switch = None
