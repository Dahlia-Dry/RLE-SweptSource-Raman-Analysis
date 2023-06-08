"""
Swept Source Raman GUI
Dahlia Dry, 2022 | dahlia23@mit.edu
Physical Optics and Electronics Group
"""
#file imports
from . import params
from .metadata import *
#package imports
from dash import dcc,html,dash_table
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
import dash_daq as daq
#INITIALIZE VARIABLES__________________________________________________________
if not params.test_mode:
    init_laser = 'DISCONNECTED'
    init_spad='DISCONNECTED'
    if params.power_monitoring:
        init_pm = 'DISCONNECTED'
    else:
        init_pm = 'DISCONNECTED- Power Monitoring OFF'
else:
    init_laser = 'TESTMODE'
    init_spad='TESTMODE'
    init_pm = 'TESTMODE'
fileparams = ['experiment_name','integration','repetitions','concentration','filename']
working = go.Figure()
current=go.Figure()
data_progress=go.Figure()
power_meter=go.Figure()
power_meter.update_layout(title="Power Meter")
time_trace=go.Figure()
time_trace.update_layout(title="Current Measurement Progress")
colorlist = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52']
datalog = ""
buffer='      \n'
default_metadata = Metadata()
init_measurement = dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
if params.web_host:
    upload_visibility = 'hidden'
    demo_visibility = 'visibile'
    default_integration = 3
    default_nexp=5
    default_experiment_name='test'
    default_concentration=0
    default_wlstart=800
    default_wlstop=803
    default_wlstep=1
    default_wlpeak=800
else:
    upload_visibility = 'visible'
    demo_visibility = 'hidden'
    default_integration=None
    default_nexp=None
    default_experiment_name=None
    default_concentration=None
    default_wlstart=None
    default_wlstop=None
    default_wlstep=None
    default_wlpeak=None
#_______________________________________________________________________________
header=html.Div([
                html.H1('Swept Source Raman Console',id='page-title',style={'padding':10}),
                dbc.Tooltip("For best viewing experience, please set browser zoom to 50%.",placement='bottom',target='page-title',id='page-title-tooltip'),
                html.A(html.Button([html.I(className="fa fa-github fa-5x"), ""],
                            style={'position':'fixed','right':100,'top':0,
                                    'border':'none','border-radius':12,'font-size':14,
                                    },id='github'),
                        href="https://github.com/Dahlia-Dry/RLE-Sweptsource-Raman",
                        target='_blank'),
                dbc.Tooltip("View documentation",target='github',placement='bottom',id='github-tooltip'),
                html.Button([html.I(className="fa fa-cog fa-5x"), ""],
                             id="open-settings", n_clicks=0,
                             style={'position':'fixed','right':10,'top':0,
                                    'border':'none','border-radius':12,'font-size':14,
                                    }),
                dbc.Tooltip("Open settings",target='open-settings',placement='bottom',id='settings-tooltip')
                ],)
wl_sweep = html.Div([
                    html.Div([dcc.Markdown(children='Integration Time:',style={'padding':10}),
                            dcc.Input(id='integration'.format('number'),type='number',value=default_integration),
                            dcc.Markdown(id='nexp-title',children='Number of Exposures/Wavelength:',style={'padding':10}),
                            dcc.Input(id='nexp'.format('number'),type='number',value=default_nexp)],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}
                    ),
                    html.Div([dcc.Checklist(id='toggle_continuous',options=['\t Continuous?'],value=[]),
                              html.Div(id='continuous', children='False',style={'display':'none'}),
                              dcc.Markdown(id="exp-reps-title",children='Experiment Repetitions:',style={'padding':10}),
                            dcc.Input(id='exp-reps'.format('number'),type='number',value=1)],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}
                    ),
                    html.Div([
                    dcc.Markdown(children='$\lambda$ start:',mathjax=True,style={'padding':10}),
                    dcc.Input(id='wl-start'.format('number'),type='number',value=default_wlstart),
                    dcc.Markdown(children="=  $cm^{-1}$",id='raman-start',mathjax=True,style={'font-style':"italic"}),
                    dcc.Markdown(children='$\lambda$ end:',mathjax=True,style={'padding':10}),
                    dcc.Input(id='wl-end'.format('number'),type='number',value=default_wlstop),
                    dcc.Markdown(children="=  $cm^{-1}$",id='raman-end',mathjax=True,style={'font-style':"italic"}),
                    dcc.Markdown(children='$\lambda$:',mathjax=True,style={'padding':10,'display':'none'}),
                    dcc.Input(id='wl-peak'.format('number'),type='number',style={'display':'none'}),
                    dcc.Markdown(children="=  $cm^{-1}$",id='raman-peak',mathjax=True,style={'font-style':"italic",'display':'none'}),
                    dcc.Markdown(children='$\lambda$ step:',mathjax=True,style={'padding':10}),
                    dcc.Input(id='wl-step'.format('number'),type='number',value=default_wlstep),
                    html.Button([html.I(className="fa fa-plus"), ""],
                             id="add-range", n_clicks=0,
                             style={'font-size':30,
                                    "margin-left": "15px"}),
                    dbc.Tooltip("Add wavelength range",target='add-range',placement='top',id='add-range-tooltip'),                
                    ],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}
                    ),
                    html.Div([
                    dash_table.DataTable(id='wl-ranges',
                                            columns=[{'name': ['start','stop','step'][i],
                                                        'id': ['start','stop','step'][i]} for i in range(3)],
                                            data=[],
                                            row_deletable=True,
                                            style_cell={'textAlign': 'center',
                                                        #'minWidth': '30%', 'width': '30%', 'maxWidth': '30%',
                                                        },
                                            style_cell_conditional=[
                                                {'if': {'column_id': 'start'},
                                                'width': '30%'}]
                                        )],style={'width':'1007px'}),])
peak = html.Div([
                    html.Div([
                    dcc.Markdown(children='Integration Time:',style={'padding':10}),
                    dcc.Input(id='integration'.format('number'),type='number',value=default_integration),
                    dcc.Markdown(id='nexp-title',children='Number of Exposures:',style={'padding':10}),
                    dcc.Input(id='nexp'.format('number'),type='number',value=default_nexp),
                    dcc.Markdown(children='$\lambda$ start:',mathjax=True,style={'padding':10,'display':'none'}),
                    dcc.Input(id='wl-start'.format('number'),type='number',style={'display':'none'}),
                    dcc.Markdown(children="=  $cm{^-1}$",mathjax=True,id='raman-start',style={'font-style':"italic",'display':'none'}),
                    dcc.Markdown(children='$\lambda$ end:',mathjax=True,style={'padding':10,'display':'none'}),
                    dcc.Input(id='wl-end'.format('number'),type='number',style={'display':'none'}),
                    dcc.Markdown(children="=  $cm^{-1}$",mathjax=True,id='raman-end',style={'font-style':"italic",'display':'none'}),
                    dcc.Markdown(children='$\lambda$:',mathjax=True,style={'padding':10}),
                    dcc.Input(id='wl-peak'.format('number'),type='number',value=default_wlpeak),
                    dcc.Markdown(children="=  $cm^{-1}$",mathjax=True,id='raman-peak',style={'font-style':"italic"}),
                    dcc.Markdown(children='$\lambda$ step:',mathjax=True,style={'padding':10,'display':'none'}),
                    dcc.Input(id='wl-step'.format('number'),type='number',style={'display':'none'}),
                    html.Button([html.I(className="fa fa-plus"), ""],
                             id="add-range", n_clicks=0,
                             style={'font-size':30,
                                    "margin-left": "15px",
                                    "display":'none'}),
                    dbc.Tooltip("Add wavelength range",target='add-range',placement='top',id='add-range-tooltip'),                
                    ],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}
                    ),
                    html.Div([
                    dash_table.DataTable(id='wl-ranges',
                                            columns=[],
                                            data=[],
                                            row_deletable=True,
                                            style_cell={'textAlign': 'center',
                                                        #'minWidth': '30%', 'width': '30%', 'maxWidth': '30%',
                                                        },
                                            style_cell_conditional=[
                                                {'if': {'column_id': 'start'},
                                                'width': '30%'}]
                                        )],style={'width':'1007px'}),])
rolling_avg = html.Div([
                    html.Div([
                    dcc.Markdown(children='Integration Time:',style={'padding':10}),
                    dcc.Input(id='integration'.format('number'),type='number'),
                    dcc.Markdown(id='nexp-title',children='Repetitions:',style={'padding':10}),
                    dcc.Input(id='nexp'.format('number'),type='number')],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}
                    ),
                    html.Div([
                    dcc.Markdown(children='$\lambda$ start:',mathjax=True,style={'padding':10,'display':'none'}),
                    dcc.Input(id='wl-start'.format('number'),type='number',style={'display':'none'}),
                    dcc.Markdown(children="=  $cm^{-1}$",id='raman-start',mathjax=True,style={'font-style':"italic",'display':'none'}),
                    dcc.Markdown(children='$\lambda$ end:',mathjax=True,style={'padding':10,'display':'none'}),
                    dcc.Input(id='wl-end'.format('number'),type='number',style={'display':'none'}),
                    dcc.Markdown(children="=  $cm^{-1}$",id='raman-end',mathjax=True,style={'font-style':"italic",'display':'none'}),
                    dcc.Markdown(children='$\lambda$:',mathjax=True,style={'padding':10}),
                    dcc.Input(id='wl-peak'.format('number'),type='number'),
                    dcc.Markdown(children="=  $cm^{-1}$",id='raman-peak',mathjax=True,style={'font-style':"italic"}),
                    dcc.Markdown(children='$\lambda$ step:',mathjax=True,style={'padding':10,'display':'none'}),
                    dcc.Input(id='wl-step'.format('number'),type='number',style={'display':'none'}),
                    html.Button([html.I(className="fa fa-plus"), ""],
                             id="add-range", n_clicks=0,
                             style={'font-size':30,
                                    "margin-left": "15px"}),
                    dbc.Tooltip("Add wavelength range",target='add-range',placement='top',id='add-range-tooltip'),                
                    ],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}
                    ),
                    html.Div([
                    dash_table.DataTable(id='wl-ranges',
                                            columns=[{'name': ['label','wavelength','wavenumber'][i],
                                                        'id': ['label','wavelength','wavenumber'][i]} for i in range(3)],
                                            data=[],
                                            row_deletable=True,
                                            style_cell={'textAlign': 'center',
                                                        #'minWidth': '30%', 'width': '30%', 'maxWidth': '30%',
                                                        },
                                            style_cell_conditional=[
                                                {'if': {'column_id': 'start'},
                                                'width': '30%'}]
                                        )],style={'width':'1007px'}),])
tab_1= html.Div(children=[
            dbc.Row([
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("Settings")),
                        html.Div([
                        dcc.Markdown(children="Select Laser: "),
                        dcc.Dropdown(params.available_lasers,id='selected-laser',value=params.default_laser,style={'width':'60%',"font-weight": "bold", 'display':'inline-block'}),
                        ]),
                        html.Div([
                        dcc.Markdown(children='SPAD Channel Mappings:'),
                        dash_table.DataTable(id='selected-spads',
                                             columns=[
                                            {'id': 'spad address', 'name': 'spad address', 'presentation': 'dropdown'},
                                            {'id': 'channel number', 'name': 'channel number'}],
                                            data=[{'spad address':list(params.default_spad_mapping.keys())[i],'channel number':list(params.default_spad_mapping.values())[i]} for i in range(len(params.default_spad_mapping))],
                                            editable=True,
                                        )]),
                        dbc.ModalFooter(
                            dbc.Button(
                                "Save and Close",
                                id="close-settings",
                                className="ms-auto",
                                n_clicks=0,
                            )
                        ),
                    ],
                    id="settings",
                    size="xl",
                    is_open=False,
                    style={'padding':10}),
                dbc.Col(html.Div([
                    #CONTROL PANEL
                    dcc.Markdown(children='## Control Panel',style={'padding':10}),
                    html.Div([
                    dcc.Markdown(children='Experiment Name:',style={'padding':10}),
                    dcc.Input(id='experiment-name'.format('text'),type='text',value=default_experiment_name),
                    dcc.Markdown(children='Concentration:',style={'padding':10}),
                    dcc.Input(id='concentration'.format('text'),type='text',value=default_concentration)],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}
                    ),
                    #Wavelength Sweep
                    html.Div([
                        dcc.Markdown(id="experiment-label",children="### Experiment Type: "),
                        dcc.Dropdown(['Wavelength Sweep', 'Peak Measurement', 'Rolling Average'], 'Wavelength Sweep',id='experiment-type',style={'width':'60%',"font-weight": "bold", 'display':'inline-block'}),
                        dbc.Tooltip("toggle experiment type",target='experiment-type',placement='top',id='toggle-type-tooltip')
                    ],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}),
                    html.Div(id='measurement-params',children=wl_sweep,style={'display':'block','padding':10},className="d-grid gap-2 d-md-flex"),
                    html.Div([dbc.Button(children="Connect Instruments",id='connection',n_clicks=0,color='success',outline=False),
                              dbc.Button(children="Shutdown Instruments",id='shutdown',n_clicks=0,color='danger'),
                              dbc.Button(children="Begin Measurement",id='measure',n_clicks=0,color='primary',disabled=True),
                              dbc.Tooltip("",target='measure',placement='bottom'),
                              dcc.Upload(dbc.Button(children="Load .exp File",n_clicks=0,color='info'),id='preset'),
                              dbc.Button(children="Pause",id='pause',n_clicks=0,color='warning',outline=False)],
                              className ="d-grid gap-2 d-md-flex",
                              style={'padding':10}),
                    #HIDDEN DATA
                    html.Div(id='start-trigger',children='False',style={'display': 'none'}),
                    html.Div(id='collected-spectra',style={'display': 'none'}),
                    html.Div(id="metajson",style={'display':'none'}),
                    html.Div(id="current_wl",children="-1",style={'display':'none'}),
                    html.Div(id="trigger-download",children="False",style={'display':'none'}),
                    html.Div(id='exposing',children='False',style={'display':'none'}),
                    html.Div(id='total_exposures',children='0',style={'display':'none'}),
                    html.Div(id='current_exposures',children='0',style={'display':'none'}),
                    html.Div(id='prev_exposures',children='0',style={'display':'none'}),
                    html.Div(id='measured_wavelengths',children='{}',style={'display':'none'}),
                    html.Div(id='failed_wavelengths',children='[]',style={'display':'none'}),
                    html.Div(id='state',children='{}',style={'display':'none'}),
                    html.Div(id='prev_state',children='{}',style={'display':'none'}),
                    html.Div(id='state_cache',children='{}',style={'display':'none'}),
                    html.Div(id='rep_count',children='1',style={'display':'none'}),
                    html.Div(id='measurement_parameters',children='{}',style={'display':'none'}),
                    html.Div(id='measurement',children=json.dumps(init_measurement),style={'display':'none'}),
                    html.Div(id='power_measurement',children=json.dumps(init_measurement),style={'display':'none'}),
                    dbc.Modal(
                        [
                            dbc.ModalHeader(dbc.ModalTitle("Measurement Done")),
                            dbc.ModalBody("",id="modal_body"),
                            dbc.ModalFooter(
                                dbc.Button(
                                    "Close", id="close_modal", className="ms-auto", n_clicks=0
                                )
                            ),
                        ],
                        id="modal",
                        is_open=False,),
                    #STATUS
                    html.Div([
                        dcc.Markdown(children='## Status',style={'padding-left':10}),
                        html.Span(children="Measurement not in progress\n",id='status',style={'padding':10,"color":"grey","font-size":"20px","font-style":"italic","padding-bottom":20})
                    ]),
                    #LASER
                    html.Div([
                        html.Span("Laser: ",style={'padding':10}),
                        html.Span(init_laser,id='laser-status', style={"color": "blue","font-weight": "bold"})
                    ]),
                    #POWER METER
                    html.Div([
                        html.Span("Power Meter: ",style={'padding':10}),
                        html.Span(init_pm,id='power-status', style={"color": "blue","font-weight": "bold"})
                    ]),
                    #SPAD
                    html.Div([
                        html.Span("SPAD Channels: \n",style={'padding':10,'white-space': 'pre-line'}),
                        dcc.Markdown(children=init_spad,id='spad-status', style={"padding":10,"color": "blue","font-weight": "bold"})
                    ]),
                    #MEASUREMENT PROGRESS
                    html.Div([
                    dcc.Markdown(children='Measurement Progress:'),
                    dcc.Interval(id="progress-interval", n_intervals=0, interval=params.prog_interval*1000),
                    dcc.Interval(id="update-interval", n_intervals=0, interval=1000),
                    dbc.Progress(id="progress"),
                    ],
                    style={'padding':10}),
                    #LOG
                    html.Div([
                        dcc.Markdown(children='## Log',style={'padding':10}),
                        dcc.Markdown(id='data-log',children=datalog,style={"maxHeight": "400px", "overflow": "scroll"})]),
                ],
                ),),
                dbc.Col(html.Div([
                    dcc.Graph(
                        id='time_trace',
                        figure=time_trace,
                    ),
                    dcc.Graph(
                        id='power_meter',
                        figure=power_meter,
                    ),
                    dcc.Graph(
                        id='data_progress',
                        figure=data_progress,
                    )
                    ]
                    ),)
                ],)],style={'height':'50vh'},)
tab_2= html.Div(children=[
            dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("Settings")),
                        dcc.Markdown(children='## Select visible + editable metadata parameters',style={'padding':10}),
                        dcc.Dropdown(
                            [x for x in list(params.meta.keys()) if x!= 'filename'],
                            [x for x in fileparams if x != 'filename'],
                            multi=True,
                            id='datatable-columns'
                        ),
                        dbc.ModalFooter(
                            dbc.Button(
                                "Save and Close",
                                id="close-settings",
                                className="ms-auto",
                                n_clicks=0,
                            )
                        ),
                    ],
                    id="settings",
                    size="xl",
                    is_open=False,),
            html.Div([dcc.Upload(
                id='upload-data',
                children=html.Div([
                    'Drag and Drop or ',
                    html.A('Select Files')
                ]),
                style={
                    'width': '100%',
                    'height': '60px',
                    'lineHeight': '60px',
                    'borderWidth': '1px',
                    'borderStyle': 'dashed',
                    'borderRadius': '5px',
                    'textAlign': 'center',
                    'margin': '10px',
                    'visibility': upload_visibility
                },
                # Allow multiple files to be uploaded
                multiple=True
            )]),
            html.Div([dbc.Button("Load Peak Measurement Demo Data",id='load-peak-demo',n_clicks=0,color='primary',outline=True,style={'visibility':demo_visibility}),
            dbc.Button("Load Wavelength Sweep Demo Data",id='load-sweep-demo',n_clicks=0,color='primary',outline=True,style={'visibility':demo_visibility})],
            className ="d-grid gap-2 d-md-flex",
            style={'padding':10,'justify-content':'left'}),
            html.Div(
                children= [
                dash_table.DataTable(
                    id='file-list',
                    columns=([{'id':p,'name':p} for p in fileparams if p !='filename']),
                    data=[{key:None for key in fileparams}],
                    style_data_conditional=[],
                    row_deletable=True,
                    editable=True,
                    row_selectable='multi',
                )],
                style={'padding':10}
            ),
            html.Div(id='spectra',style={'display': 'none'}),
            html.Div(id='original-spectra',style={'display': 'none'}),
            html.Div(id='graphnum',children='0',style={'display':'none'}),
            dbc.Row([
                dbc.Col(html.Div([
                    dcc.Graph(
                        id='working',
                        figure=working,
                    ),
                    html.Div([dbc.Button("Select All",id='select-all',n_clicks=0,color='primary'),
                              dbc.Button("Deselect All",id='deselect-all',n_clicks=0,color='primary'),
                              dbc.Button("Revert Selected to Original",id='revert',n_clicks=0,color='primary'),
                              dbc.Button("Export Selected",id='export',n_clicks=0,color='secondary')],
                              className ="d-grid gap-2 d-md-flex",
                              style={'padding':10}),
                    html.Div([dbc.Button("Median Filter Raw Data",id='median-raw',n_clicks=0,color='info'),
                              dbc.Button("Rebin Raw Data",id='re-bin',n_clicks=0,color='info'),
                              dbc.Button("Remove Samples",id='remove-samples',n_clicks=0,color='info'),
                              dbc.Button("Remove Wavelengths",id='remove-wavelengths',n_clicks=0,color='info'),],
                              className ="d-grid gap-2 d-md-flex",
                              style={'padding':10}),
                    html.Div([dbc.Button("Power Normalize (intra)",id='power-normalize',n_clicks=0,color='success'),
                              dbc.Button("Power Normalize (inter)",id='inter-normalize',n_clicks=0,color='success'),
                              dbc.Button("Lieber Fit",id='lieber',n_clicks=0,color='success'),
                              dbc.Tooltip("Method for background removal",target='lieber',placement='bottom')
                              ],
                              className ="d-grid gap-2 d-md-flex",
                              style={'padding':10}),
                    dbc.Modal(
                        [
                            dbc.ModalHeader(dbc.ModalTitle("Re-Bin Selected Spectra")),
                            dcc.Markdown(children='Integration Time:',style={'padding':10}),
                            dcc.Input(id='new-integration',type='number'),
                            dcc.Markdown(children='Number of Exposures:',style={'padding':10}),
                            dcc.Input(id='new-nexp',type='number'),
                            dcc.Markdown(children='',id='rebin_dialogue',style={'padding':10}),
                            dbc.ModalFooter(
                                dbc.Button(
                                    "Execute", id="close-re-bin", className="ms-auto", n_clicks=0
                                )
                            ),
                        ],
                        id="do_rebin",
                        is_open=False,
                    ),
                    dbc.Modal(
                        [
                            dbc.ModalHeader(dbc.ModalTitle("Remove Samples from Selected Spectra")),
                            dcc.Markdown(children='Enter sample numbers/ranges to remove (e.g. 1-3,5,7)'),
                            dcc.Markdown(children='Samples to Remove:',style={'padding':10}),
                            dcc.Input(id='samples-to-remove',type='text'),
                            dcc.Markdown(children='',id='remove_samp_dialogue',style={'padding':10}),
                            dbc.ModalFooter(
                                dbc.Button(
                                    "Execute", id="close-remove-samples", className="ms-auto", n_clicks=0
                                )
                            ),
                        ],
                        id="do_remove_samples",
                        is_open=False,
                    ),
                    dbc.Modal(
                        [
                            dbc.ModalHeader(dbc.ModalTitle("Remove Wavelengths from Selected Spectra")),
                            dcc.Markdown(children='Enter wavelengths/ranges to remove (e.g. 700-703,705,706)'),
                            dcc.Markdown(children='Wavelengths to Remove:',style={'padding':10}),
                            dcc.Input(id='wavelengths-to-remove',type='text'),
                            dcc.Markdown(children='',id='remove_wl_dialogue',style={'padding':10}),
                            dbc.ModalFooter(
                                dbc.Button(
                                    "Execute", id="close-remove-wavelengths", className="ms-auto", n_clicks=0
                                )
                            ),
                        ],
                        id="do_remove_wavelengths",
                        is_open=False,
                    ),
                    html.Div([dbc.Button("Show Limit of Detection",id='lod',n_clicks=0,color='dark'),
                              dbc.Tooltip("Toggle LOD:Select analyte peak in top left plot, then press this button ",target='lod',placement='bottom'),
                              dbc.Button("Show All Spectra",id='all-spec',n_clicks=0,color='dark'),
                              dbc.Tooltip("Toggle show all spectra",target='all-spec',placement='bottom'),
                              dbc.Button("Show Mean vs Sample Size",id='mean-n',n_clicks=0,color='dark'),
                              dbc.Button("Show Sigma vs Sample Size",id='std-n',n_clicks=0,color='dark'),],
                              className ="d-grid gap-2 d-md-flex",
                              style={'padding':10}),
                ],
                ),),
                dbc.Col(html.Div([
                    dcc.Markdown(children='## Log'),
                    dcc.Markdown(id='log',children='',style={"maxHeight": "400px", "overflow": "scroll"}),
                    html.Div([
                                dbc.Button("<-",id="back",n_clicks=0,color='primary'),
                                dbc.Button("->",id="forward",n_clicks=0,color='primary'),
                                daq.ToggleSwitch(
                                                id="ydata-type",
                                                value=True,
                                                size=60,
                                                ),
                                dbc.Tooltip("toggle y axis spad vs power data",target='ydata-type',placement='top',id='toggle-type-tooltip'),
                                daq.ToggleSwitch(
                                                id="dataprocessing-type",
                                                value=True,
                                                vertical=True,
                                                size=60,
                                                ),
                                dbc.Tooltip("toggle raw vs processed data",target='dataprocessing-type',placement='top',id='toggle-type-tooltip'),
                                dcc.Markdown("$\lambda$",mathjax=True),
                                daq.ToggleSwitch(
                                                id="spectral-units",
                                                value=True,
                                                size=60,
                                                ),
                                dcc.Markdown("$cm^{-1}$",mathjax=True),
                                dbc.Tooltip("toggle spectral units",target='spectral-units',placement='top',id='toggle-units-tooltip'),
                                ], #undo/toggle back-forth buttons
                                className ="d-grid gap-2 d-md-flex",
                                style={'padding':10}),
                    dcc.Graph(
                        id='current',
                        figure=current,
                    ),
                    ]
                    ),)
                ],)],style={'height':'50vh'},)