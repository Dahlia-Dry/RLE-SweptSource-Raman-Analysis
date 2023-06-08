'''
Swept Source Raman Dash App
Dahlia Dry, 2022 | dahlia23@mit.edu
Physical Optics and Electronics Group
Running this file launches the Dash GUI for Swept Source Raman data collection and analysis
'''
#is this sentence here?
#file imports
from tkinter import E
from gui_components.spectrum import *
from gui_components.gui_layout import *
import gui_components.params as params
from gui_components.datalog import *
from gui_components.laser import *

#package imports
import dash
import diskcache
from dash import callback_context,no_update,DiskcacheManager
import pandas as pd
import numpy as np
import base64
import os
from dash.dependencies import Input,Output,State
from dash_extensions.enrich import MultiplexerTransform,DashProxy
from dash.exceptions import PreventUpdate
import base64
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import json
from scipy import stats
import random
import sys
if not params.test_mode:
    from instrumental import Q_
from ctypes import cdll,c_long, c_ulong, c_uint32,byref,create_string_buffer,c_bool,c_char_p,c_int,c_int16,c_double, sizeof, c_voidp
from time import sleep
import datetime
import zipfile
from zipfile import ZipFile
import copy
import time
#_______________________________________________________________________________
# Define special print function for debugging
def printv(*args):
    if params.verbose:
        print(args)
    else:
        pass
#______________________________________________________________________________
#INITIALIZE VARIABLES___________________________________________________________
fontawesome='https://maxcdn.bootstrapcdn.com/font-awesome/4.4.0/css/font-awesome.min.css'
mathjax = 'https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.4/MathJax.js?config=TeX-MML-AM_CHTML'

app = DashProxy(__name__,prevent_initial_callbacks=True,
                transforms=[MultiplexerTransform()],
                external_stylesheets=[dbc.themes.BOOTSTRAP,fontawesome],
                suppress_callback_exceptions=True)
app.scripts.append_script({ 'external_url' : mathjax })
datalog = Datalog()
buffer='      \n'
cache = diskcache.Cache("./cache")
background_callback_manager = DiskcacheManager(cache)
#LAYOUT_________________________________________________________________________
#create a dynamic layout that wipes global variables when page is reloaded
def app_layout():
    printv('redefining app layout')
    reset_globals(hard=True)
    structure=html.Div([
                header,
                dcc.Tabs(id='tab', value='tab1', children=[
                    dcc.Tab(label='Data Collection', value='tab1'),
                    dcc.Tab(label='Data Analysis', value='tab2'),
                ]),
                html.Div(id='tab-content',children=tab_1)
            ])
    return structure
app.layout = app_layout
#RENDER CONTENT_________________________________________________________________
@app.callback(Output('tab-content', 'children'),
              Input('tab', 'value'))
def render_content(tab):
    if tab=='tab1': #render Data Collection
        return tab_1
    elif tab == 'tab2': #render Data Analysis
        return tab_2
#INSTRUMENT CONTROLS____________________________________________________________
def instrument_connect(datalog,laser_name,spad_dict):
    global laser
    global pm
    global spad
    global switch
    global wavelength
    if params.test_mode:
        instrument_status={'laser':no_update,'pm':no_update,'spad':no_update}
        datalog.add('test mode; no instruments to connect')
        for address in spad_dict:
            spad[address] = None
        return instrument_status,datalog
    if laser is None:
        # Initialize laser
        try:
            laser = Laser(laser_name)
        except:
            datalog.add('Error connecting to laser {}'.format(sys.exc_info()))
            laser = None
            laser_status='DISCONNECTED-ERROR'
        else:
            datalog.add('Connected to '+laser_name+' through {}'.format(laser.get_port()))
            laser.warm_up()
            wavelength = laser.get_wavelength()
            laser_status='CONNECTED-WARMING UP'
    else:
        laser_status='CONNECTED'
    if pm is None:
        #Intialize ThorLabs Power Monitor
        if not params.power_monitoring:
            pm_status = 'WARNING: Power Monitoring set to OFF.'
        else:
            try:
                from drivers.TLPM import TLPM
                pm = TLPM()
                deviceCount = c_uint32()
                pm.findRsrc(byref(deviceCount))
                printv('devices found: ' + str(deviceCount.value))
                resourceName = create_string_buffer(1024)
                for i in range(0, deviceCount.value):
                    pm.getRsrcName(c_int(i), resourceName)
                    printv(c_char_p(resourceName.raw).value)
                    break
                pm.open(resourceName, c_bool(True), c_bool(True))
                message = create_string_buffer(1024)
                pm.getCalibrationMsg(message)
                printv(c_char_p(message.raw).value)
            except:
                pm = None
                datalog.add('Could not open Thorlabs Power meter : {}'.format(sys.exc_info()))
                pm_status='DISCONNECTED-ERROR'
            else:
                datalog.add('Thorlabs Powermeter connected')

                pm.setWavelength(c_double(wavelength))
                datalog.add('Set wavelength to {} nm'.format(wavelength))

                printv('Setting power auto range on')
                pm.setPowerAutoRange(c_int16(1))

                printv('Set Analog Output slope to {} V/W'.format(params.pm_slope))
                pm.setAnalogOutputSlope(c_double(params.pm_slope))

                printv('Setting input filter state to off for higher BW')
                pm.setInputFilterState(c_int16(0))
                pm_status='CONNECTED'
    else:
        pm_status='CONNECTED'
    for address in spad_dict:
        printv('ATTEMPTING TO CONNECT TO ', address)
        if address not in spad:
            try:
                from instrumental.drivers.spad.id120 import ID120
                spad[address]=ID120(visa_address=address)
            except:
                printv('ID120 SPAD unavailable: {}'.format(sys.exc_info()))
                datalog.add('ID120 SPAD unavailable: {}'.format(sys.exc_info()))
            else:
                datalog.add('SPAD connected, setting parameters')
                spad[address].bias = Q_(int(params.spad_bias*1e6), 'uV')
                spad[address].threshold = Q_(int(params.spad_threshold*1e6), 'uV')
                spad[address].set_temp = Q_(int(params.spad_temp),'millidegC')
                spad[address].integration_time = Q_(params.spad_intTime,'ms')
                spad[address].run = True
                spad_status='CONNECTED'
    if all([value==None for value in spad.values()]): #none of the spads connected
        spad_status='DISCONNECTED-ERROR'
    else:
        spad_status='CONNECTED'
    if switch is None:
        #Initialize Switch
        try:
            from drivers.dicon import DiConOpticalSwitch

            switch = DiConOpticalSwitch(port='COM7', verbose=False)
        except:
            printv('Error cannot connect to DiCon Switch')
        else:
            printv('Opened serial port to Dicon Switch')
            if switch.identify() > 0:
                # Test channel switch
                switch.set_channel(0)
                sleep(0.5)
                printv('channel on {}'.format(switch.get_channel()))
            else:
                printv('No reply from DiCon switch module, check connection between serial cable and switch')
                switch.close()
                switch = None
    instrument_status={'laser':laser_status,'pm':pm_status,'spad':spad_status}
    return instrument_status,datalog

def check_status(datalog):
    global laser
    global pm
    global spad
    global switch
    if params.test_mode:
        laser_status=no_update
    elif laser is not None:
        laser.get_status()
        if laser.is_ready():
            laser_status='CONNECTED-READY TO USE @ {} nm'.format(laser.get_wavelength())
        else:
            laser_status='CONNECTED-WARMING UP'
    else:
        laser_status='ERROR'
    if params.test_mode:
        spad_status=''
        for address in spad.keys():
            spad_status+='&ensp; Ch'+str(params.spad_addresses[address])+ ' : spad'+address.split('::')[3]+buffer
    elif not all([value==None for value in spad.values()]):
        spad_status=''
        for address in spad.keys():
            spad_status+='&ensp; Ch'+str(params.spad_addresses[address])+ ' : spad'+address.split('::')[3]+' {}, {:0<4.4g}C'.format(spad[address].state, spad[address].temp.magnitude/1e3)+buffer
    else:
        spad_status='ERROR'
    if pm is not None:
        pm_status='CONNECTED - TUNED TO {} nm'.format(wavelength)
    elif params.test_mode or not params.power_monitoring:
        pm_status=no_update
    else:
        pm_status='ERROR'
    instrument_status={'laser':laser_status,'pm':pm_status,'spad':spad_status}
    return instrument_status,datalog

def instrument_shutdown(datalog):
    if params.test_mode:
        datalog.add('test mode; no instruments to shut down')
        instrument_status={'laser':'TESTMODE','pm':'TESTMODE','spad':'TESTMODE'}
        return instrument_status, datalog
    global laser
    global pm
    global spad
    try:
        for address in spad.keys():
            spad[address].close()
    except:
        datalog.add('Could not close SPAD : {}'.format(sys.exc_info()))
        spad_status='DISCONNECT FAILED'
    else:
        spad_status='DISCONNECTED'
        spad={}
    if laser is not None:
        try:
            laser.shut_down()
        except:
            datalog.add('Could not close laser : {}'.format(sys.exc_info()))
            laser_status='DISCONNECT FAILED'
        else:
            laser_status='OFF AND DISCONNECTED'
            laser=None
    else:
        laser_status = 'DISCONNECTED'
    if pm is not None:
        try:
            pm.close()
        except:
            printv('Could not close Thorlabs Power meter : {}'.format(sys.exc_info()))
            pm_status='DISCONNECT FAILED'
        else:
            pm_status='DISCONNECTED'
            pm=None
    else:
        pm_status = 'DISCONNECTED'
    if switch is not None:
        try:
            switch.close()
        except:
            printv('Could not close Dicon switch : {}'.format(sys.exc_info()))
        else:
            switch = None
    instrument_status={'laser':laser_status,'pm':pm_status,'spad':spad_status}
    return instrument_status,datalog

def exp_spad(spad_obj,intTime):
    printv('\nMeasuring SPAD and power from USB')
    num_of_samples = round(intTime / (params.spad_intTime*1e-3))
    timevec = np.arange(0,num_of_samples)
    spadvec = []
    powervec = []
    time_exposed=0
    # flush buffer
    for t in timevec:
        if not params.test_mode:
            expbefore = datetime.datetime.now()
            spadvec.append(spad_obj.count.magnitude)
            if params.power_monitoring:
                power_sample = []
                time_start = time.time()
                while time.time()<time_start+params.spad_intTime/1000: #collect ~1s worth of power readings, then average
                    meas_power = c_double()
                    pm.measPower(byref(meas_power))
                    power_sample.append(meas_power.value)
                powervec.append(np.mean(power_sample))
            else:
                sleep(params.spad_intTime/1000)
                powervec.append(random.randint(1,1000))
            expafter=datetime.datetime.now()
            time_exposed += (expafter-expbefore).total_seconds()
        else:
            expbefore = datetime.datetime.now()
            spadvec.append(random.randint(1,1000))
            sleep(params.spad_intTime/1000)
            powervec.append(random.randint(1,1000))
            expafter=datetime.datetime.now()
            time_exposed+=(expafter-expbefore).total_seconds()
        sleep(params.spad_intTime / 10000) #1/10 of the integration time in s
    return spadvec, powervec, time_exposed

def wavelength_sweep(integration_time,nexp,datalog):
    '''A generator that compiles spectrum from SPAD measurements according to wavelength sweep routine'''
    global laser
    global pm
    global spad
    global wavelength
    global measurement
    global power_measurement
    global measurement_buf
    global power_measurement_buf
    global exp_index
    global current_channel
    global target_wavelengths
    if not params.test_mode:
        if params.power_monitoring:
            power=c_double()
        #check that laser on
        if not laser.is_on():
            datalog.add('WARNING: Laser output off during experiment')
    for wl in target_wavelengths:
        if not params.test_mode:
            tune_success=laser.set_wavelength(wl)
            #wavelength = laser.get_wavelength()
            wavelength=wl
            if params.power_monitoring:
                pm.setWavelength(c_double(wavelength))
                pm.measPower(byref(power))
                if power.value < params.low_power_warning: # if tap power is below 30 uW --> actual power is under 1mW (1:99 tap)
                    datalog.add('Tap power is low {}, please check laser'.format(power.value))
        else:
            wavelength=wl
            tune_success=True
        #loop over all active spads
        if not tune_success:
            datalog.add('TUNING FAILED: skipping '+str(wavelength)+' nm')
            continue
        else:
            datalog.add('set laser to '+str(wavelength)+' nm')
            for address in spad.keys():
                if params.test_mode or spad[address] is not None:
                    #divert excitation to correct channel
                    current_channel=int(params.spad_addresses[address])
                    if not params.test_mode:
                        try:
                            switch.set_channel(current_channel)
                            datalog.add('set channel to '+str(params.spad_addresses[address]))
                        except:
                            pass
                    buff_power=[]
                    buff_spad=[]
                    #Delay to make sure readings consistent after wavelength adjustment
                    sleep(params.measurement_delay)
                    for n in range(1,nexp+1):
                        if wl not in measurement_buf[address]:
                            measurement_buf[address][wl]=[]
                            power_measurement_buf[address][wl]=[]
                        exp_index+=1
                        buff_spad,buff_power,time_exposed=exp_spad(spad[address],integration_time)
                        measurement_buf[address][wl].append(buff_spad)
                        power_measurement_buf[address][wl].append(buff_power)
                        printv('ADDED BUF',measurement_buf)
                        yield buff_spad,buff_power,datalog,time_exposed
        exp_index=0

def process_data(metadata,filter_complete=True):
    global measurement
    global power_measurement
    global measurement_buf
    global power_measurement_buf
    measurement_df=dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
    power_df=dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
    meta_df=dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
    #transfer data from bufs to main
    printv('MEASUREMENT',measurement)
    printv('MEASURE_BUF',measurement_buf)
    for address in measurement:
        for wl in set(measurement[address].keys()).union(measurement_buf[address].keys()): #implicitly should also match wls in power
            if wl in measurement[address] and wl in measurement_buf[address]: #conflict exists; make sure new data is appended and old data not overwritten
                measurement_buf[address][wl] = measurement[address][wl] + measurement_buf[address][wl]
        measurement[address].update(measurement_buf[address])
        power_measurement[address].update(power_measurement_buf[address])
    printv('MEASUREMENT_after',measurement)
    #empty bufs in order to speed up long measurements
    measurement_buf = dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
    power_measurement_buf = dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
    printv('MEASURE_BUF_AFTER',measurement_buf)
    for address in measurement:
        for wl in measurement[address]: #implicitly should also match wls in power
            #convert spad integrations (to be summed in processing) into strings
            #output should be length nexp
            printv('PROCESSING',wl)
            measurement_df[address][wl] = ['~'.join([str(y) for y in x]) for x in measurement[address][wl]]
            power_df[address][wl] = ['~'.join([str(y) for y in x]) for x in power_measurement[address][wl]]
        meta_df[address] = metadata
        #filter out incomplete wavelengths for autosave runs
        if filter_complete:
            measurement_df[address] = {wl:measurement_df[address][wl] for wl in measurement_df[address] if len(measurement_df[address][wl]) == meta_df[address]['repetitions']}
            power_df[address] = {wl:power_df[address][wl] for wl in power_df[address] if len(power_df[address][wl]) == meta_df[address]['repetitions']}
        else: 
            minlen = min([len(x) for x in measurement_df[address].values()])
            for wl in measurement_df[address]:
                measurement_df[address][wl]=measurement_df[address][wl][:minlen]
                power_df[address][wl]=power_df[address][wl][:minlen]
        # measurement_df[address] = dict(filter(lambda elem: len(elem[1])==minlen,measurement_df[address].items()))
        # power_df[address] = dict(filter(lambda elem: len(elem[1])==minlen,power_df[address].items()))
        meta_df[address]['spad_name']='spad'+str(address.split('::')[3])
        meta_df[address]['switch_channel']=params.spad_addresses[address]
        #printv('METADAT',type(meta_df[address]['excitation_wavelengths']),[x for x in meta_df[address]['excitation_wavelengths']])
        meta_df[address]['excitation_wavelengths'] = meta_df[address]['excitation_wavelengths']
        meta_df[address]['excitation_ramanshifts'] = [(1/float(x)-1/float(meta_df[address]['filter_wavelength']))*1e7 for x in meta_df[address]['excitation_wavelengths']]
        measurement_df[address] = pd.DataFrame(measurement_df[address])
        measurement_df[address].index.name = 'n_sample'
        measurement_df[address].index = np.arange(1,len(measurement_df[address])+1)
        power_df[address] = pd.DataFrame(power_df[address])
        power_df[address].index.name = 'n_sample'
        power_df[address].index = np.arange(1,len(power_df[address])+1)
    return measurement_df,power_df,meta_df
#HELPERS________________________________________________________________________
def reset_globals(hard=False):
    if hard:
        global laser
        global pm
        global spad
        global switch
        global target_wavelengths
        global current_channel
        global status
        laser=None
        pm=None
        spad={}
        switch=None
        printv('override Hard')
        target_wavelengths=[]
        current_channel=None
        status = 'Measurement not in progress'
    global wavelength
    global exp_index
    global measurement
    global measurement_buf
    global power_measurement
    global power_measurement_buf
    global experiment_generator
    exp_index=0
    wavelength=-1
    measurement=dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
    power_measurement=dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
    measurement_buf=dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
    power_measurement_buf=dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
    experiment_generator=None

def closest_point(selected_point,x,y):
    msx = selected_point[0]
    msy = selected_point[1]
    dist = np.sqrt((np.array(x)-msx)**2 + (np.array(y)-msy)**2)
    return np.argmin(dist)


#APP HEADER/SETTINGS CALLBACKS__________________________________________________
@app.callback(
    Output('settings', 'is_open'),
    [Input('open-settings', 'n_clicks'),Input('close-settings', 'n_clicks')],
    State('settings', 'is_open'))
def toggle_settings(n1,n2,isopen):
    if isopen:
        reset_globals(hard=True)
    if n1 or n2:
        return not isopen
    return isopen

#DATA ANALYSIS CALLBACKS________________________________________________________
@app.callback([Output('file-list', 'data'),
                Output('file-list','selected_rows'),
                Output('file-list','style_data_conditional'),
                Output('file-list','columns'),
              Output('spectra','children'),
              Output('original-spectra','children'),
              Output('log','children')],
              [Input('upload-data', 'contents'),
              Input('datatable-columns','value')],
              [State('spectra','children'),
              State('original-spectra','children'),
              State('upload-data', 'filename'),
              State('upload-data', 'last_modified')])
def show_files(list_of_contents, metadata_cols,json_spectra, json_original_spectra, list_of_names, list_of_dates):
    return_values = {'file-list_data':no_update,
                     'file-list_selected':no_update,
                     'file-list_style':no_update,
                     'file-list_columns':no_update,
                     'spectra':no_update,
                     'original-spectra':no_update,
                     'log':no_update}
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
        printv('SHOWMETA',spectra[0].meta['integration'],len(spectra[0].ref))
    else:
        spectra=[]
    if json_original_spectra is not None:
        original_spectra = spec_from_json(json_original_spectra)
    else:
        original_spectra=[]
    ctx = dash.callback_context
    if not ctx.triggered:
        trigger=None
    else:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    printv('Trigger',trigger)
    if trigger=='upload-data' and list_of_contents != 'null':
        #gen newly uploaded spectra
        for newspec in batch_process_uploads(list_of_contents,list_of_names,list_of_dates):
            spectra.append(newspec)
            original_spectra.append(newspec)
    metadata_cols.append('filename')
    if len(spectra)>0:
        data=[{col:s.meta[col] for col in metadata_cols} for s in spectra]
        data_cols = ([{'id':p,
                       'name':p,
                       'editable':Metadata().fetch(key=p,trait='editable'),
                       'on_change':{'action':'coerce','failure':'reject'},
                       'type':Metadata().fetch(key=p,trait='datatype')} for p in metadata_cols if p != 'filename'])
        logstr = str(Processlog([s.log for s in spectra]))
        #printv(pd.Series(spectra).to_json(orient='records'))
        style_data_conditional = [
        {
            'if': {
                'row_index': i,
            },
            'color': colorlist[i]
        } for i in range(len(data))
        ]
        return_values['file-list_data'] = data
        return_values['file-list_selected'] = [x for x in range(len(data))]
        return_values['file-list_style'] = style_data_conditional
        return_values['file-list_columns'] = data_cols
        return_values['spectra'] = jsonify(spectra)
        return_values['original-spectra'] = jsonify(original_spectra)
        return_values['log'] = logstr
        return tuple(list(return_values.values()))
    else:
        data=[{col:None for col in metadata_cols}]
        data_cols = ([{'id':p,'name':p,'editable':Metadata().fetch(key=p,trait='editable')} for p in metadata_cols if p != 'filename'])
        return_values['file-list_data'] = data
        return_values['file-list_selected'] = [x for x in range(len(data))]
        return_values['file-list_columns'] = data_cols
        return tuple(list(return_values.values()))

@app.callback(
    [Output('file-list', 'selected_rows')],
    [Input('select-all', 'n_clicks'),
    Input('deselect-all', 'n_clicks')],
    [State('file-list', 'data')]
)
def toggle_all_none(select_n_clicks, deselect_n_clicks, original_rows):
    ctx = dash.callback_context.triggered[0]
    ctx_caller = ctx['prop_id']
    if original_rows is not None:
        if ctx_caller == 'select-all.n_clicks':
            selected_ids = [row for row in original_rows]
            return [x for x in range(len(original_rows))]
        if ctx_caller == 'deselect-all.n_clicks':
            return []
    else:
        return no_update

@app.callback([Output('spectra','children'),
                Output('log','children'),
                Output('file-list', 'data'),
                Output('file-list','selected_rows'),
                Output('file-list','style_data_conditional')],
              [Input('revert','n_clicks')],
              [State('original-spectra','children'),
              State('datatable-columns','value')])
def revert_to_original(n,json_original_spectra,metadata_cols):
    if json_original_spectra is None:
        raise PreventUpdate
    original_spectra=spec_from_json(json_original_spectra)
    metadata_cols.append('filename')
    if len(original_spectra)==0:
        raise PreventUpdate
    data=[{col:s.meta[col] for col in metadata_cols} for s in original_spectra]
    logstr = str(Processlog([s.log for s in original_spectra]))
    style_data_conditional = [
    {
        'if': {
            'row_index': i,
        },
        'color': colorlist[i]
    } for i in range(len(data))
    ]
    return_values = {'spectra':jsonify(original_spectra),
                     'log':str(Processlog([s.log for s in original_spectra])),
                     'file-list_data':data,
                     'file-list_selected':[x for x in range(len(data))],
                     'file-list_style':style_data_conditional}
    return tuple(list(return_values.values()))

@app.callback([Output('spectra','children'),
                Output('original-spectra','children'),
                Output('log','children'),
                Output('graphnum','children')],
              [Input('file-list','data')],
              [State('spectra','children'),
              State('original-spectra','children'),
              State('file-list','data_previous')])
def update_spectra_source(rows,json_spectra,json_original_spectra,previous_rows): #re-init the spectra if changes to datatable occur
    if json_spectra is not None and json_original_spectra is not None:
        spectra_dict = {s.meta['filename']:s for s in spec_from_json(json_spectra)}
        original_spectra_dict = {s.meta['filename']:s for s in spec_from_json(json_original_spectra)}
    else:
        raise PreventUpdate
    df = pd.DataFrame(rows)
    #printv('DF',df)
    dfprev = pd.DataFrame(previous_rows)
    #printv('PREV',dfprev)
    diffs = pd.concat([df,dfprev]).drop_duplicates(keep=False)
    #printv('DIFFS',diffs)
    if len(dfprev)==0 or len(df)==0:
        raise PreventUpdate
    for i in set(list(diffs.index)):
        if len(diffs[diffs.index==i])==1: #1 entry means something added or removed
            if diffs[diffs.index==i]['filename'].tolist()[0] in dfprev['filename'].tolist(): #deleted ->remove from spectra list
                printv('deleted!')
                try:
                    del spectra_dict[diffs[diffs.index==i]['filename'].tolist()[0]]
                    del original_spectra_dict[diffs[diffs.index==i]['filename'].tolist()[0]]
                except:
                    pass #already deleted
        else: #2 entries means something modified
            filename = diffs[diffs.index==i]['filename'].tolist()[0]
            for col in [x for x in diffs.columns if Metadata().fetch(key=x,trait='editable')]:
                if col=='experiment_name' and not pd.isna(df[col].iloc[i]) and df[col].iloc[i]!='':
                    spectra_dict[filename].log.replace(spectra_dict[filename].meta[col],df[col].iloc[i])
                if df[col].iloc[i] != dfprev[col].iloc[i] and not pd.isna(df[col].iloc[i]) and df[col].iloc[i]!='':
                    spectra_dict[filename].meta[col] = df[col].iloc[i]
    return_values = {'spectra':list(spectra_dict.values()), #remove entires deleted by user from table
                     'original-spectra':jsonify(list(original_spectra_dict.values())),
                     'log':str(Processlog([s.log for s in spectra])),
                     'graphnum':'0'}
    return tuple(list(return_values.values()))

@app.callback(Output('graphnum','children'),
            [Input('forward','n_clicks'),
            Input('back','n_clicks')],
            State('graphnum','children'))
def update_graphnum(forward,back,graphnum):
    changed_id = [p['prop_id'] for p in callback_context.triggered][0]
    g =int(str(graphnum).strip())
    if 'forward' in changed_id:
        g=g+1
    elif 'back' in changed_id:
        g = g-1
    return str(g)

@app.callback(Output('current','figure'),
                [Input('spectra','children'),
                Input('graphnum','children'),
                Input('current','clickData'),
                Input('ydata-type','value'),
                Input('dataprocessing-type','value'),
                Input('spectral-units','value')])
def update_current(json_spectra,graphnum,clickData,ydata_switchval,processing_switchval,spectral_units):
    ctx = dash.callback_context
    if not ctx.triggered:
        trigger=None
    else:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        return no_update
    g =int(graphnum.strip()) % len(spectra)
    color=colorlist[g]
    printv(g,color)
    if processing_switchval:
        mode='lines+markers'
        printv('EXPERIMENT TYPE',spectra[g].meta['experiment_type'])
        if spectra[g].meta['experiment_type'] in ['Peak Measurement', 'peak']:
            if ydata_switchval:
                fig = spectra[g].plot_samples(color=color,label='experiment_name')
            else:
                fig = spectra[g].plot_samples(color=color,ydata='power',label='experiment_name')
        else:
            if spectral_units:
                xunits='ramanshift'
            else:
                xunits='wavelength'
            if ydata_switchval:
                fig = spectra[g].plot(color=color,label='experiment_name',xunits=xunits)
            else:
                fig = spectra[g].plot(color=color,label='experiment_name',ydata='power',xunits=xunits)
    else:
        if ydata_switchval:
            fig=spectra[g].plot_raw(color=color,label='experiment_name')
        else:
            fig=spectra[g].plot_raw(color=color,label='experiment_name',ydata='power')
    if clickData is not None and trigger=='current':
        selected_point = [clickData['points'][0]['x'],clickData['points'][0]['y']]
        fig.add_trace(go.Scatter(x=[selected_point[0]],y=[selected_point[1]],marker_symbol='x',line=dict(color='#000000'),
                                name='selected point'))
        fig.update_layout(showlegend=False)
    return fig

@app.callback(Output('working','figure'),
                [Input('spectra','children'),
                Input('all-spec','n_clicks'),
                Input('working','clickData'),
                Input('ydata-type','value')])
def update_working(json_spectra,spec_clicks,clickData,ydata_switchval):
    ctx = dash.callback_context
    if not ctx.triggered:
        trigger=None
    else:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        return no_update
    fig=go.Figure()
    for i in range(len(spectra)):
        color=colorlist[i]
        mode='lines+markers'
        if ydata_switchval:
            fig.add_trace(spectra[i].plot(color=color,label='experiment_name',show_err=True).data[0])
            yaxis='Count'
        else:
            fig.add_trace(spectra[i].plot(color=color,ydata='power',label='experiment_name',show_err=True).data[0])
            yaxis = 'Powermeter Reading (W)'
    if clickData is not None and trigger=='working':
        selected_point = [clickData['points'][0]['x'],clickData['points'][0]['y']]
        fig.add_shape(type='line',
                    x0=selected_point[0],x1=selected_point[0],
                    y0=0,y1=np.max(np.array([x.ref for x in spectra])),
                    line=dict(dash='dot',color='#000000'))
    fig.update_layout(title='Combined Spectra',xaxis_title='Raman Shift (cm^-1)',yaxis_title=yaxis)
    return fig

@app.callback([Output('spectra','children'),
               Output('log','children')],
              Input('power-normalize','n_clicks'),
              [State('file-list','selected_rows'),
                State('file-list','data'),
                State('spectra','children')])
def power_normalize(n, selected_rows,rows,json_spectra):
    if json_spectra is None or selected_rows is None or selected_rows == []:
        return no_update,no_update
    spectra= spec_from_json(json_spectra)
    df = pd.DataFrame([rows[x] for x in selected_rows])
    for i in range(len(spectra)):
        if spectra[i].meta['filename'] in df['filename'].to_list():
            spectra[i].power_normalize()
    logstr = str(Processlog([s.log for s in spectra]))
    return jsonify(spectra),logstr

@app.callback([Output('spectra','children'),
               Output('log','children')],
              Input('inter-normalize','n_clicks'),
              [State('file-list','selected_rows'),
                State('file-list','data'),
                State('spectra','children')])
def internormalize(n, selected_rows,rows,json_spectra):
    if json_spectra is None or selected_rows is None or selected_rows == []:
        return no_update,no_update
    spectra= spec_from_json(json_spectra)
    df = pd.DataFrame([rows[x] for x in selected_rows])
    selected_specs = []
    unselected_specs=[]
    for i in range(len(spectra)):
        if spectra[i].meta['filename'] in df['filename'].to_list():
            selected_specs.append(spectra[i])
        else:
            unselected_specs.append(spectra[i])
    inter_normalize(selected_specs)
    spectra = unselected_specs + selected_specs
    logstr = str(Processlog([s.log for s in spectra]))
    return jsonify(spectra),logstr

@app.callback([Output('spectra','children'),
               Output('log','children')],
              Input('median-raw','n_clicks'),
              [State('file-list','selected_rows'),
                State('file-list','data'),
                State('spectra','children')])
def medianfilter_raw(n, selected_rows,rows,json_spectra):
    if json_spectra is None or selected_rows is None or selected_rows == []:
        return no_update,no_update
    spectra= spec_from_json(json_spectra)
    df = pd.DataFrame([rows[x] for x in selected_rows])
    for i in range(len(spectra)):
        if spectra[i].meta['filename'] in df['filename'].to_list():
            spectra[i]=spectra[i].medianfilter_raw()
    logstr = str(Processlog([s.log for s in spectra]))
    return jsonify(spectra),logstr

@app.callback([Output('rebin_dialogue','children'),
               Output('do_rebin', 'is_open'),
               Output('spectra','children'),
               Output('log','children'),
               Output('file-list', 'data')],
               [Input('re-bin', 'n_clicks'),Input('close-re-bin', 'n_clicks')],
               [State('do_rebin', 'is_open'),
                State('file-list','selected_rows'),
                State('file-list','data'),
                State('spectra','children'),
                State('new-integration','value'),
                State('new-nexp','value'),
                State('datatable-columns','value')])
def toggle_rebin(n1,n2,isopen,selected_rows,rows,json_spectra,new_integration,new_repetitions,metadata_cols):
    return_values = {'rebin_dialogue':no_update,
                     'do_rebin':no_update,
                     'spectra':no_update,
                     'log':no_update,
                     'file-list':no_update}
    ctx = dash.callback_context
    if not ctx.triggered:
        trigger=None
    else:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger=='re-bin' and n1>0:
        return_values['do_rebin'] = not isopen
        return tuple(list(return_values.values()))
    elif trigger=='close-re-bin':
        if json_spectra is None:
            return_values['rebin_dialogue']= 'No spectra to re-bin.'
            return_values['do_rebin'] = isopen
            return tuple(list(return_values.values()))
        if selected_rows is None or selected_rows == []:
            return_values['rebin_dialogue']= 'No spectra selected to re-bin.'
            return_values['do_rebin'] = isopen
            return tuple(list(return_values.values()))
        spectra= spec_from_json(json_spectra)
        df = pd.DataFrame([rows[x] for x in selected_rows])
        selected_spectra = [s for s in spectra if s.meta['filename'] in df['filename'].to_list()]
        ntotal = int(selected_spectra[0].meta['integration'])*int(selected_spectra[0].meta['repetitions'])
        if ntotal != new_integration*new_repetitions:
            return_values['rebin_dialogue']='Total number of spad exposures (integration time x number of exposures) must ='+str(ntotal)
            return_values['do_rebin'] = isopen
            return tuple(list(return_values.values()))
        for spec in selected_spectra:
            if int(spec.meta['integration'])*int(spec.meta['repetitions']) != ntotal:
                return_values['rebin_dialogue']='All selected spectra must have total number of spad exposures ='+str(ntotal)
                return_values['do_rebin'] = isopen
                return tuple(list(return_values.values()))
        for i in range(len(spectra)):
            if spectra[i].meta['filename'] in df['filename'].to_list():
                spectra[i] = spectra[i].rebin(new_repetitions,new_integration)
        logstr = str(Processlog([s.log for s in spectra]))
        metadata_cols.append('filename')
        data=[{col:s.meta[col] for col in metadata_cols} for s in spectra]
        return_values['do_rebin'] = not isopen
        return_values['spectra'] = jsonify(spectra)
        return_values['log'] = logstr
        return_values['file-list'] = data
        return tuple(list(return_values.values()))
    raise PreventUpdate

@app.callback([Output('remove_samp_dialogue','children'),
               Output('do_remove_samples', 'is_open'),
               Output('spectra','children'),
               Output('log','children'),
               Output('file-list', 'data')],
               [Input('remove-samples', 'n_clicks'),Input('close-remove-samples', 'n_clicks')],
               [State('do_remove_samples', 'is_open'),
                State('file-list','selected_rows'),
                State('file-list','data'),
                State('spectra','children'),
                State('samples-to-remove','value'),
                State('datatable-columns','value')])
def toggle_remove_samples(n1,n2,isopen,selected_rows,rows,json_spectra,samples_to_remove,metadata_cols):
    return_values = {'remove_samp_dialogue':no_update,
                     'do_remove_samples':no_update,
                     'spectra':no_update,
                     'log':no_update,
                     'file-list':no_update}
    ctx = dash.callback_context
    if not ctx.triggered:
        trigger=None
    else:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger=='remove-samples' and n1>0:
        return no_update,not isopen,no_update,no_update,no_update
    elif trigger=='close-remove-samples':
        if json_spectra is None:
            return_values['remove_samp_dialogue']='No spectra uploaded.'
            return_values['do_remove_samples'] = isopen
            return tuple(list(return_values.values()))
        if selected_rows is None or selected_rows == []:
            return_values['remove_samp_dialogue']='No spectra selected.'
            return_values['do_remove_samples'] = isopen
            return tuple(list(return_values.values()))
        spectra= spec_from_json(json_spectra)
        df = pd.DataFrame([rows[x] for x in selected_rows])
        selected_spectra = [s for s in spectra if s.meta['filename'] in df['filename'].to_list()]
        samp_conditions = [x for x in samples_to_remove.strip('[').strip(']').replace(' ','').split(',')]
        samps_to_remove= {}
        for spec in selected_spectra:
            s_buf= []
            for c in samp_conditions:
                if '-' in c:
                    s_buf += [x for x in range(1,spec.meta['repetitions']+1) if x>=int(c.split('-')[0]) and x<=int(c.split('-')[1])]
                else:
                    s_buf.append(int(c))
            for x in s_buf:
                if x <1 or x >spec.meta['repetitions']:
                    remove_dialogue = 'Specified samples out of bounds for selected spectra.'
                    return remove_dialogue,isopen,no_update,no_update,no_update
            samps_to_remove[spec.meta['filename']]= s_buf
        for i in range(len(spectra)):
            if spectra[i].meta['filename'] in df['filename'].to_list():
                spectra[i] = spectra[i].remove_samples(samps_to_remove[spectra[i].meta['filename']])
        logstr = str(Processlog([s.log for s in spectra]))
        metadata_cols.append('filename')
        data=[{col:s.meta[col] for col in metadata_cols} for s in spectra]
        return_values['do_remove_samples'] = not isopen
        return_values['spectra'] = jsonify(spectra)
        return_values['log'] = logstr
        return_values['file-list'] = data
        return tuple(list(return_values.values()))
    raise PreventUpdate

@app.callback([Output('remove_wl_dialogue','children'),
               Output('do_remove_wavelengths', 'is_open'),
               Output('spectra','children'),
               Output('log','children'),
               Output('file-list', 'data')],
               [Input('remove-wavelengths', 'n_clicks'),Input('close-remove-wavelengths', 'n_clicks')],
               [State('do_remove_wavelengths', 'is_open'),
                State('file-list','selected_rows'),
                State('file-list','data'),
                State('spectra','children'),
                State('wavelengths-to-remove','value'),
                State('datatable-columns','value')])
def toggle_remove_wavelengths(n1,n2,isopen,selected_rows,rows,json_spectra,wls_to_remove,metadata_cols):
    ctx = dash.callback_context
    return_values = {'remove_wl_dialogue':no_update,
                     'do_remove_wavelengths':no_update,
                     'spectra':no_update,
                     'log':no_update,
                     'file-list':no_update}
    if not ctx.triggered:
        trigger=None
    else:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    if trigger=='remove-wavelengths' and n1>0:
        return no_update,not isopen,no_update,no_update,no_update
    elif trigger=='close-remove-wavelengths':
        if json_spectra is None:
            remove_dialogue='No spectra uploaded.'
            return remove_dialogue,isopen,no_update,no_update,no_update
        if selected_rows is None or selected_rows == []:
            remove_dialogue='No spectra selected.'
            return remove_dialogue,isopen,no_update,no_update,no_update
        spectra= spec_from_json(json_spectra)
        df = pd.DataFrame([rows[x] for x in selected_rows])
        selected_spectra = [s for s in spectra if s.meta['filename'] in df['filename'].to_list()]
        wls_conditions = [x for x in wls_to_remove.strip('[').strip(']').replace(' ','').split(',')]
        wls_to_remove= {}
        for spec in selected_spectra:
            wl_buf= []
            for c in wls_conditions:
                if '-' in c:
                    wl_buf += [x for x in spec.meta['excitation_wavelengths'] if np.round(x,2)>=float(c.split('-')[0]) and np.round(x,2)<=float(c.split('-')[1])]
                else:
                    wl_buf.append(float(c))
            for x in wl_buf:
                if x not in spec.meta['excitation_wavelengths']:
                    remove_dialogue = 'Specified wavelengths out of bounds for selected spectra.'
                    return remove_dialogue,isopen,no_update,no_update,no_update
            wls_to_remove[spec.meta['filename']]= wl_buf
        for i in range(len(spectra)):
            if spectra[i].meta['filename'] in df['filename'].to_list():
                spectra[i] = spectra[i].remove_wavelengths(wls_to_remove[spectra[i].meta['filename']])
        logstr = str(Processlog([s.log for s in spectra]))
        metadata_cols.append('filename')
        data=[{col:s.meta[col] for col in metadata_cols} for s in spectra]
        return_values['do_remove_wavelengths'] = not isopen
        return_values['spectra'] = jsonify(spectra)
        return_values['log'] = logstr
        return_values['file-list'] = data
        return tuple(list(return_values.values()))
    return_values['do_remove_wavelengths'] = isopen
    return tuple(list(return_values.values()))
    
@app.callback([Output('working','figure'),
               Output('log','children')],
              [Input('lod','n_clicks')],
              [State('working','clickData'),
               State('spectra','children')])
def do_lod(lod_clicks,clickData,json_spectra):
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        return no_update,no_update
    raman = clickData['points'][0]['x']
    max_index = spectra[0].meta['excitation_ramanshifts'].index(raman)
    try:
        concentrations = np.array([float(x.meta['concentration']) for x in spectra])
    except:
        raise TypeError('all concentration values must be integer or float')
    #inter-normalize refs/noise
    #inter_normalize(spectra)
    refs = np.array([x.ref[max_index] for x in spectra])
    noise = np.array([x.noise[max_index] for x in spectra])
    #np.savetxt('noise.csv',noise,delimiter=',')
    sy = np.mean(noise)
    printv('sy',sy)
    fig=go.Figure(data=go.Scatter(x=concentrations,y=refs,
                                  error_y=dict(
                                            type='data',
                                            array=noise,
                                            visible=True
                                  ),mode='markers'))
    res=stats.linregress(concentrations,refs)
    fig.add_trace(go.Scatter(x=concentrations,y=concentrations*res.slope+res.intercept,mode='lines',
                            hovertemplate='<i>y = %.5f * x + %.5f</i><br>'%(res.slope,res.intercept)+\
                                            '<b>R^2 </b>= %.3f' %(res.rvalue**2)))
    printv(sy,res.slope,res.intercept)
    #lod =(3*sy+np.min(refs)-res.intercept)/res.slope
    lod =(3*sy)/res.slope
    printv(lod,np.min(refs),np.max(refs))
    fig.add_shape(type='line',
                x0=lod,x1=lod,
                y0=np.min(refs),y1=np.max(refs),
                line=dict(dash='dot',color='#000000'))
    fig.update_layout(title = 'LOD Concentration for ' + '%.2f' %(raman) + ' Raman Peak is '+ '%.4f' %(lod)+ 'ppm',
                        xaxis_title = 'Concentration (ppm)',
                        yaxis_title = 'Signal',showlegend=False)
    logstr = Processlog([s.log for s in spectra])
    logstr.add('LOD Concentration for ' + '%.2f' %(raman) + ' Raman Peak is '+ '%.4f' %(lod)+ 'ppm')
    logstr.add('y = %.5f * x + %.5f'%(res.slope,res.intercept))
    logstr.add('r-squared = ' + str(res.rvalue**2))
    return fig,str(logstr)

@app.callback([Output('working','figure')],
              [Input('mean-n','n_clicks')],
              [State('working','clickData'),
                State('spectra','children')])
def show_mean(n,clickData,json_spectra):
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        return no_update
    raman = clickData['points'][0]['x']
    max_index = spectra[0].meta['excitation_ramanshifts'].index(raman)
    fig=go.Figure()
    for spec in spectra:
        data = spec.fetch_raw_data()[max_index].flatten()
        samples= np.arange(0,len(data),step=1)
        means = [np.mean(data[:s]) for s in samples]
        fig.add_trace(go.Scatter(x=samples,y=means,mode='lines+markers',name=spec.meta['experiment_name']))
    fig.update_layout(title = 'Sample Mean vs Number of Samples',
                        xaxis_title = 'Spad Integrations ('+str(spectra[0].meta['spad_integration_time']/1000)+' s)',
                        yaxis_title = 'Mean')
    return fig

@app.callback([Output('working','figure')],
              [Input('std-n','n_clicks')],
              [State('working','clickData'),
                State('spectra','children')])
def show_sdev(n,clickData,json_spectra):
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        return no_update
    raman = clickData['points'][0]['x']
    max_index = spectra[0].meta['excitation_ramanshifts'].index(raman)
    fig=go.Figure()
    for spec in spectra:
        data = spec.fetch_raw_data()[max_index].flatten()
        samples= np.arange(0,len(data),step=1)
        means = [np.std(data[:s],ddof=1) for s in samples]
        fig.add_trace(go.Scatter(x=samples,y=means,mode='lines+markers',name=spec.meta['experiment_name']))
    fig.update_layout(title = 'Sample Standard Deviation vs Number of Samples',
                        xaxis_title = 'Spad Integrations ('+str(spectra[0].meta['spad_integration_time']/1000)+' s)',
                        yaxis_title = 'Standard Deviation')
    return fig

@app.callback(Input('export','n_clicks'),
              [State('file-list','selected_rows'),
                State('file-list','data'),
                State('spectra','children')],
              Output('log','children'))
def export_specs(n,selected_rows,rows,json_spectra):
    if not n or json_spectra is None or selected_rows is None or selected_rows == []:
        return no_update
    spectra = spec_from_json(json_spectra)
    df = pd.DataFrame([rows[x] for x in selected_rows])
    selected_spectra = [s for s in spectra if s.meta['filename'] in df['filename'].to_list()]
    for spec in selected_spectra:
        spec.meta['data_operations']=str(spec.log)
        spec.save(params.working_directory)
        printv('SAVING OPS:',spec.log)
    #remove created instances of data in working directory
    if platform == 'darwin':
        os.system('rm -rf *.power')
        os.system('rm -rf *.spad')
        os.system('rm -rf *.log')
    else:
        os.system('del *.power')
        os.system('del *.spad')
        os.system('del *.log')
    logstr = str(Processlog([s.log for s in spectra]))
    return logstr

#DATA COLLECTION CALLBACKS______________________________________________________
#data collection leverages a circular callback structure to read from a generator of spad data
@app.callback([Output('pause','children'),
                Output('pause','outline'),
                Output('status','children'),
                Output('exposing','children'),
                Output('data-log','children')],
                Input('pause','n_clicks'),
                [State('exposing','children'),
                 State('data-log','children')])
def update_pause(n_clicks,exp,datalog):
    if n_clicks % 2 ==0: #is not paused/unpause
        children = 'Pause'
        outline=False
        experiment_status='Measurement in progress'
        exposing = not(bool(exp))
    else: #is paused
        children='Resume'
        outline=True
        experiment_status='Measurement paused'
        exposing=no_update
    if params.verbose_log:
        datalog=Datalog(datalog)
        datalog.add('called update_pause()')
        datalog = str(datalog)
    else:
        datalog = no_update
    return children,outline,experiment_status,exposing,datalog

@app.callback(Input('progress-interval','n_intervals'),
              [Output('exposing','children'),
              Output('prev_exposures','children')],
              [State('exposing','children'),
              State('current_exposures','children'),
              State('total_exposures','children'),
              State('prev_exposures','children')])
def control_exposure(n,exposing,current_exposures,total_exposures,prev_exposures):
    global experiment_generator
    global status
    printv(exposing,current_exposures,prev_exposures,total_exposures)
    if status == 'Measurement ending':
        return not bool(exposing), no_update
    if experiment_generator is None:
        return no_update,no_update
    if int(current_exposures)<=int(total_exposures) and int(current_exposures)>=0 and int(prev_exposures) != int(current_exposures):
        return not bool(exposing),str(int(prev_exposures)+1) #switch to trigger data collection
    else:
        return no_update,no_update

@app.callback([Input('exposing', 'children')],
                [Output('current_wl','children'),
                Output('trigger-download','children'),
                Output('data-log','children'),
                Output('current_exposures','children'),
                Output('prev_exposures','children'),
                Output('failed_wavelengths','children')],
                [State('experiment-type','value'),
                State('current_wl','children'),
                State('trigger-download','children'),
                State('data-log','children'),
                State('integration','value'),
                State('current_exposures','children'),
                State('total_exposures','children'),
                State('failed_wavelengths','children'),
                State('rep_count','children'),
                State('exp-reps','value')])
def collect_data(exposing,experiment_type,current_wl,download_trigger,datalog,integration,current_exposures,total_exposures,failed_wavelengths,rep_count,exp_reps):
    datalog=Datalog(datalog)
    global experiment_generator
    global exp_index
    global status
    return_values = {'current_wl':no_update,
                     'trigger-download':no_update,
                     'data-log':no_update,
                     'current_exposures':no_update,
                     'prev_exposures':no_update,
                     'failed_wavelengths':no_update}
    printv('calling collect data')
    if status == 'Measurement ending':
        datalog.add('Measurement end success')
        status = 'Measurement ended'
        return_values['trigger-download'] = str(not(bool(download_trigger)))
        return_values['data-log'] = str(datalog)
        return_values['current_exposures'] = 0
        return_values['prev_exposures'] = 0
        return tuple(list(return_values.values()))
    TIME = integration * int(current_exposures)
    prev_TIME = integration * (int(current_exposures)-1)
    failed_wavelengths = json.loads(failed_wavelengths)
    if experiment_generator is None or status in ['Measurement paused','All Measurements finished','Measurement not in progress\n']:
        printv(status,'null collect data')
        raise PreventUpdate
    else:
        if float(current_wl)!= float(wavelength): #switched to new wavelength
            return_values['current_wl'] = wavelength
            if experiment_type in ['Wavelength Sweep','Rolling Average']:
                return_values['trigger-download'] = str(not(bool(download_trigger)))
        try:
            printv(datetime.datetime.now(),'collecting data')
            buff_spad,buff_power,datalog,time_exposed=next(experiment_generator) #appends to global vars measurement,power_measurement
        except Exception as e:
            if type(e) is StopIteration: #generator finished
                exp_index=0
                if float(rep_count) == float(exp_reps): #completed all experiment repetitions
                    status='All Measurements finished'
                    datalog.add(status)
                else:
                    status=f'Measurement #{rep_count} finished'
                    datalog.add(status)
                return_values['data-log'] = str(datalog)
                return_values['trigger-download'] = str(not(bool(download_trigger)))
                return_values['current_exposures'] = 0
                return_values['prev_exposures'] = 0
                printv('RETURNING',tuple(list(return_values.values())))
                return tuple(list(return_values.values()))
            else: #?
                printv(e)
                raise PreventUpdate
        else:
            datalog.add('Acquisition {} of {}'.format(int(current_exposures)+1,int(total_exposures)) + ' - spad exposed for {} s'.format(time_exposed))
            #Run wavelength check subroutine
            if TIME % params.check_wavelength_interval < prev_TIME % params.check_wavelength_interval:
                if params.test_mode:
                    datalog.add('Laser wavelength is {}'.format(current_wl))
                else:
                    measured_wavelength = laser.get_wavelength()
                    datalog.add('Laser wavelength is {}'.format(measured_wavelength))
                    if abs(float(current_wl)-float(measured_wavelength))>params.lambda_tolerance: #re-tune needed
                        datalog.add('Wavelength error tolerance exceeded. Retuning laser to {}'.format(current_wl))
                        if not params.test_mode:
                            tune_success=laser.set_wavelength(float(current_wl))
            #Run laser realign check subroutine
            if TIME % params.alignment_interval < prev_TIME % params.alignment_interval:
                if params.test_mode:
                    datalog.add('Checking beam alignment')
                else:
                    datalog.add('Checking beam alignment: {}'.format(laser.realign_beam()))
            #Run autobackup (if not sweep):
            if TIME % params.autobackup_interval < prev_TIME % params.autobackup_interval:
                if experiment_type in ['Peak Measurement']:
                    return_values['trigger-download'] = str(not(bool(download_trigger)))
            return_values['data-log'] = str(datalog)
            return_values['current_exposures'] = str(int(current_exposures)+1)
            return tuple(list(return_values.values()))

@app.callback(
    [Output('progress', 'value'),
    Output('progress', 'label'),
    Output('laser-status','children'),
    Output('power-status','children'),
    Output('time_trace','figure'),
    Output('power_meter','figure'),
    Output('status','children')],
    [Input('update-interval', 'n_intervals')],
    [State('integration','value'),
    State('nexp','value'),
    State('current_exposures','children'),
    State('total_exposures','children'),
    State('experiment-type','value'),
    State('rep_count','children')]
)
def update_progress(n,integration,nexp,current_exposures,total_exposures,experiment_type,rep_count):
    global status
    return_values = {'progress_value':no_update,
                    'progress_label':no_update,
                    'laser-status':no_update,
                    'power-status':no_update,
                    'time_trace':no_update,
                    'power_meter':no_update,
                    'status':status}
    if 'in progress' in status:
        try:
            #update progress display
            try:
                progress=int(float(current_exposures)/float(total_exposures) * 100)
            except:
                progress=0
            if not params.test_mode:
                if laser.is_on():
                    laser_output='ON'
                else:
                    laser_output='OFF'
                    raise Exception('Laser output off during measurement; ending experiment')
                newlaser = 'Output '+laser_output+' at '+str(wavelength)+' nm through channel '+str(current_channel)
                if params.power_monitoring:
                    newpower = 'CONNECTED - TUNED TO ' + str(wavelength)+ ' nm'
                else:
                    newpower= 'Warning: Power Monitoring is off'
            else:
                newlaser = 'TESTMODE - current wavelength is '+str(wavelength)+' nm through channel '+str(current_channel)
                newpower = 'TESTMODE'
            time_trace=go.Figure()
            power_meter=go.Figure()
            if experiment_type in ['Peak Measurement','Wavelength Sweep']:
                for address in spad:
                    try:
                        flat_measure=np.array(measurement[address][wavelength]).flatten()
                    except:
                        flat_measure=np.array([])
                    try:
                        flat_power=np.array(power_measurement[address][wavelength]).flatten()
                    except:
                        flat_power=np.array([])
                    time_trace.add_trace(go.Scatter(x=np.arange(len(flat_measure)),
                                                            y=flat_measure,
                                                            mode='lines',name='spad'+str(address.split('::')[3])))
                    if params.power_monitoring:
                        power_meter.add_trace(go.Scatter(x=np.arange(len(flat_power)),
                                                                y=flat_power,
                                                                mode='lines',name='spad'+str(address.split('::')[3])))
            else: #rolling average
                measurement_buff = list(measurement.values())[0]
                power_buff = list(power_measurement.values())[0]
                for wl in measurement_buff:
                    try:
                        flat_measure=np.array(measurement_buff[wl]).flatten()
                    except:
                        flat_measure=np.array([])
                    try:
                        flat_power=np.array(power_buff[wl]).flatten()
                    except:
                        flat_power=np.array([])
                    time_trace.add_trace(go.Scatter(x=np.arange(len(flat_measure)),
                                                            y=flat_measure,
                                                            mode='lines',name=wl))
                    if params.power_monitoring:
                        power_meter.add_trace(go.Scatter(x=np.arange(len(flat_power)),
                                                                y=flat_power,
                                                                mode='lines',name=wl))
            time_trace.update_layout(title='SPAD Time Trace',xaxis_tickformat =',d')
            power_meter.update_layout(title='Power Meter Time Trace',xaxis_tickformat =',d')
            # only add text after 5% progress to ensure text isn't squashed too much
            return_values['progress_value'] = progress
            return_values['progress_label'] = f'Repetition {rep_count} : {progress} %' if progress >= 5 else ''
            return_values['laser-status'] = newlaser
            return_values['power-status'] = newpower
            return_values['time_trace'] = time_trace
            return_values['power_meter'] = power_meter
            return tuple(list(return_values.values()))
        except Exception as e:
            printv(e)
    elif status == 'Measurement paused':
        try:
            progress=int((list(target_wavelengths).index(float(wavelength))/len(target_wavelengths) + 1/len(target_wavelengths)*exp_index/(len(measurement)*nexp)) * 100)
        except:
            progress=0
        return_values['progress_value'] = progress
        return_values['progress_label'] = f'Repetition {rep_count} : {progress} %' if progress >= 5 else ''
        return tuple(list(return_values.values()))
    elif 'finished' in status:
        progress = 0
        return_values['progress_value'] = progress
        return_values['progress_label'] = f'Repetition {rep_count} : {progress} %' if progress >= 5 else ''
        return tuple(list(return_values.values()))
    else:
        progress = 0
        return_values['progress_value'] = progress
        return_values['progress_label'] = f'Repetition {rep_count} : {progress} %' if progress >= 5 else ''
        return_values['time_trace'] = go.Figure()
        return_values['power_meter'] = go.Figure()
        return tuple(list(return_values.values()))

@app.callback(Output('data_progress','figure'),
                [Input('collected-spectra','children')])
def update_displayed_spectra(json_spectra):
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra) #list of spectra of length n corresponding to n active spads
    else:
        return go.Figure()
    if spectra[0].meta['experiment_type'] in ['Peak Measurement','Rolling Average']:
        fig = spectra[0].plot_samples(label='experiment_name')
    elif spectra[0].meta['experiment_type'] == 'Wavelength Sweep':
        fig = spectra[0].plot(label='experiment_name',show_err=True)
    return fig

@app.callback(
    [Output('raman-start','children'),
    Output('raman-end','children'),
    Output('raman-peak','children')],
    [Input('wl-start','value'),
    Input('wl-end','value'),
    Input('wl-peak','value')]
)
def calc_raman(excitation_start,excitation_end,excitation_peak):
    filter_wl=params.filter_wl
    if excitation_start is not None and excitation_end is not None:
        return '$=%.2f$ $cm^{-1}$'%((1/float(excitation_start)-1/float(filter_wl))*1e7), \
               '$=%.2f$ $cm^{-1}$'%((1/float(excitation_end)-1/float(filter_wl))*1e7),''
    elif excitation_start is not None:
        return '$=%.2f$ $cm^{-1}$'%((1/float(excitation_start)-1/float(filter_wl))*1e7),'',''
    elif excitation_end is not None:
        return '','$=%.2f$ $cm^{-1}$'%((1/float(excitation_end)-1/float(filter_wl))*1e7),''
    elif excitation_peak is not None:
        return '','','$=%.2f$ $cm^{-1}$'%((1/float(excitation_peak)-1/float(filter_wl))*1e7)
    else:
        return '','',''

@app.callback(
    [Output('measurement-params','children'),
    Output('nexp-title','children')],
    Input('experiment-type','value')
)
def change_experiment(experiment_type):
    if experiment_type == 'Peak Measurement':
        return peak,'Number of Exposures:'
    elif experiment_type == 'Wavelength Sweep':
        return wl_sweep,'Number of Exposures/Wavelength:'
    elif experiment_type == 'Rolling Average':
        return rolling_avg,'Repetitions:'

@app.callback(
    Input('preset','contents'),
    [Output('experiment-type','value'),
    Output('experiment-name','value'),
    Output('concentration','value'),
    Output('integration','value'),
    Output('nexp','value'),
    Output('wl-start','value'),
    Output('wl-end','value')])
def load_preset(contents):
    global target_wavelengths
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string).decode('ascii')
    experiment_name,concentration,integration,nexp,wl_start,wl_end='','','','','',''
    for i in range(len(decoded.split('\n'))):
        line=decoded.split('\n')[i]
        if 'name:' in line:
            experiment_name=line.split(':')[1].strip()
        elif 'concentration:' in line:
            concentration=(line.split(':')[1].strip())
        elif 'integration' in line:
            integration=float(line.split(':')[1].strip())
        elif 'repetitions' in line:
            nexp=float(line.split(':')[1].strip())
        elif 'wavelengths' in line:
            target_wavelengths=decoded.split('\n')[i+1:]
    try:
        target_wavelengths=[float(x.strip()) for x in target_wavelengths if len(x.strip())>0]
    except:
        raise Exception('improperly formatted .exp file')
    target_wavelengths=sorted(target_wavelengths, key = lambda x:float(x)) #sort wl_list in ascending order
    wl_start=target_wavelengths[0]
    wl_end=target_wavelengths[-1]
    return 'Wavelength Sweep',experiment_name,concentration,integration,nexp,wl_start,wl_end

@app.callback(Input('add-range','n_clicks'),
              [Output('wl-start','value'),
              Output('wl-end','value'),
              Output('wl-step','value'),
              Output('wl-peak','value'),
              Output('wl-ranges','data')],
              [State('wl-start','value'),
              State('wl-end','value'),
              State('wl-step','value'),
              State('wl-peak','value'),
              State('wl-ranges','data'),
              State('experiment-type','value')])
def add_wavelength_range(n,wlstart,wlstop,wlstep,wlpeak,data,experiment_type):
    if experiment_type=='Wavelength Sweep':
        if not n or any([x is None for x in [wlstart,wlstop,wlstep]]):
            raise PreventUpdate
        data.append({'start':wlstart,'stop':wlstop,'step':wlstep})
    else:
        if not n or wlpeak is None:
            raise PreventUpdate
        data.append({'label':'Point '+str(len(data)+1),'wavelength':wlpeak,'wavenumber':(1/float(wlpeak)-1/float(params.filter_wl))*1e7})
    return_values = {'wl-start':None,
                    'wl-end':None,
                    'wl-step':None,
                    'wl-peak':None,
                    'wl-ranges':data}
    return tuple(list(return_values.values()))

@app.callback([Input('wl-ranges','data'),
                Input('experiment-type','value'),
                Input('experiment-name','value'),
                Input('integration','value'),
                Input('nexp','value'),
                Input('wl-peak','value')],
              Output('measure','disabled'))
def update_wavelength_range(rows,experiment_type,experiment_name,integration,nexp,wl_peak):
    global target_wavelengths
    if experiment_type == 'Wavelength Sweep':
        if len(rows)==0:
            target_wavelengths = []
        else:
            target_wavelengths = list(np.round(np.concatenate([np.linspace(start=rows[i]['start'],stop=rows[i]['stop'],num= 1+round((rows[i]['stop']-rows[i]['start'])/rows[i]['step']),endpoint=True) for i in range(len(rows))]),2))
            target_wavelengths=sorted(target_wavelengths, key = lambda x:float(x)) #sort wl_list in ascending order
    elif experiment_type == 'Peak Measurement':
        if wl_peak is not None:
            target_wavelengths = [wl_peak]
        else:
            target_wavelengths = []
    elif experiment_type == 'Rolling Average':
        if len(rows)==0:
            target_wavelengths=[]
        else:
            target_wavelengths=[float(rows[i]['wavelength']) for i in range(len(rows))]*nexp
    if len(target_wavelengths)>0 and experiment_name is not None and integration is not None and nexp is not None:
        #params are valid, enable begin measurement
        return False
    return True

@app.callback(
    Input('connection','n_clicks'),
    [Output('connection','children'),
    Output('connection','color'),
    Output('connection','outline'),
    Output('laser-status','children'),
    Output('spad-status','children'),
    Output('power-status','children'),
    Output('laser-status','style'),
    Output('spad-status','style'),
    Output('power-status','style'),
    Output('data-log','children')],
    [State('data-log','children'),
    State('selected-laser','value'),
    State('selected-spads','data')]
)
def connect_instruments(n_clicks,datalog,laser_name,spad_data):
    datalog=Datalog(datalog)
    spad_dict = {spad_data[i]['spad address']:spad_data[i]['channel number'] for i in range(len(spad_data)) if spad_data[i]['channel number'] is not None}
    instrument_status,datalog=instrument_connect(datalog,laser_name,spad_dict)
    instrument_status,datalog=check_status(datalog)
    styles=[]
    for instrument in [laser,spad,pm]:
        if params.test_mode:
            styles.append(no_update)
        elif instrument is not None:
            styles.append({'color': 'green','font-weight': 'bold'})
        else:
            styles.append({'color': 'red','font-weight': 'bold'})
    return_values= {'connection_children':no_update,
                    'connection_color':no_update,
                    'connection_outline':True,
                    'laser-status_children':instrument_status['laser'],
                    'spad-status_children':instrument_status['spad'],
                    'power-status_children':instrument_status['pm'],
                    'spad-status_style':styles[0],
                    'power-status_style':styles[1],
                    'laser-status_style':styles[2],
                    'data-log':str(datalog)}
    if params.test_mode or (laser is not None and spad is not None and pm is not None):
        return_values['connection_children'] = 'Check Status'
        return_values['connection_color'] = 'success'
    else:
        return_values['connection_children'] = 'Reconnect'
        return_values['connection_color'] = 'danger'
    return tuple(list(return_values.values()))

@app.callback(
    Input('shutdown','n_clicks'),
    [Output('laser-status','children'),
    Output('spad-status','children'),
    Output('power-status','children'),
    Output('laser-status','style'),
    Output('spad-status','style'),
    Output('power-status','style'),
    Output('data-log','children')],
    State('data-log','children')
)
def shutdown_instruments(n_clicks,datalog):
    instrument_status,datalog=instrument_shutdown(datalog)
    styles=[]
    for instrument in [laser,spad,pm]:
        if instrument is None:
            styles.append({'color': 'blue','font-weight': 'bold'})
        elif params.test_mode:
            styles.append(no_update)
        else:
            styles.append({'color': 'red','font-weight': 'bold'})
    return_values= {'laser-status_children':instrument_status['laser'],
                    'spad-status_children':instrument_status['spad'],
                    'power-status_children':instrument_status['pm'],
                    'spad-status_style':styles[0],
                    'power-status_style':styles[1],
                    'laser-status_style':styles[2],
                    'data-log':str(datalog)}
    return tuple(list(return_values.values()))

@app.callback(
    [Input('measure','n_clicks'),
     Input('rep_count','children')],
    [Output('data-log','children'),
    Output('prev_exposures','children'),
    Output('total_exposures','children'),
    Output('measure','children'),
    Output('measure','color'),
    Output('collected-spectra','children'),
    Output('update-interval','interval'),
    Output('metajson','children')],
    [State('selected-laser','value'),
    State('experiment-type','value'),
    State('experiment-name','value'),
    State('concentration','value'),
    State('measure','children'),
    State('integration','value'),
    State('nexp','value'),
    State('wl-start','value'),
    State('wl-end','value'),
    State('wl-step','value'),
    State('wl-peak','value'),
    State('exposing','children'),
    State('data-log','children')]
)
def do_measurement(n_clicks,rep_count,laser_name,experiment_type,experiment_name,concentration,measure_text,integration,nexp,wlstart,wlstop,wlstep,wlpeak,exposing,datalog):
    global experiment_generator
    global laser
    global spad
    global switch
    global pm
    global wavelength
    global target_wavelengths
    global status
    datalog=Datalog(datalog)
    meta = Metadata()
    reset_globals()
    return_values = {'data-log':no_update,
                    'prev_exposures':no_update,
                    'total_exposures':no_update,
                    'measure_children':no_update,
                    'measure_color':no_update,
                    'collected_spectra':no_update,
                    'update-interval':no_update,
                    'metajson':no_update}
    ctx = dash.callback_context
    if not ctx.triggered:
        trigger=None
    else:
        trigger = ctx.triggered[0]['prop_id'].split('.')[0]
    printv('trigger:',trigger)
    if (trigger=='measure' and measure_text == 'Begin Measurement') or (trigger=='rep_count'):
        printv('starting new run')
        #reset logfile
        datalog = Datalog()
        if not params.test_mode:
            instrument_status,datalog=check_status(datalog)
            #turn on laser
            laser.output_on()
            if params.force_spad_cool:
                while 'READY' not in instrument_status['spad']: 
                    #wait for spad to cool to start measurement
                    sleep(3)
                    instrument_status,datalog=check_status(datalog)
                    printv(instrument_status)
        #update metadata
        meta['laser'] = laser_name
        if int(rep_count) == 1:
            meta['experiment_name'] = experiment_name
        else:
            meta['experiment_name'] = experiment_name + '_' + rep_count
        printv('name',meta['experiment_name'])
        meta['experiment_type']=experiment_type
        meta['integration'] = integration
        meta['concentration']=concentration
        meta['repetitions'] = nexp
        if experiment_type == 'Rolling Average':
            nexp=1
        printv(integration,nexp,str(datalog))
        printv(target_wavelengths)
        experiment_generator = wavelength_sweep(integration,nexp,datalog)
        printv(experiment_generator)
        datalog.add('Parameters good. Beginning measurement')
        meta['starttime'] = datetime.datetime.now().isoformat()
        status=f'Measurement #{rep_count} in progress'
        printv(status)
        return_values['data-log'] = str(datalog)
        return_values['prev_exposures']=-1
        return_values['total_exposures'] =str(nexp*len(target_wavelengths)*len(spad))
        return_values['measure_children'] = 'End Measurement'
        return_values['measure_color'] = 'dark'
        return_values['collected_spectra'] = None
        return_values['update-interval'] = (integration * 1000)/2; 
        return_values['metajson'] = meta.to_json()
        return tuple(list(return_values.values()))
    else: #stop measurement
        status = 'Measurement ending'
        printv('stopping measurement')
        datalog.add('stopping measurement')
        sleep(3)
        return_values['data-log'] = str(datalog)
        return_values['prev_exposures']=0
        return_values['measure_children'] = 'Begin Measurement'
        return_values['measure_color'] = 'primary'
        return_values['collected_spectra'] = None
        return_values['metajson'] = Metadata().to_json()
        return tuple(list(return_values.values()))

@app.callback(
    [Input('trigger-download','children')],
    [Output('collected-spectra','children'),
    Output('modal_body','children'),
    Output('modal','is_open'),
    Output('experiment-name','value'),
    Output('concentration','value'),
    Output('integration','value'),
    Output('nexp','value'),
    Output('wl-start','value'),
    Output('wl-end','value'),
    Output('wl-step','value'),
    Output('wl-ranges','data'),
    Output('data-log','children'),
    Output('metajson','children'),
    Output('failed_wavelengths','children'),
    Output('rep_count','children')],
    [State('experiment-type','value'),
    State('metajson','children'),
    State('data-log','children'),
    State('failed_wavelengths','children'),
    State('rep_count','children'),
    State('exp-reps','value')],
    prevent_initial_call=True,
    #background=True,
    #manager=background_callback_manager
)
def download_data(download_trigger,experiment_type,metajson,datalog,failed_wavelengths,rep_count,exp_reps):
    global target_wavelengths
    global status
    printv('download called')
    failed_wavelengths = json.loads(failed_wavelengths)
    datalog=Datalog(datalog)
    return_values = {'collected-spectra':no_update,
                   'modal_body':no_update,
                   'modal':no_update,
                   'experiment-name':no_update,
                   'concentration':no_update,
                   'integration':no_update,
                   'nexp':no_update,
                   'wl-start':no_update,
                   'wl-end':no_update,
                   'wl-step':no_update,
                   'wl-ranges':no_update,
                   'data-log':no_update,
                   'metajson':no_update,
                   'failed_wavelengths':no_update,
                   'rep_count':no_update}
    printv('STATUS',status)
    download = ('finished' in status) or ('ended' in status)
    autobackup = params.auto_backup and 'in progress' in status
    printv(download,autobackup)
    if target_wavelengths==[] or not any([download,autobackup]):
        raise PreventUpdate
    printv('download in progress')
    metadata = Metadata(metajson)
    metadata['excitation_wavelengths'] = list(filter(lambda i: i not in failed_wavelengths, target_wavelengths))
    metadata['endtime'] = datetime.datetime.now().isoformat()
    if experiment_type == 'Wavelength Sweep':
        measurement_df,power_df,meta_df= process_data(metadata) #returns dict of dicts indexed by SPAD address
    else:
        measurement_df,power_df,meta_df = process_data(metadata,filter_complete=False)
    zip_data(measurement_df,power_df,meta_df,datalog,params.working_directory)
    #remove created instances of data in working directory
    if platform == 'darwin':
        os.system('rm -rf *.power')
        os.system('rm -rf *.spad')
        os.system('rm -rf *.log')
    else:
        os.system('del *.power')
        os.system('del *.spad')
        os.system('del *.log')
    printv('DATA ZIPPED')
    modalbody = meta_df[next(iter(meta_df))]['experiment_name']+ ' data zipped to ' + params.working_directory
    try:
        spectra =[Spectrum(measurement_df[address],power_df[address],meta_df[address]) for address in measurement_df]  #list of each spad readout from experiment
    except Exception as e:
        printv(e)
        raise PreventUpdate
    if download: #measurement is finished;serve notification
        try:
            return_values['collected-spectra'] = jsonify(spectra)
        except Exception as e:
            printv(e)
            datalog.add('Error downloading data :(')
        if float(rep_count)==float(exp_reps): # reached desired number of experiment repetitions; display end message
            status = 'Ending measurement'
            datalog.add('Full experiment data downloaded')
            return_values['modal_body'] = modalbody
            return_values['modal'] = True
            return_values['rep_count'] = '1'
            return_values['wl-ranges'] = []
            return_values['experiment-name'] = ''
            return_values['concentration'] = ''
            for key in ['integration','nexp','wl-start','wl-end','wl-step','metajson']:
                return_values[key] = None
        else: #if not, trigger new measurement
            status = f'Measurement {rep_count} finished'
            return_values['rep_count'] =str(int(rep_count) + 1)
            printv('rep_count',return_values['rep_count'])
        return_values['data-log'] = str(datalog)
        return_values['failed_wavelengths'] = '[]'
        return tuple(list(return_values.values()))
    elif autobackup: #auto backup
        try:
            return_values['collected-spectra'] = jsonify(spectra)
        except Exception as e:
            printv(e)
            datalog.add('Error backing up data :(')
        else:
            datalog.add('Autobackup complete')
        return_values['data-log'] = str(datalog)
        return tuple(list(return_values.values()))
    else:
        raise PreventUpdate()
    
@app.callback([Output('continuous','children'),
               Output('exp-reps','value'),
               Output('exp-reps-title','style'),
               Output('exp-reps','style')],
               Input('toggle_continuous','value'))
def toggle_continuous(toggle_value):
    if len(toggle_value) == 0:
        #continuous box un-checked
        return str(False), no_update, {'padding':10},{'padding':10}
    else:
        #continuous box checked
        return str(True), str(float('inf')),{'padding':10,'display':'none'}, {'padding':10,'display':'none'}

@app.callback(
    Output('modal', 'is_open'),
    [Input('close_modal','n_clicks')],
    [State('modal', 'is_open')],
)
def toggle_experiment_done(toggle_close, is_open):
    if toggle_close:
        return not is_open
    return is_open

#RUN APP_______________________________________________________________________
if __name__ == '__main__':
    if params.test_mode and not params.auto_backup:
        app.run_server(debug=True,dev_tools_hot_reload=False)
    else:
        app.run_server(debug=True)