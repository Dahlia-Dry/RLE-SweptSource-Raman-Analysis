from collections import UserDict
from . import params
import json
import copy
from gui_components.attribute import Attribute

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
                    try:
                        n = float(data[key])
                    except:
                        self.data[key] = Attribute(data[key],'text',None,'custom')
                    else:
                        self.data[key] = Attribute(data[key],'numeric',None,'custom')
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
            if trait == 'value':
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
        elif key is not None:
            if trait == 'value':
                u=self.data[key].value
            elif trait =='datatype':
                u=self.data[key].datatype
            elif trait =='info':
                u=self.data[key].info
            elif trait =='editable':
                u=self.data[key].editable
        else:
            if trait == 'value':
                u={label:attr.value for label,attr in self.data.items()}
            elif trait == 'datatype':
                u={label:attr.datatype for label,attr in self.data.items()}
            elif trait == 'info':
                u={label:attr.info for label,attr in self.data.items()}
            elif trait =='editable':
                u={label:attr.editable for label,attr in self.data.items()}
        return u
    def to_json(self):
        outdata = self.fetch()
        for key in outdata:
            try:
                json.dumps(outdata[key])
            except: #not json serializable
                outdata[key]=str(outdata[key])
        return json.dumps(outdata)
    def to_markdown(self,exclude_editable=False):
        md = ""
        mdbuf = '      \n'
        for key in self.data.keys():
            if exclude_editable and self.data[key].editable:
                continue
            else:
                if self.data[key].visible:
                    md+= f"**{key}**: {self.data[key].value}{mdbuf}"
        return md
    def add_field(self,key,value):
        try:
            n = float(value)
        except:
            self.data[key] = Attribute(value,'text',None,'custom')
        else:
            self.data[key] = Attribute(value,'numeric',None,'custom')