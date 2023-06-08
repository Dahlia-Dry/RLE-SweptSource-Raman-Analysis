from drivers.superlum import Superlum
from drivers.m2_solstis_v3 import M2_Solstis
from drivers.M2_tune_v4 import M2_tune
from datetime import datetime
from . import params
from time import sleep

class Laser(object):
    def __init__(self,name):
        self.name = name
        if self.name =='superlum':
            self.driver = Superlum(port='COM8', verbose=False)
            self.driver.connect()
        elif self.name == 'tisapph':
            self.driver = M2_Solstis()
        else:
            raise Exception('Unknown laser ',self.name)
    def get_port(self):
        if self.name =='superlum':
            return self.driver.port
        elif self.name == 'tisapph':
            return "ssh"
    def get_status(self):
        if self.name =='superlum':
            self.driver.get_status()
        elif self.name == 'tisapph':
            pass
    def is_ready(self):
        if self.name =='superlum':
            return self.driver.aotf_tec and self.driver.aotf_tec_stable and self.driver.sld_tec and self.driver.sld_tec_stable
        elif self.name == 'tisapph':
            return self.driver is not None
    def is_on(self):
        if self.name =='superlum':
            return self.driver.laser_on
        elif self.name == 'tisapph':
            return self.driver is not None
    def warm_up(self):
        if self.name == 'superlum':
            self.driver.set_mode(mode='T') # single tone mode
            self.driver.verbose = True
            self.get_status()
            self.driver.verbose = False
            self.driver.set_mode(mode='W')
        elif self.name == 'tisapph':
            pass
    def output_on(self):
        if self.name =='superlum':
            self.driver.set_output(on=True)
        elif self.name == 'tisapph':
            return self.driver is not None
    def output_off(self):
        if self.name =='superlum':
            self.driver.set_output(on=False)
        elif self.name == 'tisapph':
            return self.driver is None
    def shut_down(self):
        if self.name =='superlum':
            self.driver.set_mode(mode='O')
            self.driver.close(shutdown=False)
        elif self.name == 'tisapph':
            self.driver.close()
    def get_wavelength(self):
        if self.name =='superlum':
            return self.driver.get_wavelength()
        elif self.name == 'tisapph':
            return self.driver.poll_wavelength()
    def set_wavelength(self,wl):
        if self.name == 'superlum':
            self.driver.set_wavelength(wavelength=wl)
            tune_success=True
        elif self.name == 'tisapph':
            timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
            tune_success, measured_wavelength = M2_tune(self.driver,float(wl),timestamp_str)
            if str(tune_success)=='0':
                tune_success=False
            else:
                if abs(measured_wavelength-wl)>params.lambda_tolerance:
                    sleep(5)
                    print('wavelength error tolerance exceeded. Retrying tune.')
                    tune_success, measured_wavelength = M2_tune(self.driver,float(wl),timestamp_str)
                    if abs(measured_wavelength-wl)>params.lambda_tolerance:
                        tune_success= False
                tune_success=True
            print('tune_success',tune_success)
        return tune_success
    def realign_beam(self):
        if self.name == 'superlum':
            return "null"
        elif self.name =='tisapph':
            return self.driver.one_shot()
            
            
    
