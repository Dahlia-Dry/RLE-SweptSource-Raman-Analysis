import sys
sys.path.append('..')
from time import sleep
from gui_components.laser import *


laser = Laser('superlum')
laser.warm_up()
wavelength = laser.get_wavelength()
print('current wl: ', wavelength)

for wl in range(770,826):
    laser.set_wavelength(wl)
    print('current wl: ', wl)
    sleep(60)
    laser.output_off()
    print('turning output off')
    sleep(10)
    print('turning output on')
    laser.output_on()

