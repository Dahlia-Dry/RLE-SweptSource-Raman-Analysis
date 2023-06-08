# -*- coding: utf-8 -*-
"""
Driver for controlling Klinger Scientific CC1.1 motor controller

Usage Example:
from instrumental.drivers.motion.klinger import KlingerMotorController
mc = KlingerMotorController(visa_address='GPIB0::8::INSTR')
mc.set_steprate(R=254, S=1, F=29)
mc.go_steps(N=1000)
mc.close()
"""

from . import Motion
# from .. import ParamSet
# from ...log import get_logger
# from .. import VisaMixin
# from ..util import check_units
# from ... import u

import visa
#
# log = get_logger(__name__)
#
# __all__ = ['NSCA1']
#
#
# # TODO: There should be a function wrapper
# class ImplicitUnitsException(Exception):
#     pass


class KlingerMotorController(Motion):
    """ Class for controlling Klinger Scientific CC1.1
        which is IEEE 488.1 compliant (488.2 is back-compliant but this instrument does not respond to *IDN? query)
    """
    _INST_PARAMS_ = ['visa_address']

    def _initialize(self):
        self._rsrc = visa.ResourceManager().open_resource(
            self._paramset['visa_address'],
            read_termination='\r',
            write_termination='\r')

    def close(self):
        self._rsrc.close()

    def go_steps(self, N):
        if N>0 and N<65536:
            self._rsrc.write("N {}".format(N))
            self._rsrc.write("+")
            self._rsrc.write("G")

        elif N<0 and N>-65536:
            self._rsrc.write("N {}".format(-N))
            self._rsrc.write("-")
            self._rsrc.write("G")
        else:
            print('Invalid steps for given N')

    def go_nm(self, nm=0):
        self.go_steps(N=nm*10)

    def set_steprate(self, R, S, F):
        # Step rate R (1~255) - larger is faster
        if R>0 and R<256:
            self._rsrc.write("R {}".format(R))
        else:
            print('Invalid step rate R')

        # Step rate acceleration parameter S(1~255) - larger is faster
        if S>0 and S<256:
            self._rsrc.write("S {}".format(S))
        else:
            print('Invalid step rate acceleration parameter S')

        # Step rate factor parameter F(1~255) - smaller is faster
        if F>0 and F<256:
            self._rsrc.write("F {}".format(F))
        else:
            print('Invalid step rate factor parameter F')

    def wait_until_motor_is_idle(self):
        # the CC1 will hold NDAC and NRFD in true state so that the data transfer is delayed
        pass
