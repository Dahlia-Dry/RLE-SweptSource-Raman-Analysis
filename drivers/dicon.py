# -*- coding: utf-8  -*-
"""
Driver for DiCon FiberOptics MEMS 1xN Optical Switch Module on RS232 communication
"""

from serial import Serial
import re

class DiConOpticalSwitch():

    def __init__(self, port='COM1', timeout=1.0, verbose=True):
        self.port = port
        self.timeout = timeout
        self.verbose = verbose
        self._channel = 0

        self._ser = Serial(port, baudrate=115200, timeout=1.0)

        # Read number of channels from module
        self._ser.reset_input_buffer()
        self._ser.write(b'CF?\r')
        self._ser.read() # dummy read the newline
        reply = self._ser.readline().decode("utf-8")
        try:
            self._channel_max = int(re.split(',', reply)[1])
        except Exception as ex:
            self._channel_max = 16
            print(ex)
            print(reply)

        # Park switch
        self.park_switch()

    def identify(self):
        self._ser.reset_input_buffer()
        self._ser.write(b'ID?\r')
        self._ser.read() # dummy read the newline
        reply = self._ser.readline()
        print(reply)

        return len(reply)

    def set_channel(self, new_channel):
        if new_channel >=0 and new_channel <= self._channel_max:
            self._channel = new_channel
            self._ser.reset_input_buffer()
            self._ser.write(bytes('I1 {}\r'.format(new_channel), 'utf-8'))
        else:
            print('DiConOpticalSwitch: Invalid channel')

    def get_channel(self):
        """ Returns current channel setting of the switch"""
        self._ser.reset_input_buffer()
        self._ser.write(b'I1?\r')
        self._ser.read() # dummy read the newline
        resp = self._ser.readline()
        if self.verbose:
            print(resp)

        # Parse response
        ch = re.match(r"\d+", resp.decode('utf-8'))
        if ch is not None:
            return int(ch[0])
        else:
            return -1

    def park_switch(self):
        # Park switch
        self._ser.write(b'PK\r')

    def close(self):
        self.park_switch()

        # Close serial port
        self._ser.close()
