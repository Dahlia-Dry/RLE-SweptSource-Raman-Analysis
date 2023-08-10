class Attribute(object):
    def __init__(self,value,datatype,info,category,editable=True,visible=True):
        self.value=value
        self.datatype=datatype
        self.info=info
        self.category=category
        self.editable=editable
        self.visible=visible