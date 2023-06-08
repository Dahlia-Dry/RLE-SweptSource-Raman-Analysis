# -*- coding: utf-8 -*-
"""
V4 add one shot to optimize cavity alignment in each step including idle error

Created on Thu Nov 19 20:23:48 2020

@author: User

based on V2, created Nov 9 2020

chnaging so that idle status doesn't restart the process'
and also allows data collection if wanelength is close enough

within status 3, no maintaining of tolerance is required. data is simply collected at the measured wavelength

laser object as an input instead of re-calling it

"""



def M2_tune(laser,target_wavelength,timestamp_str):

    #imports

    #from m2_solstis_v2 import M2_Solstis
    #laser = M2_Solstis()
    import numpy as np
    from time import sleep
    #from datetime import datetime
    #import csv

    #laser.lock('off')

    # tuning times parameters

    # wait_time_while_tuning = 20 # time [sec] for laser to attempt tuning before polling status
    wait_time_while_tuning = 2 # [sec] during test

    # wait_time_while_maintaining = 2 # [sec] to allow settling

    maintaining_tolerance = 0.015

    wl_str=str(target_wavelength)

    error_count=0
    max_error_count = 3

    tuning_count=0
    max_tuning_count = 3

    #maintaining_count=0
    #max_maintaining_count = 3

    success = [] # initializing tuning success indicator

    # creating laser log to be saved as csv
    laser_log = []

    laser_log.append('max_error_count = {} \n '.format(max_error_count))
    laser_log.append('max_tuning_count = {} \n'.format(max_tuning_count))
    #laser_log.append('max_maintaining_count = {} \n '.format(max_maintaining_count))

    status = -1 # initializing

    laser_log.append('Initializing laser poll status = {} \n '.format(status))

    #print('starting tuning to {} nm  '.format(target_wavelength))
    #laser_log.append('starting tuning to {} nm  '.format(target_wavelength))

    measured_wavelength = 0 #initialize

    laser_log.append('Initializing measured wavelength to 0')

    while status != 3:

        measured_wavelength = laser.poll_wavelength() # getting actual wavelength read
        laser_log.append('wavelength from wavemeter is {} '.format(measured_wavelength))

        # checking error from previous rounds and logging every loop

        laser_log.append('error_count = {} \n'.format(error_count))
        laser_log.append('tuning_count = {} \n'.format(tuning_count))
        #laser_log.append('maintaining_count = {} \n'.format(maintaining_count))

        if error_count > max_error_count:
            print('Max Error count reached. Tuning failed ')
            laser_log.append('Max error count reached. Tuning failed ')
            success = 0
            laser.stop()
            break

        if tuning_count > max_tuning_count:
            print('Max runing count reached. Tuning failed ')
            laser_log.append('Max tuning count reached. Tuning failed ')
            success = 0
            laser.stop()
            break

        if status == -1:    #just started

            laser_log.append('laser status is now {} \n'.format(status))

            laser.set_wavelength(wavelength = target_wavelength)

            print('M2_Solstis: setting wavelength to {} '.format(target_wavelength))
            laser_log.append('setting wavelength to = {} '.format(target_wavelength))
            #print('sleep tuning commenced')

            sleep(wait_time_while_tuning)

            # after giving the laser some time we check status
            #laser.one_shot()

            #sleep(5)
            #measured_wavelength = laser.poll_wavelength() #measuring the current wavelength
            #laser_log.append('wavelength from wavemeter is now {} nm '.format(measured_wavelength))
            #print('current wavelength from wavemeter is now {} nm '.format(measured_wavelength))

            status = laser.poll_status #getting current laser tuning status

            #laser_log.append('laser status is now {} \n'.format(status))
            #print('current laser status is now {} \n'.format(status))

        elif status == 0:
            #idle happend. idle count+1. if wavelength is close enough collect data, else reset wavelength. stop tuning.

            laser_log.append('ERROR M2_Solstis: Status 0: idle. software inactive!')
            print('ERROR M2_Solstis: idle. software inactive!')
            #print('M2_Solstis: resetting to {}'.format(target_wavelength))

            measured_wavelength = laser.poll_wavelength()

            if np.abs((measured_wavelength - target_wavelength)) > maintaining_tolerance:

                #laser.one_shot()

                #sleep(wait_time_while_tuning) # wait!

                status = laser.poll_status # check again

                error_count=error_count+1

            else:

                status = 3

                #laser.stop ()
                #laser.lock('on')

                laser_log.append('despite idle wavelength is close and data will be acquired')

                print('moving forward with data acquisition')


        elif status == 1:
            #no wavameter.  stop tuning.

            # laser.set_wavelength(wavelength = int(target_wavelengths[wi]))
            laser_log.append('ERROR M2_Solstis: Status 1: failed poll wavelength, no wavemeter')
            print('ERROR M2_Solstis: failed poll wavelength, no wavemeter')

            laser.stop()
            error_count = error_count+1

            status = -1  # going back to the while loop while increasing error count

        elif status == 2:

            #tuning in process. do nothing. wait and poll status again

            laser_log.append('Status = 2, Tuning still in progress, waiting and trying to poll status again: # {} \n'.format(tuning_count))
            tuning_count = tuning_count+1

            print('M2_Solstis: Tuning laser wavelength. Trying {} \n'.format(tuning_count))
            #print('M2_Solstis: Current wavelength from wavemeter is {}'.format(measured_wavelength))

            sleep(wait_time_while_tuning)

            status = laser.poll_status
            #print(status)

    else: #status=3 laser is maintaining wavelength

        laser_log.append('laser status is now {} (should only be 3) \n'.format(status))
        print('laser status is now {} (ready to acquire) \n'.format(status))

        measured_wavelength = laser.poll_wavelength() #measuring the current wavelength

        laser_log.append('wavelength from wavemeter is now {} nm '.format(measured_wavelength))
        laser_log.append('laser status is now {} and maintaining. READY \n'.format(status))
        print('M2_Solstis: maintaining target wavelength at {} and ready for data Collection.'.format(measured_wavelength))

        success = 1

        laser.stop()
        #laser.lock('on')


    return success, measured_wavelength
