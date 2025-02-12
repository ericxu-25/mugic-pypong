# mugic_helper.py - module used for interfacing with mugic IMU
# portions of code borrowed from the pymugic module
# * https://github.com/amiguet/pymugic
# quaternion module is taken from peter hinch
# * https://github.com/peterhinch/micropython-samples/blob/master/QUATERNIONS.md
# oscpy reference:
# * https://github.com/kivy/oscpy

# TODO
# * create mockable mugic device

import oscpy as osc
from oscpy.server import OSCThreadServer
from mugic_pygame_helpers import Screen, TextSprite, Color
import time
import pygame
import math
from math import pi
from collections import deque as stack
from threading import Timer
import quaternion.quat as quat
import quaternion.graph3d as graph3d

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
        self.port = port
        self._mugic_init()
        self.use_quat = True
        self._data = stack()
        self.dirty = False
        self._init_image(100, 100)
        return

    @staticmethod
    def _parse_datagram(cls, *values):
        values = [t(v) for t, v in zip(MugicDevice.types, values)]
        datagram = {
            k: v
            for k, v in zip(MugicDevice.datagram, values)
        }
        self.dirty = True
        return datagram

    @staticmethod
    def _datagram_to_string(datagram):
        data_string = ""
        for data in datagram.values():
            data_string +=  "," + str(data)
        return data_string

    def _callback(self, *values):
        datagram = MugicDevice.parse_datagram(*values)
        self._data.append(datagram)

    def _mugic_init(self):
        # prepare for connections
        self._osc_server = OSCThreadServer()
        address = '0.0.0.0'
        self._socket = self._osc_server.listen(
                address=address, port=self.port, default=True)
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

    def _init_image(self, w, h):
        self._image_size = (w, h)
        self.image = pygame.Surface(self._image_size)
        self.image.set_colorkey(Color.black)

    def _set_image_size(self, w=None, h=None):
        if w == None and h == None:
            return self._image_size
        use_new_surface = False
        if w == None: w = self._image_size[0]
        elif w != self._image_size[0]:
            self._image_size = (w, self._image_size[1])
            use_new_surface = True
        if h == None: h = self._image_size[1]
        elif h != self._image_size[1]:
            self._image_size = (self._image_size[0], h)
            use_new_surface = True
        if use_new_surface:
            self._init_image(*self._image_size)
        return self._image_size

    def setImageSize(self, w, h):
        self._set_image_size(w, h)

    def rotateImage(self, angle=1):
        try:
            self._image_rotation = (
                    self._image_rotation + angle) % 360
            self._camera.rotate(self._image_rotation)
        except AttributeError:
            self._init_image_cube()
        self.dirty = True

    def zoomImage(self, distance):
        try:
            self._camera.zoom(distance)
        except AttributeError:
            self._init_image_cube()
        self.dirty = True

    def _init_image_cube(self):
        self._image_rotation = 0
        if hasattr(self, '_image_cube'): return
        self._image_cube = graph3d.Cube(Color.red , Color.blue, Color.green)
        self._image_cube += (-0.5, -0.5, -0.5)
        self._camera = graph3d.Camera()
        self._camera["cube"] = self._image_cube
        self._camera["axes"] = graph3d.Axes(Color.white)

    def getImage(self, w=None, h=None):
        w, h = self._set_image_size(w, h)
        if not self.dirty: return self._image
        try:
            self.image.fill(Color.black)
            self._camera.show(self.image)
        except AttributeError:
            self._init_image_cube()
            return self.getImage(w, h)
        return self.image

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

    @staticmethod
    def recordMugicDevice(mugic, datafile, seconds = 60):
        print("Recording Mugic Device", mugic, "for the next", seconds, "seconds...")
        file = open(datafile, "w")
        recordThread = Timer(
                seconds,
                lambda: _write_recorded_data(mugic, file))
        return

    @staticmethod
    def _write_recorded_data(mugic, file):
        for datagram in mugic.getDatagrams().reverse():
            datagram = MugicDevice._datagram_to_string(datagram)
            print("writing datagram:", datagram)
            file.write(datagram)
        print("Recording complete")
        file.close()

def _viewMugicDevice():
    pygame.init()
    # window setup
    window_size = (500, 500)
    pygame.display.set_mode(window_size)
    pygame.display.set_caption("PyMugic IMU orientation visualization")
    display = pygame.display.get_surface()
    frames = 0
    ticks = pygame.time.get_ticks()
    # object setup
    mugic_device = MugicDevice(port = 4000)
    mugic_device.setImageSize(*window_size)
    display_screen = Screen(*window_size).setScreen(display)
    text_display = TextSprite(display_screen)
    display_screen.addSprite(text_display)
    text_display.setFormatString("fps: {}")
    text_display.setText("NOT CONNECTED").setFontSize(30)
    text_display.moveTo(50, 50)
    display_screen._redraw()
    pygame.display.flip()
    # main loop
    while True:
        event = pygame.event.poll()
        if (event.type == pygame.QUIT or
            (event.type == pygame.KEYDOWN
             and event.key == pygame.K_ESCAPE)):
            break
        state = pygame.key.get_pressed()

        if state[pygame.K_a]:
            mugic_device.rotateImage(-1/36)
        elif state[pygame.K_d]:
            mugic_device.rotateImage(1/36)
        elif state[pygame.K_w]:
            mugic_device.zoomImage(0.1)
        elif state[pygame.K_s]:
            mugic_device.zoomImage(-0.1)

        if mugic_device.dirty:
            mugic_image = mugic_device.getImage()
            display_screen._redraw()
            display.blit(mugic_image, (0, 0))
            pygame.display.flip()
            mugic_device.dirty = False
            frames += 1
        else:
            time.sleep(.01)
        fps_value = ((frames*1000)/(pygame.time.get_ticks()-ticks))
        text_display.setText(fps_value)
    pygame.quit()

# MAIN FUNCTION - for use with testing / recording
if __name__ == "__main__":
    print("Running mugic_helper display...")
    _viewMugicDevice()

