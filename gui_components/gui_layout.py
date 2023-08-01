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
fileparams = ['experiment_name','integration','repetitions','analytes']
working = go.Figure()
current=go.Figure()
data_progress=go.Figure()
power_meter=go.Figure()
power_meter.update_layout(title="Power Meter")
time_trace=go.Figure()
time_trace.update_layout(title="Current Measurement Progress")
colorlist = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52']
core_metadata = ['experiment_name','analytes','medium','target_analyte','notes','integration','repetitions','data_operations','spad_datafile','power_datafile']
datalog = ""
buffer='      \n'
default_metadata = Metadata()
init_measurement = dict(zip([ad for ad in params.spad_addresses.keys()],[{} for _ in params.spad_addresses.values()]))
if params.web_host:
    upload_visibility = 'hidden'
    demo_visibility = 'visible'
else:
    upload_visibility = 'visible'
    demo_visibility = 'hidden'
#_______________________________________________________________________________
header=html.Div([
                html.H1('Swept Source Raman Data Analysis Console',id='page-title',style={'padding':10}),
                dbc.Tooltip("For best viewing experience, please set browser zoom to 50%.",placement='bottom',target='page-title',id='page-title-tooltip'),
                html.A(html.Button([html.I(className="fa fa-github fa-5x"), ""],
                            style={'position':'fixed','right':100,'top':0,
                                    'border':'none','border-radius':12,'font-size':14,
                                    },id='github'),
                        href="https://github.com/Dahlia-Dry/RLE-Sweptsource-Raman-Analysis",
                        target='_blank'),
                dbc.Tooltip("View documentation",target='github',placement='bottom',id='github-tooltip'),
                html.Button([html.I(className="fa fa-cog fa-5x"), ""],
                             id="open-settings", n_clicks=0,
                             style={'position':'fixed','right':10,'top':0,
                                    'border':'none','border-radius':12,'font-size':14,
                                    }),
                dbc.Tooltip("Open settings",target='open-settings',placement='bottom',id='settings-tooltip')
                ],)

content= html.Div(children=[
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
            dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("View+Edit Metadata")),
                        dcc.Markdown('## Experiment Info',style={'padding':10}),
                        html.Div([
                        dash_table.DataTable(id='meta-experiment',
                                            columns=[{'name': ['field','value'][i],
                                                        'id': ['field','value'][i]} for i in range(2)],
                                            data=[],
                                            style_cell={'textAlign': 'center'})
                        ],style={'padding':10}),
                        dcc.Markdown('## Sample Info',style={'padding':10}),
                        html.Div([
                        dcc.Markdown(children='Analyte Name:',style={'padding':10}),
                        dcc.Input(id='analyte-name',type='text',value=None),
                        dcc.Markdown(children='Concentration:',style={'padding':10}),
                        dcc.Input(id='analyte-concentration',type='number',value=None),
                        dcc.Markdown(children='Units:',style={'padding':10}),
                        dcc.Input(id='analyte-units',type='text',value='ppm'),
                        html.Button([html.I(className="fa fa-plus"), ""],
                                id="add-analyte", n_clicks=0,
                                style={'font-size':30,
                                        "margin-left": "15px"}),
                        dbc.Tooltip("Add analyte",target='add-analyte',placement='top',id='add-analyte-tooltip'), 
                        ],
                        className ="d-grid gap-2 d-md-flex",
                        style={'padding':10}
                        ),
                        html.Div([
                        dash_table.DataTable(id='meta-analytes',
                                                columns=[{'name': ['name','concentration','units'][i],
                                                            'id': ['name','concentration','units'][i]} for i in range(3)],
                                                data=[],
                                                row_deletable=True,
                                                style_cell={'textAlign': 'center',
                                                            },
                                                style_cell_conditional=[
                                                    {'if': {'column_id': 'start'},
                                                    'width': '30%'}]
                                            )],style={'width':'1007px','padding':10}),

                        dbc.ModalFooter(
                            dbc.Button(
                                "Save and Close",
                                id="closemeta",
                                n_clicks=0,
                                className="ms-auto",
                            )
                        ),
                    ],
                    id="viewmeta",
                    size="xl",
                    is_open=False,),
            dcc.Location(id='url', refresh=False),
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
            dcc.Dropdown([], value=None, id='analytes-dropdown',style={'width':'50%'}),
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
                                dbc.Tooltip("toggle raw vs processed data",target='dataprocessing-type',placement='top',id='toggle-process-tooltip'),
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