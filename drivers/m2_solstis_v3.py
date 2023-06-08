# -*- coding: utf-8 -*-
"""
Created on Thu Nov 19 20:57:24 2020
added lock wavelength WARNING: locking triggers tuning and setting of a new wavelength target by SOLSTIS

@author: User
"""


# -*- coding: utf-8  -*-
# Copyright 2020 Nili Persits and Jaehwan Kim and Zheng Li
"""
Driver for M2 Solstis Tunable Laser

This driver talks to ICE BLOC the controller for the Solstis laser through TCP/IP sockets

Usage Example:
    from instrumental.drivers.lasers.solstis import M2_Solstis
    # laser = M2_Solstis()
    laser.set_wavelength(wavelength=850.0)
    wavelength =  laser.poll_wavelength()
    laser.close()
"""
# from . import Laser

import socket
import json
from time import sleep
import sys

# from ... import Q_

_INST_CLASSES = ['M2_Solstis']

class M2_Solstis:
    """ A M2 Solstis tunable laser.

    _INST_PARAMS:
        host_address : Address to control computer
        port : Port
        client_ip : client ip setting in ICE BLOC
    """
    # _INST_PARAMS_ = ['host_address', 'port', 'client_ip']
    # _INST_PARAMS_ = []

    def __init__(self):
        """ Initializes socket communications with laser controller and sends start_link command
        """
        # Internal parameters
        self.timeout = 1.0
        self.wavelength_tolerance = 0.01  #nm
        self.poll_timeout = 30
        host_address='localhost'
        port=9001
        client_ip='192.168.1.100'
        self.latest_reply = None
        self.poll_status = -1

        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.s.settimeout(self.timeout) # sets timeout
            # self.s.connect((self._paramset['host_address'], self._paramset['port']))
            self.s.connect((host_address, port))
        except:
            # print('M2_Solstis: cannot open socket connection to {}:{}'.format(self._paramset['host_address'], self._paramset['port']))
            print('M2_Solstis: cannot open socket connection to {}:{}'.format(host_address, port))
            print("Unexpected error:", sys.exc_info()[0])
            self.s = None

            raise RuntimeError('M2_Solstis: cannot open socket connection to {}:{}'.format(host_address, port))
        else:
            # send start link command and parse return
            json_startlink = {
                'message': {
                    'transmission_id': [1],
                    'op': 'start_link',
                    'parameters': {
                        'ip_address': client_ip
                    }
                }
            }

            command_startlink = json.dumps(json_startlink)
            self.s.sendall(bytes(command_startlink,'utf-8'))

            json_reply = json.loads(self.s.recv(1024))
            if json_reply['message']['transmission_id'][0] == 1 and json_reply['message']['parameters']['status'] == 'ok':
                # print('M2_Solstis: successfully started link to {}:{} as {}'.format(self._paramset['host_address'], self._paramset['port'], self._paramset['client_id']))
                print('M2_Solstis: successfully started link to {}:{} as {}'.format(host_address, port, client_ip))
            else:
                # print('M2_Solstis: failed to start link to {}:{} as {}'.format(self._paramset['host_address'], self._paramset['port'], self._paramset['client_id']))
                print('M2_Solstis: failed to start link to {}:{} as {}'.format(host_address, port, client_ip))
                print('M2_Solstis: reply from controller {}'.format(json_reply))

                self.s.close()
                self.s = None

    def one_shot(self):
        """ Runs one-shot routine for beam alignment
        First moves the laser's center wavelength to 780 nm followed by one-shot command
        Returns
        -------
        status: str
            returns status of the one shot command
        """
        #self.set_wavelength(wavelength)

        if self.s is not None:
            transID=97
            json_oneshot = {
                'message': {
                    'transmission_id': [transID],
                    'op': 'beam_alignment',
                    'parameters': {
                        'mode': [4]
                    }
                }
            }
            self.s.sendall(bytes(json.dumps(json_oneshot),'utf-8'))
            sleep(1.0)
            json_reply=json.loads(self.s.recv(1024))
            self.latest_reply = json_reply
            if json_reply['message']['parameters']['status'] == 0:
                print('M2_Solstis: one shot beam alignment successful')

                return 'Success'
            elif json_reply['message']['parameters']['status'] == 1:
                print('M2_Solstis: one shot beam alignment failed')

                return 'Failed'
            else:
                print('software idle')

                return 'fubar'
        else:
            print('M2_Solstis: socket not connected')
            return 'Failed'

    def poll_wavelength(self):
        """ Returns wavelength from wavemeter in nanometers

        Returns
        -------
        wavelength : Q_ class
            returns current measured wavelength if successful or Q 0.0 otherwise

        status id
        0: idle
        1: no wavemeter
        2: tuning
        3: maintaining
        9: no connection
        """



        wavelength =  0.0

        if self.s is not None:
            transID=99
            json_getwave = {
                'message': {
                    'transmission_id': [transID],
                    'op': 'poll_wave_m'
                }
            }
            self.s.sendall(bytes(json.dumps(json_getwave),'utf-8'))
            sleep(2.0)
            json_reply=json.loads(self.s.recv(1024))
            if (json_reply['message']['transmission_id'] == [transID]) and (json_reply['message']['parameters']['status'] in [[0], [2], [3]]):
                wavelength = json_reply['message']['parameters']['current_wavelength'][0]
                # print('M2_Solstis: Current wavelength from wavemeter is {}'.format(wavelength))

                if json_reply['message']['parameters']['status'] ==[0]:
                    # print('M2_Solstis: idle: software inactive!')
                    self.poll_status=0

                if json_reply['message']['parameters']['status'] ==[2]:
                    # print('M2_Solstis: Tuning laser wavelength')
                    self.poll_status=2

                elif json_reply['message']['parameters']['status'] ==[3]:
                    # print('M2_Solstis: maintaining target wavelength at {}'.format(wavelength))
                    self.poll_status=3

            else:
                # print('M2_Solstis: failed poll wavelength, no wavemeter')
                # print('M2_Solstis: reply from controller {}'.format(json_reply))
                self.poll_status=1

                wavelength =  0.0
        else:
            # print('M2_Solstis: socket not connected')
            self.poll_status=9
            wavelength =  0.0


        self.latest_reply = json_reply
        return wavelength

    def set_wavelength(self, wavelength):
        """ Sends set wavelength command and checks reply

        Parameters
        ----------
        wavelength : in nm
            target wavelength

        Returns
        -------
        error : int or str
            Zero is returned if wavelength was set correctly.

            Otherwise, error string returned by the laser is returned.

            open question about how the tuning is done

            0 : sussessfully sent
            1 : not sent
            9 : socket error

        """
        if self.s is None:
            # print('M2_Solstis: socket not connected')
            return 9
        else:
            transID=91
            json_setwave = {
                'message': {
                    'transmission_id': [transID],
                    'op': 'set_wave_m',
                    'parameters': {
                        'wavelength': [wavelength]
                    }
                }
            }

            self.s.sendall(bytes(json.dumps(json_setwave),'utf-8'))
            sleep(1.0)
            json_reply=json.loads(self.s.recv(1024))
            self.latest_reply = json_reply
            if json_reply['message']['transmission_id'] == [transID] and json_reply['message']['parameters']['status'] == [0]:
                # print('M2_Solstis: started tuning to {}'.format(wavelength))

                # for i in range(self.poll_timeout):
                #     current_wavelength = self.poll_wavelength()
                #     if self.latest_reply['message']['parameters']['status'] in [[3]]:
                #         print('M2_Solstis: finished tuning to {}'.format(current_wavelength))
                #         return 0

                # print('M2_Solstis: current wavelength {}'.format(current_wavelength))
                return 0
            else:
                # print('M2_Solstis: command not sent')
                # print('M2_Solstis: reply from controller {}'.format(json_reply))

                return 1

    def stop(self):
        """ this operation stops the tuning operation in progress


        Returns
        -------
        status : str
            Zero is returned if stop was successful
            1 if there is no link to the wavemeter
            9 : socket error
        wavelength the current and last wavelength

        """
        if self.s is None:
            # print('M2_Solstis: socket not connected')
            return 9
        else:
            transID=77
            json_stopwave = {
                'message': {
                    'transmission_id': [transID],
                    'op': 'stop_wave_m',
                }
            }

            self.s.sendall(bytes(json.dumps(json_stopwave),'utf-8'))
            # sleep(1.0)
            json_reply=json.loads(self.s.recv(1024))
            self.latest_reply = json_reply

            if (json_reply['message']['transmission_id'] == [transID]) and json_reply['message']['parameters']['status'] == [0]:
                #wavelength = json_reply['message']['parameters']['current_wavelength'][0]
               return 0
            else:
                # print('M2_Solstis: failed connection to wavemeter')
                # print('M2_Solstis: reply from controller {}'.format(json_reply))

                return 1

    def lock(self, operation):
        """ this operation locks or removes lock on wavelength
         operation is 'on' or 'off'

        Returns
        -------
        status : str
            Zero is returned if operation was unsuccessful
            1 if there is no link to the wavemeter
            9 : socket error
        wavelength the current and last wavelength

        """
        if self.s is None:
            # print('M2_Solstis: socket not connected')
            return 9
        else:
            transID=8
            json_lockwave = {
                'message': {
                    'transmission_id': [transID],
                    'op': 'lock_wave_m',
                    'parameters': {
                        'operation': operation
                    }
                }
            }

            #print(json_lockwave)

            self.s.sendall(bytes(json.dumps(json_lockwave),'utf-8'))
            # sleep(1.0)
            json_reply=json.loads(self.s.recv(1024))
            self.latest_reply = json_reply

            #print(json_reply)

            if json_reply['message']['transmission_id'] == [transID] and json_reply['message']['parameters']['status'] == [0]:

                print('M2_Solstis: lock or unlock wavelength successfull')
                #wavelength = json_reply['message']['parameters']['current_wavelength'][0]
                # print('M2_Solstis: Tuning stopped. Current wavelength from wavemeter is {}'.format(wavelength))
                return 0
            else:
                # print('M2_Solstis: failed connection to wavemeter')
                # print('M2_Solstis: reply from controller {}'.format(json_reply))

                return 1


    def close(self):
        """
        Closes socket connection to the laser.
        """
        if self.s is not None:
            self.s.close()
