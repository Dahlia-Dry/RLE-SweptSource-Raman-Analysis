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
fileparams = ['experiment_name','integration','repetitions','analytes']
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
    demo_visibility = 'visible'
else:
    upload_visibility = 'visible'
    demo_visibility = 'hidden'

filters = ['median filter','outlier filter']
normalizations = ['intra-normalization','inter-normalization']
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

combined_spectra= dcc.Tab(value='combined_spectra',label="Combined Spectra", 
                          children=[
                              html.Div([dcc.Markdown('#### Export Plot Data'),],
                                       className ="d-grid gap-2 d-md-flex",style={'padding':10}),
                              html.Div([dcc.Markdown('folder:'),
                                dcc.Input(id='combined-save-dir',type='text',value=params.working_directory[1:-1],style={'width':500})],className ="d-grid gap-2 d-md-flex",
                                style={'padding':10}),
                              html.Div([dcc.Markdown('filename:'),
                                dcc.Input(id='combined-filename',type='text',value='',style={'width':200}),
                                dcc.Markdown('.csv'),
                                dbc.Button(html.I(className="fa fa-download"),id='combined-export',n_clicks=0,color='secondary')],
                                className ="d-grid gap-2 d-md-flex",
                                style={'padding':10}),
                          ])

lod = dcc.Tab(value='lod',label="Limit of Detection", 
                          children=[
                              html.Div([
                                  dcc.Markdown("target analyte:"),
                                  dcc.Dropdown([], value=None, id='analytes-dropdown',style={'width':'50%'})
                              ],className ="d-grid gap-2 d-md-flex",style={'padding':10}),
                              html.Div([
                                  dcc.Markdown("target peak:"),
                                  dcc.Input(id='target-peak-lod',type='number',value=None),
                                  dbc.Tooltip("Click on combined spectra plot to select target peak",target='target-peak-lod',placement='bottom'),
                                  dcc.Markdown("$cm^{-1}$",mathjax=True)
                              ],className ="d-grid gap-2 d-md-flex",style={'padding':10}),
                              html.Div([dbc.Button("Compute LOD",id='do-lod',n_clicks=0,color='success')],
                                        className ="d-grid gap-2 d-md-flex",
                                        style={'padding':10}),
                              html.Div([dcc.Markdown("",id='lod-info')],style={'padding':10}),
                              html.Div([dcc.Markdown('#### Export Plot Data'),],
                                       className ="d-grid gap-2 d-md-flex",style={'padding':10}),
                              html.Div([dcc.Markdown('folder:'),
                                dcc.Input(id='lod-save-dir',type='text',value=params.working_directory[1:-1],style={'width':500})],className ="d-grid gap-2 d-md-flex",
                                style={'padding':10}),
                              html.Div([dcc.Markdown('filename:'),
                                dcc.Input(id='lod-filename',type='text',value='',style={'width':200}),
                                dcc.Markdown('.csv'),
                                dbc.Button(html.I(className="fa fa-download"),id='lod-export',n_clicks=0,color='secondary')],
                                className ="d-grid gap-2 d-md-flex",
                                style={'padding':10}),
                              ],)

stats = dcc.Tab(value='stats',label="Stats",
                            children = [
                                html.Div([
                                  dcc.Markdown("target peak:"),
                                  dcc.Input(id='target-peak-stat',type='number',value=None),
                                  dbc.Tooltip("Click on combined spectra plot to select target peak",target='target-peak-stat',placement='bottom'),
                                  dcc.Markdown("$cm^{-1}$",mathjax=True)
                                ],className ="d-grid gap-2 d-md-flex",style={'padding':10}),
                                html.Div([
                                dbc.Button("Show Mean vs Sample Size",id='mean-n',n_clicks=0,color='success'),
                                dbc.Button("Show Sigma vs Sample Size",id='std-n',n_clicks=0,color='success')
                                ],
                                className ="d-grid gap-2 d-md-flex",
                                style={'padding':10}),
                            ])

log = dcc.Tab(value='log',label='Log',
              children = [
                    dcc.Markdown(id='log',children='',style={"maxHeight": "400px", "overflow": "scroll"})])

custom_plot = dcc.Tab(value='custom_plot',label='Custom Plot',
                      children=[html.Div([
                                  dcc.Markdown("target peak:"),
                                  dcc.Input(id='target-peak-custom',type='number',value=None),
                                  dbc.Tooltip("Click on combined spectra plot to select target peak",target='target-peak-custom',placement='bottom'),
                                  dcc.Markdown("$cm^{-1}$",mathjax=True)
                              ],className ="d-grid gap-2 d-md-flex",style={'padding':10}),
                              html.Div([
                                  dcc.Markdown("x axis:"),
                                  dcc.Dropdown([], value=None, id='x-dropdown',style={'width':'50%'})
                                ],className ="d-grid gap-2 d-md-flex",style={'padding':10}),
                              html.Div([dbc.Button("Show Custom Plot",id='do-custom',n_clicks=0,color='success')],
                                        className ="d-grid gap-2 d-md-flex",
                                        style={'padding':10}),])

indiv_plot = dcc.Tab(value='indiv-plot',label='Plot',
                     children = html.Div([
                    dcc.Graph(
                        id='current',
                        figure=current,
                    ),
                    html.Div([
                                dbc.Button(html.I(className="fa fa-arrow-left"),id="back",n_clicks=0,color='primary'),
                                dbc.Button(html.I(className="fa fa-arrow-right"),id="forward",n_clicks=0,color='primary'),
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
                    ]))

content= html.Div(children=[
            #HIDDEN DATA
            html.Div(id='spectra',style={'display': 'none'}),
            html.Div(id='original-spectra',style={'display': 'none'}),
            html.Div(id='graphnum',children='0',style={'display':'none'}),
            html.Div(id='cached_plot_data',children='',style={'display':'none'}),
            #MODALS
            dbc.Modal(
                        [
                            dbc.ModalHeader(dbc.ModalTitle("Data export done")),
                            dbc.ModalBody("",id="save-body")
                        ],
                        id="save-modal",
                        is_open=False,),
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
                        dcc.Markdown('### Experiment Info',style={'padding':10}),
                        html.Div([
                            dcc.Markdown(children='Measurement Title:',style={'padding':10}),
                            dcc.Input(id='experiment-name',type='text',value=None),
                            ],
                            className ="d-grid gap-2 d-md-flex",
                            style={'padding':10}
                        ),
                        html.Div([
                        dcc.Markdown(children='Notes',style={'padding':10}),
                        dcc.Textarea(
                            id='notes',
                            value='',
                            style={'width':'75%'}
                        )],
                        className ="d-grid gap-2 d-md-flex",
                        style={'padding':10}),
                        dcc.Markdown('### Sample Info',style={'padding':10}),
                        html.Div(
                            [dcc.Markdown(children='Medium:',style={'padding':10}),
                            dcc.Input(id='medium',type='text',value=None)],
                            className ="d-grid gap-2 d-md-flex",
                            style={'padding':10}
                        ),
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
                        dcc.Markdown('### Custom fields',style={'padding':10}),                 
                        html.Div([
                        dash_table.DataTable(id='custom-fields',
                                                columns=[{'name': ['field','value'][i],
                                                            'id': ['field','value'][i]} for i in range(2)],
                                                data=[],
                                                row_deletable=True,
                                                editable=True,
                                                style_cell={'textAlign': 'center',
                                                            },
                                                style_cell_conditional=[
                                                    {'if': {'column_id': 'start'},
                                                    'width': '30%'}]
                                            )],style={'width':'1007px','padding':10}),                                     
                        dcc.Markdown('### Additional metadata',style={'padding':10}),
                        html.Div(
                            [dcc.Markdown(children='',style={'padding':10},id='metadata')],
                            className ="d-grid gap-2 d-md-flex",
                            style={'padding':10}
                        ),
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
            dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle("ERROR")),
                        dcc.Markdown(id='error-message',children='',style={'padding':10})
                    ],
                    id="error",
                    size="xl",
                    is_open=False,),
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
            dcc.Location(id='url', refresh=False),
            #DATA UPLOAD
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
            #LOAD DEMO DATA
            html.Div([dbc.Button("Load Peak Measurement Demo Data",id='load-peak-demo',n_clicks=0,color='primary',outline=True,style={'visibility':demo_visibility}),
                      dbc.Button("Load Wavelength Sweep Demo Data",id='load-sweep-demo',n_clicks=0,color='primary',outline=True,style={'visibility':demo_visibility})],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10,'justify-content':'left'}),
            #METADATA + SPECTRA TABLE
            html.H2('View+Edit Metadata',id='meta-header',style={'padding':10}),
            dbc.Tooltip("Click within the table to edit metadata of uploaded spectra.",target='meta-header',placement='bottom',id='meta-tooltip'),
            html.Div([dbc.Button("Select All",id='select-all',n_clicks=0,color='primary'),
                    dbc.Button("Deselect All",id='deselect-all',n_clicks=0,color='primary'),
                    dcc.Markdown("Add custom field:"),
                    dcc.Input(id='custom-field',type='text',value=None),
                    dcc.Dropdown(['numeric','text'], value='numeric', id='datatype-dropdown',style={'width':200}),
                    dbc.Button("+",id='add-col',n_clicks=0,color='primary',disabled=True)],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}),
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
                    page_size=15
                )],
                style={'padding':10}
            ),
            #ANALYZE+PLOT SPECTRA
            dbc.Row([
                dbc.Col(html.Div([
                    html.H2('Analyze Individual Spectra',id='indiv-spec',style={'padding':10}),
                    dbc.Tooltip("Click within the table to edit metadata of uploaded spectra.",target='indiv-spec',placement='bottom',id='indiv-tooltip'),
                    html.Div([dbc.Button("Reshape data",id='reshape',n_clicks=0,color='info'),
                    dbc.Button("Remove samples",id='remove-samples',n_clicks=0,color='info'),
                    dbc.Button("Remove wavelengths",id='remove-wavelengths',n_clicks=0,color='info')],
                    className ="d-grid gap-2 d-md-flex",
                    style={'padding':10}),
                    html.Div([dbc.Button("Revert metadata to original",id='revert-meta',n_clicks=0,color='primary'),
                            dbc.Button("Revert data to original",id='revert-data',n_clicks=0,color='primary')],
                            className ="d-grid gap-2 d-md-flex",
                            style={'padding':10}),
                    html.Div([dcc.Markdown('Export selected to folder:'),
                            dcc.Input(id='save-dir',type='text',value=params.working_directory[1:-1],style={'width':500}),
                            dbc.Button(html.I(className="fa fa-download fa-2x"),id='export',n_clicks=0,color='secondary')],
                            className ="d-grid gap-2 d-md-flex",
                            style={'padding':10}),
                    html.Div([dcc.Markdown("### Filter: "),
                              dcc.Dropdown(id='filter-selection',options=filters,value=None,style={'width':'75%'}),
                              dbc.Button("apply",id='filter-data',n_clicks=0,color='success')],
                              className ="d-grid gap-2 d-md-flex",
                              style={'padding':10}),
                    html.Div([dcc.Markdown("### Normalize: "),
                              dcc.Dropdown(id='norm-selection',options=normalizations,value=None,style={'width':'75%'}),
                              dbc.Button("apply",id='normalize-data',n_clicks=0,color='success')],
                              className ="d-grid gap-2 d-md-flex",
                              style={'padding':10}),
                ],
                ),),
                dbc.Col(
                    dcc.Tabs(id='indiv_plot_tabs',value='indiv-plot',children=[indiv_plot,log])
                    )
                ],),
            dbc.Row([
                dbc.Col([
                     html.H2('Analyze Multiple Spectra',id='multi-spec',style={'padding':10}),
                    dbc.Tooltip("Click within the table to edit metadata of uploaded spectra.",target='multi-spec',placement='bottom',id='multi-tooltip'),
                    dcc.Tabs(id="multi_plot_tabs", value='combined_spectra', children=[combined_spectra,stats,lod,custom_plot])
                ]),
                dbc.Col([
                    dcc.Graph(
                        id='working',
                        figure=working,
                    )]),
            ])],style={'height':'50vh'},)


