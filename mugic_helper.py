# mugic_helper.py - module used for interfacing with mugic IMU
# portions of code borrowed from the pymugic module
# * https://github.com/amiguet/pymugic
# oscpy reference:
# * https://github.com/kivy/oscpy

# TODO
# * create mockable mugic device

from oscpy.server import OSCThreadServer
import time
import pygame
import math
from collections import deque as stack

# TODO clean up these imports
from OpenGL.GL import (GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, GL_DEPTH_TEST, GL_LEQUAL,
                       GL_MODELVIEW, GL_NICEST, GL_PERSPECTIVE_CORRECTION_HINT, GL_PROJECTION,
                       GL_QUADS, GL_RGBA, GL_SMOOTH, GL_UNSIGNED_BYTE, glBegin, glClear,
                       glClearColor, glClearDepth, glColor3f, glDepthFunc, glDrawPixels, glEnable,
                       glEnd, glHint, glLoadIdentity, glMatrixMode, glRasterPos3d, glRotatef,
                       glShadeModel, glTranslatef, glVertex3f, glViewport)
from OpenGL.GLU import gluPerspective
from pygame.locals import DOUBLEBUF, KEYDOWN, K_ESCAPE, OPENGL, QUIT, K_a, K_s

# Base Classes


# wrapper class for a 9 axis IMU for pygame
# 9 axis - 3 for gyroscope, 3 for acceleration, 3 for compass
class PygameIMU:
    def __init__(self):
        print("PygameIMU under development")

    def calibrate(self):
        return self

#  mugic_init         - prepares osc server for connections
#  get_connect_status - gets connection status of the mugic device
#  get_datagram       - get the most recent datagram from the mugic device
#  calibrate          - set calibration data
#  get_datagrams      - get the most recent datagrams from the mugic device
#  get_image          - gets the 3d visualization of the mugic device

class MugicDevice(PygameIMU):
    # Datagram signature
    types= [float if t == 'f' else int for t in 'fffffffffffffffffiiiiifi']
    # Datagram structure
    datagram = (
        'AX', 'AY', 'AZ', # accelerometer
        'EX', 'EY', 'EZ', # Euler angles
        'GX', 'GY', 'GZ', # Gyrometer
        'MX', 'MY', 'MZ', # Magnetometer
        'QW', 'QX', 'QY', 'QZ', # Quaternions
        'Battery', 'mV', # Battery state
        'calib_sys', 'calib_gyro', 'calib_accel', 'calib_mag', # Calibration state
        'seconds', # since last reboot
        'seqnum', # messagesequence number
    )

    def __init__(self, port, useQuat=True):
        self._mugic_init()
        self._image_size = (100, 100)
        self.screen = pygame.Surface(self._image_size)
        self.use_quat = True
        self._data = stack()
        return

    @classmethod
    def _parse_datagram(self, *values):
        values = [t(v) for t, v in zip(MugicDevice.types, values)]
        datagram = {
            k: v
            for k, v in zip(MugicDevice.datagram, values)
        }
        return datagram

    def _callback(self, *values):
        datagram = MugicDevice.parse_datagram(*values)
        self._data.append(datagram)

    def _mugic_init(self):
        # prepare for connections
        self._osc_server = OSCThreadServer()
        address = '0.0.0.0'
        self._socket = osc.listen(address=address, port=port, default=True)
        self._osc_server.bind(b'/mugicdata', self._callback)
        return

    def connected(self):
        return len(self._data) != 0

    def getDatagram(self):
        datagram = self._data.pop()
        return datagram

    def getDatagrams(self):
        datagrams = self._data.copy()
        self._data.clear()
        return datagrams

    def calibrate(self, calib_data):
        # TODO
        return

    def _set_image_size(self, w=None, h=None):
        if w == None and h == None:
            return self._image_size
        use_new_surface = False
        if w == None: w = self._image_size[0]
        elif w != self._image_size[0]:
            self._image_size[0] = w
            use_new_surface = True
        if h == None: h = self._image_size[1]
        elif h != self._image_size[1]:
            self._image_size[1] = h
            use_new_surface = True
        if use_new_surface:
            self.screen = pygame.Surface(self._image_size)
        return self._image_size

    def getImage(self, w=None, h=None):
        w, h = self._set_image_size(w, h)
        return None

# mock mugic device - use to simulate a mugic device
class MockMugicDevice(MugicDevice):
    def __init__(self, port, datafile, useQuat=True):
        super().__init__(port, useQuat)
        self._datafile = datafile
        address = '0.0.0.0'
        self._osc_client = OSCClient(address, port)

    def send_data(self):
        # TODO - make thread, send all messages in data file
        self._osc_client.send_message(b'/mugicdata', data)

    @classmethod
    def recordMugicDevice(mugic, datafile, seconds = 2000):
        print("Recording Mugic Device", mugic, "for the next", seconds, "seconds...")
        #TODO
        print("Recording complete")
        return

# MAIN FUNCTION - for use with testing
if __name__ == "__main__":
    print("Running mugic_helper module tests...")
    # tests go here
    print("mugic_helper module tests completed.")
