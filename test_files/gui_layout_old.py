"""
Swept Source Raman GUI
Dahlia Dry, 2022 | dahlia23@mit.edu
Physical Optics and Electronics Group
"""
#file imports
from . import params
#package imports
from dash import dcc,html,dash_table
import plotly.graph_objects as go
import dash_bootstrap_components as dbc
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
fileparams = ['Name','Nspec','Time(s)','Label','Concentration']
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
#_______________________________________________________________________________
tab_1= html.Div(children=[
            dbc.Row([
                dbc.Col(html.Div([
                    #CONTROL PANEL
                    dcc.Markdown(children='## Control Panel',style={'padding':10}),
                    html.Div([
                    dcc.Markdown(children='Experiment Name:',style={'padding':10}),
                    dcc.Input(id='experiment-name'.format('text'),type='text'),
                    dcc.Markdown(children='Concentration:',style={'padding':10}),
                    dcc.Input(id='concentration'.format('text'),type='text')],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}
                    ),
                    #Wavelength Sweep
                    dcc.Markdown(children='### Wavelength Sweep',style={'padding':10}),
                    html.Div([
                    dcc.Markdown(children='Integration Time:',style={'padding':10}),
                    dcc.Input(id='integration'.format('number'),type='number'),
                    dcc.Markdown(children='Number of Exposures/Wavelength:',style={'padding':10}),
                    dcc.Input(id='nexp'.format('number'),type='number')],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}
                    ),
                    html.Div([
                    dcc.Markdown(children='lambda start:',style={'padding':10}),
                    dcc.Input(id='wl-start'.format('number'),type='number'),
                    html.Span(children="=  cm^-1",id='raman-start',style={'font-style':"italic"}),
                    html.Span(children='lambda end:',style={'padding':10}),
                    dcc.Input(id='wl-end'.format('number'),type='number'),
                    html.Span(children="=  cm^-1",id='raman-end',style={'font-style':"italic"}),
                    dcc.Markdown(children='lambda step:',style={'padding':10}),
                    dcc.Input(id='wl-step'.format('number'),type='number'),
                    dbc.Tooltip("",target='wl-step',placement='right',id='wl-step-tooltip')],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}
                    ),
                    html.Div([dbc.Button(children="Connect Instruments",id='connection',n_clicks=0,color='success',outline=False),
                              dbc.Button(children="Shutdown Instruments",id='shutdown',n_clicks=0,color='danger'),
                              dbc.Button(children="Begin Measurement",id='measure',n_clicks=0,color='primary'),
                              dbc.Tooltip("",target='measure',placement='bottom'),
                              dcc.Upload(dbc.Button(children="Load .exp File",n_clicks=0,color='info'),id='preset'),
                              dbc.Button(children="Pause",id='pause',n_clicks=0,color='warning',outline=False)],
                              className ="d-grid gap-2 d-md-flex",
                              style={'padding':10}),
                    #HIDDEN DATA
                    html.Div(id='collected-spectra',style={'display': 'none'}),
                    html.Div(id='collected-graphnum',children='0',style={'display':'none'}),
                    #html.Div(id="exposing",children="False",style={'display':'none'}),
                    html.Div(id="relay_a",children="True",style={'display':'none'}),
                    html.Div(id="relay_b",children="False",style={'display':'none'}),
                    html.Div(id="current-wl",children="-1",style={'display':'none'}),
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
                        is_open=False,
                    ),
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
                    dcc.Interval(id="progress-interval", n_intervals=0, interval=params.prog_interval),
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
                    ),
                    html.Div([
                                dbc.Button("<-",id="back",n_clicks=0,color='primary'),
                                dbc.Button("->",id="forward",n_clicks=0,color='primary')], #toggle back-forth buttons
                                className ="d-grid gap-2 d-md-flex",
                                style={'padding':10}),
                    ]
                    ),)
                ],)],style={'height':'50vh'},)
tab_2= html.Div(children=[
            html.Div(dcc.Upload(
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
                    'margin': '10px'
                },
                # Allow multiple files to be uploaded
                multiple=True
            )),
            html.Div(
                children= [
                dcc.Store(id='diff-store'),
                dash_table.DataTable(
                    id='file-list',
                    columns=([{'id':p,'name':p} for p in fileparams]),
                    data=[{'Name':'',
                        'Nspec':0,
                        'Time(s)':0,
                        'Label':'',
                        'Concentration':''}],
                    style_data_conditional=[],
                    row_selectable='multi',
                    row_deletable=True,
                    editable=True
                )]
            ),
            html.Div(id='spectra',style={'display': 'none'}),
            html.Div(id='graphnum',children='0',style={'display':'none'}),
            dbc.Row([
                dbc.Col(html.Div([
                    dcc.Graph(
                        id='working',
                        figure=working,
                    ),
                    dcc.Markdown(id='dialogue',children=''),
                    html.Div([dbc.Button("Do Lieber Fit",id='lieber',n_clicks=0,color='success'),
                              dbc.Tooltip("Method for background removal",target='lieber',placement='bottom'),
                              dbc.Button("Do Batch Subtraction",id='subtract',n_clicks=0,color='success'),
                              dbc.Tooltip("Toggle to spectrum you wish to subtract, then press this button",target='subtract',placement='bottom'),
                              dbc.Button("Do Max Peak Normalizaton",id='norm',n_clicks=0,color='success'),
                              dbc.Tooltip("Click max peak on bottom right plot, then press this button",target='norm',placement='bottom'),],
                              className ="d-grid gap-2 d-md-flex",
                              style={'padding':10}),
                    html.Div([dbc.Button("Show Limit of Detection",id='lod',n_clicks=0,color='info'),
                              dbc.Tooltip("Toggle LOD:Select analyte peak in top left plot, then press this button ",target='lod',placement='bottom'),
                              dbc.Button("Show All Spectra",id='all-spec',n_clicks=0,color='info'),
                              dbc.Tooltip("Toggle show all spectra",target='all-spec',placement='bottom'),],
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
                                dbc.Button("undo",id="undo",n_clicks=0,color='primary')], #undo/toggle back-forth buttons
                                className ="d-grid gap-2 d-md-flex",
                                style={'padding':10}),
                    dcc.Graph(
                        id='current',
                        figure=current,
                    ),
                    ]
                    ),)
                ],)],style={'height':'50vh'},)