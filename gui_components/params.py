from sys import platform
from datetime import datetime
from gui_components.attribute import Attribute
import os

#_______________________________________________________________________________
#TOGGLE TEST MODE_______________________________________________________________
#test_mode=True nullifies instrument ops, returns dummy data to allow for remote software testing
test_mode=True
verbose = False
#_______________________________________________________________________________

#CONSOLE PARAMETERS____________________________________________________________
measurement_delay=2 #delay to make sure readings consistent after wavelength adjustment [s]
prog_interval=0.5 #interval to check progress [s]
check_wavelength = True
check_wavelength_interval= 10 #interval to check wavelength [s]
check_alignment = False
alignment_interval = 900 #interval to check laser cavity beam alignment [s]
auto_backup=True #set to True will periodically write data to destination zip
autobackup_interval = 3600 #interval to download backup copy of data [s]
web_host = False #if being hosted on a server other than localhost (heroku)
verbose_log = True
#_______________________________________________________________________________

#WORKING DIRECTORY______________________________________________________________
#different working directory for windows vs mac
if web_host:
    working_directory = '"'+os.path.join(os.path.expanduser('~'),'Downloads')+'"'
else:
    if platform == 'darwin': #Mac
        working_directory =  '"/Users/dahlia/Projects/RLE/ssr-test-outputs"'
    else:
        working_directory= '"C:/Users/SweptSourceRaman/Dropbox/Ram Lab Raman Data Repository/Dahlia Spectra"' #default path to save data to
#_______________________________________________________________________________

#LASER___________________________________________________________________________
default_laser = 'tisapph'
available_lasers=['superlum','tisapph']
lambda_tolerance=0.01
filter_wl=884 #filter wavelength [nm]
#_______________________________________________________________________________

#SPAD___________________________________________________________________________
#spad_addresses is a dict that maps spad visa address to channel on dicon switch
#available spad addresses:'USB0::0x1DDC::0x0330::002008::INSTR','USB0::0x1DDC::0x0330::002001::INSTR','USB0::0x1DDC::0x0330::002000::INSTR'
default_spad_mapping = {'USB0::0x1DDC::0x0330::002008::INSTR':None,'USB0::0x1DDC::0x0330::002001::INSTR':1,'USB0::0x1DDC::0x0330::002000::INSTR':None}
spad_addresses={'USB0::0x1DDC::0x0330::002001::INSTR':1}
spad_intTime=1000 #spad integration time [ms]
spad_bias=200.0 #spad voltage bias [V]
spad_threshold=0.1 #spad voltage threshold [V]
spad_temp=-40000 #spad temp in milidegC
force_spad_cool = True
#_______________________________________________________________________________

#POWER MONITORING________________________________________________________________
pm_slope = 0.001 #power meter slope
low_power_warning = 1.0e-7 #power level in W at which to warn user that power output is low
#_______________________________________________________________________________

#EDIT METADATA ATTRIBUTES HERE________________________________________________
meta={
    #user fields are entered by user
    'experiment_name': Attribute(None,'text',None,'experiment',),
    'analytes': Attribute(None,list, None,'sample'),
    'target_analyte':Attribute(None,'text', None,'sample',editable=False,visible=False),
    'medium': Attribute('distilled water','text',None,'experiment',),
    'notes': Attribute(None,'text',None,'experiment'),
    'filename': Attribute(None,'text',None,'experiment',editable=False,visible=False),
    #time fields are set by params and software
    'starttime': Attribute(None,'datetime',None,'experiment',editable=False,),
    'endtime': Attribute(None,'datetime',None,'inst',editable=False),
    #detector fields 
    'laser':Attribute(default_laser,'text',None,'detector',editable=True),
    'spad_name': Attribute(None,'text',None,'detector',editable=True),
    'switch_channel': Attribute(None,'text',None,'detector',editable=True),
    'filter_wavelength': Attribute(filter_wl,'numeric',None,'detector',editable=True),
    'spad_integration_time': Attribute(spad_intTime,'numeric',None,'detector',editable=True),
    'spad_bias': Attribute(spad_bias,'numeric',None,'detector',editable=True),
    'spad_threshold': Attribute(spad_threshold,'numeric',None,'detector',editable=True),
    #experiment fields are set by user for experiment
    'integration':Attribute(None,'numeric','exposure time [s]','experiment',editable=False),
    'repetitions':Attribute(None,'numeric','number of exposures at each wavelength','experiment',editable=False),
    'seq_num':Attribute(1,'numeric','index number if part of time series','experiment',editable=False),
    'excitation_wavelengths':Attribute(None,list,None,'experiment',editable=False),
    'excitation_ramanshifts':Attribute(None,list,None,'experiment',editable=False),
    #datafile fields are saved copies of the original data for analysis purposes
    'data_operations':Attribute(None,'text',None,'processing',editable=False),
    'spad_datafile':Attribute(None,'text',None,'datafile',editable=False,visible=False),
    'power_datafile':Attribute(None,'text',None,'datafile',editable=False,visible=False)
}