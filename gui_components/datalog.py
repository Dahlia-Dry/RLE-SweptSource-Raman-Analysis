import pandas as pd
import datetime

class Datalog(object):
    def __init__(self,data=None):
        if data is not None:
            self.data=data
        else:
            self.data=''
    def add(self,newlog):
        buffer='      \n'
        self.data=self.data +'&ensp; '+ self.timestamp() + newlog + buffer      
    def timestamp(self):
        return str(pd.to_datetime(datetime.datetime.now()).round('1s'))+ '>> '
    def __str__(self):
        return self.data 
    def save(self,filename):
        f= open(filename,'w')
        f.write(self.__str__().replace('&ensp; ',''))
        f.close()

class Processlog(Datalog):
    def __init__(self,data=None):
        if data is None:
            self.data=''
        elif type(data) is list and all([type(d)==Processlog for d in data]):
            self.data= '\n'.join([str(d) + \
            '\n________________________________________________________________' for d in data])
        else:
            self.data=data
    def add(self,newlog):
        buffer='      \n'
        if type(newlog) == pd.DataFrame:
            md = [x.strip('|') for x in newlog.to_markdown().split('\n')]
            del(md[1])
            for m in md:
                self.data += '&ensp; '+m + buffer
        else:
            self.data=self.data +'&ensp; '+ newlog + buffer
    def replace(self,old,new):
        self.data=self.data.replace(old,new)
