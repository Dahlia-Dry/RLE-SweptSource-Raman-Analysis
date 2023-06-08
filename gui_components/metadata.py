from collections import UserDict
from . import params
import json
import copy

class Metadata(object):
    """
    data is dict or string representation of dict (json serializable)
    """
    def __init__(self,data=None):
        self.data = copy.deepcopy(params.meta)
        if data is not None:
            if type(data) == str:
                data = json.loads(data)
            for key in data:
                try:
                    if type(data[key]) != self.data[key].datatype:
                        if self.data[key].datatype is list and type(data[key]) is str:
                            data[key] = [x for x in data[key].strip('[').strip(']').split(',')]
                    self.data[key].value=data[key]
                except:
                    #raise KeyError('key '+key+ 'not in programmed metadata params. Edit params.py to add this key.')
                    print('key '+key +' not in params')
    def __setitem__(self,a,v):
        try:
            self.data[a].value=v 
        except: #new metadata value
            raise KeyError('key '+a+ 'not in programmed metadata params. Edit params.py to add this key.')
    def __getitem__(self,key):
        if key not in self.data.keys():
            raise KeyError('key '+key+ 'not in programmed metadata params. Edit params.py to add this key.')
        else:
            return self.data[key].value
    def fetch(self,key=None,cat=None,trait='value'):
        if cat is not None:
            if cat not in [x.category for x in self.data.values()]:
                raise KeyError('category '+cat+ 'not in programmed metadata params. Edit params.py to add this category.')
            elif trait == 'value':
                u={
                    label:attr.value for label,attr in self.data.items() if attr.category==cat
                }
            elif trait =='datatype':
                u={
                    label:attr.datatype for label,attr in self.data.items() if attr.category==cat
                }
            elif trait =='info':
                u={
                    label:attr.info for label,attr in self.data.items() if attr.category==cat
                }
            else:
                raise KeyError('trait '+trait+ 'not in programmed metadata params. Edit params.py to add this trait.')
        elif key is not None:
            if key not in self.data.keys():
                raise KeyError('key '+key+ 'not in programmed metadata params. Edit params.py to add this key.')
            elif trait == 'value':
                u=self.data[key].value
            elif trait =='datatype':
                u=self.data[key].datatype
            elif trait =='info':
                u=self.data[key].info
            elif trait =='editable':
                u=self.data[key].editable
            else:
                raise KeyError('trait '+trait+ 'not in programmed metadata params. Edit params.py to add this trait.')
        else:
            if trait == 'value':
                u={label:attr.value for label,attr in self.data.items()}
            elif trait == 'datatype':
                u={label:attr.datatype for label,attr in self.data.items()}
            elif trait == 'info':
                u={label:attr.info for label,attr in self.data.items()}
            elif trait =='editable':
                u={label:attr.editable for label,attr in self.data.items()}
            else:
                raise KeyError('trait '+trait+ 'not in programmed metadata params. Edit params.py to add this trait.')
        return u
    def to_json(self):
        outdata = self.fetch()
        for key in outdata:
            try:
                json.dumps(outdata[key])
            except: #not json serializable
                outdata[key]=str(outdata[key])
        return json.dumps(outdata)