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
from dash import callback_context,no_update,DiskcacheManager
import pandas as pd
import numpy as np
import os
from dash.dependencies import Input,Output,State
from dash_extensions.enrich import MultiplexerTransform,DashProxy
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from scipy import stats
if not params.test_mode:
    from instrumental import Q_
from ctypes import cdll,c_long, c_ulong, c_uint32,byref,create_string_buffer,c_bool,c_char_p,c_int,c_int16,c_double, sizeof, c_voidp
from time import sleep
import zipfile
import requests

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
server = app.server
datalog = Datalog()
buffer='      \n'
#LAYOUT_________________________________________________________________________
#create a dynamic layout that wipes global variables when page is reloaded
def app_layout():
    printv('redefining app layout')
    structure=html.Div([
                header,
                html.Div(id='content',children=content)
            ])
    return structure
app.layout = app_layout
#HELPER FUNCTIONS_______________________________________________________________
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
              Output('analytes-dropdown','options'),
              Output('log','children')],
              [Input('url', 'search')],
              [State('datatable-columns','value')])
def fetch_data(url_search,metadata_cols):
    return_values = {'file-list_data':no_update,
                     'file-list_selected':no_update,
                     'file-list_style':no_update,
                     'file-list_columns':no_update,
                     'spectra':no_update,
                     'original-spectra':no_update,
                     'analytes':no_update,
                     'log':no_update}
    try:
        code = url_search.split("&")[0].split("=")[1].strip()
        foldername = url_search.split("&")[1].split("=")[1].strip()
        print(code)
        print(foldername)
    except:
        raise PreventUpdate
    dropbox_url = f"https://www.dropbox.com/s/{code}/{foldername}?dl=1"
    spectra=[]
    original_spectra = []
    try:
        response = requests.get(dropbox_url)
        open('data.zip','wb').write(response.content)
        with zipfile.ZipFile('data.zip', 'r') as zip_ref:
            zip_ref.extractall('data')
        with zipfile.ZipFile('data.zip', 'r') as zip_ref:
            zip_ref.extractall('data')
    except Exception as e:
        print(e)
        raise PreventUpdate
    for newspec in batch_process_folder('data'):
        spectra.append(newspec)
        original_spectra.append(newspec)
    if platform == 'darwin':
        os.system('rm -rf data')
        os.system('rm data.zip')
    else:
        os.system('rmdir data')
        os.system('rm data.zip')
    if 'filename' not in metadata_cols:
        metadata_cols.append('filename')
    if len(spectra)>0:
        data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
        analyte_records = [record for rlist in [s.meta['analytes'] for s in spectra] for record in rlist]
        analytes = pd.DataFrame.from_records(analyte_records)
        data_cols = ([{'id':p,
                       'name':p,
                       'editable':Metadata().fetch(key=p,trait='editable'),
                       'on_change':{'action':'coerce','failure':'reject'},
                       'type':'text'} for p in metadata_cols if p != 'filename'])
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
        return_values['analytes'] = list(set(analytes['name']))
        return_values['log'] = logstr
        return tuple(list(return_values.values()))
    else:
        data=[{col:None for col in metadata_cols}]
        data_cols = ([{'id':p,'name':p,'editable':Metadata().fetch(key=p,trait='editable')} for p in metadata_cols if p != 'filename'])
        return_values['file-list_data'] = data
        return_values['file-list_selected'] = [x for x in range(len(data))]
        return_values['file-list_columns'] = data_cols
        return tuple(list(return_values.values()))
    
@app.callback([Output('file-list', 'data'),
                Output('file-list','selected_rows'),
                Output('file-list','style_data_conditional'),
                Output('file-list','columns'),
              Output('spectra','children'),
              Output('original-spectra','children'),
              Output('analytes-dropdown','options'),
              Output('log','children')],
              [Input('upload-data', 'contents')],
              [State('datatable-columns','value'),
              State('spectra','children'),
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
                     'analytes':no_update,
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
    if list_of_contents != 'null':
        #gen newly uploaded spectra
        for newspec in batch_process_uploads(list_of_contents,list_of_names,list_of_dates):
            spectra.append(newspec)
            original_spectra.append(newspec)
    if 'filename' not in metadata_cols:
        metadata_cols.append('filename')
    if len(spectra)>0:
        data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
        analyte_records = [record for rlist in [s.meta['analytes'] for s in spectra] for record in rlist]
        analytes = pd.DataFrame.from_records(analyte_records)
        data_cols = ([{'id':p,
                       'name':p,
                       'editable':Metadata().fetch(key=p,trait='editable'),
                       'on_change':{'action':'coerce','failure':'reject'},
                       'type':'text'} for p in metadata_cols if p != 'filename'])
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
        return_values['analytes'] = list(set(analytes['name']))
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
        Input('analytes-dropdown','value'),
        [Output('file-list', 'data'),
        Output('file-list','columns'),
        Output('spectra','children'),
        Output('original-spectra','children'),
        Output('datatable-columns','value')],
        [State('spectra','children'),
         State('original-spectra','children'),
         State('datatable-columns','value')]
)
def set_target_analyte(selected_analyte,json_spectra,json_original_spectra,metadata_cols):
    return_values = {'file-list_data':no_update,
                     'file-list_columns':no_update,
                     'spectra':no_update,
                     'original-spectra':no_update,
                     'meta-cols':no_update}
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        raise PreventUpdate
    if json_original_spectra is not None:
        original_spectra = spec_from_json(json_original_spectra)
    else:
        raise PreventUpdate
    if 'filename' not in metadata_cols:
        metadata_cols.append('filename')
    data_cols = ([{'id':p,
                       'name':p,
                       'editable':Metadata().fetch(key=p,trait='editable'),
                       'on_change':{'action':'coerce','failure':'reject'},
                       'type':'text'} for p in metadata_cols if p != 'filename']+ 
                       [{'id':'target_analyte',
                         'name':'target_analyte',
                         'editable':True,
                         'type':'text'}])
    data = []
    for i in range(len(spectra)):
        spec_data = {col:str(spectra[i].meta[col]) for col in metadata_cols}
        analytes = pd.DataFrame.from_records(spectra[i].meta['analytes'])
        if len(analytes)==0:
            spec_data['target_analyte'] = ""
        else:
            analytes.index = list(analytes['name'])
            if selected_analyte in list(analytes['name']):
                spec_data['target_analyte'] = f"{analytes.loc[selected_analyte]['concentration']} [{analytes.loc[selected_analyte]['units']}]"
                spectra[i].meta['target_analyte'] = f"{analytes.loc[selected_analyte]['concentration']} [{analytes.loc[selected_analyte]['units']}]"
                original_spectra[i].meta['target_analyte'] = f"{analytes.loc[selected_analyte]['concentration']} [{analytes.loc[selected_analyte]['units']}]"
            else:
                spec_data['target_analyte'] = ""
                spectra[i].meta['target_analyte'] = ""
                original_spectra[i].meta['target_analyte'] = ""
        data.append(spec_data)
    if 'target_analyte' not in metadata_cols:
        metadata_cols.append('target_analyte')
    return_values['file-list_columns'] = data_cols
    return_values['file-list_data']= data
    return_values['spectra'] = jsonify(spectra)
    return_values['original-spectra'] = jsonify(original_spectra)
    return_values['meta-cols'] =metadata_cols
    return tuple(list(return_values.values()))

@app.callback(Input('file-list','active_cell'),
              [Output('viewmeta','is_open'),
               Output('meta-analytes','data')],
              [State('spectra','children')]
)
def show_analyte_meta(active_cell,json_spectra):
    if active_cell['column_id'] != 'analytes':
        raise PreventUpdate
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        raise PreventUpdate
    spectrum = spectra[active_cell['row']]
    data = spectrum.meta['analytes']
    return True, data

@app.callback(Input('add-analyte','n_clicks'),
              [Output('meta-analytes','data')],
              [State('analyte-name','value'),
              State('analyte-concentration','value'),
              State('analyte-units','value'),
              State('meta-analytes','data')]
)
def add_analyte_meta(n,name,concentration,units,data):
    if not n or all([x is None for x in [name,concentration,units]]): 
        raise PreventUpdate
    data.append({'name':name,'concentration':concentration,'units':units})
    return data

@app.callback(Input('closemeta','n_clicks'),
              [Output('spectra','children'),
               Output('file-list','data'),
               Output('viewmeta','is_open')],
              [State('file-list','active_cell'),
               State('spectra','children'),
               State('meta-analytes','data'),
               State('datatable-columns','value')])
def save_analyte_meta(n,active_cell,json_spectra,analyte_data,metadata_cols):
    print(active_cell['column_id'])
    if active_cell['column_id'] != 'analytes':
        raise PreventUpdate
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        raise PreventUpdate
    spectra[active_cell['row']].meta['analytes'] = analyte_data
    if 'filename' not in metadata_cols:
        metadata_cols.append('filename')
    data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
    return jsonify(spectra),data,False


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
    if 'filename' not in metadata_cols:
        metadata_cols.append('filename')
    if len(original_spectra)==0:
        raise PreventUpdate
    data=[{col:str(s.meta[col]) for col in metadata_cols} for s in original_spectra]
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
    for col in df:
        df[col] =df[col].astype('str')
    #printv('DF',df)
    dfprev = pd.DataFrame(previous_rows)
    for col in dfprev:
        dfprev[col] =dfprev[col].astype('str')
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
                try:
                    if df[col].iloc[i] != dfprev[col].iloc[i] and not pd.isna(df[col].iloc[i]) and df[col].iloc[i]!='':
                        spectra_dict[filename].meta[col] = df[col].iloc[i]
                except KeyError:
                    raise PreventUpdate
    return_values = {'spectra':jsonify(list(spectra_dict.values())), #remove entires deleted by user from table
                     'original-spectra':jsonify(list(original_spectra_dict.values())),
                     'log':str(Processlog([s.log for s in list(spectra_dict.values())])),
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
        # if spectra[g].meta['experiment_type'] in ['Peak Measurement', 'peak']:
        #     if ydata_switchval:
        #         fig = spectra[g].plot_samples(color=color,label='experiment_name')
        #     else:
        #         fig = spectra[g].plot_samples(color=color,ydata='power',label='experiment_name')
        if spectral_units:
            xunits='ramanshift'
        else:
            xunits='wavelength'
        if ydata_switchval:
            fig = spectra[g].plot(color=color,label='experiment_name',xunits=xunits,show_err=True)
        else:
            fig = spectra[g].plot(color=color,label='experiment_name',ydata='power',xunits=xunits,show_err=True)
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
        if 'filename' not in metadata_cols:
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
        if 'filename' not in metadata_cols:
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
        if 'filename' not in metadata_cols:
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
    concentrations = []
    for s in spectra:
        try:
            concentrations.append(float(s.meta['target_analyte'].split(' ')[0]))
        except Exception as e:
            print(e)
            concentrations.append(0)
    concentrations = np.array(concentrations)
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


#RUN APP_______________________________________________________________________
if __name__ == '__main__':
    if params.test_mode:
        app.run_server(debug=True,dev_tools_hot_reload=False)
    else:
        app.run_server(debug=False)