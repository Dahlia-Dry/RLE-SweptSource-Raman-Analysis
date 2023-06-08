#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
GUI for FDA project 830nm Swept Source Raman Network
Required Instruments:
1. Superlum laser
2. Thorlabs PM101A
3. DICON FiberOptic Switch
4. NI cDAQ-9171
5. IDQuantique SPAD
6. DICON FiberOptic Switch
"""

import sys
from pyqtgraph.Qt import QtGui, QtCore
from os import path
import csv

import numpy as np
import matplotlib.pyplot as plt
from instrumental import Q_
from instrumental.drivers.util import visa_timeout_context

import pyqtgraph as pg
import pyqtgraph.exporters
from pyqtgraph.ptime import time

from time import sleep
from datetime import datetime
import time

import drivers.redpitaya_scpi as scpi
import socket
from ctypes import cdll,c_long, c_ulong, c_uint32,byref,create_string_buffer,c_bool,c_char_p,c_int,c_int16,c_double, sizeof, c_voidp

from nidaqmx.constants import AcquisitionType

# GUI
class Window(QtGui.QMainWindow):
    # ize class variables
    timer_factor = 1.2e-3

    def __init__(self):

        # Initialize instance variables
        self.ui_refresh_period = 100 # ms
        self.ui_buffer_length = 500 # data points

        self.spectra_data = np.array([])
        self.power_data = []
        self.tap_power_data = []
        self.power_data_timestamps = []
        self.power_data_timezero = time.time()
        self.current_wl =0.0 # nm
        self.data_dir = path.normpath('./')

        self.exp_running = False
        self.hr4000_params={'IntegrationTime_micros':100000}

        # Wavelength sweep parameters
        self.wavelength = 786.0
        self.wavelength_start = Q_(786.0, 'nm')
        self.wavelength_stop = Q_(788.0, 'nm')
        self.wavelength_step = Q_(1.0, 'nm')
        self.wavelength_bias = Q_(-2.5, 'V')
        self.exp_N = 1

        # Measurement parameters
        self.intTime = 2.0 # sec
        self.sample = "Polystyrene"

        # Instrument Parameters
            # DAQ
        self.sampling_freq = 1000 # daq sampling frequency
        self.pm_slope = 0.001
            # Optics
        self.filter_wl=853.75 # Alluxa filter center wavelength
            # Switch
        self.total_channels = 12
        self.channel = 0
            # SPAD
        self.spad_intTime = 0.200 # s
        self.spad_bias = 190.0 #V
        self.spad_threshold = 0.1 #V

        self.spad_timer = None
        self.laser_timer = None

        self.initialize_instruments()

        self.initialize_gui()

        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.refresh_ui)
        self.timer.start(self.ui_refresh_period) # in msec

    def initialize_instruments(self):
        self.laser=None
        self.switch= None
        self.pm = None
        self.pm_tap = None
        self.spad = None
        self.daq = None

        # Initialize Superlum laser
        try:
            from drivers.superlum import Superlum

            self.laser = Superlum(port='COM4', verbose=False)
            self.laser.connect()
        except:
            print('Error connecting to Superlum {}'.format(sys.exc_info()))
            self.laser = None
        else:
            print('Connected to Superlum through serial port {}'.format(self.laser.port))
            self.laser.set_mode(mode='T') # single tone mode

            self.laser.verbose = True
            self.laser.get_status()
            self.laser.verbose = False
            self.wavelength = self.laser.get_wavelength()

        # Test DICON optical switch connection
        try:
            from drivers.dicon import DiConOpticalSwitch

            self.switch = DiConOpticalSwitch(port='COM3', verbose=False)
        except:
            print('Error cannot connect to DiCon Switch')
        else:
            print('Opened serial port to Dicon Switch')
            if self.switch.identify() > 0:
                # Test channel switch
                self.switch.set_channel(self.channel)
                sleep(0.5)
                print('channel on {}'.format(self.switch.get_channel()))
            else:
                print('No reply from DiCon switch module, check connection between serial cable and switch')

                self.switch.close()
                self.switch = None

        print()
        # Open connection to Thorlabs PM101A powermeter
        try:
            from drivers.TLPM import TLPM

            self.pm = TLPM()
            deviceCount = c_uint32()
            self.pm.findRsrc(byref(deviceCount))

            print("devices found: " + str(deviceCount.value))

            resourceName = create_string_buffer(1024)

            for i in range(0, deviceCount.value):
                self.pm.getRsrcName(c_int(i), resourceName)
                print(c_char_p(resourceName.raw).value)
                break

            self.pm.open(resourceName, c_bool(True), c_bool(True))

            message = create_string_buffer(1024)
            self.pm.getCalibrationMsg(message)
            print(c_char_p(message.raw).value)

        except:
            self.pm = None
            print('Could not open Thorlabs Power meter : {}'.format(sys.exc_info()))
        else:
            print('Thorlabs Powermeter connected')

            self.pm.setWavelength(c_double(self.wavelength))
            print('Set wavelength to {} nm'.format(self.wavelength))

            print('Setting power auto range on')
            self.pm.setPowerAutoRange(c_int16(1))

            print('Set Analog Output slope to {} V/W'.format(self.pm_slope))
            self.pm.setAnalogOutputSlope(c_double(self.pm_slope))

            print('Setting input filter state to off for higher BW')
            self.pm.setInputFilterState(c_int16(0))


        # Setup NI DAQ, tested compatibility with NI USB-6259, NI-488.2 version 19.5
        # NI 9239 in cDAQ-9171, needs NI DAQmx driver https://www.ni.com/en-us/support/downloads/drivers/download.ni-daqmx.html#382067
        print()
        try:
            import nidaqmx
        #     print('Setting up connection with NI USB-6159')
        #     self.daq = nidaqmx.Task()
        #     self.daq.ai_channels.add_ai_voltage_chan("Dev1/ai3", min_val=0.0, max_val=10.0) # Channel to Femto detector
        #     self.daq.ai_channels.add_ai_voltage_chan("Dev1/ai1", min_val=0.0, max_val=2.5) # channel to tap pm
        # #     self.daq.timing.cfg_samp_clk_timing(int(self.sampling_freq))) #, samps_per_chan=int(total_samples)) , to sync with redpitaya use sampling_freq

            print('Setting up connection with NI 9239 in cDAQ-9171 chassis')
            self.daq = nidaqmx.Task()
            self.daq.ai_channels.add_ai_voltage_chan("cDAQ1Mod1/ai0", min_val=0.0, max_val=10.0) # Channel to Femto detector
            self.daq.ai_channels.add_ai_voltage_chan("cDAQ1Mod1/ai1", min_val=0.0, max_val=2.5) # channel to tap pm
        except:
            print('NI-DAQ is unavailable: {}'.format(sys.exc_info()))
        else:
            # sampling freq is set in _init method
            self.daq.timing.cfg_samp_clk_timing(self.sampling_freq, sample_mode=AcquisitionType.CONTINUOUS)
            print('NI-DAQ connected with sampling rate {}'.format(self.sampling_freq))

            from nidaqmx.stream_readers import AnalogMultiChannelReader

            self.daq.in_stream.relative_to = nidaqmx.constants.ReadRelativeTo.MOST_RECENT_SAMPLE
            self.daq.in_stream.offset = 0
            # self.daq.in_stream.over_write = nidaqmx.constants.OverwriteMode
            self.daqreader = AnalogMultiChannelReader(self.daq.in_stream)
            self.daq.start()


        print()
        try:
            from instrumental.drivers.spad.id120 import ID120

            self.spad = ID120(visa_address='USB0::0x1DDC::0x0330::002008::INSTR')

        except:
            print('ID120 SPAD unavailable: {}'.format(sys.exc_info()))
            self.spad = None
        else:
            print('SPAD connected, setting parameters')
            self.spad.bias = Q_(int(self.spad_bias*1e6), 'uV')
            self.spad.threshold = Q_(int(self.spad_threshold*1e6), 'uV')
            self.spad.run = True
            # self.spad.temp = -40000 # -50 degC


    def initialize_gui(self):
        super(Window, self).__init__()
        self.setGeometry(100, 100, 1000, 800)
        self.setWindowTitle("POE FDA Project 830nm Swept Source Raman Network")
        # self.setWindowIcon(QtGui.QIcon('pythonlogo.png'))

        # Menu definition
        mainMenu = self.menuBar()

        ## File menu
        fileMenu = mainMenu.addMenu('&File')

        processDataAction = QtGui.QAction("Process &Data", self)
        processDataAction.setShortcut("Ctrl+D")
        processDataAction.setStatusTip('Process data to spectra')
        processDataAction.triggered.connect(self.processDataEvent)
        fileMenu.addAction(processDataAction)

        extractAction = QtGui.QAction("&Quit Application", self)
        extractAction.setShortcut("Ctrl+Q")
        extractAction.setStatusTip('Leave The App')
        # extractAction.triggered.connect(self.close_application)
        extractAction.triggered.connect(self.closeEvent)
        fileMenu.addAction(extractAction)


        ## Experiments menu, experiment availability aware
        experimentMenu = mainMenu.addMenu('&Experiments')

        if self.daq is not None:
            measFemtoAction = QtGui.QAction("Measure Femto", self)
            measFemtoAction.setShortcut("Ctrl+F")
            # measIVAction.setStatusTip('Probe device before taking measurement')
            measFemtoAction.triggered.connect(self.exp_femto)
            experimentMenu.addAction(measFemtoAction)
        else:
            print('NI DAQ not available disabling Femto measurement menu')

        if self.spad is not None:
            self.measSpadAction = QtGui.QAction("Measure SPAD", self)
            self.measSpadAction.setShortcut("Ctrl+S")
            # measIVAction.setStatusTip('Probe device before taking measurement')
            self.measSpadAction.triggered.connect(self.exp_spad)
            experimentMenu.addAction(self.measSpadAction)

            self.measSpadAction.setEnabled(False)

            if self.laser is not None:
                self.measWSSpadAction = QtGui.QAction("Wavelength Sweep SPAD", self)
                self.measWSSpadAction.setShortcut("Ctrl+A")
                # measIVAction.setStatusTip('Probe device before taking measurement')
                self.measWSSpadAction.triggered.connect(self.exp_wlsweep_spad)
                experimentMenu.addAction(self.measWSSpadAction)

                self.measWSSpadAction.setEnabled(False)
            else:
                print('Laser is not available disabling SPAD wavelength sweep measurement menu')
        else:
            print('SPAD not available disabling SPAD measurement menu')

        # if self.smu is not None:
        #     measIVAction = QtGui.QAction("Measure I&V Curve", self)
        #     measIVAction.setShortcut("Ctrl+M")
        #     measIVAction.setStatusTip('Probe device before taking measurement')
        #     measIVAction.triggered.connect(self.exp_iv)
        #     experimentMenu.addAction(measIVAction)
        # else:
        #     print('SMU not available disabling IV curve menu')
        #
        # if self.pm is not None:
        #     measIllumAction = QtGui.QAction("Measure &Illumination", self)
        #     measIllumAction.setShortcut("Ctrl+I")
        #     measIllumAction.setStatusTip('Place over power meter to measure illumination')
        #     measIllumAction.triggered.connect(self.exp_illum)
        #     experimentMenu.addAction(measIllumAction)
        # else:
        #     print('PM not available disabling illumination calibration menu')
        #
        # if self.spec is not None:
        #     measSpectraAction = QtGui.QAction("Measure &Spectra", self)
        #     measSpectraAction.setShortcut("Ctrl+S")
        #     measSpectraAction.setStatusTip('Measuring spectra')
        #     measSpectraAction.triggered.connect(self.exp_spectra)
        #     experimentMenu.addAction(measSpectraAction)
        #
        #     if self.smu is not None:
        #         measPhotocurrentAction = QtGui.QAction("Measure &Photocurrent", self)
        #         measPhotocurrentAction.setShortcut("Ctrl+P")
        #         measPhotocurrentAction.setStatusTip('Place over device to measure Photocurrent')
        #         measPhotocurrentAction.triggered.connect(self.exp_photocurrent)
        #         experimentMenu.addAction(measPhotocurrentAction)
        # else:
        #     print('Spectrometer not available, disabling spectra measurement menu')

        # Generate status bar
        self.statusBar()

        # Set Window as central widget
        self.w = QtGui.QWidget()
        self.setCentralWidget(self.w)

        ## Create a grid layout to manage the widgets size and position
        self.layout = QtGui.QGridLayout()
        self.w.setLayout(self.layout)

        row = 0
    ###### UI group controls
        self.ui_group = QtGui.QGroupBox('UI settings')
        glayout = QtGui.QGridLayout()
        self.ui_group.setLayout(glayout)
        subrow=0

        glayout.addWidget(QtGui.QLabel('UI refresh period [msec]'), subrow,0, 1,1)

        self.edit_uiTime = QtGui.QLineEdit('{:d}'.format(self.ui_refresh_period))
        self.edit_uiTime.returnPressed.connect(self.set_ui_params)
        glayout.addWidget(self.edit_uiTime, subrow, 1,  1,1)

        glayout.addWidget(QtGui.QLabel('Plots buffer length [int]'), subrow,2, 1,1)
        self.edit_uiBufferLength = QtGui.QLineEdit('{:d}'.format(self.ui_buffer_length))
        self.edit_uiBufferLength.returnPressed.connect(self.set_ui_params)
        glayout.addWidget(self.edit_uiBufferLength, subrow, 3,  1,1)

        subrow = subrow+1

        self.check_all = QtGui.QCheckBox('Data Acquisition')
        self.check_all.stateChanged.connect(self.toggle_all_output)
        self.check_all.setCheckState(0) # off
        glayout.addWidget(self.check_all, subrow, 0, 1, 1)
        subrow = subrow+1

        self.layout.addWidget(self.ui_group, row,0,  subrow,4)
        row = row + subrow


    ###### Experiment group controls

        self.exp_group= QtGui.QGroupBox('Experiment settings')
        glayout = QtGui.QGridLayout()
        self.exp_group.setLayout(glayout)
        subrow=0

        glayout.addWidget(QtGui.QLabel('Sample:'), subrow,0, 1,1)
        self.edit_sample = QtGui.QLineEdit(self.sample)
        self.edit_sample.returnPressed.connect(self.set_ui_params)
        glayout.addWidget(self.edit_sample, subrow, 1,  1,1)
        subrow = subrow+1

        glayout.addWidget(QtGui.QLabel('Experiment Integration time [sec]'), subrow,0, 1,1)
        self.edit_intTime = QtGui.QLineEdit('{:g}'.format(self.intTime))
        self.edit_intTime.returnPressed.connect(self.set_ui_params)
        glayout.addWidget(self.edit_intTime, subrow, 1,  1,1)
        subrow = subrow+1

        self.layout.addWidget(self.exp_group, row,0,  subrow,4)
        row = row + subrow


        # Power meter related UI elements
        if self.pm is not None:
            self.pm_group= QtGui.QGroupBox('Power meter settings')
            glayout = QtGui.QGridLayout()
            self.pm_group.setLayout(glayout)
            subrow=0

            self.label_illumpower = QtGui.QLabel('Tap Power: ')
            self.label_illumpower.setStyleSheet("font: bold 10pt Arial; color: gray")
            glayout.addWidget(self.label_illumpower, subrow, 0, 1, 2)

            self.check_pm = QtGui.QCheckBox('Read Power Meter')
            self.check_pm.stateChanged.connect(self.toggle_pm_output)
            self.check_pm.setCheckState(0) # off
            glayout.addWidget(self.check_pm, subrow, 2, 1, 1)

            self.btn_save = QtGui.QPushButton('Save Power trace')
            self.btn_save.clicked.connect(self.save_power_trace)
            glayout.addWidget(self.btn_save, subrow, 3, 1,1) # save spectra button

            subrow = subrow+1

            self.layout.addWidget(self.pm_group, row,0,  subrow,4)
            row = row + subrow
        else:
            self.check_pm = None


        if self.laser is not None:
            ## Wavelength sweep box
            self.laser_group = QtGui.QGroupBox('Superlum laser control')

            glayout = QtGui.QGridLayout()
            self.laser_group.setLayout(glayout)

            subrow=0
            ## Laser button
            self.btn_laser_out = QtGui.QPushButton('Output On')
            if self.laser.laser_rdy:
                print('Laser warmed up and ready to use')
                self.btn_laser = QtGui.QPushButton('Shutdown Laser')
            else:
                self.btn_laser = QtGui.QPushButton('Warm up Laser')
                self.btn_laser_out.setEnabled(False)

            self.btn_laser.clicked.connect(self.laser_control)
            glayout.addWidget(self.btn_laser, subrow, 0, 1,1)

            self.btn_laser_out.clicked.connect(self.laser_output)
            glayout.addWidget(self.btn_laser_out, subrow, 1, 1,1)
            subrow = subrow+1

            glayout.addWidget(QtGui.QLabel('Wavelength [nm]:'), subrow,0,  1,1)
            self.edit_wavelength = QtGui.QLineEdit('{}'.format(self.wavelength))
            # self.edit_wavelength.editingFinished.connect(self.set_wavelength)
            glayout.addWidget(self.edit_wavelength, subrow,1,  1,1)

            self.btn_setwl = QtGui.QPushButton('Set Wavelength')
            self.btn_setwl.clicked.connect(self.set_wavelength)
            glayout.addWidget(self.btn_setwl, subrow, 2, 1,1)

            self.laser_timer = QtCore.QTimer()
            self.laser_timer.timeout.connect(self.check_laser_status)

            self.layout.addWidget(self.laser_group, row, 0, subrow,4)
            row =row+subrow

            ## Wavelength sweep box
            self.wlsweep_group = QtGui.QGroupBox('Wavelength Sweep Parameters')

            glayout = QtGui.QGridLayout()

            self.wlsweep_group.setLayout(glayout)

            subrow=0
            glayout.addWidget(QtGui.QLabel('   Start [nm]:'), subrow,0,  1,1)
            self.edit_wavelength_start = QtGui.QLineEdit('{}'.format(self.wavelength_start.magnitude))
            self.edit_wavelength_start.returnPressed.connect(self.set_sweep_params)
            glayout.addWidget(self.edit_wavelength_start, subrow, 1,  1,1)
            subrow = subrow+1


            glayout.addWidget(QtGui.QLabel('   End [nm]:'), subrow,0,  1,1)
            self.edit_wavelength_stop = QtGui.QLineEdit('{}'.format(self.wavelength_stop.magnitude))
            self.edit_wavelength_stop.returnPressed.connect(self.set_sweep_params)
            glayout.addWidget(self.edit_wavelength_stop, subrow,1,  1,1)
            subrow = subrow+1


            glayout.addWidget(QtGui.QLabel('   Step [nm]:'), subrow,0,  1,1)
            self.edit_wavelength_step = QtGui.QLineEdit('{}'.format(self.wavelength_step.magnitude))
            self.edit_wavelength_step.returnPressed.connect(self.set_sweep_params)
            glayout.addWidget(self.edit_wavelength_step, subrow,1,  1,1)
            subrow = subrow + 1
            #
            # glayout.addWidget(QtGui.QLabel('   Bias [V]:'), subrow,0,  1,1)
            # self.edit_wavelength_bias = QtGui.QLineEdit('{}'.format(self.wavelength_bias.magnitude))
            # self.edit_wavelength_bias.editingFinished.connect(self.set_sweep_params)
            # glayout.addWidget(self.edit_wavelength_bias, subrow,1,  1,1)
            # subrow = subrow + 1

            glayout.addWidget(QtGui.QLabel('   # of Repetitions'), subrow,0,  1,1)
            self.edit_exp_N = QtGui.QLineEdit('{}'.format(self.exp_N))
            self.edit_exp_N.returnPressed.connect(self.set_sweep_params)
            glayout.addWidget(self.edit_exp_N, subrow,1,  1,1)

            # self.btn_single = QtGui.QPushButton('Take single measurement')
            # self.btn_single.clicked.connect(self.take_single_measurement)
            # glayout.addWidget(self.btn_single, subrow, 2, 1,1) # save spectra button
            # subrow = subrow+1

            self.layout.addWidget(self.wlsweep_group, row,0,  subrow,4)
            row = row + subrow
        else:
            self.layout.addWidget(QtGui.QLabel('Wavelength [nm]:'), row,0,  1,1)
            self.edit_wavelength = QtGui.QLineEdit('{}'.format(self.wavelength_start.magnitude))
            self.edit_wavelength.editingFinished.connect(self.set_wavelength)
            self.layout.addWidget(self.edit_wavelength, row,1,  1,1)
            row = row+1


        if self.daq is not None:

            self.daq_group = QtGui.QGroupBox('NI-DAQ control')

            glayout = QtGui.QGridLayout()

            self.daq_group.setLayout(glayout)

            subrow=0
            self.label_daqdata = QtGui.QLabel('DAQ data: ')
            self.label_daqdata.setStyleSheet("font: bold 10pt Arial; color: gray")
            glayout.addWidget(self.label_daqdata, subrow, 0, 1, 2)

            self.check_daq = QtGui.QCheckBox('Read DAQ')
            self.check_daq.stateChanged.connect(self.toggle_daq_output)
            self.check_daq.setCheckState(0) # off
            glayout.addWidget(self.check_daq, subrow, 2, 1, 1)

            self.btn_save_daq = QtGui.QPushButton('Save DAQ trace')
            self.btn_save_daq.clicked.connect(self.save_daq_trace)
            glayout.addWidget(self.btn_save_daq, subrow, 3, 1,1) # save spectra button
            subrow = subrow+1

            glayout.addWidget(QtGui.QLabel('DAQ Sampling rate [Hz]'), row,0, 1,1)
            self.edit_sampRate = QtGui.QLineEdit('{:g}'.format(self.sampling_freq))
            self.edit_sampRate.returnPressed.connect(self.set_ui_params)
            glayout.addWidget(self.edit_sampRate, row, 1,  1,1)
            subrow = subrow+1

            self.layout.addWidget(self.daq_group, row,0,  subrow,4)
            row = row + subrow

        if self.spad is not None:

            self.spad_group = QtGui.QGroupBox('SPAD control')
            glayout = QtGui.QGridLayout()
            self.spad_group.setLayout(glayout)

            subrow=0
            self.label_spadState = QtGui.QLabel('SPAD State: {}'.format(self.spad.state))
            glayout.addWidget(self.label_spadState, subrow, 0, 1, 2)
            subrow = subrow+1

            self.label_spaddata = QtGui.QLabel('SPAD data: ')
            self.label_spaddata.setStyleSheet("font: bold 10pt Arial; color: gray")
            glayout.addWidget(self.label_spaddata, subrow, 0, 1, 2)

            self.check_spad = QtGui.QCheckBox('Read SPAD')
            self.check_spad.stateChanged.connect(self.toggle_spad_output)
            self.check_spad.setCheckState(0) # off
            glayout.addWidget(self.check_spad, subrow, 2, 1, 1)

            self.btn_save_spad = QtGui.QPushButton('Save SPAD trace')
            self.btn_save_spad.clicked.connect(self.save_spad_trace)
            glayout.addWidget(self.btn_save_spad, subrow, 3, 1,1)
            subrow = subrow+1

            glayout.addWidget(QtGui.QLabel('SPAD integration time [s]'), subrow,0, 1,1)
            self.edit_spad_intTime = QtGui.QLineEdit('{:g}'.format(self.spad_intTime))
            self.edit_spad_intTime.editingFinished.connect(self.set_spad_params)
            glayout.addWidget(self.edit_spad_intTime, subrow, 1,  1,1)
            subrow = subrow +1

            glayout.addWidget(QtGui.QLabel('SPAD Bias [V]'), subrow,0, 1,1)
            self.edit_spad_bias = QtGui.QLineEdit('{:g}'.format(self.spad_bias))
            self.edit_spad_bias.editingFinished.connect(self.set_spad_params)
            glayout.addWidget(self.edit_spad_bias, subrow, 1,  1,1)
            subrow = subrow +1

            glayout.addWidget(QtGui.QLabel('SPAD Threshold [V]'), subrow,0, 1,1)
            self.edit_spad_threshold = QtGui.QLineEdit('{:g}'.format(self.spad_threshold))
            self.edit_spad_threshold.editingFinished.connect(self.set_spad_params)
            glayout.addWidget(self.edit_spad_threshold, subrow, 1,  1,1)
            subrow = subrow +1

            self.layout.addWidget(self.spad_group, row,0,  subrow,4)
            row = row + subrow

            self.spad_timer = QtCore.QTimer()
            self.spad_timer.timeout.connect(self.check_spad_status)
            self.spad_timer.start(1000)
        else:
            self.check_spad = None


        if self.switch is not None:
            self.switch_group = QtGui.QGroupBox('DiCon Switch')

            vbox = QtGui.QGridLayout()
            self.switch_group.setLayout(vbox)
            self.switch_radiobtns = []
            for i in range(self.total_channels+1):
                if i == 0:
                    self.switch_radiobtns.append(QtGui.QRadioButton('Parked'))
                else:
                    self.switch_radiobtns.append(QtGui.QRadioButton(str(i)))

                if i == self.channel:
                    self.switch_radiobtns[i].setChecked(True)

                vbox.addWidget(self.switch_radiobtns[i], i//4, i%4, 1,1)
                self.switch_radiobtns[i].toggled.connect(self.set_switch)
            self.layout.addWidget(self.switch_group, row, 0, self.total_channels, 4)
            row = row +1
        # else:

        plot_row_height = 5
        plot_col_width = 6
        control_col_width = 4
        row = 0

        # Plot of swept source spectra
        self.p_spec = pg.PlotWidget(title="Swept Source Spectra")
        self.xlabel = self.p_spec.setLabel('bottom',text='Wavenumber',units='1/cm')
        self.ylabel = self.p_spec.setLabel('left',text='Counts',units='Arb. Unit')
        self.layout.addWidget(self.p_spec, row, control_col_width, plot_row_height, plot_col_width)
        row = row+plot_row_height


        if self.pm is not None:
            # Plot of tap power meter
            self.p_power = pg.PlotWidget(title='Power Meter')
            self.p_power.setLabel('bottom',text='Time',units='sec')
            self.p_power.setLabel('left',text='Power',units='W')
            self.p_power.setLogMode(x=None, y=True)
            self.layout.addWidget(self.p_power, row, control_col_width, plot_row_height, plot_col_width)

            self.power_data = []
            self.power_data_timestamps = []
            self.p_power_line = [] # line object for fast plot update
            row = row+plot_row_height

        # Plot of SPAD data
        if self.spad is not None:
            self.p_spad = pg.PlotWidget(title='SPAD')
            self.p_spad.setLabel('bottom',text='Time',units='sec')
            self.p_spad.setLabel('left',text='Count Rate',units='Hz')
            self.layout.addWidget(self.p_spad, row, control_col_width, plot_row_height, plot_col_width)

            self.spad_data = []
            self.spad_data_timestamps = []
            self.p_spad_line = [] # line object for fast plot update
            row = row+plot_row_height

        if self.daq is not None:
            # Plot of DAQ data
            self.p_daq = pg.PlotWidget(title='NI DAQ')
            self.p_daq.setLabel('bottom',text='Time',units='sec')
            self.p_daq.setLabel('left',text='Voltage',units='V')
            self.p_daq.setLogMode(x=None, y=None)
            self.layout.addWidget(self.p_daq, row, control_col_width, 2*plot_row_height, plot_col_width)

            self.daq_data = []
            self.daq_data_timestamps = []
            self.p_daq_line = [] # line object for fast plot update
            row = row+plot_row_height






        # # Plot of tap power fluctuations
        # self.p_tap_power = pg.PlotWidget()
        # self.p_tap_power.setLabel('bottom',text='Time',units='sec')
        # self.p_tap_power.setLabel('left',text='Power',units='W')
        # self.layout.addWidget(self.p_tap_power, row+4, 4, int(row/2), int(row/2)+2)

        # # Console widget
        # import pyqtgraph.console
        # namespace = {'pg': pg, 'np': np}
        # self.c = pyqtgraph.console.ConsoleWidget(namespace=namespace, text="Console loaded")
        # # self.layout.addWidget(self.c, 3*plot_row_height, 0, plot_row_height, 6+4)
        # self.layout.addWidget(self.c, 3*plot_row_height, 0, plot_row_height, 4)

        # Equalizes column stretch factor
        for i in range(self.layout.columnCount()):
            self.layout.setColumnStretch(i, 1)
        # Equalizes row stretch factor
        for i in range(self.layout.rowCount()):
            self.layout.setRowStretch(i, 1)

        self.show()

    # UI Event handlers
    def save_spectra(self):
        self.timer.stop()
        timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')

        # Save csv
        fname = self.edit_deviceName.text()+'-'+timestamp_str+'.csv'
        fpath = path.normpath(path.join(self.data_dir,fname))

        with open(fpath, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile, dialect='excel')
            csvwriter.writerow(['Wavelength nm', 'Count', 'Integration time', str(self.hr4000_params['IntegrationTime_micros'])])

            for i in range(self.spectra_data.shape[0]):
                csvwriter.writerow([str(self.spectra_data[i,0]), str(self.spectra_data[i,1])])

        # Save png
        fname = self.edit_deviceName.text()+'-'+timestamp_str+'.png'
        fpath = path.normpath(path.join(self.data_dir,fname))

        # QtGui.QApplication.processEvents()
        # create an exporter instance, as an argument give it
        # the item you wish to export
        exporter = pg.exporters.ImageExporter(self.p_spec.scene())
        exporter.export(fpath)

        self.statusBar().showMessage('Saved spectra to {}'.format(fpath), 5000)
        # restart timer
        self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

    def save_power_trace(self):
        self.timer.stop()

        saveDirectory, measDescription, fullpath = self.get_filename()

        if len(measDescription)>0:
            fields = ['Time [s]']
            data = []
            if self.pm is not None:
                fields.append('Power [W]')
                data = self.power_data

            if self.pm_tap is not None:
                fields.append('Tap Power [W]')
                if len(data) > 0:
                    fields.append('Coefficient')
                    data = list(zip(self.power_data, self.tap_power_data, [self.power_data[i]/tap_power for (i, tap_power) in enumerate(self.tap_power_data)]))
                else:
                    data = self.tap_power_data

            if len(data) > 0:
                # header_sm = sm_sample + ' measured on SM probe when optical switch on channel {}'.format(channel)
                np.savetxt(fullpath+'.csv', \
                           np.vstack((np.array(self.power_data_timestamps),  \
                                np.array(data))).T, \
                                delimiter=",", fmt='%s', header=','.join(fields), comments='')

                # Save png
                fpath = fullpath+'.png'

                exporter = pg.exporters.ImageExporter(self.p_power.scene())
                exporter.export(fpath)

                self.statusBar().showMessage('Saved power trace to {}'.format(fpath), 5000)
            else:
                print('No data to save in power trace window')
                self.statusBar().showMessage('No data to save in power trace window', 1000)

        else:
            self.statusBar().showMessage('Canceled Power trace save', 1000)
        # restart timer
        self.timer.start(self.ui_refresh_period) # in msec

    def save_current_trace(self):
        self.timer.stop()
        saveDirectory, measDescription, fullpath = self.get_filename()
        if len(measDescription)>0:
            fields = ['Time', 'Current [A]']
            data = self.current_data

            if len(data) > 0:
                self.save_to_csv(saveDirectory, measDescription, fields, self.current_data_timestamps, data)

                # Save png
                fpath = fullpath+'.png'

                exporter = pg.exporters.ImageExporter(self.p_current.scene())
                exporter.export(fpath)

                self.statusBar().showMessage('Saved current trace to {}'.format(fpath), 5000)
            else:
                print('No data to save in current trace window')
                self.statusBar().showMessage('No data to save in current trace window', 1000)

        else:
            self.statusBar().showMessage('Canceled current trace save', 1000)
        # restart timer
        self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

    def save_daq_trace(self):
        print("Not implemented")
        pass

    def save_spad_trace(self):
        print("Not implemented")
        pass

    def laser_control(self):
        laser_btn = self.sender()
        print(laser_btn.text())
        if laser_btn.text() == 'Warm up Laser':
            laser_btn.setText('Laser Warming up')
            print('Warming up laser')

            self.laser.set_mode(mode='W') # On mode

            self.laser_timer.start(1000) # ms

            self.laser_flags = [True]*4
        elif laser_btn.text() == 'Shutdown Laser':
            print('Turning off laser output')

            laser_btn.setText('Warm up Laser')
            self.btn_laser_out.setText('Output On')
            self.btn_laser_out.setEnabled(False)

            # Shutdown laser
            self.laser.set_mode(mode='O')

    def laser_output(self):
        laser_btn = self.sender()

        if laser_btn.text() == 'Output On':
            laser_btn.setText('Output Off')
            print('Turning on laser output')
        else:
            laser_btn.setText('Output On')
            print('Turning off laser output')


    def check_laser_status(self):
        self.laser.get_status()
        if self.laser.aotf_tec and self.laser_flags[0]:
            print('AOTF TEC ON...')
            self.laser_flags[0] = False
        if self.laser.aotf_tec_stable and self.laser_flags[1]:
            print('AOTF TEC STABLE!')
            self.laser_flags[1] = False
        if self.laser.sld_tec and self.laser_flags[2]:
            print('SLD TEC ON...')
            self.laser_flags[2] = False
        if self.laser.sld_tec_stable and self.laser_flags[3]:
            print('SLD TEC STABLE!')
            self.laser_flags[3] = False

        if self.laser.laser_rdy:
            print('Superlum ready to use')
            self.laser_timer.stop()

            self.btn_laser.setText('Shutdown Laser')
            self.btn_laser_out.setEnabled(True)

    def check_spad_status(self):
        state = self.spad.state

        self.label_spadState.setText('SPAD State: {}, {:0<4.4g}C'.format(state, self.spad.temp.magnitude/1e3))

        if self.laser is not None:
            if state =="READY":
                self.measSpadAction.setEnabled(True)
                self.measWSSpadAction.setEnabled(True)
            else:
                self.measSpadAction.setEnabled(False)
                self.measWSSpadAction.setEnabled(False)

    def check_laser_status(self):
        measured_wavelength = self.laser.poll_wavelength() # getting actual wavelength read
        # print('wavelength from wavemeter is {} '.format(measured_wavelength))
        self.label_laserState.setText('Laser State: poll status {}, {} nm'.format(self.laser.poll_status, measured_wavelength))


    def take_single_measurement(self):
        # Takes single measurement without sweeping wavelength
        with visa_timeout_context(self.smu._rsrc, 5000):
            print('Measuring photocurrent for single wavelength')
            saveDirectory, measDescription, fullpath = self.get_filename()

            if len(measDescription)>0:
                start = time.time()

                # prepare source meter
                self.set_smu_params()
                # Keithley
                if self.smu_channel== None:
                    self.smu.set_integration_time(0.2)
                else:
                    self.chkbox1.setChecked(True)
                    # self.smu.set_integration_time('short')

                #  Load measurement parameters
                wl = self.target_wl
                # self.goto_wavelength(wavelength = wl)

                data_x = []
                data_y = []

                print('Measuring {}'.format(wl.to_compact()))

                self.pm_tap.wavelength = wl
                data_x.append(wl.magnitude)

                data_row = []
                data_row2 = []
                data_row3 = []
                for n in range(self.exp_N):
                    data_row.append(self.smu.measure_current())
                    data_row2.append(self.pm.power())
                    data_row3.append(self.pm_tap.power)
                    print('   Sample {} at {}: {}  with {}, tap {}'.format(n, wl, data_row[-1], data_row2[-1], data_row3[-1]))
                # Append average and stdev
                data_mean = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row]))
                data_std = np.std(np.array([measure.to_base_units().magnitude for measure in data_row]))
                data_mean2 = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row2]))
                data_std2 = np.std(np.array([measure.to_base_units().magnitude for measure in data_row2]))
                data_mean3 = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row3]))
                data_std3 = np.std(np.array([measure.to_base_units().magnitude for measure in data_row3]))


                # data_row.extend([Q_(data_mean, 'A'), Q_(data_std, 'A')])
                # data_row = [data_row[i-2] for i in range(len(data_row))]
                # data_y.append(data_row)

                data_y.append([Q_(data_mean, 'A'), Q_(data_std, 'A'), Q_(data_mean2, 'W'), Q_(data_std2, 'W'), Q_(data_mean3, 'W'), Q_(data_std3, 'W')])

                # fields = ['Wavelength [nm]'] + ['Avg. Power [A]', 'Std Dev [A]'] + ['Photocurrent {} [A]'.format(n) for n in range(self.exp_N)]
                fields = ['Wavelength [nm]'] + ['Avg. Photocurrent [A]', 'Std Dev [A]'] + ['Avg. Power [W]', 'Std Dev [W]'] + ['Avg. Tap Power [W]', 'Std Dev [W]']
                self.save_to_csv(saveDirectory, measDescription, fields, data_x, data_y)

                # return source meter to fast sampling
                # Keithley
                if self.smu_channel== None:
                    self.smu.set_integration_time(0.2)
                else:
                    self.chkbox1.setChecked(True)
                    # self.smu.set_integration_time('short')

                print('Experiment lasted {} seconds'.format(time.time()-start))
            else:
                self.statusBar().showMessage('Canceled Photocurrent Experiment', 1000)

    def set_ui_params(self):
        # print(self.sender())
        self.timer.stop()
        print('\nsetting ui parameters')

        self.sample = self.edit_sample.text()
        print("sample: {}".format(self.sample))

        self.intTime = float(self.edit_intTime.text())
        print("intTime {}".format(self.intTime))

        self.ui_refresh_period = float(self.edit_uiTime.text())
        print("ui_refresh_period {}".format(self.ui_refresh_period))

        self.ui_buffer_length = int(self.edit_uiBufferLength.text())
        print("ui_buffer_length {}".format(self.ui_buffer_length))

        self.sampling_freq = float(self.edit_sampRate.text())
        print("sampling_freq {}".format(self.sampling_freq))


        if self.daq is not None and self.exp_running == False:
            # Setup NI daq acquisition settings
            # num_of_samples = int(self.ui_refresh_period*1e-3*self.sampling_freq)
            # self.daq.timing.cfg_samp_clk_timing(int(self.sampling_freq), samps_per_chan=num_of_samples) # to sync with redpitaya use sampling_freq
            self.daq.stop()
            self.daq.timing.cfg_samp_clk_timing(self.sampling_freq, sample_mode=AcquisitionType.CONTINUOUS) # to sync with redpitaya use sampling_freq
            self.daq.start()

        self.timer.start(self.ui_refresh_period)

    def set_spad_params(self):
        if self.spad is not None:
            # Integration time
            self.spad_intTime = float(self.edit_spad_intTime.text())
            # print("spad_intTime {}".format(self.spad_intTime))

            # integration_time = max([int(self.spad_intTime), 0.00])
            # integration_time = min([100000, integration_time])
            print('Setting spad integration time to {}s'.format(self.spad_intTime))

            self.spad.integration_time = Q_(self.spad_intTime, 's')
            set_value = self.spad.integration_time.to('s').magnitude
            if abs(self.spad_intTime - set_value) > 0.01: # if the actual value is not same as set value
                print('   Warning: spad integration time 0.2~100 step 0.2')
            self.spad_intTime = set_value
            self.edit_spad_intTime.setText('{:g}'.format(self.spad_intTime))

            # Bias
            self.spad_bias = float(self.edit_spad_bias.text())
            print('Setting spad bias to {}V'.format(self.spad_bias))

            self.spad.bias = Q_(self.spad_bias, 'V')
            set_value = self.spad.bias.to('V').magnitude
            if abs(self.spad_bias - set_value) > 0.01: # if the actual value is not same as set value
                print('   Warning: spad bias 0~250 step 0.08')
            self.spad_bias = set_value
            self.edit_spad_bias.setText('{:g}'.format(self.spad_bias))

            # Threshold
            self.spad_threshold = float(self.edit_spad_threshold.text())
            print('Setting spad threshold to {}V'.format(self.spad_threshold))

            self.spad.threshold = Q_(self.spad_threshold, 'V')
            set_value = self.spad.threshold.to('V').magnitude
            if abs(self.spad_threshold - set_value) > 0.0001: # if the actual value is not same as set value
                print('   Warning: spad threshold 0.0~1.047 step 0.0005')
            self.spad_threshold = set_value
            self.edit_spad_threshold.setText('{:g}'.format(self.spad_threshold))





        # spec.integration_time_micros(hr4000_params['IntegrationTime_micros'])
        self.timer.start(max([self.ui_refresh_period, 200.0])) # in msec

        self.statusBar().showMessage('Set SPAD parameters', 5000)
        print('setting SPAD parameters done\n')



    def set_smu_params(self):
        if self.smu_channel is not None:
            try:
                self.smu_channel = int(self.edit_channel.text())
            except:
                self.statusBar().showMessage('Invalid input for SMU channel', 3000)
                self.smu_channel = 1
                self.edit_channel.setText('1')

        try:
            self.smu_bias = Q_(float(self.edit_bias.text()), 'V')
        except:
            self.statusBar().showMessage('Invalid input for SMU voltage', 3000)
            self.smu_bias = Q_(0.0, 'V')
            self.edit_channel.setText('0.0')

        if self.smu is not None:
            if self.smu_channel is not None:
                self.smu.set_channel(channel=self.smu_channel)

            self.smu.set_voltage(voltage=self.smu_bias)
            self.statusBar().showMessage('Setting SMU channel {} to {:.4g~}'.format(self.smu_channel, self.smu_bias), 3000)

    def set_directory(self):
        self.timer.stop()
        self.data_dir = QtGui.QFileDialog.getExistingDirectory()

        self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

        self.statusBar().showMessage('Set data directory to {}'.format(self.data_dir), 5000)

    def set_wavelength(self): #, wavelength):
        # wl_edit = self.sender()
        wl_edit = self.edit_wavelength
        wavelength = float(wl_edit.text()) # nm

        self.wavelength = wavelength
        measured_wavelength = wavelength


        if self.laser is not None:
            self.laser.set_wavelength(wavelength)
            measured_wavelength = self.laser.get_wavelength()
            print(measured_wavelength)
        if self.pm is not None:
            self.pm.setWavelength(c_double(measured_wavelength))

        self.statusBar().showMessage('Setting wavelength to {:.4g}nm'.format(wavelength), 5000)

        # self.goto_wavelength(wavelength = self.target_wl)

    # Set parameters for wavelength sweep
    def set_sweep_params(self):
        self.wavelength_start = Q_(float(self.edit_wavelength_start.text()), 'nm')
        self.wavelength_stop = Q_(float(self.edit_wavelength_stop.text()), 'nm')
        self.wavelength_step = Q_(float(self.edit_wavelength_step.text()), 'nm')

        self.exp_N = int(self.edit_exp_N.text())

        self.statusBar().showMessage('Setting wavelength sweep parameters', 1000)

    # Set parameters for bias voltage sweep
    def set_biasV_sweep_params(self):
        self.statusBar().showMessage('Setting Voltage IV sweep parameters', 1000)

        try:
            self.biasV_start = Q_(float(self.edit_biasV_start.text()), 'V')
        except:
            self.statusBar().showMessage('Error setting start bias', 1000)
            self.edit_biasV_start.setText(str(self.biasV_start.magnitude))

        try:
            self.biasV_stop = Q_(float(self.edit_biasV_stop.text()), 'V')
        except:
            self.statusBar().showMessage('Error setting stop bias', 1000)
            self.edit_biasV_stop.setText(str(self.biasV_stop.magnitude))

        try:
            self.biasV_step = Q_(float(self.edit_biasV_step.text()), 'V')
        except:
            self.statusBar().showMessage('Error setting bias step', 1000)
            self.edit_biasV_step.setText(str(self.biasV_step.magnitude))

        try:
            self.exp_biasV_N = int(self.edit_exp_biasV_N.text())
        except:
            self.statusBar().showMessage('Error setting N', 1000)
            self.edit_exp_biasV_N.setText(str(self.exp_biasV_N))

    def set_switch(self):
        ch_btn = self.sender()

        if ch_btn.isChecked() == True:
            print('Switch at '+ch_btn.text())
            if ch_btn.text() == 'Parked':
                self.channel = 0
            else:
                self.channel = int(ch_btn.text())
            self.switch.set_channel(self.channel)


    def set_smu_intTime(self, btn):
        self.smu.set_integration_time(time=btn.text())
        self.statusBar().showMessage('Setting SMU integration time to '+btn.text(), 1000)

    def toggle_pm_output(self):
        if self.check_pm.isChecked():
            self.label_illumpower.setStyleSheet("font: bold 10pt Arial")
            self.power_data.clear()
            self.power_data_timestamps.clear()

            self.power_data_timezero = time.time()

            self.p_power.clear()
            self.p_power_line = self.p_power.plot(pen=(1,2))
        else:
            self.label_illumpower.setStyleSheet("font: bold 12pt Arial; color: gray")


    def toggle_daq_output(self):
        if self.check_daq.isChecked():
            self.label_daqdata.setStyleSheet("font: bold 10pt Arial")
            self.daq_data.clear()
            self.daq_data_timestamps.clear()

            self.daq_data_timezero = time.time()

            self.p_daq.clear()
            self.p_daq_line = self.p_daq.plot(pen=(1,2))
        else:
            self.label_daqdata.setStyleSheet("font: bold 12pt Arial; color: gray")

    def toggle_spad_output(self):
        if self.check_spad.isChecked():
            self.label_spaddata.setStyleSheet("font: bold 10pt Arial")
            self.spad_data.clear()
            self.spad_data_timestamps.clear()

            self.spad_data_timezero = time.time()

            self.p_spad.clear()
            self.p_spad_line = self.p_spad.plot(pen=(1,2))
        else:
            self.label_spaddata.setStyleSheet("font: bold 12pt Arial; color: gray")


    def toggle_smu_output(self):
        if self.check_smu.checkState() == 0:
            self.label_photocurrent.setStyleSheet("font: bold 10pt Arial; color: gray")
        else:
            # Keithley
            if self.smu_channel== None:
                self.smu.set_integration_time(0.5)
            else:
                self.chkbox2.setChecked(True)
                # self.smu.set_integration_time('medium')
            self.label_photocurrent.setStyleSheet("font: bold 10pt Arial")
            self.current_data = []
            self.current_data_timestamps = []
            self.current_data_timezero = time.time()

            self.p_current.clear()

    def toggle_all_output(self):
        if self.check_all.checkState() == 0:
            if self.pm is not None:
                self.check_pm.setCheckState(0) # on

            if self.daq is not None:
                self.check_daq.setCheckState(0)
        else:
            self.data_timestamps.clear()
            self.data_timezero = time.time()

            if self.pm is not None:
                self.check_pm.setCheckState(1) # on

            if self.daq is not None:
                self.check_daq.setCheckState(1)



    def set_feedback_params(self):
        self.Kp=float(self.edit_kp.text())
        self.Ki=float(self.edit_ki.text())
        self.Kd=float(self.edit_kd.text())

        self.statusBar().showMessage('Set feedback gains', 1000)

    # Timer event handler
    def refresh_ui(self):
        # if self.spec is not None:
        #     # Check checkbox GUI to set options for spectrometer data acquisition
        #     averaging = False
        #     correction = False
        #     if self.check_spectra_avg.isChecked():
        #         averaging =True
        #     if self.check_spectra_correct.isChecked():
        #         correction =True
        #
        #     self.spectra_data = np.transpose( self.spec.spectrum(correct_dark_counts=averaging, correct_nonlinearity=correction) )
        #     self.p_spec.plot(self.spectra_data, clear=True)
        #
        #     # refresh peak wavelength
        #     # print(self.spectra_data.shape)
        #     self.current_wl = Q_(self.spectra_data[np.argmax(self.spectra_data[:,1]), 0], 'nm')
        #     self.label_wavelength.setText("Peak wavelength {:4.4g~}".format(self.current_wl.to_compact()))
        #     # self.label_wavelength.setText("Peak wavelength {}".format(self.current_wl.to_compact()))

        active_plotting = False
        if self.check_pm is not None:
            if self.check_pm.checkState() > 0:
                active_plotting = True
                self.power_data_timestamps.append(time.time()-self.power_data_timezero)

                label_illumpower_text = ''

                if self.pm is not None:
                    meas_power = c_double()
                    self.pm.measPower(byref(meas_power))
                    label_illumpower_text = 'Tap: {:0<4.4g} W,'.format(meas_power.value)
                    # self.label_illumpower.setText('Illumination Power: {:0<4.4g~}'.format(meas_power.to_compact()))

                    self.power_data.append(meas_power.value)
                    # self.p_power.plot(self.power_data_timestamps, self.power_data, pen=(1,2), clear=True)

                    if len(self.power_data) > self.ui_buffer_length:
                        self.p_power_line.setData(self.power_data_timestamps[-self.ui_buffer_length:-1], self.power_data[-self.ui_buffer_length:-1])
                    else:
                        self.p_power_line.setData(self.power_data_timestamps, self.power_data)

                self.label_illumpower.setText(label_illumpower_text)

        if self.check_daq is not None:
            if self.check_daq.checkState() >0:
                active_plotting = True
                self.daq_data_timestamps.append(time.time()-self.daq_data_timezero)
                label_daq_text = ''

                values_read = np.zeros((2, ), dtype=np.float64) # (channel, samples)
                self.daqreader.read_one_sample(values_read) #, timeout=integration_time)
                # temp_buff = self.daq.read(number_of_samples_per_channel=int(1), timeout=self.ui_refresh_period*1e-3)
                label_daq_text = 'DAQ Ch0: {:0<4.4g} V,'.format(values_read[0])

                self.daq_data.append(values_read[0])
                if len(self.daq_data) > self.ui_buffer_length:
                    self.p_daq_line.setData(self.daq_data_timestamps[-self.ui_buffer_length:-1], self.daq_data[-self.ui_buffer_length:-1])
                else:
                    self.p_daq_line.setData(self.daq_data_timestamps, self.daq_data)

                self.label_daqdata.setText(label_daq_text)

        if self.check_spad is not None:
            if self.check_spad.checkState() >0:
                active_plotting = True
                self.spad_data_timestamps.append(time.time()-self.spad_data_timezero)

                value_read = self.spad.count.magnitude/self.spad_intTime*1e3
                label_spad_text = 'SPAD: {:0<4.4g} Hz,'.format(value_read)

                self.spad_data.append(value_read)
                if len(self.spad_data) > self.ui_buffer_length:
                    self.p_spad_line.setData(self.spad_data_timestamps[-self.ui_buffer_length:-1], self.spad_data[-self.ui_buffer_length:-1])
                else:
                    self.p_spad_line.setData(self.spad_data_timestamps, self.spad_data)

                self.label_spaddata.setText(label_spad_text)


    # Menu handlers
    def exp_illum(self):
        with visa_timeout_context(self.pm._rsrc, 1000):
            print('Measuring Illumination')
            saveDirectory, measDescription, fullpath = self.get_filename()

            # check that a file name is designated and that the sweep parameters are correct
            if len(measDescription)>0:
                start = time.time()

                # spectometer not connected
                if self.spec is None:
                    self.wavelength_start = self.target_wl
                    self.wavelength_stop =  self.wavelength_start+Q_(1.0, 'nm')
                    self.wavelength_step = Q_(2.0, 'nm')
                    self.exp_N = 500

                # wavelength sweep if spectrometer is connected
                if (self.wavelength_stop-self.wavelength_start)*self.wavelength_step>0.0:

                    # prepare power meter
                    # self.pm.set_slow_filter()

                    #  Load measurement parameters
                    wl = self.wavelength_start

                    data_x = []
                    data_y = []
                    while (wl <= self.wavelength_stop and self.wavelength_step>0.0) or (wl >= self.wavelength_stop and self.wavelength_step<0.0):
                        print('Measuring {}'.format(wl.to_compact()))

                        try:
                            import winsound
                            winsound.Beep(2200, 1000)
                        except:
                            print('winsound not available no beeping')

                        # only move when we are doing more than 1 step measurement
                        if np.abs((self.wavelength_stop-self.wavelength_start)/self.wavelength_step)>1:
                            meas_wl = self.goto_wavelength(wl)
                            sleep(5.0)
                        else:
                            meas_wl = wl

                        self.pm.wavelength = meas_wl
                        self.pm_tap.wavelength = meas_wl
                        data_x.append(meas_wl.magnitude)

                        data_row = []
                        data_row2 = []
                        for n in range(self.exp_N):
                            data_row.append(self.pm.power())
                            data_row2.append(self.pm_tap.power)
                            print('   Sample {} at {} : Actual {}, Tap {}'.format(n, meas_wl, data_row[-1], data_row2[-1]))

                        # Append average and stdev
                        data_mean = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row]))
                        data_std = np.std(np.array([measure.to_base_units().magnitude for measure in data_row]))
                        data_mean2 = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row2]))
                        data_std2 = np.std(np.array([measure.to_base_units().magnitude for measure in data_row2]))
                        data_coeff = data_mean/data_mean2


                        # Bring average and stdev to the front
                        # data_row.extend([Q_(data_mean, 'W'), Q_(data_std, 'W')])
                        # data_row = [data_row[i-2] for i in range(len(data_row))]
                        # data_y.append(data_row)

                        data_y.append([Q_(data_mean, 'W'), Q_(data_std, 'W'), Q_(data_mean2, 'W'), Q_(data_std2, 'W'), Q_(data_coeff, '')])

                        self.refresh_ui()

                        wl = wl + self.wavelength_step


                # fields = ['Wavelength [nm]'] + ['Avg. Power [W]', 'Std Dev [W]'] + ['Power {} [W]'.format(n) for n in range(self.exp_N)]
                fields = ['Wavelength [nm]'] + ['Avg. Power [W]', 'Std Dev [W]'] +['Tap Avg. Power [W]', 'Std Dev [W]'] + ['Coefficient'] + ['average over {} points'.format(self.exp_N)]

                self.save_to_csv(saveDirectory, measDescription, fields, data_x, data_y)

                # return power meter to fast sampling
                self.pm.set_no_filter()

                print('Experiment lasted {} seconds'.format(time.time()-start))

                try:
                    import winsound
                    winsound.Beep(2500, 1000)
                except:
                    print('winsound not available no beeping')

                #self.mc.go_steps(N=int(self.wavelength_stop.magnitude-self.wavelength_start.magnitude)*250)
            else:
                self.statusBar().showMessage('Cancelled Illumination Experiment', 1000)
            # print([saveDirectory, measDescription])

    def exp_spectra(self):

        print('Measuring Spectra')
        saveDirectory, measDescription, fullpath = self.get_filename()

        # check that a file name is designated
        if len(measDescription)>0:

            self.timer.stop()
            timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')

            # Save csv
            fname = measDescription+'-'+timestamp_str+'.csv'
            fpath = path.normpath(path.join(saveDirectory,fname))

            with open(fpath, 'w', newline='') as csvfile:
                csvwriter = csv.writer(csvfile, dialect='excel')
                csvwriter.writerow(['Wavelength nm', 'Count', 'Integration time', str(self.hr4000_params['IntegrationTime_micros'])])

                for i in range(self.spectra_data.shape[0]):
                    csvwriter.writerow([str(self.spectra_data[i,0]), str(self.spectra_data[i,1])])

            # Save png
            fname = self.measDescription.text()+'-'+timestamp_str+'.png'
            fpath = path.normpath(path.join(saveDirectory,fname))

            # QtGui.QApplication.processEvents()
            # create an exporter instance, as an argument give it
            # the item you wish to export
            exporter = pg.exporters.ImageExporter(self.p_spec.scene())
            exporter.export(fpath)

            self.statusBar().showMessage('Saved spectra to {}'.format(fpath), 5000)
            # restart timer
            self.timer.start(max([Window.timer_factor*self.hr4000_params['IntegrationTime_micros'], 200.0])) # in msec

            print('Experiment lasted {} seconds'.format(time.time()-start))

            try:
                import winsound
                winsound.Beep(2500, 1000)
            except:
                print('winsound not available no beeping')
        else:
            self.statusBar().showMessage('Cancelled Illumination Experiment', 1000)

    def exp_photocurrent(self):
        with visa_timeout_context(self.smu._rsrc, 5000):
            print('Measuring photocurrent')
            saveDirectory, measDescription, fullpath = self.get_filename()

            # check that a file name is designated and that the sweep parameters are correct
            if len(measDescription)>0 and (self.wavelength_stop-self.wavelength_start)*self.wavelength_step>0.0:

                try:
                    import winsound
                    winsound.Beep(2200, 1000)
                except:
                    print('winsound not available no beeping')

                start = time.time()

                # prepare source meter
                self.set_smu_params()
                self.smu.set_voltage(self.wavelength_bias)
                # Keithley
                if self.smu_channel== None:
                    self.smu.set_integration_time(0.2)
                else:
                    self.chkbox1.setChecked(True)
                    # self.smu.set_integration_time('short')

                #  Load measurement parameters
                wl = self.wavelength_start

                data_x = []
                data_y = []
                while (wl <= self.wavelength_stop and self.wavelength_step>0.0) or (wl >= self.wavelength_stop and self.wavelength_step<0.0):
                    print('Measuring {}'.format(wl.to_compact()))

                    # only move when we are doing more than 1 step measurement
                    if np.abs((self.wavelength_stop-self.wavelength_start)/self.wavelength_step)>1:
                        meas_wl = self.goto_wavelength(wl)
                    else:
                        meas_wl = wl

                    sleep(5.0)
                    # self.pm.wavelength = meas_wl
                    self.pm_tap.wavelength = meas_wl
                    data_x.append(meas_wl.magnitude)

                    data_row = []
                    data_row2 = []
                    for n in range(self.exp_N):
                        data_row.append(self.smu.measure_current())
                        data_row2.append(self.pm_tap.power)
                        print('   Sample {} at {}: {}  with {}'.format(n, meas_wl, data_row[-1], data_row2[-1]))
                    # Append average and stdev
                    data_mean = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row]))
                    data_std = np.std(np.array([measure.to_base_units().magnitude for measure in data_row]))
                    data_mean2 = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row2]))
                    data_std2 = np.std(np.array([measure.to_base_units().magnitude for measure in data_row2]))

                    # data_row.extend([Q_(data_mean, 'A'), Q_(data_std, 'A')])
                    # data_row = [data_row[i-2] for i in range(len(data_row))]
                    # data_y.append(data_row)

                    data_y.append([Q_(data_mean, 'A'), Q_(data_std, 'A'), Q_(data_mean2, 'W'), Q_(data_std2, 'W')])

                    self.refresh_ui()

                    wl = wl + self.wavelength_step

                # fields = ['Wavelength [nm]'] + ['Avg. Power [A]', 'Std Dev [A]'] + ['Photocurrent {} [A]'.format(n) for n in range(self.exp_N)]
                fields = ['Wavelength [nm]'] + ['Avg. Photocurrent [A]', 'Std Dev [A]'] + ['Avg. Power [W]', 'Std Dev [W]'] + ['Coefficient', 'Actual Power [W]'] + ['Responsivity [A/W]', 'Q.E.'] + ['average over {} points'.format(self.exp_N)]
                self.save_to_csv(saveDirectory, measDescription, fields, data_x, data_y)

                # return source meter to previous state

                if self.smu_channel== None:
                    # Keithley
                    self.smu.set_integration_time(0.2)
                else:
                    # HP Parameter analyzer
                    self.chkbox1.setChecked(True)
                    # self.smu.set_integration_time('short')
                self.smu.set_voltage(self.smu_bias)

                print('Experiment lasted {} seconds'.format(time.time()-start))

                try:
                    import winsound
                    winsound.Beep(2500, 1000)
                except:
                    print('winsound not available no beeping')


                # self.mc.go_steps(N=int(self.wavelength_stop.magnitude-self.wavelength_start.magnitude)*250)
            else:
                self.statusBar().showMessage('Canceled Photocurrent Experiment', 1000)

    def exp_wlsweep_spad(self):

        self.set_ui_params()
        self.set_sweep_params()

        self.statusBar().showMessage('Running SPAD wavelength sweep Experiment', 1000)

        # Wavelength sweep experiment

        timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')

        fpath_log_csv = './data/'+timestamp_str+'/'+timestamp_str+'_log.csv'

        run_log = []

        fiber_channel = {
            #1: 'rp-f084D3.local',
            2: 'rp-f08473.local'
            #2: 'rp-f08358.local'
        }


        # mm_sample = {}

        # for (channel, hostname) in fiber_channel.items():
        #     mm_sample[channel] = input('What is the sample you are looking at MM channel {}? '.format(channel))
        #     run_log.append('mm_sample, {} \n'.format(mm_sample[channel]))
        #
        # # run_log.append('mm sample, {} \n'.format(mm_sample))
        # run_log.append('sampling_freq, {} \n'.format(sampling_freq))
        #
        # np.savetxt(fpath_log_csv, run_log, delimiter=",",fmt="%s",newline = "\n", comments='')
        # # Take user input for wavelength sweep
        # sweep_presets = [ # [start, stop, step]
        #                     [778.93, 778.93, 1, 'glucose peak'],
        #                     [786.80, 786.80, 1, 'polystyrene peak'],
        #                     [788.93, 789.93, 0.25, '4 wavelength test sweep'],
        #                     [770.0, 825.0, 5.0, 'full range fast sweep'],
        #                     [780.25, 789.50, 0.25, 'polystyrene narrow sweep'],
        #                     [775.0, 812.0, 0.25, 'polystyrene wide sweep'],
        #                     ]
        # print('Available sweep presets')
        # print('m#: [start, stop, step]')
        # for (ind, sweep_params) in enumerate(sweep_presets):
        #     print('m{}: {}'.format(ind, sweep_params))
        # start_wavelength=input('Start wavelength or m# for presets: ')
        # if start_wavelength[0] == 'm': # recall presets
        #     ind = int(start_wavelength[1:])
        #     start_wavelength = sweep_presets[ind][0]
        #     end_wavelength = sweep_presets[ind][1]
        #     step_size = sweep_presets[ind][2]
        # else:
        #     start_wavelength = float(start_wavelength)
        #     end_wavelength=float(input('End wavelength: '))
        #     step_size=float(input('Step size: '))
        #



        start_wavelength = self.wavelength_start.magnitude
        end_wavelength = self.wavelength_stop.magnitude
        step_size = self.wavelength_step.magnitude

        target_wavelengths = np.arange(start_wavelength, end_wavelength+step_size, step_size) # the array of wavlengths we are aiming for = 2 # to allow settling

        #target_wavelengths = np.arange(start_wavelength, end_wavelength+step_size*0.1, step_size) # the array of wavlengths we are aiming for = 2 # to allow settling
        #target_wavelengths = [814.75, 815, 811.0, 811.25, 811.5]

        integration_time = self.intTime # seconds on each wavelength
        N_repetitions = self.exp_N # number of repeating each data points (wavelengths acquisitions)

        # lockin=input('Lock in Y/N: ')
        # lock_in=lockin.upper()
        lock_in = 'N'

        print('\nStarting Wavelength Sweep with SPAD-------')
        print('start_wavelength,  {}  '.format(start_wavelength))
        print('end_wavelength, {}  '.format(end_wavelength))
        print('step_size, {}  '.format(step_size))
        print('integration_time, {} '.format(integration_time))
        print('N_repetitions, {} '.format(N_repetitions))
        print('lock_in, {} \n'.format(lock_in))

        # np.savetxt(fpath_log_csv, run_log, delimiter=",", fmt="%s", newline="\n", comments='')
        #### End of user input

        # Begin run
        t0 = time.time()

        # initializing output data structures
        power_output_dic = {} # time domain power monitoring
        spad_output_dic = {}
        spectra_dic = {}
        spectra_norm_dic = {}
        spectra_std_dic = {}
        wl_dic = {}

        for (channel, hostname) in fiber_channel.items():
            power_output_dic[channel] = []
            spad_output_dic[channel] = []
            spectra_dic[channel] = []
            spectra_norm_dic[channel] = []
            spectra_std_dic[channel] = []
            wl_dic[channel] = []

        # Turn on laser output
        # self.switch.set_channel(2)
        self.laser.set_output(on=True)

        # Setup power meter wavelength settings
        power = c_double()
        # avgTime = c_double()
        # print( tlPM.getAvgTime(c_int16(2), byref(avgTime)) ) # previously set average time
        # print(power)

        failed_wavelength = target_wavelengths # wavelengths we will return to if their tuning fails

        # Setup NI daq acquisition settings
        # num_of_samples = int(integration_time*sampling_freq)
        # nidaq.timing.cfg_samp_clk_timing(int(sampling_freq), samps_per_chan=num_of_samples) # to sync with redpitaya use sampling_freq
        num_of_samples = round(self.intTime / self.spad_intTime)

        # Variables for plot
        # fig = None
        plot = True

        while len(failed_wavelength)!=0:

            target_wavelengths = failed_wavelength # setting targets as failed from previous

            failed_wavelength = [] # emptying out the previous failed

            for (wi,wl) in enumerate(target_wavelengths):
                tune_success = self.laser.set_wavelength(wavelength=wl) # returns 1 if successful
                sleep(1.0)
                measured_wavelength = self.laser.get_wavelength()

                if abs(measured_wavelength-wl) > 0.01: # using just wavelength setting in laser but may need to implement wavemeter
                    tune_success = 0

                if tune_success == 0:
                    failed_wavelength.append(target_wavelengths[wi])

                elif tune_success == 1:
                    print('\n\n{}nm {} out of {} wavelengths({}-{}nm)'.format(measured_wavelength, wi+1, target_wavelengths.shape[0], target_wavelengths[0], target_wavelengths[-1]))

                    self.pm.setWavelength(c_double(measured_wavelength))
                    self.pm.measPower(byref(power))

                    if power.value < 1.0e-7: # if tap power is below 30 uW --> actual power is under 1mW (1:99 tap)
                    #   raise ValueError('Tap power is low {} uW, please check laser'.format(power.value*1e6))
                        print('Tap power is low {} uW, please check laser'.format(power.value*1e6))

                    for (channel, hostname) in fiber_channel.items():
                        # switch.set_channel(channel) #remember to change back to (channel)
                        # sleep(0.5)
                        # print('Measuring on channel {}'.format(switch.get_channel()))

                        for n in range (1,N_repetitions+1):
                            print('Acquisition {} of {}'.format(n,N_repetitions))

                            buff_power = []
                            buff_spad = []

                            timevec, buff_spad, buff_power = self.exp_spad(single=False)

                            # Saves wavelength and add data to dictionary
                            power_output_dic[channel].append([measured_wavelength] + list(buff_power))
                            spad_output_dic[channel].append([measured_wavelength] + list(buff_spad))
                            time_array_save = np.concatenate((np.array([0]), timevec))

                        # save data each round  so to not lose all of it if the process fails

                        print('Writing output csv files for channel {}'.format(channel))
                        fpath_pre = './data/'+self.sample+'_'+timestamp_str+'_Ch'+str(channel)

                        fpath_power_csv = fpath_pre+'_power.csv'
                        header_power = 'Power meter output when optical switch on channel {}'.format(channel)
                        np.savetxt(fpath_power_csv,
                                   np.vstack((time_array_save, np.array(power_output_dic[channel]))).T,
                                   delimiter=",",fmt='%s', comments='') #, header = header_power)

                        fpath_spad_csv = fpath_pre+'_spad.csv'
                        header_spad = 'SPAD input when optical switch on channel {}'.format(channel)
                        np.savetxt(fpath_spad_csv,
                                   np.vstack((time_array_save, np.array(spad_output_dic[channel]))).T,
                                   delimiter=",",fmt='%s', comments='') #, header = header_power)
                        # Compute averages, output_dic[channel][repetitions][0]=wavelength, output_dic[channel][repetitions][1:]=voltage
                        tap = np.array(power_output_dic[channel])[-N_repetitions:,1:]
                        signal = np.array(spad_output_dic[channel])[-N_repetitions:,1:]

                        tap_avg = np.mean(tap, axis=0)
                        signal_avg = np.mean(signal, axis=0)

                        spectra_dic[channel].append(np.mean(signal))
                        spectra_std_dic[channel].append(np.std(signal))
                        spectra_norm_dic[channel].append(np.mean(signal)/np.mean(tap))

                        wl_dic[channel].append(wl)

                        if plot==True:
                            fpath_png = fpath_pre+'_{:g}nm.png'.format(measured_wavelength)
                            print('Plotting {}\n'.format(fpath_png))

                            fig, ax = plt.subplots(nrows=2, ncols=2, sharex=False, sharey=False, figsize=(20, 10))
                            fig.suptitle('Measurement on channel {} at {} nm, {} sec x N={}'.format(channel, measured_wavelength, integration_time, N_repetitions))

                            # Plot time trace
                            ax[0,0].set_title('Power meter')
                            ax[0,0].fill_between(timevec, np.min(tap, axis=0), np.max(tap, axis=0), facecolor='tab:orange', label='Power meter min/max',step='post', alpha=0.7)
                            ax[0,0].plot(timevec, tap_avg, label='Power meter (avg)', color='tab:blue', linewidth=1.0)
                            ax[0,0].set_ylabel('Optical Power [W]')
                            ax[0,0].set_xlabel('Time [sec]')
                            ax[0,0].legend()

                            ax[1,0].set_title('Raman through ID Quantique SPAD')
                            ax[1,0].fill_between(timevec, np.min(signal, axis=0), np.max(signal, axis=0), facecolor='tab:orange', label='Raman signal min/max', step='post', alpha=0.7)
                            ax[1,0].plot(timevec, signal_avg, label='Raman signal (avg)', color='tab:blue', linewidth=1.0)
                            ax[1,0].set_ylabel('Photon Rate [Hz]')
                            ax[1,0].set_xlabel('Time [sec]')
                            ax[1,0].legend()


                            # plot spectra
                            ax[0,1].set_title('Raman Spectra of {}'.format(self.sample))
                            ax[0,1].plot(np.array(wl_dic[channel]), spectra_dic[channel], marker='.', color='tab:blue', linewidth=1)
                            ax[0,1].set_ylabel('Raman Signal [A.U.]')
                            ax[0,1].set_xlabel('Wavelength [nm]')

                            ax[1,1].plot(self.wave_2_waveshift(np.array(wl_dic[channel])), spectra_dic[channel], marker='.', color='tab:blue', linewidth=1)
                            ax[1,1].set_ylabel('Raman Signal [A.U.]')
                            ax[1,1].set_xlabel('Raman Shift[cm$^{-1}$]')

                            plt.savefig(fpath_png)

            print('failed wavelength = {}'.format(failed_wavelength))

        # Turn off laser output
        self.laser.set_output(on=False)
        


        if plot==True:
            for (channel, hostname) in fiber_channel.items():

                fpath_pre = './data/'+self.sample+'_'+timestamp_str+'_Ch'+str(channel)
                fpath_png = fpath_pre+'_Spectra.png'
                print('Plotting full spectra {}'.format(fpath_png))

                fig, ax = plt.subplots(nrows=2, ncols=1, sharex=False, sharey=True, figsize=(10, 10))
                fig.suptitle('Spectra on channel {} at {}-{} nm, {} sec x N={}'.format(channel, target_wavelengths[0], target_wavelengths[-1], integration_time, N_repetitions))

                ax[0].errorbar(wl_dic[channel], spectra_dic[channel], yerr=spectra_std_dic[channel], color='tab:blue', linewidth=1, elinewidth=0.5, capsize=3)
                ax[0].set_ylabel('A.U.')
                ax[0].set_xlabel('nm')
                #         ax[0].legend()

            #     ax[1].set_title('Spectra in $cm^{-1}$')
                ax[1].errorbar(self.wave_2_waveshift(np.array(wl_dic[channel])), spectra_dic[channel], yerr=spectra_std_dic[channel], color='tab:blue', linewidth=1, elinewidth=0.5, capsize=3)
                ax[1].set_ylabel('A.U.')
                ax[1].set_xlabel('cm$^{-1}$')

                plt.savefig(fpath_png)

                self.p_spec.plot(self.wave_2_waveshift(np.array(wl_dic[channel])), spectra_dic[channel], pen=(1,2), clear=True)

        t1 = time.time()

        elapsed_run_time =time.strftime("%H:%M:%S", time.gmtime(t1-t0))

        # run_log.append('elapsed_run_time, {} \n'.format(elapsed_run_time))

        # np.savetxt(fpath_log_csv, run_log, delimiter=",",fmt="%s",newline = "\n", comments='')

        print('Wavelength SPAD Sweep Experiment Done. Experiment ran {}\m'.format(elapsed_run_time))



    def exp_femto(self):
        print('\nFemto detector measurement started')
        self.exp_running = True

        integration_time = 1/self.sampling_freq
        self.daq.stop()
        self.daq.timing.cfg_samp_clk_timing(self.sampling_freq, sample_mode=AcquisitionType.CONTINUOUS) #, samps_per_chan=1)
        self.daq.start()
        timezero  = time.time()
        timevec = []
        femtovec = []
        powervec = []
        t = time.time()-timezero
        prog_t = t
        while t < self.intTime:
            timevec.append(t)
            # daq_buff = self.daq.read(number_of_samples_per_channel=int(1), timeout=self.intTime*1.5)
            # values_read = np.zeros((2, 1), dtype=np.float64) # (channel, samples)
            #self.daqreader.read_many_sample(values_read, number_of_samples_per_channel=1, timeout=2)
            values_read = np.zeros((2, ), dtype=np.float64) # (channel, samples)
            self.daqreader.read_one_sample(values_read) #, timeout=integration_time)

            # print(daq_buff)
            femtovec.append(values_read[0]) # channel 0

            meas_power = c_double()
            self.pm.measPower(byref(meas_power))
            powervec.append(meas_power.value)

            # sleep(integration_time)
            t = time.time()-timezero
            remain = round(self.intTime-t)
            if t-prog_t > 10.0 and remain > 0:
                print('{:g} seconds remaining from {:g}'.format(remain, self.intTime))
                prog_t = t
            # print(t)

        # self.spad.run = True

        timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
        fpath_csv = './data/{}_Femto_{:g}nm_'.format(self.sample, self.wavelength)+timestamp_str+'.csv'
        header_sm = '{},Femto Avg [V],{},Femto std,{},Power Avg [W],{},Power Std,{},\n'.format( \
            self.sample, np.mean(femtovec), np.std(femtovec), np.mean(powervec), np.std(powervec)) + \
            'Time [s],Femto [V],Power [W],'

        np.savetxt(fpath_csv,
                   np.vstack((np.array(timevec), np.array(femtovec), np.array(powervec))).T,
                   delimiter=",", fmt='%s', header=header_sm, comments='')

        self.exp_running = False

        print('Femto detector measurement done\n')

        self.p_daq.plot(timevec, femtovec, pen=(1,2), clear=True)

        self.p_power.plot(timevec, np.abs(powervec), pen=(1,2), clear=True)

        # num_of_samples = int(self.sampling_freq*self.intTime)
        # self.daq.timing.cfg_samp_clk_timing(int(self.sampling_freq), samps_per_chan=num_of_samples)
        # # with visa_timeout_context(self.daq._rsrc, self.intTime*1000):
        # print('\nMeasuring Femto Detector from NI DAQ')
        # # saveDirectory, measDescription, fullpath = self.get_filename()
        #
        # # check that a file name is designated and that the sweep parameters are correct
        #
        # # if len(measDescription)>0 :
        # daq_buff = self.daq.read(number_of_samples_per_channel=num_of_samples, timeout=self.intTime*1.5)
        #
        # timevec = np.arange(0, num_of_samples, 1)/self.sampling_freq
        # powervec = np.array([v/self.pm_slope for v in daq_buff[1]])
        #
        # time_array_save = np.concatenate((np.array([0]), timevec))
        #
        # timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
        # fpath_csv = './data/Femto_{:g}nm_'.format(self.wavelength)+timestamp_str+'.csv'
        # header_sm = 'Time [s], Ch0 [V], Ch1 [V], Power [W]'
        # # header_sm = sm_sample + ' measured on SM probe when optical switch on channel {}'.format(channel)
        # np.savetxt(fpath_csv,
        #            np.vstack((timevec, np.array(daq_buff), powervec)).T,
        #            delimiter=",", fmt='%s', header=header_sm)
        #
        #     # else:
        #         # self.statusBar().showMessage('Canceled Femto Experiment, check parameters', 1000)
        # print('Femto detector measurement done')
        #
        # self.p_daq.plot(timevec, daq_buff[0], pen=(1,2), clear=True)
        # self.p_daq.plot(timevec, daq_buff[1], pen=(2,2))
        #
        # self.p_power.plot(timevec, np.abs(powervec), pen=(1,2), clear=True)


    def exp_spad(self, single=True):

        print('\nMeasuring SPAD and power from USB')
        self.exp_running = True

        if single ==True: # When run from Measure SPAD menu
            # if self.spad is not None:
            integration_time = max([int(self.spad_intTime*1000), 200])
            integration_time = min( [100000, integration_time])
            print('Setting spad integration time to {} ms'.format(integration_time))

            self.spad.integration_time = Q_(integration_time, 'ms')

            num_of_samples = round(self.intTime / (integration_time*1e-3))
            print(num_of_samples)
        else: # when called from different method
            integration_time = self.spad_intTime*1e3 # spad_intTime is in sec
            num_of_samples = round(self.intTime / (integration_time*1e-3))

        timezero  = time.time()
        timevec = np.arange(0,num_of_samples,1)*integration_time*1e-3
        spadvec = []
        powervec = []
        # flush buffer

        t = time.time()-timezero
        prog_t = t
        for t in timevec:
            spadvec.append(self.spad.count.magnitude/integration_time*1e3)

            meas_power = c_double()
            self.pm.measPower(byref(meas_power))
            powervec.append(meas_power.value)

            sleep(integration_time / 1000)
            # t = time.time()-timezero

            # print('t={}'.format(t))

            if t-prog_t > 5.0:
                print('{:g} seconds remaining from {:g}'.format(self.intTime-t, self.intTime))
                prog_t = t
            # print(t)

        # self.spad.run = True
        if single==True:
            timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
            fpath_csv = './data/{}_SPAD_{:g}nm_'.format(self.sample, self.wavelength)+timestamp_str+'.csv'
            header_sm = '{},SPAD Avg [Hz],{},SPAD std,{},Power Avg [W],{},Power Std,{},\n'.format( \
                self.sample, np.mean(spadvec), np.std(spadvec), np.mean(powervec), np.std(powervec)) + \
                'Time [s],SPAD [Hz],Ch1 [W],'

            np.savetxt(fpath_csv,
                       np.vstack((np.array(timevec), np.array(spadvec), np.array(powervec))).T,
                       delimiter=",", fmt='%s', header=header_sm, comments='')

            # Plot on widgets
            self.p_power.plot(timevec, powervec, pen=(1,2), clear=True)
            self.p_spad.plot(timevec, spadvec, pen=(1,2), clear=True)

        print('SPAD measurement done\n')
        self.exp_running = False

        return (timevec, spadvec, powervec)


    def exp_iv(self):
        with visa_timeout_context(self.smu._rsrc, 5000):
            print('\nMeasuring IV curve')
            saveDirectory, measDescription, fullpath = self.get_filename()

            # check that a file name is designated and that the sweep parameters are correct
            if len(measDescription)>0 and (self.biasV_stop-self.biasV_start)*self.biasV_step>0.0:
                try:
                    import winsound
                    winsound.Beep(2200, 1000)
                except:
                    print('winsound not available no beeping')

                start = time.time()

                # prepare source meter
                self.set_smu_params()

                if self.smu_channel== None:
                    # Keithley 2400
                    self.smu.set_integration_time(1.0)
                else:
                    # HP Parameter analyzer
                    self.chkbox3.setChecked(True)
                    # self.smu.set_integration_time('long')

                #  Load measurement parameters
                bias = self.biasV_start

                data_x = []
                data_y = []
                while (bias <= self.biasV_stop and self.biasV_step>0.0) or (bias >= self.biasV_stop and self.biasV_step<0.0):
                    print('Measuring current at bias {}'.format(bias.to_compact()))

                    self.smu.set_voltage(bias)
                    sleep(1.0) # wait a second for bias to settle

                    data_x.append(bias.magnitude)

                    data_row = []
                    data_row2 = []
                    for n in range(self.exp_biasV_N):
                        data_row.append(self.smu.measure_current())
                        if self.pm_tap is not None:
                            data_row2.append(self.pm_tap.power)
                        else:
                            data_row2.append(Q_(0.0, 'W'))
                        print('   Sample {} at {}: {}  with {}'.format(n, bias, data_row[-1], data_row2[-1]))
                    # Append average and stdev
                    data_mean = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row]))
                    data_std = np.std(np.array([measure.to_base_units().magnitude for measure in data_row]))
                    data_mean2 = np.mean(np.array([measure.to_base_units().magnitude for measure in data_row2]))
                    data_std2 = np.std(np.array([measure.to_base_units().magnitude for measure in data_row2]))

                    # data_row.extend([Q_(data_mean, 'A'), Q_(data_std, 'A')])
                    # data_row = [data_row[i-2] for i in range(len(data_row))]
                    # data_y.append(data_row)

                    data_y.append([Q_(data_mean, 'A'), Q_(data_std, 'A'), Q_(data_mean2, 'W'), Q_(data_std2, 'W')])

                    bias = bias + self.biasV_step

                # fields = ['Wavelength [nm]'] + ['Avg. Power [A]', 'Std Dev [A]'] + ['Photocurrent {} [A]'.format(n) for n in range(self.exp_N)]
                fields = ['Voltage [V]', 'Avg. Current [A]', 'Current stdev [A]', 'Avg. Tap Power [W]', 'Tap Power stdev [W]']
                self.save_to_csv(saveDirectory, measDescription, fields, data_x, data_y)

                plt.figure()
                plt.semilogy(data_x, [np.abs(row[0].magnitude) for row in data_y])
                plt.xlabel('Bias [V]')
                plt.ylabel('Current [A]')
                plt.savefig(path.normpath(path.join(saveDirectory,measDescription+'.png')))

                # return source meter to fast sampling

                if self.smu_channel== None:
                    # Keithley 2400
                    self.smu.set_integration_time(0.2)
                else:
                    # HP Parameter analyzer
                    self.chkbox1.setChecked(True)
                    # self.smu.set_integration_time('short')
                self.smu.set_voltage(self.smu_bias)

                print('Experiment lasted {} seconds'.format(time.time()-start))

                try:
                    import winsound
                    winsound.Beep(2500, 1000)
                except:
                    print('winsound not available no beeping')
            else:
                self.statusBar().showMessage('Canceled IV Experiment, check parameters', 1000)

    # def close_application(self):
    #
        # sys.exit()

    def processDataEvent(self, event):
        filter = "CSV (*.csv)"
        file_name = QtGui.QFileDialog()
        file_name.setFileMode(QtGui.QFileDialog.ExistingFiles)
        names = file_name.getOpenFileNames(self, "Open files for processing")
        # fpath = QtGui.QFileDialog.getSaveFileName(self, 'Save Data to')

        print(names)

        import re

        femtofiles = []
        femtowl = []
        spadfiles = []
        spadwl = []
        for n in names[0]:
            femtosearch = re.search("\S+Femto_?(\d+\.*\d*)\S+", n)
            if femtosearch:
                femtofiles.append(n)
                femtowl.append(float(femtosearch.groups()[0]))
            else:
                spadsearch = re.search("\S+SPAD_?(\d+\.*\d*)\S+", n)
                if spadsearch:
                    spadfiles.append(n)
                    spadwl.append(float(spadsearch.groups()[0]))

        # choose to plot either femto or spad
        if len(femtofiles) > len(spadfiles):
            files = femtofiles
            wl = femtowl
            device = "Femto"
        else:
            files = spadfiles
            wl = spadwl
            device = "SPAD"

        # sort according to wl
        wl = np.sort(wl)
        files = np.array(files)[np.argsort(wl)]

        print(wl)
        print(files)

        import csv

        avg = []
        std = []
        power_avg = []
        power_std = []
        for f in files:
            with open(f, 'r') as infile:
                reader = csv.reader(infile, delimiter=',')
                header = next(reader)
                sample = header[0] # Assumes user selected the same samples
                avg.append(float(header[2]))
                std.append(float(header[4]))
                power_avg.append(float(header[6]))
                power_std.append(float(header[8]))


        timestamp_str = datetime.strftime(datetime.now(),'%Y_%m_%d_%H_%M_%S')
        fpath_csv = './data/{}_{}_{:g}_to_{:g}nm_'.format(sample, device, wl[0], wl[-1])+timestamp_str+'.csv'
        header_sm = '{},{},\n'.format(sample, device) + \
            '\n'.join(files) + \
            '\nWavelength [nm],Avg,Std,Power Avg [W],Power Std,'
        np.savetxt(fpath_csv,
                   np.vstack((np.array(wl), np.array(avg), np.array(std),np.array(power_avg), np.array(power_std))).T,
                   delimiter=",", fmt='%s', header=header_sm, comments='')

        self.p_spec.plot(self.wave_2_waveshift(wl), avg, pen=(1,2), clear=True)

        print('Data processed\n')

    def closeEvent(self, event):
        self.timer.stop()
        if self.spad is not None:
            self.spad_timer.stop()

            self.spad.close()
        # Close Instruments
        try:
            self.laser.close(shutdown=False)
        except:
            print('Could not close laser : {}'.format(sys.exc_info()))
        else:
            print('Superlum tunable laser shutdown and closed')


        # # Redpitayas
        # try:
        #     # Turn off MEMS chopper
        #     rpc_s[chopper_rp_hostname].tx_txt('OUTPUT1:STATE OFF')
        #
        #     #if chopper_rp is in rp_s:
        #      #   rp_s[sm_voa_rp].tx_txt('OUTPUT1:STATE OFF')
        #     #for (hostname,rp_socket) in rp_s.items():
        #     #    rp_socket.close()
        #     print('{} with IP {} successfully disconnected'.format(chopper_rp_hostname, ipc_s[hostname]))
        # except:
        #     print('Could not close redpitayas : {}'.format( sys.exc_info())) # hostname, sys.exc_info()))

        # NI DAQ
        if self.daq is not None:
            try:
                self.daq.stop()
                self.daq.close()
                self.daq = None
            except:
                print('Could not close NI DAQ: {}'.format(sys.exc_info()))


        # Dicon Switch
        if self.switch is not None:
            try:
                self.switch.close()
            except:
                print('Could not close Dicon Optical Switch : {}'.format(sys.exc_info()))
            else:
                print('Dicon Optical Switch connection closed')


        # Thorlabs PM101A Powermeter
        if self.pm is not None:
            try:
                self.pm.close()
            except:
                print('Could not close Thorlabs Power meter : {}'.format(sys.exc_info()))
            else:
                print('Thorlabs Powermeter connection closed')
                self.pm = None

        if type(event) == bool:
            sys.exit()
        else:
            event.accept()

    # Helper Functions
    def get_filename(self):
        fpath = QtGui.QFileDialog.getSaveFileName(self, 'Save Data to')

        saveDirectory = path.dirname(fpath[0])
        measDescription = path.basename(fpath[0])

        return saveDirectory, measDescription, fpath[0]

    def save_to_csv(self, saveDirectory, measDescription, fields, data_x, data_y):

        # fields = ['Wavelength', 'count']
        fname = measDescription+'.csv'
        fpath = path.normpath(path.join(saveDirectory,fname))
        # print(fpath)

        with open(fpath, 'w', newline='') as csvfile:
            csvwriter = csv.writer(csvfile, dialect='excel')

            csvwriter.writerow(fields)

            for row in range(len(data_x)):
                try :
                    # print('print ok')
                    csvwriter.writerow([data_x[row]]+[format(data_y[row][col].magnitude) for col in range(len(data_y[row]))])
                except:
                    # print('exception occurred: ', sys.exc_info()[0])
                    csvwriter.writerow([data_x[row], format(data_y[row].magnitude)])
                    # print( format(data_y[row].magnitude))

    def wave_2_waveshift(self, laser_wl):
        # wave is filter center frequency in nm
        wave_shift = 1 / laser_wl * 1e7 - 1 / self.filter_wl * 1e7
        return wave_shift # in 1/cm

    def goto_wavelength(self, wavelength):
        # Check necessary instruments
        if self.spec is not None and self.mc is not None:
            print('going to {}'.format(wavelength))

            timeout = self.feedback_timeout # s
            tick = 0.0
            tock = 0.0

            # Get current wavelength
            self.spectra_data = np.transpose( self.spec.spectrum() )
            self.p_spec.plot(self.spectra_data, clear=True)

            current_wl = Q_(self.spectra_data[np.argmax(self.spectra_data[:,1]), 0], 'nm')
            self.label_wavelength.setText("Peak wavelength {:4.4g~}".format(self.current_wl.to_compact()))

            prevError = Q_(0.0, 'nm')
            errorAccum = Q_(0.0, 'nm')
            errorDot = Q_(0.0, 'nm')
            error = wavelength-current_wl

            while tick < timeout and np.abs(error)>Q_(0.3, 'nm'):
                errP = self.Kp*error.magnitude
                errI = self.Ki*(errorAccum).magnitude
                errD = self.Kd*(errorDot).magnitude
                drive = -np.clip(int(errP+errI+errD), -5000, 5000)

                if drive != 0:
                    self.mc.go_steps(N=drive)

                    #  clip tock to let motor have time to respond
                    tock = np.clip(np.abs(drive)/1000, 1.0, 5.0)
                else:
                    tock = 1.0

                tick = tick + tock
                sleep(tock)

                # Get new wavelength and estimate error
                self.spectra_data = np.transpose( self.spec.spectrum() )
                self.p_spec.plot(self.spectra_data, clear=True)

                current_wl = Q_(self.spectra_data[np.argmax(self.spectra_data[:,1]), 0], 'nm')
                self.label_wavelength.setText("Peak wavelength {:4.4g~}".format(self.current_wl.to_compact()))

                prevError = error
                error = wavelength-current_wl

                errorAccum = errorAccum + (error + prevError)/2.0*tock
                errorDot = (error-prevError)/tock
                print('Time {} : Moved {} steps resulting in error {}'.format(tick, drive, error.to_compact()))

            return current_wl

def run():
    app = QtGui.QApplication(sys.argv)
    GUI = Window()
    sys.exit(app.exec_())

# run application
run()
