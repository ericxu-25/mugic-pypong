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
from oscpy.client import OSCClient
from mugic_pygame_helpers import Screen, TextSprite, Color
import time
import pygame
import math
from math import pi
from collections import deque as stack
from threading import Timer, Thread
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
    mu_datagram = (
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

    def __init__(self, port=4000):
        self.port = port
        self._data = stack()
        self.dirty = False
        self._init_image(100, 100)
        self._mugic_init()
        return

    @staticmethod
    def _parse_datagram(*values):
        values = [t(v) for t, v in zip(MugicDevice.types, values)]
        datagram = {
            k: v
            for k, v in zip(MugicDevice.mu_datagram, values)
        }
        return datagram

    @staticmethod
    def _datagram_to_string(datagram):
        data_string = ",".join([str(v) for v in datagram.values()])
        return data_string

    def _callback(self, *values):
        datagram = MugicDevice._parse_datagram(*values)
        self._data.append(datagram)
        self.dirty = True

    def _mugic_init(self):
        # prepare for connections
        if self.port is None: return
        self._osc_server = OSCThreadServer()
        address = '0.0.0.0'
        self._socket = self._osc_server.listen(
                address=address, port=self.port, default=True)
        self._osc_server.bind(b'/mugicdata', self._callback)
        return

    def connected(self):
        return len(self._data) != 0

    def getDatagram(self):
        if len(self._data) == 0:
            return None
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

    def rotateImageX(self, angle=1):
        try:
            self._image_rotationx += angle
            self._image_rotationx %= (2*pi)
            self._camera.rotateX(self._image_rotationx)
        except AttributeError:
            self._init_image_cube()
        self.dirty = True

    def rotateImageY(self, angle=1):
        try:
            self._image_rotationy += angle
            self._image_rotationy %= (2*pi)
            self._camera.rotateY(self._image_rotationy)
        except AttributeError:
            self._init_image_cube()
        self.dirty = True

    def zoomImage(self, distance):
        try:
            self._camera.zoom(distance)
        except AttributeError:
            self._init_image_cube()
        self.dirty = True

    def resetImage(self):
        del self._image_cube
        self._init_image_cube()
        self.dirty = True

    def _init_image_cube(self):
        self._image_rotationx = 0
        self._image_rotationy = 0
        if hasattr(self, '_image_cube'): return
        self._image_cube = graph3d.Cube(Color.magenta, Color.cyan, Color.orange)
        self._image_cube += (-0.5, -0.5, -0.5)
        self._image_cube *= (0.4, 0.3, 1)
        self._camera = graph3d.Camera()
        self._camera["cube"] = self._image_cube
        self._camera["axes"] = graph3d.Axes(Color.red, Color.green, Color.blue)

    def getImage(self, w=None, h=None):
        w, h = self._set_image_size(w, h)
        if not self.dirty: return self._image
        try:
            self.image.fill(Color.black)
            # apply datagram transformations
            datagram = self.getDatagram()
            if datagram is not None:
                data_quat = quat.Quaternion(
                        datagram['QW'],
                        datagram['QX'],
                        datagram['QY'],
                        datagram['QZ'])
                #print(quat.euler(data_quat))
                self._camera["cube"] = self._image_cube @ data_quat
            self._camera.show(self.image)
        except AttributeError:
            self._init_image_cube()
            return self.getImage(w, h)
        return self.image

# mock mugic device - used to simulate a mugic device
class MockMugicDevice(MugicDevice):
    def __init__(self, port=None, datafile=None):
        super().__init__(port)
        self._datafile = datafile
        address = '127.0.0.1'
        self._osc_client = OSCClient(address, port)
        self._start_time = 0
        self._base_time = 0
        if datafile is not None:
            self.sendData(datafile)
        if datafile is None and port is None:
            print("Warning: blank MockMugicDevice!")

    @property
    def dirty(self):
        if self._next_datagram_is_available():
            self._dirty = True
        return self._dirty

    @dirty.setter
    def dirty(self, val:bool):
        self._dirty = val

    def _datagram_is_ready(self, datagram):
        if len(self._data) == 0: return False
        elapsed = pygame.time.get_ticks() - self._start_time
        datagram_time = datagram['seconds']
        next_datagram_time = datagram_time - self._base_time
        if elapsed < next_datagram_time*10: return False
        return True

    def _next_datagram_is_available(self):
        if len(self._data) == 0: return False
        top = self._data[-1]
        if not self._datagram_is_ready(top): return False
        return True

    def getDatagram(self):
        if not self._next_datagram_is_available(): return None
        datagram = self._data.pop()
        self.dirty = True
        return datagram

    def getDatagrams(self):
        datagrams = deque()
        index = 0
        for datagram in self._data:
            if not _datagram_is_ready(datagram): break
            datagrams.appendLeft(datagram)
            index += 1
        self._data = self._data[index:]
        return datagrams

    def sendData(self, datafile):
        print("MockMugicDevice: sending data in file", datafile)
        first_datagram_time = 0
        for data in open(datafile, 'r'):
            values = [t(v) for t, v in zip(MugicDevice.types,
                                           data.split(','))]
            if first_datagram_time == 0:
                first_datagram_time = values[22]
            if self.port is None:
                self._callback(*values)
            else:
                self._osc_client.send_message(b'/mugicdata', values)
        print("MockMugicDevice: completed sending", datafile)
        self._start_time = pygame.time.get_ticks()
        self._base_time = first_datagram_time


def recordMugicDevice(mugic, datafile, seconds=60):
    print("waiting for mugic to be connected...")
    total_wait_time = 0
    wait_period = 0.5
    while not mugic.connected():
        time.sleep(wait_period)
        total_wait_time += wait_period
        if total_wait_time > max(seconds, 60):
            print("aborting... waited too long!")
            return
    print("Recording Mugic Device", mugic, "for the next", seconds, "seconds...")
    file = open(datafile, "w")
    recordTimer = Timer(
            seconds,
            lambda: _write_recorded_data(mugic, file))
    recordTimer.start()
    return

def _write_recorded_data(mugic, file):
    print("preparing to write", len(mugic._data), "datagrams...")
    for datagram in mugic.getDatagrams():
        datagram = MugicDevice._datagram_to_string(datagram)
        # print("writing datagram:", datagram)
        file.write(datagram+'\n')
    print("Recording complete")
    file.close()

def _viewMugicDevice(mugic_device):
    print("Running mugic_helper display...")
    pygame.init()
    # window setup
    window_size = (500, 500)
    pygame.display.set_mode(window_size)
    pygame.display.set_caption("PyMugic IMU orientation visualization")
    display = pygame.display.get_surface()
    frames = 0
    ticks = pygame.time.get_ticks()
    # object setup
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

        rot_amount = pi/180
        if state[pygame.K_a]:
            mugic_device.rotateImageY(-rot_amount)
        elif state[pygame.K_d]:
            mugic_device.rotateImageY(rot_amount)
        if state[pygame.K_w]:
            mugic_device.rotateImageX(-rot_amount)
        elif state[pygame.K_s]:
            mugic_device.rotateImageX(rot_amount)
        elif state[pygame.K_z]:
            mugic_device.zoomImage(0.1)
        elif state[pygame.K_x]:
            mugic_device.zoomImage(-0.1)
        elif state[pygame.K_r]:
            mugic_device.resetImage()

        if mugic_device.dirty:
            mugic_image = mugic_device.getImage()
            display_screen._redraw()
            display.blit(mugic_image, (0, 0))
            pygame.display.flip()
            mugic_device.dirty = False
            if not mugic_device.connected():
                continue
            frames += 1
            fps_value = ((frames*1000)/(pygame.time.get_ticks()-ticks))
            text_display.setText(round(fps_value, 3))
        else:
            time.sleep(.01)
    pygame.quit()

def _recordMugic(mugic, seconds=60, filename="recording.txt"):
    recordMugicDevice(mugic, filename, seconds)

# MAIN FUNCTION - for use with testing / recording
if __name__ == "__main__":
    mugic = MockMugicDevice(datafile="recording.txt")
    _viewMugicDevice(mugic)
    #mugic = MugicDevice(port=4000)
    #_recordMugic(mugic, seconds=10)

