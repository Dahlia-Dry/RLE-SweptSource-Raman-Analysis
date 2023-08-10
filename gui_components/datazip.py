import zipfile
import os
from sys import platform
import json

def zip_data(measurement_data,power_data,meta_data,datalog=None,working_directory=None,name=None):
    #takes measurement_data and power_data as dicts of dicts indexed by spad address
    if name is None:
        experiment_name = meta_data[next(iter(meta_data))]['experiment_name']
    else:
        experiment_name=name
    with zipfile.ZipFile(experiment_name+'.zip', "w") as zf:
        for address in measurement_data: #and, trivially, also power data
            print('zipping ',address)
            mdf = experiment_name+"_"+str(meta_data[address]['spad_name'])+".spad"
            pdf = experiment_name+"_"+str(meta_data[address]['spad_name'])+".power"
            logfile = experiment_name+".log"
            mf = open(mdf,'w')
            pf = open(pdf,'w')
            #print([(x,type(x)) for x in meta_data[address].fetch().values()])
            json.dump(meta_data[address].fetch(),mf)
            print('dumped metadata')
            json.dump(meta_data[address].fetch(),pf)
            mf.write('\n')
            pf.write('\n')
            mf.close()
            pf.close()
            measurement_data[address].to_csv(mdf,mode='a',index_label='n_sample')
            power_data[address].to_csv(pdf,mode='a',index_label='n_sample')
            zf.write(mdf)
            zf.write(pdf)
            if datalog is not None:
                datalog.save(logfile)
                zf.write(logfile)
        zf.close()
    if working_directory is not None:
        if not os.path.exists(working_directory[1:-1]):
            os.mkdir(working_directory[1:-1])
        if platform == 'darwin':
            os.system("mv "+experiment_name+".zip " + 
                working_directory[:-1]+"/"+experiment_name+".zip"+working_directory[-1])
        else:
            os.system("move "+experiment_name+".zip " + 
                working_directory[:-1]+"/"+experiment_name+".zip"+working_directory[-1])

def save_data(measurement_data,power_data,meta_data,datalog=None,working_directory=None,name=None):
    #takes measurement_data and power_data as dicts of dicts indexed by spad address
    if name is None:
        experiment_name = meta_data[next(iter(meta_data))]['experiment_name']
    else:
        experiment_name=name
    for address in measurement_data: #and, trivially, also power data
        mdf = experiment_name+"_"+str(meta_data[address]['spad_name'])+".spad"
        pdf = experiment_name+"_"+str(meta_data[address]['spad_name'])+".power"
        logfile = experiment_name+".log"
        mf = open(mdf,'w')
        pf = open(pdf,'w')
        print([(x,type(x)) for x in meta_data[address].fetch().values()])
        json.dump(meta_data[address].fetch(),mf)
        print('dumped metadata')
        json.dump(meta_data[address].fetch(),pf)
        mf.write('\n')
        pf.write('\n')
        mf.close()
        pf.close()
        measurement_data[address].to_csv(mdf,mode='a',index_label='n_sample')
        power_data[address].to_csv(pdf,mode='a',index_label='n_sample')
        if datalog is not None:
            datalog.save(logfile)
    if working_directory is not None:
        if not os.path.exists(working_directory[1:-1]):
            os.mkdir(working_directory[1:-1])
        if platform == 'darwin':
            os.system("mv "+experiment_name+"_"+str(meta_data[address]['spad_name'])+".spad " + 
                working_directory[:-1]+"/"+experiment_name+"_"+str(meta_data[address]['spad_name'])+".spad"+working_directory[-1])
            os.system("mv "+experiment_name+"_"+str(meta_data[address]['spad_name'])+".power " + 
                working_directory[:-1]+"/"+experiment_name+"_"+str(meta_data[address]['spad_name'])+".power"+working_directory[-1])
            if datalog is not None:
                os.system("mv "+experiment_name+".log " + 
                    working_directory[:-1]+"/"+experiment_name+".log"+working_directory[-1])
        else:
            os.system("move "+experiment_name+"_"+str(meta_data[address]['spad_name'])+".spad " + 
                working_directory[:-1]+"/"+experiment_name+"_"+str(meta_data[address]['spad_name'])+".spad"+working_directory[-1])
            os.system("move "+experiment_name+"_"+str(meta_data[address]['spad_name'])+".power " + 
                working_directory[:-1]+"/"+experiment_name+"_"+str(meta_data[address]['spad_name'])+".power"+working_directory[-1])
            if datalog is not None:
                os.system("move "+experiment_name+".log " + 
                    working_directory[:-1]+"/"+experiment_name+".log"+working_directory[-1])