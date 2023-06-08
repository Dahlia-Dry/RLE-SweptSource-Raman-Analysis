from datalog import *
import params

#LASER CONTROL FUNCTIONS
def instrument_connect(datalog):
    if params.test_mode:
        return
    global laser
    global pm
    global spad
    global switch
    global wavelength
    if laser is None:
        # Initialize Superlum laser
        try:
            from drivers.superlum import Superlum
            laser = Superlum(port='COM4', verbose=False)
            laser.connect()
        except:
            datalog.add('Error connecting to Superlum {}'.format(sys.exc_info()))
            laser = None
            laser_status='DISCONNECTED-ERROR'
        else:
            datalog.add('Connected to Superlum through serial port {}'.format(laser.port))
            laser.set_mode(mode='T') # single tone mode
            laser.verbose = True
            laser.get_status()
            laser.verbose = False
            wavelength = laser.get_wavelength()
            laser.set_mode(mode='W')
            laser_status='CONNECTED-WARMING UP'
    """if pm is None:
        #Intialize ThorLabs Power Monitor
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
            datalog.add('Could not open Thorlabs Power meter : {}'.format(sys.exc_info()))
            pm_status='DISCONNECTED-ERROR'
        else:
            datalog.add('Thorlabs Powermeter connected')

            pm.setWavelength(c_double(wavelength))
            datalog.add('Set wavelength to {} nm'.format(wavelength))

            print('Setting power auto range on')
            pm.setPowerAutoRange(c_int16(1))

            print('Set Analog Output slope to {} V/W'.format(params.pm_slope))
            pm.setAnalogOutputSlope(c_double(params.pm_slope))

            print('Setting input filter state to off for higher BW')
            pm.setInputFilterState(c_int16(0))
            pm_status='CONNECTED'
    if None in spad.values():
        #Initialize SPAD
        for address in spad:
            print('ATTEMPTING TO CONNECT TO ', address)
            if spad[address]==None:
                try:
                    from instrumental.drivers.spad.id120 import ID120
                    spad[address]=ID120(visa_address=address)
                except:
                    print('ID120 SPAD unavailable: {}'.format(sys.exc_info()))
                    datalog.add('ID120 SPAD unavailable: {}'.format(sys.exc_info()))
                else:
                    datalog.add('SPAD connected, setting parameters')
                    spad[address].bias = Q_(int(params.spad_bias*1e6), 'uV')
                    spad[address].threshold = Q_(int(params.spad_threshold*1e6), 'uV')
                    spad[address].run = True
                    spad_status='CONNECTED'
        if all([value==None for value in spad.values()]): #none of the spads connected
            spad_status='DISCONNECTED-ERROR'
    if switch is None:
        #Initialize Switch
        try:
            from drivers.dicon import DiConOpticalSwitch

            switch = DiConOpticalSwitch(port='COM3', verbose=False)
        except:
            print('Error cannot connect to DiCon Switch')
        else:
            print('Opened serial port to Dicon Switch')
            if switch.identify() > 0:
                # Test channel switch
                switch.set_channel(0)
                sleep(0.5)
                print('channel on {}'.format(switch.get_channel()))
            else:
                print('No reply from DiCon switch module, check connection between serial cable and switch')
                switch.close()
                switch = None
    instrument_status={'laser':laser_status,'pm':pm_status,'spad':spad_status}"""
    return datalog

def check_status(datalog):
    if params.test_mode:
        return
    global laser
    global pm
    global spad
    global switch
    if laser is not None:
        laser.get_status()
        datalog.add('querying laser status...')
        if laser.aotf_tec:
            datalog.add('AOTF TEC ON...')
        if laser.aotf_tec_stable:
            datalog.add('AOTF TEC STABLE!')
        if laser.sld_tec:
            datalog.add('SLD TEC ON...')
        if laser.sld_tec_stable:
            datalog.add('SLD TEC STABLE!')
        if laser.laser_rdy:
            datalog.add('LASER READY')
        if laser.aotf_tec and laser.aotf_tec_stable and laser.sld_tec and laser.sld_tec_stable:
            laser_status='CONNECTED-READY TO USE @ {} nm'.format(laser.get_wavelength())
    """if not all([value==None for value in spad.values()]):
        spad_status=''
        for address in spad.keys():
            spad_status+='Ch'+str(params.spad_addresses[address])+ ' : spad'+address.split('::')[3]+' {}, {:0<4.4g}C'.format(spad[address].state, spad[address].temp.magnitude/1e3)+buffer
    if pm is not None:
        pm_status='CONNECTED - TUNED TO {} nm'.format(wavelength)
    instrument_status={'laser':laser_status,'pm':pm_status,'spad':spad_status}"""
    return datalog

def parse_laser_output_status(status_str):
    status_list = status_str.split('\n')
    print(status_list)
    #output = [x for x in status_list if "SLD laser output" in x][0]
    return output


laser=None
pm=None
spad=dict(zip([ad for ad in params.spad_addresses.keys()],[None for _ in params.spad_addresses.values()]))
switch=None
datalog=Datalog()
wavelength=-1
datalog=instrument_connect(datalog)
#print(str(datalog))
datalog=check_status(datalog)
#print(str(datalog))
#x=input()
laser.set_output(on=True)
laser.verbose=True
status=laser.get_status()
laser.verbose=False
print('On?',laser.laser_on)
