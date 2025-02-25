# mugic_helper.py - module used for interfacing with mugic IMU
# portions of code borrowed from the pymugic module
# * https://github.com/amiguet/pymugic
# quaternion & 3d drawing module taken (and modified) from peter hinch
# * https://github.com/peterhinch/micropython-samples/blob/master/QUATERNIONS.md
# oscpy reference:
# * https://github.com/kivy/oscpy

# TODO
# * implement reading from usb device
# * add variable display text sprites
# * add IMU functions

import oscpy as osc
from oscpy.server import OSCThreadServer
from oscpy.client import OSCClient
import time
import math
from math import pi
from collections import deque
import quaternion.quat as quat
import quaternion.graph3d as graph3d
from array import array

import sys
import pygame
from mugic_pygame_helpers import Window, WindowScreen, TextSprite, Color
from threading import Timer

# helper functions
def _log_scale(number):
    sign = -1 if number < 0 else 1
    return (math.log(abs(number)+1)/3.0) * sign

# Base Classes

# interface for a generic IMU device
class IMU:
    # assumes 9-axis Datagram structure
    # Datagram types and structure
    types = [float] * 25
    datagram = (
        'AX', 'AY', 'AZ', # Accelerometer
        'EX', 'EY', 'EZ', # Euler angles
        'GX', 'GY', 'GZ', # Gyrometer
        'MX', 'MY', 'MZ', # Magnetometer
        'QW', 'QX', 'QY', 'QZ', # Quaternion angles
        'VX', 'VY', 'VZ', # Velocity
        'X', 'Y', 'Z',    # Position
    )

    def __init__(self, buffer_size=10):
        self.dirty = False
        if buffer_size == None:
            print("Warning - IMU uncapped buffer size!")
            self._data = deque()
        else:
            self._data = deque(maxlen=buffer_size)
        self.zero()

    @property
    def dirty(self):
        if len(self._data) > 0:
            self._dirty = True
        return self._dirty

    @dirty.setter
    def dirty(self, val):
        self._dirty = bool(val)

    def peekDatagram(self, raw=False, smooth=3):
        if len(self._data) == 0: return None
        if not smooth or smooth == 1:
            datagrams = [self._data[-1].copy()]
        else:
            datagrams = [self._data[-i-1].copy() for i in range(min(len(self._data), smooth))]
        return self._smooth(datagrams, raw)

    def popDatagram(self, raw=False, smooth=3):
        if len(self._data) == 0: return None
        datagrams = [self._data.pop()]
        if not smooth or smooth == 1:
            return self._smooth(datagrams, raw)
        for i in range(smooth):
            if i+1 > len(self._data): break
            datagrams.append(self._data[-i-1])
        return self._smooth(datagrams, raw)

    def popDatagrams(self, raw=False):
        datagrams = self._data.copy()
        self._data.clear()
        if raw: return datagrams
        return [self._calibrate(d) for d in datagrams]

    def refresh(self):
        if len(self._data) == 0: return None
        self._dirty = True
        last_datagram = self._data[0]
        self._data.clear()
        self._data.appendleft(last_datagram)
        return last_datagram

    def zero(self, *args, **kwargs):
        self._zero = dict()
        for key in IMU.datagram:
            self._zero[key] = 0
        if len(args) != 0:
            for key, arg in zip(self.datagram, args):
                self._zero[key] = arg
        self._zero.update(kwargs)

    def calibrate(self, *args, **kwargs):
        self.zero(*args, **kwargs)
        # don't calibrate magnetometer
        self._zero['MX'] = 0
        self._zero['MY'] = 0
        self._zero['MZ'] = 0

    def _calibrate(self, datagram):
        calibrated_quat = (IMU.to_quaternion(datagram) *
                           IMU.to_quaternion(self._zero).conjugate()).normalise()
        for key, value in self._zero.items():
            datagram[key] -= value
        datagram['QW'] = calibrated_quat.w
        datagram['QX'] = calibrated_quat.x
        datagram['QY'] = calibrated_quat.y
        datagram['QZ'] = calibrated_quat.z
        return datagram

    # returns smoothed datagram via moving average
    # might want to look into madgwick/kalman filter in the future
    def _smooth(self, datagrams, raw=False):
        if len(datagrams) == 1:
            if raw: return datagrams[0]
            return self._calibrate(datagrams[0])
        smoothed_datagram = datagrams[0].copy()
        for datagram in datagrams[1:]:
            for value in self.__class__.datagram:
                smoothed_datagram[value] += datagram[value]
        for value in self.__class__.datagram:
            smoothed_datagram[value] /= len(datagrams)
        norm_quat = IMU.to_quaternion(smoothed_datagram).normalise()
        smoothed_datagram['QW'] = norm_quat.w
        smoothed_datagram['QX'] = norm_quat.x
        smoothed_datagram['QY'] = norm_quat.y
        smoothed_datagram['QZ'] = norm_quat.z
        if raw: return smoothed_datagram
        return self._calibrate(smoothed_datagram)


    @staticmethod
    def to_quaternion(datagram):
        if datagram['QW'] == 0: return quat.Quaternion(1, 0, 0, 0)
        return quat.Quaternion(datagram['QW'], datagram['QX'],
                               datagram['QY'], datagram['QZ'])

    @staticmethod
    def _datagram_to_string(datagram):
        data_string = ",".join([str(v) for v in datagram.values()])
        return data_string

    # returns the in-between of two data points
    @staticmethod
    def lerp(d1, d2, ratio=0.5):
        lerped_datagram = d1.copy()
        for val in d1.keys():
            lerped_datagram[val] = d1[val] + ratio*(d1[val]- d2[val])
        lerped_quat = IMU.to_quaternion(d1).nlerp(IMU.to_quaternion(d2), ratio)
        lerped_datagram['QW'] = lerped_quat.w
        lerped_datagram['QX'] = lerped_quat.x
        lerped_datagram['QY'] = lerped_quat.y
        lerped_datagram['QZ'] = lerped_quat.z
        return lerped_datagram

    @staticmethod
    def accel(datagram):
        if datagram is None: return None
        return [datagram['AX'], datagram['AY'], datagram['AZ']]

    @staticmethod
    def gyro(datagram):
        if datagram is None: return None
        return [datagram['GX'], datagram['GY'], datagram['GZ']]

    @staticmethod
    def quat(datagram):
        if datagram is None: return None
        return IMU.to_quaternion(datagram)

    @staticmethod
    def euler(datagram):
        if datagram is None: return None
        return [datagram['EX'], datagram['EY'], datagram['EZ']]

    @staticmethod
    def velocity(datagram):
        if datagram is None: return None
        return [datagram['VX'], datagram['VY'], datagram['VZ']]

    @staticmethod
    def position(datagram):
        if datagram is None: return None
        return [datagram['X'], datagram['Y'], datagram['Z']]

# IMUController interface
# Methods:
# * next() -> get next datagram, None if disconnected
# * variety of state querying commands
# Future Methods to implement:
# * compassAngle
class IMUController(IMU):
    def __init__(self, buffer_size=10):
        super().__init__(buffer_size)
        self._connected = False
        self._time_stamp = time.time()
        self._next_datagram = None
        self._state = None
        self.low_pass = [0.15] * 3
        self._speed = array('d', [0, 0, 0])
        self._position = array('d', [0, 0, 0])

    @classmethod
    def _parse_datagram(cls, *values):
        values = [t(v) for t, v in zip(cls.types, values)]
        datagram = dict(zip(cls.datagram, values))
        return datagram

    def _callback(self, *values):
        datagram = self._parse_datagram(*values)
        datagram = self._update_state(datagram)
        self._data.appendleft(datagram)
        self._dirty = True
        self._connected = True

    def connected(self):
        return self._connected

    def calibrate(self, *args, **kwargs):
        if len(self._data) != 0 and len(args) == 0:
            super().calibrate(**self.peekDatagram(raw=True))
        else:
            super().calibrate(*args, **kwargs)
        # don't want to calibrate these values
        self._zero['Battery'] = 0
        self._zero['seqnum'] = 0
        self._zero['seconds'] = 0
        self._zero['calib_sys'] = 0
        self._zero['calib_accel'] = 0
        self._zero['calib_gyro'] = 0
        self._zero['calib_mag'] = 0
        self._zero['VX'] = 0
        self._zero['VY'] = 0
        self._zero['VZ'] = 0
        self.low_pass = [self._zero['AX'], self._zero['AY'], self._zero['AZ']]
        self.low_pass = [abs(val) * 3 for val in self.low_pass]
        self._dirty = True

    # because we are using a single IMU, there is some drift, which makes
    # accurately getting position a challenge. So position and speed really
    # just return the details of big gestures and return to rest otherwise

    # appends additional data to each datagram
    def _update_state(self, datagram):
        now = time.time()
        if self._state is not None:
            delta_t = now - self._time_stamp
            # solve for the change in speed/rot - take halfway point to approximate
            accel = [(self._state[v] + datagram[v])/2.0 for v in ('AX', 'AY', 'AZ')]
            for i in range(3):
                if abs(accel[i]) > self.low_pass[i]:
                    self._speed[i] += accel[i] * delta_t
                else: self._speed[i] /= 1.2
                self._position[i] += self._speed[i] * delta_t
        datagram['VX'], datagram['VY'], datagram['VZ'] = self._speed
        datagram['X'], datagram['Y'], datagram['Z'] = self._position
        self._state = datagram
        self._time_stamp = now
        return datagram

    def next(self, raw=False, smooth=3):
        next_datagram = self.peekDatagram(raw, smooth)
        # check if there was a disconnect
        if self._next_datagram is not None and time.time() - self._last_datagram_time > 3:
            print("mugic device disconnected")
            self._connected = False
            self._dirty = True
            self._next_datagram = None
            self.popDatagrams()
            return None
        if len(self._data) > smooth:
            self.popDatagram()
        if (next_datagram is not None
        and (self._next_datagram is None
             or next_datagram['seqnum'] != self._next_datagram['seqnum'])):
            self._next_datagram = next_datagram
            self._last_datagram_time = time.time()
        return self._next_datagram

    @property
    def data(self):
        return self.next()

    # easy controller methods - query controller speed, gyro, facing
    def _moving(self, axis, direction=1, threshold=0.1):
        datagram = self.next()
        if datagram == None: return False
        axis = 'VX' if axis == 0 else 'VY' if axis == 1 else 'VZ'
        if datagram[axis] * direction > threshold:
            return True
        return False

    def _rotating(self, axis, direction=1, threshold=10):
        datagram = self.next()
        if datagram == None: return False
        axis = 'GX' if axis == 0 else 'GY' if axis == 1 else 'GZ'
        if datagram[axis] * direction > threshold:
            return True
        return False

    def _facing(self, axis, direction, threshold=45):
        datagram = self.next()
        direction = (360 + direction)%360
        if datagram == None: return False
        axis  = 'EX' if axis == 0 else 'EY' if axis == 1 else 'EZ'
        angle = datagram[axis]
        left  = (direction + 360 - threshold) % 360
        right = (direction + threshold) % 360
        if angle > left and angle < right:
            return True
        return False

    def movingUp(self, threshold=0.1): return self._moving(1, 1, threshold)
    def movingDown(self, threshold=0.1): return self._moving(1, -1, threshold)
    def movingRight(self, threshold=0.1): return self._moving(2, 1, threshold)
    def movingLeft(self, threshold=0.1): return self._moving(2, -1, threshold)
    def movingForward(self, threshold=0.1): return self._moving(0, 1, threshold)
    def movingBackward(self, threshold=0.1): return self._moving(0, -1, threshold)

    def rotatingRight(self, threshold=10): return self._rotating(0, 1, threshold)
    def rotatingLeft(self, threshold=10): return self._rotating(0, -1, threshold)
    def rotatingUp(self, threshold=10): return self._rotating(1, 1, threshold)
    def rotatingDown(self, threshold=10): return self._rotating(1, -1, threshold)
    def twistingRight(self, threshold=10): return self._rotating(2, -1, threshold)
    def twistingLeft(self, threshold=10): return self._rotating(2, -1, threshold)

    def facingUp(self, threshold=45): return self._facing(1, 90, threshold)
    def facingDown(self, threshold=45): return self._facing(1, -90, threshold)
    def facingRight(self, threshold=45): return self._facing(0, 90, threshold)
    def facingLeft(self, threshold=45): return self._facing(0, -90, threshold)
    def facingForward(self, threshold=45): return self._facing(0, 0, threshold)
    def facingBackward(self, threshold=45): return self._facing(0, 180, threshold)
    def tiltedLeft(self, threshold=45): return self._facing(2, -90, threshold)
    def tiltedRight(self, threshold=45): return self._facing(2, 90, threshold)
    def tiltedUp(self): return self._facing(2, 0, threshold) # upside up
    def tiltedDown(self): return self._facing(2, 180, threshold) # upside down

    def jolted(self, threshold=10):
        datagram = self.next()
        move_magnitude = math.sqrt(sum([a*a for a in IMU.accel(datagram)]))
        if move_magnitude > threshold: return True
        return False

class MugicDevice(IMUController):
    # Datagram signature
    types = [float if t == 'f' else int for t in 'fffffffffffffffffiiiiififffffffff']
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
        'VX', 'VY', 'VZ', # Velocity (not provided by IMU)
        'X', 'Y', 'Z',    # Position (not provided by IMU)
    )

    def __init__(self, port=4000, buffer_size=10):
        super().__init__(buffer_size)
        self.port = port
        self._mugic_init()
        return

    def _mugic_init(self):
        # prepare for connection
        if self.port is None: return
        self._osc_server = OSCThreadServer()
        address = '0.0.0.0'
        self._socket = self._osc_server.listen(
                address=address, port=self.port, default=True)
        self._osc_server.bind(b'/mugicdata', self._callback)
        return

    def _smooth(self, datagrams, raw=False):
        ret_val = super()._smooth(datagrams, raw)
        ret_val['seqnum'] = datagrams[0]['seqnum']
        return ret_val

# mock mugic device - used to simulate a mugic device
class MockMugicDevice(MugicDevice):
    def __init__(self, port=None, datafile=None):
        super().__init__(port, buffer_size=None)
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
        elapsed = time.time() - self._start_time
        datagram_time = datagram['seconds']
        next_datagram_time = datagram_time - self._base_time
        if elapsed < next_datagram_time/2: return False
        return True

    def _next_datagram_is_available(self):
        if len(self._data) == 0: return False
        top = self._data[-1]
        if not self._datagram_is_ready(top): return False
        self._connected = True
        return True

    def popDatagram(self, raw=False, smooth=3):
        if not self._next_datagram_is_available(): return None
        return super().popDatagram(raw, smooth)

    def peekDatagram(self, raw=False, smooth=3):
        if not self._next_datagram_is_available(): return None
        return super().peekDatagram(raw, smooth)

    def popDatagrams(self, raw=False):
        datagrams = deque()
        index = 0
        for datagram in reversed(self._data):
            if not self._datagram_is_ready(datagram): break
            if not raw: self._calibrate(datagram)
            datagrams.appendleft(datagram)
        for _ in datagrams:
            self._data.pop()
        return datagrams

    def sendData(self, datafile):
        print("MockMugicDevice: sending data in file", datafile)
        self._base_time = 0
        for data in open(datafile, 'r'):
            values = [t(v) for t, v in zip(MugicDevice.types,
                                           data.split(','))]
            if self._base_time == 0:
                self._base_time = values[22]
            if self.port is None:
                self._callback(*values)
            else:
                self._osc_client.send_message(b'/mugicdata', values)
        print("MockMugicDevice: completed sending", datafile)
        self._start_time = time.time()

class IMUDisplay:
    def __init__(self, imu, w=100, h=100):
        self._imu = imu
        self._init_text()
        self._init_image(w, h)

    def _init_image(self, w, h):
        self._image_size = (w, h)
        self._image = pygame.Surface(self._image_size)
        self._image.set_colorkey(Color.black)

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
            self._camera.rotateX(angle)
        except AttributeError:
            self._init_image_cube()
        self._imu.dirty = True

    def rotateImageY(self, angle=1):
        try:
            self._camera.rotateY(angle)
        except AttributeError:
            self._init_image_cube()
        self._imu.dirty = True

    def rotateImageZ(self, angle=1):
        try:
            self._camera.rotateZ(angle)
        except AttributeError:
            self._init_image_cube()
        self._imu.dirty = True

    def zoomImage(self, distance):
        try:
            self._camera.zoom(distance)
        except AttributeError:
            self._init_image_cube()
        self._imu.dirty = True

    def resetImage(self):
        del self._image_cube
        self._init_image_cube()
        self._imu.dirty = True

    def _init_image_cube(self):
        if hasattr(self, '_image_cube'): return
        self._image_cube = graph3d.Cube(Color.magenta, Color.cyan, Color.orange)
        self._image_cube += (-0.5, -0.5, -0.5)
        self._image_accel = graph3d.Axis(Color.red, width = 2)
        self._image_gyro = graph3d.Axis(Color.blue, width = 2)
        self._image_magnet = graph3d.Axis(Color.white, width = 2) * (0.1, 0.1, 0.1)
        self._camera = graph3d.Camera()
        # setup camera to make image easier to understand
        # transformations for Mugic 1.0
        # self._image_cube *= (0.8, 0.5, 0.2)
        #self._camera.rotateX(-pi/2)
        #self._camera.rotateY(-pi)
        #self._camera.rotateZ(pi/2)
        #self._camera.rotateX(pi)
        # transformations for Mugic 2.0
        self._image_cube *= (0.5, 0.8, 0.2)
        self._camera.rotateX(-pi/2)
        self._camera["accel"] = self._image_accel
        self._camera["compass"] = self._image_magnet
        self._camera["gyro"] = self._image_gyro
        self._camera["cube"] = self._image_cube
        self._camera["axes"] = graph3d.Axes(Color.red, Color.green, Color.blue)

    def getImage(self, w=None, h=None, datagram=None):
        w, h = self._set_image_size(w, h)
        if not self._imu.dirty: return self._image
        try:
            _ = self._image_cube
        except AttributeError as e:
            if hasattr(self, "_image_cube"): raise AttributeError(e)
            self._init_image_cube()
            return self.getImage(w, h)
        self._image.fill(Color.black)
        if not self._imu.connected():
            pygame.draw.circle(self._image, (255, 0, 0), (w-w//16, h-h//16), max(w//32, 3))
            return self._image
        else:
            pygame.draw.circle(self._image, (0, 255, 0), (w-w//16, h-h//16), max(w//32, 3))
        # apply datagram transformations
        if datagram is None:
            datagram = self._imu.peekDatagram()
        if datagram is not None:
            data_quat = quat.Quaternion(
                    datagram['QW'],
                    datagram['QX'],
                    datagram['QY'],
                    datagram['QZ'])
            data_quat = data_quat.normalise()
            accel_data = quat.Vector(
                    _log_scale(datagram['AX']),
                    _log_scale(datagram['AY']),
                    _log_scale(datagram['AZ']))
            magnet_data = quat.Vector(
                    _log_scale(datagram['MX']),
                    _log_scale(datagram['MY']),
                    _log_scale(datagram['MZ']))
            gyro_data = quat.Vector(
                    _log_scale(datagram['GX']/60.0),
                    _log_scale(datagram['GY']/60.0),
                    _log_scale(datagram['GZ']/60.0))
            speed_data = [_log_scale(data / 3)
                             for data in (datagram['VX'], datagram['VY'], datagram['VZ'])]
            #print(quat.euler(data_quat))
            self._camera["accel"] = self._image_accel * accel_data
            self._camera["gyro"] = self._image_gyro * gyro_data
            self._camera["compass"] = self._image_magnet * magnet_data
            self._camera["cube"] = self._image_cube @ data_quat + speed_data
        self._camera.show(self._image)
        return self._image

    def _init_text(self):
        self._text = "No Connection"
        display_labels = ["quaternion", "euler", "accel", "gyro", "magnetometer", "velocity", "position", "battery", "frame", "calib"]
        self._format_text = '\n'.join(
            [value+": {}" for value in display_labels])

    def getText(self):
        if not self._imu.dirty: return self._text
        md = self._imu.peekDatagram()
        if md == None: return self._text
        quat = "{:>5.2f}, {:>5.2f}, {:>5.2f}, {:>5.2f}"\
                .format(md['QW'], md['QX'], md['QY'], md['QZ'])
        data_row = "{:>6.2f}, {:>6.2f}, {:>6.2f}"
        euler = data_row.format(md['EX'], md['EY'], md['EZ'])
        accel = data_row.format(md['AX'], md['AY'], md['AZ'])
        gyro = data_row.format(md['GX'], md['GY'], md['GZ'])
        mag = data_row.format(md['MX'], md['MY'], md['MZ'])
        battery = "{:.2f}".format(md['Battery'])
        seq = md['seqnum']
        speed = data_row.format(md['VX'], md['VY'], md['VZ'])
        position = data_row.format(md['X'], md['Y'], md['Z'])
        calib_status = ", ".join([a +\
                ("EWW" if b < 1.0 else "BAD" if b < 2.0 else "GUD" if b < 3.0 else "WOW")\
                for a, b in zip(["S:", "A:", "G:", "M:"],
                                [md[val] for val in
                                 ['calib_sys', 'calib_accel', 'calib_gyro', 'calib_mag']])])
        calib_status = "{"+calib_status+"}"
        self._text = self._format_text.format(quat, euler, accel, gyro,
                                        mag, speed, position, battery, seq, calib_status)
        return self._text

    @property
    def image(self):
        return self.getImage()

    @property
    def text(self):
        return self.getText()

# TESTING FUNCTIONS BELOW
def _recordMugicDevice(mugic, datafile, seconds=60):
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
    for datagram in reversed(mugic.popDatagrams(raw=True)):
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
    Window().rescale(*window_size)
    Window().name = "PyMugic IMU orientation visualization"
    display = pygame.display.get_surface()
    frames = 0
    ticks = pygame.time.get_ticks()
    # mugic display setup
    mugic_display = IMUDisplay(mugic_device)
    mugic_display.setImageSize(*window_size)
    # object setup
    display_screen = WindowScreen(*window_size)
    Window().addScreen(display_screen)
    fps_text = TextSprite()
    mugic_data_text = TextSprite()
    display_screen.addSprite(fps_text)
    display_screen.addSprite(mugic_data_text)
    fps_text.setFormatString("fps: {}")
    fps_text.setText("NOT CONNECTED").setFontSize(30)
    fps_text.moveTo(50, 50)
    mugic_data_text.setFormatString("{}")
    mugic_data_text.moveTo(50, 100)
    mugic_data_text.setFontSize(20)
    mugic_data_text.hide()
    display_screen._redraw()
    pygame.display.flip()
    # variables
    last_datagram = list()
    fps_value = 0
    # main loop
    while True:
        event = pygame.event.poll()
        if (event.type == pygame.QUIT or
            (event.type == pygame.KEYDOWN
             and event.key == pygame.K_ESCAPE)):
            break
        elif event.type == pygame.VIDEORESIZE:
            Window()._resize_window(event.w, event.h)
            mugic_device.dirty = True
        elif (event.type == pygame.KEYDOWN
              and event.key == pygame.K_f):
            mugic_data_text.toggleVisibility()
        state = pygame.key.get_pressed()
        rot_amount = pi/180
        if state[pygame.K_a]:
            mugic_display.rotateImageX(-rot_amount)
        elif state[pygame.K_d]:
            mugic_display.rotateImageX(rot_amount)
        if state[pygame.K_w]:
            mugic_display.rotateImageY(-rot_amount)
        elif state[pygame.K_s]:
            mugic_display.rotateImageY(rot_amount)
        if state[pygame.K_q]:
            mugic_display.rotateImageZ(-rot_amount)
        elif state[pygame.K_e]:
            mugic_display.rotateImageZ(rot_amount)
        elif state[pygame.K_z]:
            mugic_display.zoomImage(0.1)
        elif state[pygame.K_x]:
            mugic_display.zoomImage(-0.1)
        elif state[pygame.K_r]:
            mugic_display.resetImage()
        elif state[pygame.K_c]:
            mugic_device.calibrate(*last_datagram)
            frames = 0
            ticks = pygame.time.get_ticks() - 1

        next_datagram = mugic_device.next(raw=True)
        if next_datagram is not None and next_datagram.values() != last_datagram:
            last_datagram = list(next_datagram.values())
            frames += 1
            mugic_device.dirty = True
            fps_value = ((frames*1000)/(pygame.time.get_ticks()-ticks))

        if mugic_device.dirty:
            mugic_image = mugic_display.getImage()
            display_screen._redraw()
            mugic_image = pygame.transform.scale_by(mugic_image,
                                                 display_screen._scale)
            display.blit(mugic_image, (0, 0))
            mugic_data_text.setText(mugic_display.getText())
            mugic_device.dirty = False
        else:
            time.sleep(.01)
        fps_text.setText(round(fps_value, 3))
        pygame.display.flip()
    pygame.quit()


# MAIN FUNCTION - for use with testing / recording
# python mugic_helper.py [p|r] [datafile] [seconds]
if __name__ == "__main__":
    _, *args = sys.argv
    datafile = args[1] if len(args) >= 2 else "recording.txt"
    seconds = int(args[2]) if len(args) >= 3 else 10
    if len(args) == 0:
        mugic = MugicDevice(port=4000)
        _viewMugicDevice(mugic)
    elif 'r' in args[0]:
        mugic = MugicDevice(port=4000)
        _recordMugicDevice(mugic, datafile, seconds)
    elif 'p' in args[0]:
        mugic = MockMugicDevice(datafile=datafile)
        _viewMugicDevice(mugic)
    else:
        mugic = MugicDevice(port=4000)
        _viewMugicDevice(mugic)


