"""
make a copy of this file in this folder, call it params.py, and tweak as desired
"""

from sys import platform

#_______________________________________________________________________________
#TOGGLE TEST MODE_______________________________________________________________
#test_mode=True nullifies instrument ops, returns dummy data to allow for remote software testing
test_mode=True
#_______________________________________________________________________________

#CONSOLE PARAMETERS____________________________________________________________
data_type='sweptsource' #data type, 'biomod' or 'sweptsource'
power_monitoring=True #if False, write null data to .power files
auto_backup=True #set to True will periodically write data to destination zip
filter_wl=853.75 #filter wavelength [nm]
spad_intTime=1000 #spad integration time [ms]
spad_bias=200.0 #spad voltage bias [V]
spad_threshold=0.1 #spad voltage threshold [V]
pm_slope = 0.001 #power meter slope
measurement_delay=1 #delay to make sure readings consistent after wavelength adjustment [s]
prog_interval=1000 #interval to check progress [ms]
#_______________________________________________________________________________

#WORKING DIRECTORY______________________________________________________________
#different working directory for windows vs mac
if platform == 'darwin': #Mac
    working_directory = '"/Users/dahlia/Projects/raman/python-pipeline/test_files"'
else:
    working_directory= '"C:/Users/User/Dropbox (MIT)/Ram Lab Raman Data Repository/Dahlia Spectra"' #default path to save data to
#_______________________________________________________________________________

#SPAD ADDRESSES_________________________________________________________________
#spad_addresses is a dict that maps spad visa address to channel on dicon switch
#available spad addresses:'USB0::0x1DDC::0x0330::002008::INSTR','USB0::0x1DDC::0x0330::002001::INSTR','USB0::0x1DDC::0x0330::002000::INSTR'
spad_addresses={'USB0::0x1DDC::0x0330::002001::INSTR':1,'USB0::0x1DDC::0x0330::002008::INSTR':2}
#_______________________________________________________________________________