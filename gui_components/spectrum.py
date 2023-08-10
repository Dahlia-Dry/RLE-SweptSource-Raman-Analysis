"""
Raman Spectrum Analysis Tools
Dahlia Dry, 2022 | dahlia23@mit.edu
Physical Optics and Electronics Group
This file defines an class Spectrum and associated helper functions which can be used to analyze Raman data
"""
#file imports
from .datalog import *
from .metadata import Metadata
from .datazip import *
#package imports
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import scipy.signal
import base64
import io
import json
from BaselineRemoval import BaselineRemoval
import os
import copy
import sigfig

class Spectrum(object):
    def __init__(self,data,power,metadict,ref=None,noise=None,log=None,verbose=True):
        self.data = data
        self.power=power
        if type(metadict) is not Metadata:
            self.meta = Metadata(metadict) #dict or str 
        else:
            self.meta=metadict
        if self.meta['spad_datafile'] is None:
            self.meta['spad_datafile'] = self.data.to_json() 
            self.meta['power_datafile'] = self.power.to_json()
        if type(self.data.values.flatten()[0])==str: 
            print('doing preprocessing')
            #if input is raw .spad file, save a copy to metadata then preprocess
            self.data = self.sum_spad_exposures()
            self.power= self.avg_power_exposures()
        #log = self.meta['data_operations']
        if log is not None:
            if type(log) is str:
                self.log= Processlog(log) #str
            else:
                self.log=log
        else:
            self.log=Processlog()
            self.log.add('**Spectrum for ' + self.meta['experiment_name']+ '**')
        if ref is not None:
            self.ref = ref
        else:
            self.ref = self.avg_samples(self.data)
        if noise is not None:
            self.noise = noise
        else:
            self.noise = self.noise_samples(self.data)
        self.verbose=verbose
    #methods for dealing with raw data
    def fetch_raw(self,data,wavelength=None,samplenumber=None):
        #return mxnxi cube, where m are wavelengths, n are sample numbers, and i are spad integrations (e.g. i=100 for 100s integration)
        if data=='spad':
            datafile = pd.DataFrame(json.loads(self.meta['spad_datafile']))
        elif data =='power':
            datafile = pd.DataFrame(json.loads(self.meta['power_datafile']))
        datafile.index = datafile.index.astype(int)
        datafile = datafile.sort_index(ascending=True)
        datafile.rename(columns={c:float(c) for c in datafile.columns},inplace=True)
        cube=[]
        for wl in datafile.columns: #iterate over wavelengths
            wl_buf=[]
            for sample in datafile[wl].to_list(): #iterate over samples
                wl_buf.append([float(x) for x in str(sample).split('~') if len(x)>0])
            cube.append(wl_buf)
        if wavelength is None and samplenumber is None:
            return np.array(cube)
        elif wavelength is None:
            index= self.meta['excitation_wavelengths'].index(float(wavelength))
            return np.array(cube)[index]
        else:
            index= samplenumber-1
            return np.array(cube)[:,index,:]
    def fetch_raw_data(self,wavelength=None,samplenumber=None):
        #convenience function
        return self.fetch_raw('spad',wavelength,samplenumber)
    def fetch_raw_power(self,wavelength=None,samplenumber=None):
        #convenience function
        return self.fetch_raw('power',wavelength,samplenumber)
    def cube_to_df(self,cube,metadata=None):
        if metadata is None:
            metadata = self.meta
        if type(cube) != np.ndarray:
            cube=np.array(cube)
        raw_data={}
        integration=metadata['integration']
        repetitions=metadata['repetitions']
        for i in range(len(metadata['excitation_wavelengths'])):
            wl=metadata['excitation_wavelengths'][i]
            raw_data[wl]=cube[i].flatten()
            raw_data[wl]=['~'.join([str(x) for x in raw_data[wl][n*integration:(n+1)*integration]]) for n in range(repetitions)]
        new_datafile = pd.DataFrame(raw_data)
        new_datafile.index.name = 'n_sample'
        new_datafile.index = np.arange(1,len(new_datafile)+1)
        return new_datafile
    #methods for processing .spad, .power data files
    def sum_spad_exposures(self):
        # initial preprocessing step for raw spad file
        # resulting self.data is nxm dataframe for n samples of m wavelengths
        df = self.data.copy()
        for i in range(len(df.values)):
            for j in range(len(df.values[0])):
                df.values[i][j]=sum([float(x) for x in str(df.values[i][j]).split('~') if len(x)>0])
        return df
    def avg_power_exposures(self):
        # initial preprocessing step for raw power file
        # resulting self.power is nxm dataframe for n samples of m wavelengths
        df=self.power.copy()
        for i in range(len(df.values)):
            for j in range(len(df.values[0])):
                df.values[i][j]=sigfig.round(np.mean([float(x) for x in str(df.values[i][j]).split('~') if len(x)>0]),6)
        return df
    #methods for computing ref and noise
    def avg_wavelengths(self,df):
        # resulting self.ref is nx1 array of average sample values
        avgs=[]
        for i in range(len(df.values)):
            avgs.append(np.mean(df.values[i]))
        return np.array(avgs).vstack()
    def avg_samples(self,df):
        # resulting self.ref is 1xm array of average wavelength avlues
        avgs = []
        for j in range(len(df.values[0])):
            avgs.append(np.mean([df.values[x][j] for x in range(len(df.values))]))
        return np.array(avgs)
    def noise_wavelengths(self,df):
        # resulting self.noise is nx1 array of sample sdevs
        sdevs=[]
        for i in range(len(df.values)):
            sdevs.append(np.std(df.values[i],ddof=1))
        return np.array(sdevs)
    def noise_samples(self,df):
        # resulting self.noise is 1xm array of wavelength sdevs
        sdevs = []
        for j in range(len(df.values[0])):
            sdevs.append(np.std([df.values[x][j] for x in range(len(df.values))],ddof=1))
        return np.array(sdevs)
    #methods for inplace processing (no changes to metadata)
    def power_normalize(self):
        # scale each (n,m) sample by the inverse of its power value normalized against the overall max power value
        maxpower = np.max(self.power.values.flatten())
        weights=self.data.copy()
        for i in range(len(self.data.values)):
            for j in range(len(self.data.values[0])):
                weights.values[i][j] = self.power.values[i][j]/maxpower
                self.data.values[i][j]=self.data.values[i][j]/weights.values[i][j] 
        self.log.add('performed power normalization')
        if self.verbose:
            self.log.add('weights: ' + '-'.join(["{:.4f}".format(x) for x in weights.values.flatten()]))
        self.ref = self.avg_samples(self.data)
        self.noise = self.noise_samples(self.data)         
    def medfilt_reps(self):
        for j in range(len(self.data.values[0])):
            self.data.values[:,j] = scipy.signal.medfilt(self.data.values[:,j]) #default kernel size 3, same as matlab
        self.ref = self.avg_samples(self.data)
        self.noise = self.noise_samples(self.data)
    def savitsky_golay(self,window=11,degree=0):
        for i in range(len(self.data['Spectrum'])):
            self.data['Spectrum'][i]=scipy.signal.savgol_filter(self.data['Spectrum'][i],window,degree)
        self.ref = np.mean(np.array(self.data['Spectrum']),axis=0) #across cols
        self.noise= np.std(np.array(self.data['Spectrum']),axis=0,ddof=1) #across cols
    def lieber_baseline(self,order,maxiter,cutoff_wl=None):
        if cutoff_wl is not None:
            pass #figure this out
        for i in range(len(self.data['Spectrum'])):
            baseObj=BaselineRemoval(self.data['Spectrum'][i])
            Modpoly_output=baseObj.ModPoly(degree=6,repitition=200)
            self.data['Spectrum'][i] = Modpoly_output
        self.ref = np.mean(np.array(self.data['Spectrum']),axis=0) #across cols
        self.noise= np.std(np.array(self.data['Spectrum']),axis=0,ddof=1) #across cols
    def subtract_spec(self,spec):
        self.ref = self.ref-spec.ref
        self.noise=np.sqrt((self.noise)**2 + (spec.noise)**2)
    def rescale(self,weight):
        self.ref=self.ref*weight
        self.noise=self.noise*weight
    #methods for processing that return new spectra (change to metadata)
    def rebin(self,new_repetitions,new_integration):
        new_repetitions=int(new_repetitions)
        new_integration=int(new_integration)
        #start from original data
        raw_datacube=self.fetch_raw_data()
        raw_powercube=self.fetch_raw_power()
        #convert to dict and flatten
        raw_data={}
        raw_power={}
        for i in range(len(self.meta['excitation_wavelengths'])):
            wl=self.meta['excitation_wavelengths'][i]
            raw_data[wl]=raw_datacube[i].flatten()
            raw_power[wl]=raw_powercube[i].flatten()
        raw_data[wl]=['~'.join([str(x) for x in raw_data[wl][n*new_integration:(n+1)*new_integration]]) for n in range(new_repetitions)]
        raw_power[wl]=['~'.join([str(x) for x in raw_power[wl][n*new_integration:(n+1)*new_integration]]) for n in range(new_repetitions)]
        # make new spectrum object with same metadata
        newmeta = Metadata(self.meta.to_json())
        newmeta['integration'] = new_integration
        newmeta['repetitions'] = new_repetitions
        newmeta['spad_datafile']=None
        newmeta['power_datafile']=None
        #print('newmeta:',newmeta.to_json())
        new_datafile = pd.DataFrame(raw_data)
        new_datafile.index.name = 'n_sample'
        new_datafile.index = np.arange(1,len(new_datafile)+1)
        new_powerfile = pd.DataFrame(raw_power)
        new_powerfile.index.name = 'n_sample'
        new_powerfile.index = np.arange(1,len(new_powerfile)+1)
        newlog = Processlog()
        newlog.add('**Spectrum for ' + newmeta['experiment_name']+ '**')
        newlog.add('rebinned to '+str(new_integration)+'x'+str(new_repetitions))
        return Spectrum(new_datafile,new_powerfile,newmeta,ref=None,noise=None,log=newlog)
    def medianfilter_raw(self):
        #run median filter over raw data (corresponding integration units in each sample)
        cube=self.fetch_raw_data()
        for m in range(len(cube)): #iterate over wavelengths
            for i in range(len(cube[0][0])):#iterate over integration units
                cube[m,:,i] = scipy.signal.medfilt(cube[m,:,i])
        datafile= self.cube_to_df(cube)
        powerfile = pd.DataFrame(json.loads(self.meta['power_datafile']))
        powerfile.index = powerfile.index.astype(int)
        powerfile = powerfile.sort_index(ascending=True)
        powerfile.rename(columns={c:float(c) for c in powerfile.columns},inplace=True)
         # make new spectrum object with same metadata
        newmeta = Metadata(self.meta.to_json())
        newmeta['spad_datafile']=None
        newmeta['power_datafile']=None
        self.log.add('- median filtered raw data')
        return Spectrum(datafile,powerfile,newmeta,ref=None,noise=None,log=self.log)
    def remove_samples(self,samplenumbers):
        datacube=self.fetch_raw_data()
        newdatacube=[[] for _ in range(len(datacube))]
        powercube=self.fetch_raw_power()
        newpowercube=[[] for _ in range(len(datacube))]
        print(datacube.shape)
        for m in range(len(datacube)): #iterate over wavelengths
            newdatacube[m] = np.delete(datacube[m],[int(x-1) for x in samplenumbers],axis=0)
            newpowercube[m] = np.delete(powercube[m],[int(x-1) for x in samplenumbers],axis=0)
        newdatacube=np.array(newdatacube)
        newpowercube=np.array(newpowercube)
        newmeta=Metadata(self.meta.to_json())
        newmeta['spad_datafile']=None
        newmeta['power_datafile']=None
        newmeta['repetitions'] = len(newdatacube[0])
        print(newdatacube.shape)
        datafile= self.cube_to_df(newdatacube,newmeta)
        print(datafile.head())
        powerfile= self.cube_to_df(newpowercube,newmeta)
        self.log.add('- removed samples '+','.join([str(x) for x in samplenumbers]))
        return Spectrum(datafile,powerfile,newmeta,ref=None,noise=None,log=self.log)
    def remove_wavelengths(self,wls):
        datacube=self.fetch_raw_data()
        newdatacube=[[] for _ in range(len(datacube))]
        powercube=self.fetch_raw_power()
        newpowercube=[[] for _ in range(len(datacube))]
        print(datacube.shape)
        newdatacube = np.delete(datacube,[self.meta['excitation_wavelengths'].index(wl) for wl in wls],axis=0)
        newpowercube= np.delete(powercube,[self.meta['excitation_wavelengths'].index(wl) for wl in wls],axis=0)
        newdatacube=np.array(newdatacube)
        newpowercube=np.array(newpowercube)
        newmeta=Metadata(self.meta.to_json())
        newmeta['spad_datafile']=None
        newmeta['power_datafile']=None
        newmeta['excitation_wavelengths'] = copy.deepcopy(self.meta['excitation_wavelengths'])
        for wl in wls:
            newmeta['excitation_wavelengths'].remove(wl)
        newmeta['excitation_ramanshifts'] = [(1/float(x)-1/float(newmeta['filter_wavelength']))*1e7 for x in newmeta['excitation_wavelengths']]
        print(newdatacube.shape)
        print(len(newmeta['excitation_wavelengths']))
        datafile= self.cube_to_df(newdatacube,newmeta)
        print(datafile.head())
        powerfile= self.cube_to_df(newpowercube,newmeta)
        self.log.add('- removed wavelengths '+','.join([str(x) for x in wls]))
        return Spectrum(datafile,powerfile,newmeta,ref=None,noise=None,log=self.log)
    #methods for plotting
    def plot(self,color=None,label=None,ydata='spad',xunits='ramanshift',show_err=False):
        if color is None:
            color='#636EFA' #plotly default blue
        if label is not None:
            if label in self.meta.fetch().keys():
                label = self.meta[label]
        if xunits == 'wavelength':
            xaxis='Wavelength (nm)'
            xdata = self.meta['excitation_wavelengths']
        else:
            xaxis ='Raman Shift (cm^-1)'
            xdata = self.meta['excitation_ramanshifts']
        if ydata=='spad':
            ydata = self.ref
            y_err= self.noise
            yaxis_title='SPAD Count'
        elif ydata=='power':
            ydata=self.avg_samples(self.power)
            y_err = self.noise_samples(self.power)
            yaxis_title='Powermeter Reading (W)'
        else:
            raise Exception("ydata must be either 'spad' or 'power'")
        fig=go.Figure()
        if show_err:
            fig.add_trace(go.Scatter(x=xdata,y=ydata,mode='lines+markers',
                                line=dict(color=color),
                                name=label,
                                error_y=dict(
                                            type='data',
                                            array=y_err,
                                            visible=True)
                                    ))
        else:
            fig.add_trace(go.Scatter(x=xdata,y=ydata,mode='lines+markers',
                                line=dict(color=color),name=label))
        fig.update_layout(title=label,xaxis_title=xaxis,yaxis_title=yaxis_title)
        return fig
    def plot_samples(self,color=None,label=None,ydata='spad'):
        if color is None:
            color='#636EFA' #plotly default blue
        if label is not None:
            if label in self.meta.fetch().keys():
                label = self.meta[label]
        colorlist = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A', '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52']
        xaxis='Sample number'
        xdata = np.arange(1,len(self.data)+1)
        fig=go.Figure()
        if ydata =='spad':
            yaxis_title = 'SPAD Count'
            wavelengths = list(set(self.meta['excitation_wavelengths']))
            yvals = self.data[wavelengths[0]].values.flatten()
            fig.add_trace(go.Scatter(x=xdata,y=yvals,mode='lines+markers',
                    line=dict(color=color),name=wavelengths[0]))
            if len(wavelengths)>1:
                i=1
                for wl in wavelengths[1:]:
                    yvals = self.data[wl].values.flatten()
                    fig.add_trace(go.Scatter(x=xdata,y=yvals,mode='lines+markers',
                        line=dict(color=colorlist[i]),name=wl))
                    i+=1
        elif ydata=='power':
            yaxis_title = 'Powermeter Reading (W)'
            wavelengths = list(set(self.meta['excitation_wavelengths']))
            yvals = self.power[wavelengths[0]].values.flatten()
            fig.add_trace(go.Scatter(x=xdata,y=yvals,mode='lines+markers',
                    line=dict(color=color),name=wavelengths[0]))
            if len(wavelengths)>1:
                i=1
                for wl in wavelengths[1:]:
                    yvals = self.power[wl].values.flatten()
                    fig.add_trace(go.Scatter(x=xdata,y=yvals,mode='lines+markers',
                        line=dict(color=colorlist[i]),name=wl))
                    i+=1
        else:
            raise Exception("ydata must be either 'spad' or 'power'")
        fig.update_layout(title=label,xaxis_title=xaxis,yaxis_title=yaxis_title)
        return fig
    def plot_raw(self,color=None,label=None,ydata='spad'):
        if color is None:
            color='#636EFA'
        if label is not None:
            if label in self.meta.fetch().keys():
                label = self.meta[label]
        if ydata == 'spad':
            raw_data = self.fetch_raw_data().flatten()
            yaxis_title='SPAD Count'
        elif ydata =='power':
            raw_data = self.fetch_raw_power().flatten()
            yaxis_title = 'Powermeter Reading'
        else:
            raise Exception("ydata must be either 'spad' or 'power'")
        x_data = np.arange(1,len(raw_data)+1)
        fig=go.Figure()
        fig.add_trace(go.Scatter(x=x_data,y=raw_data,mode='lines',
                                line=dict(color=color)))
        fig.update_layout(title=label,xaxis_title='Time (s)',yaxis_title=yaxis_title)
        return fig

    #save data
    def save(self,folder=None):
        datacube = self.fetch_raw_data()
        powercube = self.fetch_raw_power()
        datadict={self.meta['spad_name']:self.cube_to_df(datacube)}
        powerdict={self.meta['spad_name']:self.cube_to_df(powercube)}
        newmeta = copy.deepcopy(self.meta)
        newmeta['spad_datafile'] = None
        newmeta['power_datafile'] = None
        newmeta['data_operations'] = str(self.log)
        metadict= {self.meta['spad_name']:newmeta}
        self.log.add('saved to zip')
        save_data(datadict,powerdict,metadict,working_directory=folder)

def inter_normalize(spectra):
    avg_powers = [np.mean(s.avg_samples(s.power)) for s in spectra]
    weights = [x/max(avg_powers) for x in avg_powers]
    print('inter-normalize weights:',weights)
    for i in range(len(spectra)):
        spectra[i].rescale(1/weights[i])
        spectra[i].log.add('performed inter-normalization: scaled by {}'.format(1/weights[i]))

def batch_process_folder(dirname,fname=None):
    spec_objs = []
    list_of_names=[x for x in os.listdir(dirname) if (x[0] != '.' and not x.endswith('.log'))]
    paths = [x.split('.')[0] for x in list_of_names]
    contentdict = {key:{'spec':None,'power':None} for key in list(set(paths))}
    for i in range(len(list_of_names)):
        if list_of_names[i].endswith('.spad'):
            contentdict[list_of_names[i].split('.')[0]]['spec']=open(os.path.join(dirname,list_of_names[i]))
        elif list_of_names[i].endswith('.power'):
            contentdict[list_of_names[i].split('.')[0]]['power']=open(os.path.join(dirname,list_of_names[i]))
        #else:
            #raise Exception('unrecognized file extension:'+list_of_names[i])
    for key in list(contentdict.keys()):
        if None in contentdict[key]:
            raise Exception(key + 'lacks either a spec file or a power file')
        else:
            spec_upload =sweptsource_spec_from_upload(contentdict[key],key,decode=False)
            if fname is not None and spec_upload.meta['experiment_name'] == fname:
                return spec_upload
            spec_objs.append(spec_upload)
    return spec_objs

def sweptsource_spec_from_upload(contents,filename,decode=True):
    if decode:
        s_content_type,s_content_string=contents['spec'].split(',')
        s_decoded = base64.b64decode(s_content_string)
        p_content_type,p_content_string=contents['power'].split(',')
        p_decoded=base64.b64decode(p_content_string)
        fspec = io.StringIO(s_decoded.decode('utf-8'))
        fpower = io.StringIO(p_decoded.decode('utf-8'))
    else:
        fspec = contents['spec']
        fpower= contents['power']
    upload_meta = fspec.readline()
    fpower.readline()
    upload_spec = pd.read_csv(fspec,index_col='n_sample')
    upload_power=pd.read_csv(fpower,index_col='n_sample')
    upload_spec.rename(columns={col:float(col) for col in upload_spec.columns},inplace=True)
    upload_power.rename(columns={col:float(col) for col in upload_power.columns},inplace=True)
    newspec= Spectrum(upload_spec,upload_power,upload_meta)
    return copy.deepcopy(newspec)

def batch_process_uploads(list_of_contents,list_of_names,list_of_dates):
    if list_of_contents is None or list_of_contents =='null':
        return []
    spec_objs = []
    paths = [x.split('.')[0] for x in list_of_names]
    contentdict = {key:{'spec':None,'power':None} for key in list(set(paths))}
    for i in range(len(list_of_names)):
        if list_of_names[i].endswith('.spad'):
            contentdict[list_of_names[i].split('.')[0]]['spec']=list_of_contents[i]
        elif list_of_names[i].endswith('.power'):
            contentdict[list_of_names[i].split('.')[0]]['power']=list_of_contents[i]
    for key in list(contentdict.keys()):
        print('KEY',key)
        if None in contentdict[key].values():
            continue
        else:
            spec_upload =sweptsource_spec_from_upload(contentdict[key],key)
            spec_upload.meta['filename'] = key
            spec_objs.append(spec_upload)
    return spec_objs

def spec_from_json(json_spectra):
    spectra_raw= json.loads(json_spectra)
    spectra = []
    buf=[]
    for s in spectra_raw:
        data = pd.DataFrame(json.loads(s['data']))
        data.index = data.index.astype(int)
        data = data.sort_index(ascending=True)
        data.rename(columns={c:float(c) for c in data.columns},inplace=True)
        power = pd.DataFrame(json.loads(s['power']))
        power.index = power.index.astype(int)
        power = power.sort_index(ascending=True)
        power.rename(columns={c:float(c) for c in power.columns},inplace=True)
        new_spec=Spectrum(data,
                            power,
                            json.loads(s['meta']),
                            np.array(s['ref']),
                            np.array(s['noise']),
                            s['log'])
        spectra.append(copy.deepcopy(new_spec))
    return spectra

def jsonify(spectra):
    if spectra is None:
        return json.dumps(None)
    dictlist = []
    buf=[]
    for spec in spectra: #spectra is list of spectrum objects of length n, where n is number of active spads
        objdict=  {'data':spec.data.to_json(),
                    'power':spec.power.to_json(),
                    'meta':spec.meta.to_json(),
                    'ref':spec.ref.tolist(),
                    'noise':spec.noise.tolist(),
                    'log':str(spec.log)}
        dictlist.append(objdict)
    return json.dumps(dictlist)
