'''
Swept Source Raman Dash App
Dahlia Dry, 2022 | dahlia23@mit.edu
Physical Optics and Electronics Group
Running this file launches the Dash GUI for Swept Source Raman data analysis
'''
#is this sentence here?
#file imports
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

# --------------------------- file upload callbacks -------------------------- #
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
    dropbox_url = f"https://www.dropbox.com/sh/{code}/{foldername}?dl=1"
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
    if len(spectra)>0:
        data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
        analyte_records = [record for rlist in [s.meta['analytes'] for s in spectra] for record in rlist]
        analytes = pd.DataFrame.from_records(analyte_records)
        data_cols = ([{'id':p,
                       'name':p,
                       'editable':Metadata().fetch(key=p,trait='editable'),
                       'on_change':{'action':'coerce','failure':'reject'},
                       'type':'text'} for p in metadata_cols])
        logstr = str(Processlog([s.log for s in spectra]))
        #printv(pd.Series(spectra).to_json(orient='records'))
        style_data_conditional = [
        {
            'if': {
                'row_index': i,
            },
            'color': colorlist[i % len(colorlist)]
        } for i in range(len(data))
        ]
        return_values['file-list_data'] = data
        return_values['file-list_selected'] = [x for x in range(len(data))]
        return_values['file-list_style'] = style_data_conditional
        return_values['file-list_columns'] = data_cols
        return_values['spectra'] = jsonify(spectra)
        return_values['original-spectra'] = jsonify(original_spectra)
        try:
            return_values['analytes'] = list(set(analytes['name']))
        except:
            pass
        return_values['log'] = logstr
        return tuple(list(return_values.values()))
    else:
        data=[{col:None for col in metadata_cols}]
        data_cols = ([{'id':p,'name':p,'editable':Metadata().fetch(key=p,trait='editable')} for p in metadata_cols])
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
    if len(spectra)>0:
        data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
        analyte_records = [record for rlist in [s.meta['analytes'] for s in spectra] for record in rlist]
        analytes = pd.DataFrame.from_records(analyte_records)
        data_cols = ([{'id':p,
                       'name':p,
                       'editable':Metadata().fetch(key=p,trait='editable'),
                       'on_change':{'action':'coerce','failure':'reject'},
                       'type':'text'} for p in metadata_cols])
        logstr = str(Processlog([s.log for s in spectra]))
        #printv(pd.Series(spectra).to_json(orient='records'))
        style_data_conditional = [
        {
            'if': {
                'row_index': i,
            },
            'color': colorlist[i% len(colorlist)]
        } for i in range(len(data))
        ]
        return_values['file-list_data'] = data
        return_values['file-list_selected'] = [x for x in range(len(data))]
        return_values['file-list_style'] = style_data_conditional
        return_values['file-list_columns'] = data_cols
        return_values['spectra'] = jsonify(spectra)
        return_values['original-spectra'] = jsonify(original_spectra)
        try:
            return_values['analytes'] = list(set(analytes['name']))
        except:
            pass
        return_values['log'] = logstr
        return tuple(list(return_values.values()))
    else:
        data=[{col:None for col in metadata_cols}]
        data_cols = ([{'id':p,'name':p,'editable':Metadata().fetch(key=p,trait='editable')} for p in metadata_cols])
        return_values['file-list_data'] = data
        return_values['file-list_selected'] = [x for x in range(len(data))]
        return_values['file-list_columns'] = data_cols
        return tuple(list(return_values.values()))
# ------------------------------ table callbacks ----------------------------- #
@app.callback([Output('spectra','children'),
                Output('original-spectra','children'),
                Output('log','children'),
                Output('graphnum','children')],
              [Input('file-list','data')],
              [State('spectra','children'),
              State('original-spectra','children'),
              State('file-list','data_previous')])
def update_spectra_source(rows,json_spectra,json_original_spectra,prev_rows): #re-init the spectra if changes to datatable occur
    if json_spectra is not None and json_original_spectra is not None and prev_rows is not None and rows is not None:
        spectra = spec_from_json(json_spectra)
        original_spectra = spec_from_json(json_original_spectra)
    else:
        raise PreventUpdate
    print('LEN',len(rows),len(prev_rows),len(spectra))
    if len(rows) < len(prev_rows) and len(spectra) != len(rows): #someting deleted
        for i in range(len(rows)):
            if prev_rows[i] != rows[i]:
                original_spectra.pop(i)
                spectra.pop(i)
                return_values = {'spectra':jsonify(spectra), #remove entires deleted by user from table
                                'original-spectra':jsonify(original_spectra),
                                'log':str(Processlog([s.log for s in spectra])),
                                'graphnum':'0'}
                return tuple(list(return_values.values()))
        original_spectra.pop(-1)
        spectra.pop(-1)
        return_values = {'spectra':jsonify(spectra), #remove entires deleted by user from table
                         'original-spectra':jsonify(original_spectra),
                         'log':str(Processlog([s.log for s in spectra])),
                         'graphnum':'0'}
        return tuple(list(return_values.values()))
    else:
        raise PreventUpdate

@app.callback(Input('custom-field','value'),
              Output('add-col','disabled'))
def enable_add_col(fieldname):
    if len(fieldname)>=1 and fieldname is not None:
        return False
    else:
        return True
    
@app.callback(Input('add-col','n_clicks'),
              [Output('file-list','columns'),
               Output('datatable-columns','value'),
               Output('spectra','children'),
               Output('original-spectra','children'),
               Output('custom-field','value')],
                [State('file-list','columns'),
                 State('datatable-columns','value'),
                State('custom-field','value'),
                State('spectra','children'),
                State('original-spectra','children'),
                State('datatype-dropdown','value')]
)
def add_column(n,cols,metadata_cols,new_col,json_spectra,json_original_spectra,datatype):
    cols.append({
            'id': new_col, 'name': new_col,
            'renamable': True, 'deletable': True
    })
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        raise PreventUpdate
    if json_original_spectra is not None:
        original_spectra = spec_from_json(json_original_spectra)
    else:
        raise PreventUpdate
    for i in range(len(spectra)):
        if datatype == 'numeric':
            spectra[i].meta.add_field(new_col,0)
            original_spectra[i].meta.add_field(new_col,0)
        else:
            spectra[i].meta.add_field(new_col,'')
            original_spectra[i].meta.add_field(new_col,'')
    metadata_cols.append(new_col)
    return cols, metadata_cols,jsonify(spectra),jsonify(original_spectra),''

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
    data_cols = ([{'id':p,
                       'name':p,
                       'editable':Metadata().fetch(key=p,trait='editable'),
                       'on_change':{'action':'coerce','failure':'reject'},
                       'type':'text'} for p in metadata_cols]+ 
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
               Output('meta-analytes','data'),
               Output('experiment-name','value'),
               Output('notes','value'),
               Output('medium','value'),
               Output('metadata','children'),
               Output('custom-fields','data')],
              [State('spectra','children')]
)
def show_meta(active_cell,json_spectra):
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        raise PreventUpdate
    return_values = {'isopen':True,
                     'analytes':no_update,
                     'name':no_update,
                     'notes':no_update,
                     'medium':no_update,
                     'metadata':no_update,
                     'custom-fields':no_update}
    spectrum = spectra[active_cell['row']]
    return_values['analytes'] = spectrum.meta['analytes']
    return_values['name'] = spectrum.meta['experiment_name']
    return_values['notes'] = spectrum.meta['notes']
    return_values['medium'] = spectrum.meta['medium']
    return_values['metadata'] = spectrum.meta.to_markdown(exclude_editable=True)
    custom_fields = spectrum.meta.fetch(cat='custom')
    custom_fields_data = []
    for field in custom_fields:
        custom_fields_data.append({'field':field,'value':spectrum.meta[field]})
    return_values['custom-fields'] = custom_fields_data
    return tuple(list(return_values.values()))

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
               Output('x-dropdown','options'),
               Output('analytes-dropdown','options'),
               Output('viewmeta','is_open')],
              [State('file-list','active_cell'),
               State('spectra','children'),
               State('meta-analytes','data'),
               State('datatable-columns','value'),
               State('experiment-name','value'),
               State('notes','value'),
               State('medium','value'),
               State('custom-fields','data')])
def save_analyte_meta(n,active_cell,json_spectra,analyte_data,metadata_cols,name,notes,medium,custom_fields):
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        raise PreventUpdate
    spectra[active_cell['row']].meta['analytes'] = analyte_data
    spectra[active_cell['row']].meta['experiment_name'] = name
    spectra[active_cell['row']].meta['notes'] = notes
    spectra[active_cell['row']].meta['medium'] = medium
    for c in custom_fields:
        spectra[active_cell['row']].meta[c['field']] = c['value']
    analyte_records = [record for rlist in [s.meta['analytes'] for s in spectra] for record in rlist]
    analytes = pd.DataFrame.from_records(analyte_records)
    try:
        analyte_options = list(set(analytes['name']))
    except:
        analyte_options=no_update
    data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
    meta_datatypes = spectra[active_cell['row']].meta.fetch(trait='datatype')
    print(meta_datatypes)
    x_options =[key for key in meta_datatypes if meta_datatypes[key] == 'numeric']
    return jsonify(spectra),data,x_options,analyte_options,False

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
# ------------------------------ undo callbacks ------------------------------ #
@app.callback(Input('revert-data','n_clicks'),
              [Output('spectra','children'),
                Output('log','children'),
                Output('file-list', 'data'),
                Output('file-list','selected_rows')],
              [State('spectra','children'),
               State('original-spectra','children'),
               State('datatable-columns','value')])
def revert_data(n,json_spectra,json_original_spectra,metadata_cols):
    return_values = {'spectra':no_update,
                     'log':no_update,
                     'file-list_data':no_update,
                     'file-list_selected':no_update}
    if json_spectra is not None and json_original_spectra is not None:
        spectra = spec_from_json(json_spectra)
        original_spectra = spec_from_json(json_original_spectra)
    else:
        raise PreventUpdate
    for i in range(len(original_spectra)):
        newmeta = spectra[i].meta
        newmeta['integration'] = original_spectra[i].meta['integration']
        newmeta['repetitions'] = original_spectra[i].meta['repetitions']
        newmeta['excitation_wavelengths'] = original_spectra[i].meta['excitation_wavelengths']
        newmeta['excitation_ramanshifts'] = [(1/float(x)-1/float(spectra[i].meta['filter_wavelength']))*1e7 for x in newmeta['excitation_wavelengths']]
        spectra[i] = Spectrum(original_spectra[i].data,original_spectra[i].power,newmeta)
    data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
    return_values['spectra'] = jsonify(spectra)
    return_values['log'] = str(Processlog([s.log for s in spectra]))
    return_values['file-list_data']=data
    return_values['file-list_selected']=[x for x in range(len(data))]
    return tuple(list(return_values.values()))

@app.callback(Input('revert-meta','n_clicks'),
              [Output('spectra','children'),
                Output('log','children'),
                Output('file-list', 'data'),
                Output('file-list','selected_rows')],
              [State('spectra','children'),
               State('original-spectra','children'),
               State('datatable-columns','value')])
def revert_meta(n,json_spectra,json_original_spectra,metadata_cols):
    return_values = {'spectra':no_update,
                     'log':no_update,
                     'file-list_data':no_update,
                     'file-list_selected':no_update}
    if json_spectra is not None and json_original_spectra is not None:
        spectra = spec_from_json(json_spectra)
        original_spectra = spec_from_json(json_original_spectra)
    else:
        raise PreventUpdate
    for i in range(len(original_spectra)):
        newmeta = original_spectra[i].meta
        newmeta['data_operations'] = spectra[i].meta['data_operations']
        newmeta['integration'] = spectra[i].meta['integration']
        newmeta['repetitions'] = spectra[i].meta['repetitions']
        newmeta['excitation_wavelengths'] = spectra[i].meta['excitation_wavelengths']
        newmeta['excitation_ramanshifts'] = [(1/float(x)-1/float(original_spectra[i].meta['filter_wavelength']))*1e7 for x in spectra[i].meta['excitation_wavelengths']]
        spectra[i].meta = newmeta
    data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
    return_values['spectra'] = jsonify(spectra)
    return_values['log'] = str(Processlog([s.log for s in spectra]))
    return_values['file-list_data']=data
    return_values['file-list_selected']=[x for x in range(len(data))]
    return tuple(list(return_values.values()))
# -------------------------- preprocessing callbacks ------------------------- #
@app.callback(Output('do_rebin','is_open'),
              Input('reshape','n_clicks'),
              prevent_initial_call=True)
def open_rebin(n):
    return True

@app.callback([Output('rebin_dialogue','children'),
               Output('do_rebin', 'is_open'),
               Output('spectra','children'),
               Output('log','children'),
               Output('file-list', 'data')],
               [Input('close-re-bin', 'n_clicks')],
               [State('file-list','selected_rows'),
                State('file-list','data'),
                State('spectra','children'),
                State('new-integration','value'),
                State('new-nexp','value'),
                State('datatable-columns','value')])
def toggle_rebin(n,selected_rows,rows,json_spectra,new_integration,new_repetitions,metadata_cols):
    return_values = {'rebin_dialogue':no_update,
                     'do_rebin':no_update,
                     'spectra':no_update,
                     'log':no_update,
                     'file-list':no_update}
    if json_spectra is None:
        return_values['rebin_dialogue']= 'No spectra to re-bin.'
        return_values['do_rebin'] = True
        return tuple(list(return_values.values()))
    if selected_rows is None or selected_rows == []:
        return_values['rebin_dialogue']= 'No spectra selected to re-bin.'
        return_values['do_rebin'] = True
        return tuple(list(return_values.values()))
    spectra= spec_from_json(json_spectra)
    for i in selected_rows:
        if int(spectra[i].meta['integration'])*int(spectra[i].meta['repetitions']) != new_integration * new_repetitions:
            return_values['rebin_dialogue']='All selected spectra must have total number of spad exposures ='+str(ntotal)
            return_values['do_rebin'] = True
            return tuple(list(return_values.values()))
    for i in selected_rows:
        spectra[i] = spectra[i].rebin(new_repetitions,new_integration)
        spectra[i].meta['data_operations']=str(spectra[i].log)
    logstr = str(Processlog([s.log for s in spectra]))
    data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
    return_values['do_rebin'] = False
    return_values['spectra'] = jsonify(spectra)
    return_values['log'] = logstr
    return_values['file-list'] = data
    return tuple(list(return_values.values()))

@app.callback(Output('do_remove_samples','is_open'),
              Input('remove-samples','n_clicks'),
              prevent_initial_call=True)
def open_remove_samples(n):
    return True

@app.callback([Output('remove_samp_dialogue','children'),
               Output('do_remove_samples', 'is_open'),
               Output('spectra','children'),
               Output('log','children'),
               Output('file-list', 'data')],
               [Input('close-remove-samples', 'n_clicks')],
               [State('file-list','selected_rows'),
                State('spectra','children'),
                State('samples-to-remove','value'),
                State('datatable-columns','value')])
def toggle_remove_samples(n,selected_rows,json_spectra,samples_to_remove,metadata_cols):
    return_values = {'remove_samp_dialogue':no_update,
                     'do_remove_samples':no_update,
                     'spectra':no_update,
                     'log':no_update,
                     'file-list':no_update}
    if json_spectra is None:
        return_values['remove_samp_dialogue']='No spectra uploaded.'
        return_values['do_remove_samples'] = True
        return tuple(list(return_values.values()))
    if selected_rows is None or selected_rows == []:
        return_values['remove_samp_dialogue']='No spectra selected.'
        return_values['do_remove_samples'] = True
        return tuple(list(return_values.values()))
    spectra= spec_from_json(json_spectra)
    samp_conditions = [x for x in samples_to_remove.strip('[').strip(']').replace(' ','').split(',')]
    for i in selected_rows:
        s_buf= []
        for c in samp_conditions:
            if '-' in c:
                s_buf += [x for x in range(1,spectra[i].meta['repetitions']+1) if x>=int(c.split('-')[0]) and x<=int(c.split('-')[1])]
            else:
                s_buf.append(int(c))
        for x in s_buf:
            if x <1 or x >spectra[i].meta['repetitions']:
                return_values['remove_samp_dialogue'] = 'Specified samples out of bounds for selected spectra.'
                return_values['do_remove_samples'] = True
                return tuple(list(return_values.values()))
        spectra[i] = spectra[i].remove_samples(s_buf)
        spectra[i].meta['data_operations']=str(spectra[i].log)
    logstr = str(Processlog([s.log for s in spectra]))
    data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
    return_values['do_remove_samples'] = False
    return_values['spectra'] = jsonify(spectra)
    return_values['log'] = logstr
    return_values['file-list'] = data
    return tuple(list(return_values.values()))

@app.callback(Output('do_remove_wavelengths','is_open'),
              Input('remove-wavelengths','n_clicks'),
              prevent_initial_call=True)
def open_rebin(n):
    return True

@app.callback([Output('remove_wl_dialogue','children'),
               Output('do_remove_wavelengths', 'is_open'),
               Output('spectra','children'),
               Output('log','children'),
               Output('file-list', 'data')],
               [Input('close-remove-wavelengths', 'n_clicks')],
               [State('file-list','selected_rows'),
                State('spectra','children'),
                State('wavelengths-to-remove','value'),
                State('datatable-columns','value')])
def toggle_remove_wavelengths(n,selected_rows,json_spectra,wls_to_remove,metadata_cols):
    return_values = {'remove_wl_dialogue':no_update,
                     'do_remove_wavelengths':no_update,
                     'spectra':no_update,
                     'log':no_update,
                     'file-list':no_update}
    if json_spectra is None:
        remove_dialogue='No spectra uploaded.'
        return remove_dialogue,True,no_update,no_update,no_update
    if selected_rows is None or selected_rows == []:
        remove_dialogue='No spectra selected.'
        return remove_dialogue,True,no_update,no_update,no_update
    spectra= spec_from_json(json_spectra)
    wls_conditions = [x for x in wls_to_remove.strip('[').strip(']').replace(' ','').split(',')]
    for i in selected_rows:
        wl_buf= []
        for c in wls_conditions:
            if '-' in c:
                wl_buf += [x for x in spectra[i].meta['excitation_wavelengths'] if np.round(x,2)>=float(c.split('-')[0]) and np.round(x,2)<=float(c.split('-')[1])]
            else:
                wl_buf.append(float(c))
        for x in wl_buf:
            if x not in spectra[i].meta['excitation_wavelengths']:
                remove_dialogue = 'Specified wavelengths out of bounds for selected spectra.'
                return remove_dialogue,True,no_update,no_update,no_update
        spectra[i] = spectra[i].remove_wavelengths(wl_buf)
        spectra[i].meta['data_operations']=str(spectra[i].log)
    logstr = str(Processlog([s.log for s in spectra]))
    data=[{col:str(s.meta[col]) for col in metadata_cols} for s in spectra]
    return_values['do_remove_wavelengths'] = False
    return_values['spectra'] = jsonify(spectra)
    return_values['log'] = logstr
    return_values['file-list'] = data
    return tuple(list(return_values.values()))
# -------------------------- normalization ------------------------- #
@app.callback([Output('spectra','children'),
               Output('log','children')],
              Input('normalize-data','n_clicks'),
              [State('norm-selection','value'),
                State('file-list','selected_rows'),
                State('spectra','children')])
def do_normalization(n, norm_type, selected_rows,json_spectra):
    if json_spectra is None or selected_rows is None or selected_rows == []:
        raise PreventUpdate
    spectra= spec_from_json(json_spectra)
    if norm_type == 'intra-normalization':
        for i in selected_rows:
            spectra[i].power_normalize()
            spectra[i].meta['data_operations']=str(spectra[i].log)
    elif norm_type == 'inter-normalization':
        inter_normalize([spectra[i] for i in selected_rows])
        for i in range(len(spectra)):
            spectra[i].meta['data_operations']=str(spectra[i].log)
    logstr = str(Processlog([s.log for s in spectra]))
    return jsonify(spectra),logstr
# ----------------------------- filtering ----------------------------- #
@app.callback([Output('spectra','children'),
               Output('log','children')],
              Input('filter-data','n_clicks'),
              [State('filter-selection','value'),
                State('file-list','selected_rows'),
                State('spectra','children')])
def do_filter(n, filter_type,selected_rows,json_spectra):
    if json_spectra is None or selected_rows is None or selected_rows == []:
        raise PreventUpdate
    spectra= spec_from_json(json_spectra)
    if filter_type == 'median filter':
        for i in selected_rows:
            spectra[i]=spectra[i].medianfilter_raw()
            spectra[i].meta['data_operations']=str(spectra[i].log)
    elif filter_type == 'outlier filter':
        #TODO: add outlier filter
        pass
    logstr = str(Processlog([s.log for s in spectra]))
    return jsonify(spectra),logstr
# ------------------------------ plot callbacks ------------------------------ #
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
    color=colorlist[g% len(colorlist)]
    printv(g,color)
    if processing_switchval:
        mode='lines+markers'
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
                [Input('multi_plot_tabs','value'),
                Input('spectra','children'),
                Input('working','clickData'),
                Input('ydata-type','value')])
def update_working(tab,json_spectra,clickData,ydata_switchval):
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
        color=colorlist[i % len(colorlist)]
        mode='lines+markers'
        if ydata_switchval:
            fig.add_trace(spectra[i].plot(color=color,label='experiment_name',show_err=True).data[0])
            yaxis='SPAD Count'
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

@app.callback([Output('target-peak-lod','value'),
               Output('target-peak-custom','value'),
               Output('target-peak-stat','value')],
              Input('working','clickData'))
def update_target_peak(clickData):
    n_outputs = 3
    return tuple([clickData['points'][0]['x'] for _ in range(n_outputs)])

@app.callback([Output('working','figure'),
               Output('log','children'),
               Output('do-lod','children'),
               Output('do-lod','outline'),
               Output('lod-info','children'),
               Output('cached_plot_data','children')],
              [Input('do-lod','n_clicks')],
              [State('target-peak-lod','value'),
               State('spectra','children'),
               State('do-lod','children')])
def do_lod(lod_clicks,raman,json_spectra,lod_state):
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        raise PreventUpdate
    if lod_state == 'Compute LOD':
        max_index = spectra[0].meta['excitation_ramanshifts'].index(raman)
        concentrations = []
        for s in spectra:
            try:
                concentrations.append(float(s.meta['target_analyte'].split(' ')[0]))
                units =s.meta['target_analyte'].split(' ')[1]
            except Exception as e:
                print(e)
                concentrations.append(0)
        concentrations = np.array(concentrations)
        refs = np.array([x.ref[max_index] for x in spectra])
        noise = np.array([x.noise[max_index] for x in spectra])
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
        plot_data = {'concentrations':concentrations.tolist(),'spad':refs.tolist(),'spad_err':noise.tolist()}
        printv(sy,res.slope,res.intercept)
        #lod =(3*sy+np.min(refs)-res.intercept)/res.slope
        lod =(3*sy)/res.slope
        printv(lod,np.min(refs),np.max(refs))
        fig.add_shape(type='line',
                    x0=lod,x1=lod,
                    y0=np.min(refs),y1=np.max(refs),
                    line=dict(dash='dot',color='#000000'))
        fig.update_layout(title = 'LOD Concentration for ' + '%.2f' %(raman) + ' Raman Peak is '+ '%.4f' %(lod)+ units,
                            xaxis_title = f'Concentration {units}',
                            yaxis_title = 'Signal',showlegend=False)
        logstr = Processlog([s.log for s in spectra])
        lod_info ='LOD Concentration for ' + '%.2f' %(raman) + ' Raman Peak is '+ '%.4f' %(lod)+" \[" +units[1:-1]+ "\]"+ buffer
        lod_info += 'y = %.5f * x + %.5f'%(res.slope,res.intercept) + buffer
        lod_info += 'r-squared = ' + str(res.rvalue**2)
        return fig,str(logstr),'Clear LOD',True,lod_info,json.dumps(plot_data)
    else:
        fig=go.Figure()
        for i in range(len(spectra)):
            color=colorlist[i % len(colorlist)]
            mode='lines+markers'
            fig.add_trace(spectra[i].plot(color=color,label='experiment_name',show_err=True).data[0])
            yaxis='SPAD Count'
        fig.update_layout(title='Combined Spectra',xaxis_title='Raman Shift (cm^-1)',yaxis_title=yaxis)
        logstr = Processlog([s.log for s in spectra])
        lod_info=""
        return fig, str(logstr),'Compute LOD',False,lod_info,no_update

@app.callback([Output('working','figure'),
               Output('log','children'),
               Output('do-custom','children'),
               Output('do-custom','outline')],
              [Input('do-custom','n_clicks')],
              [State('target-peak-custom','value'),
               State('x-dropdown','value'),
               State('spectra','children'),
               State('do-custom','children')])
def custom_plot(n,raman,xaxis,json_spectra,custom_state):
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        raise PreventUpdate
    if custom_state == 'Show Custom Plot':
        selected_index = spectra[0].meta['excitation_ramanshifts'].index(raman)
        xvals = []
        for s in spectra:
            try:
                xvals.append(float(s.meta[xaxis]))
            except Exception as e:
                print(e)
                xvals.append(0)
        xvals = np.array(xvals)
        refs = np.array([x.ref[selected_index] for x in spectra])
        noise = np.array([x.noise[selected_index] for x in spectra])
        sy = np.mean(noise)
        printv('sy',sy)
        fig=go.Figure(data=go.Scatter(x=xvals,y=refs,
                                    error_y=dict(
                                                type='data',
                                                array=noise,
                                                visible=True
                                    ),mode='markers'))
        fig.update_layout(xaxis_title = xaxis,
                            yaxis_title = 'SPAD Count',showlegend=False)
        logstr = Processlog([s.log for s in spectra])
        return fig,str(logstr),'Clear Custom Plot',True
    else:
        fig=go.Figure()
        for i in range(len(spectra)):
            color=colorlist[i % len(colorlist)]
            mode='lines+markers'
            fig.add_trace(spectra[i].plot(color=color,label='experiment_name',show_err=True).data[0])
            yaxis='SPAD Count'
        fig.update_layout(title='Combined Spectra',xaxis_title='Raman Shift (cm^-1)',yaxis_title=yaxis)
        logstr = Processlog([s.log for s in spectra])
        return fig, str(logstr),'Show Custom Plot',False

@app.callback([Output('working','figure')],
              [Input('mean-n','n_clicks')],
              [State('target-peak-stat','value'),
               State('spectra','children')])
def show_mean(n,raman,json_spectra):
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        raise PreventUpdate
    selected_index = spectra[0].meta['excitation_ramanshifts'].index(raman)
    fig=go.Figure()
    for spec in spectra:
        data = spec.fetch_raw_data()[selected_index].flatten()
        samples= np.arange(0,len(data),step=1)
        means = [np.mean(data[:s]) for s in samples]
        fig.add_trace(go.Scatter(x=samples,y=means,mode='lines+markers',name=spec.meta['experiment_name']))
    fig.update_layout(title = 'Sample Mean vs Number of Samples',
                        xaxis_title = 'Spad Integrations ('+str(spectra[0].meta['spad_integration_time']/1000)+' s)',
                        yaxis_title = 'Mean')
    return fig

@app.callback([Output('working','figure')],
              [Input('std-n','n_clicks')],
              [State('target-peak-stat','value'),
               State('spectra','children')])
def show_sdev(n,raman,json_spectra):
    if json_spectra is not None:
        spectra = spec_from_json(json_spectra)
    else:
        raise PreventUpdate
    selected_index = spectra[0].meta['excitation_ramanshifts'].index(raman)
    fig=go.Figure()
    for spec in spectra:
        data = spec.fetch_raw_data()[selected_index].flatten()
        samples= np.arange(0,len(data),step=1)
        means = [np.std(data[:s],ddof=1) for s in samples]
        fig.add_trace(go.Scatter(x=samples,y=means,mode='lines+markers',name=spec.meta['experiment_name']))
    fig.update_layout(title = 'Sample Standard Deviation vs Number of Samples',
                        xaxis_title = 'Spad Integrations ('+str(spectra[0].meta['spad_integration_time']/1000)+' s)',
                        yaxis_title = 'Standard Deviation')
    return fig
# ------------------------------------- - ------------------------------------ #

@app.callback(Input('lod-export','n_clicks'),
              [State('lod-filename','value'),
               State('cached_plot_data','children')],
               [Output('lod-download','data'),
                Output('save-modal','is_open'),
               Output('save-body','children')])
def save_lod(n,filename,cached_data):
    df = pd.DataFrame(json.loads(cached_data))
    status='STATUS: success'
    return dcc.send_data_frame(df.to_csv, filename+'.csv'),True,status

@app.callback(Input('export','n_clicks'),
              [State('file-list','selected_rows'),
                State('file-list','data'),
                State('spectra','children'),
                State('save-name','value')],
              [Output('download-specs','data'),
               Output('log','children'),
               Output('save-modal','is_open'),
               Output('save-body','children')])
def export_specs(n,selected_rows,rows,json_spectra,save_name):
    if not n or json_spectra is None or selected_rows is None or selected_rows == []:
        return no_update
    spectra = spec_from_json(json_spectra)
    selected_spectra = [spectra[i] for i in selected_rows]
    try:
        zipdata = zip_spectra(save_name,selected_spectra)
    except Exception as e:
        return no_update,no_update,True,f'status: FAILURE-- {e}'
    #remove created instances of data in working directory
    if platform == 'darwin':
        os.system('rm -rf *.power')
        os.system('rm -rf *.spad')
    else:
        os.system('del *.power')
        os.system('del *.spad')
    logstr = str(Processlog([s.log for s in spectra]))
    return dcc.send_file(save_name+'.zip'),logstr,True,'status: success'

#RUN APP_______________________________________________________________________
if __name__ == '__main__':
    if params.test_mode:
        app.run_server(debug=True,dev_tools_hot_reload=False)
    else:
        app.run_server(debug=False)