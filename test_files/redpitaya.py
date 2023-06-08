import redpitaya_scpi as scpi
class Redpitaya(object):
    def __init__(self,scpi_address):
        self.scpi_address = scpi_address #ip address for scpi server
        #time scale/length of buffer according to decimation
        self.timescales={1:131.072e-6,8:1.049e-3,64:8.389e-3,1024:134.218e-3,
                        8192:1.074,65536:8.59}
    def analog_read(self,decimation,integration_time):
        """read 1 buf worth of analog data from specified pin
            for info on decimation see redpitaya docs"""
        pass
