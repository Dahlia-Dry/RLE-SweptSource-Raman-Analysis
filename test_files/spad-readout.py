import sys
sys.path.append("..")
import time
from gui_components import params
from time import sleep
from instrumental import Q_
from ctypes import cdll,c_long, c_ulong, c_uint32,byref,create_string_buffer,c_bool,c_char_p,c_int,c_int16,c_double, sizeof, c_voidp
import datetime
spads=[]
for address in ['USB0::0x1DDC::0x0330::002001::INSTR']:
    print('ATTEMPTING TO CONNECT TO ', address)
    try:
        from instrumental.drivers.spad.id120 import ID120
        spads.append(ID120(visa_address=address))
        print('spad imported')
    except:
        print('ID120 SPAD unavailable: {}'.format(sys.exc_info()))
        break
    else:
        print('SPAD connected, setting parameters')
        spads[-1].bias = Q_(int(params.spad_bias*1e6), 'uV')
        spads[-1].threshold = Q_(int(params.spad_threshold*1e6), 'uV')
        spads[-1].run = True
        spads[-1].integration_time = Q_(params.spad_intTime,'ms')
        spads[-1].set_temp = Q_(int(params.spad_temp),'millidegC')
        
exp_before=datetime.datetime.now()

while True:
    exp_before= datetime.datetime.now()
    m = spads[-1].count.magnitude
    time.sleep(params.spad_intTime/1000)
    exp_after=datetime.datetime.now()
    timedelta = (exp_after-exp_before).total_seconds()
    Temp_read = spads[-1].temp.magnitude/1e3
    print('time: ',timedelta)
    print('photon count: ',m)
    print('temp: ',Temp_read)