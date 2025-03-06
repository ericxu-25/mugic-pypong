# mugic_helper.py - module used for interfacing with mugic IMU
# portions of code borrowed from the pymugic module
# * https://github.com/amiguet/pymugic
# quaternion & 3d drawing module taken (and modified) from peter hinch
# * https://github.com/peterhinch/micropython-samples/blob/master/QUATERNIONS.md
# oscpy reference:
# * https://github.com/kivy/oscpy

# WISHLIST
# * implement reading from usb device

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

import argparse
import pygame
from mugic_pygame_helpers import Window, WindowScreen, TextSprite, Color
from threading import Timer

# helper functions
def _log_scale(number):
    sign = -1 if number < 0 else 1
    return (math.log(abs(number)+1)/3.0) * sign

def normalise_point(point):
    magnitude = math.sqrt(sum([p**2 for p in point]))
    return tuple([p/magnitude for p in point])

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
    )
    buffer_limit = 30
    # direction the IMU faces - for IMUDisplay
    orientation = (1, 0, 0)
    # the dimensions of the IMU - for IMUDisplay
    dimensions = (1, 1, 1)

    def __init__(self, buffer_size=10):
        self.dirty = False
        self._buffer_size = buffer_size
        self._reserve = None
        # maintain buffer size under buffer_limit (for speed)
        if buffer_size is None:
            self._reserve = deque()
            self._data = deque(maxlen=self.buffer_limit)
        elif buffer_size > self.buffer_limit:
            self._reserve = deque(maxlen=buffer_size)
            self._data = deque(maxlen=self.buffer_limit)
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
        calibrated_quat = (IMU.to_quaternion(self._zero).inverse()
                           * IMU.to_quaternion(datagram)).normalise()
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
            if raw: return datagrams[0].copy()
            return self._calibrate(datagrams[0].copy())
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

    def _parse_datagram(self, *values):
        values = [t(v) for t, v in zip(self.types, values)]
        datagram = dict(zip(self.datagram, values))
        datagram = self._update_state(datagram)
        return datagram

    def _callback(self, *values):
        datagram = self._parse_datagram(*values)
        self._data.appendleft(datagram)
        if self._reserve is not None:
            self._reserve.appendleft(datagram)
        self._dirty = True
        self._connected = True

    def connected(self):
        return self._connected

    def calibrate(self, *args, **kwargs):
        if len(self._data) != 0 and len(args) == 0:
            next_datagram = self.peekDatagram(raw=True)
            if next_datagram is None: return
            super().calibrate(**next_datagram)
        else:
            super().calibrate(*args, **kwargs)
        self._dirty = True

    # appends additional state data to each datagram
    def _update_state(self, datagram):
        now = time.time()
        self._state = datagram
        self._time_stamp = now
        return datagram

    def next(self, raw=False, smooth=6):
        next_datagram = self.peekDatagram(raw=raw, smooth=smooth)
        if raw: return next_datagram
        # check if there was a disconnect
        if self._next_datagram is not None and time.time() - self._last_datagram_time > 3:
            print("controller disconnected")
            self._connected = False
            self._dirty = True
            self._next_datagram = None
            self.popDatagrams()
            return None
        if next_datagram is None: return self._next_datagram
        if (self._next_datagram is None
            or next_datagram['seqnum'] > self._next_datagram['seqnum']):
            self._next_datagram = next_datagram
            self._last_datagram_time = time.time()
        return self._next_datagram.copy()

    @property
    def data(self):
        return self.next()

    # easy controller methods - query controller speed, gyro, facing
    def _moving(self, axis, direction=1, threshold=0.2, datagram=None):
        if datagram is None: datagram = self.next()
        if datagram is None: return False
        axis = 'AX' if axis == 0 else 'AY' if axis == 1 else 'AZ'
        if datagram[axis] * direction > threshold:
            return True
        return False

    def _rotating(self, axis, direction=1, threshold=80, datagram=None):
        if datagram is None: datagram = self.next()
        if datagram is None: return False
        axis = 'GX' if axis == 0 else 'GY' if axis == 1 else 'GZ'
        if datagram[axis] * direction > threshold:
            return True
        return False

    # using euler angles leads to gimbal lock problems...
    def _facing(self, axis, direction, threshold=45, datagram=None):
        if datagram is None:
            datagram = self.next()
        direction = (360 + direction%360) % 360
        if datagram is None: return False
        axis = 'EX' if axis == 0 else 'EY' if axis == 1 else 'EZ'
        angle = (int(datagram[axis]) + 360) % 360
        # angle = quat.euler(IMU.to_quaternion(datagram))[axis] * 180
        left  = (direction + 360 - threshold) % 360
        right = (direction + threshold) % 360
        if left > right:
            return left <= angle or angle <= right
        return angle >= left and angle <= right

    # converts the IMU's quaternion orientation to what point it is facing
    def _quat_facing(self, datagram):
        data_quat = IMU.to_quaternion(datagram).normalise()
        unit_vector = quat.Vector(*self.orientation) @ data_quat
        return unit_vector.xyz

    # alternative approach to facing using quaternions
    def _pointing(self, point, threshold=0.70, datagram=None, pointing_at=None):
        if pointing_at is None and datagram is None:
            datagram = self.next()
        if pointing_at is None:
            pointing_at = self._quat_facing(datagram)
        return self._pointing_at(point, pointing_at, threshold)

    # simple distance function based check
    def _pointing_at(self, p0, p1, threshold):
        distance = math.sqrt(sum([(v1-v2)**2 for v1,v2 in zip(p0,p1)]))
        return distance < threshold

    # interface methods
    def movingUp(self, **kwargs): return self._moving(1, 1, **kwargs)
    def movingDown(self, **kwargs): return self._moving(1, -1, **kwargs)
    def movingRight(self, **kwargs): return self._moving(2, 1, **kwargs)
    def movingLeft(self, **kwargs): return self._moving(2, -1, **kwargs)
    def movingForward(self, **kwargs): return self._moving(0, 1, **kwargs)
    def movingBackward(self, **kwargs): return self._moving(0, -1, **kwargs)

    def rotatingRight(self, **kwargs): return self._rotating(0, 1, **kwargs)
    def rotatingLeft(self, **kwargs): return self._rotating(0, -1, **kwargs)
    def rotatingUp(self, **kwargs): return self._rotating(1, 1, **kwargs)
    def rotatingDown(self, **kwargs): return self._rotating(1, -1, **kwargs)
    def twistingRight(self, **kwargs): return self._rotating(2, 1, **kwargs)
    def twistingLeft(self, **kwargs): return self._rotating(2, -1, **kwargs)

    # y axis facings
    def pitchingUp(self, **kwargs): return self._facing(1, 90, **kwargs)
    def pitchingDown(self, **kwargs): return self._facing(1, -90, **kwargs)
    def pitchingForward(self, **kwargs): return self._facing(1, 0, **kwargs)
    def pitchingBackward(self, **kwargs): return self._facing(1, 180, **kwargs)

    # x axis facings
    def yawingRight(self, **kwargs): return self._facing(0, 90, **kwargs)
    def yawingLeft(self, **kwargs): return self._facing(0, -90, **kwargs)
    def yawingForward(self, **kwargs): return self._facing(0, 0, **kwargs)
    def yawingBackward(self, **kwargs): return self._facing(0, 180, **kwargs)

    # z axis facings
    def rollingRight(self, **kwargs): return self._facing(2, 90, **kwargs)
    def rollingLeft(self, **kwargs): return self._facing(2, -90, **kwargs)
    def rollingUp(self, **kwargs): return self._facing(2, 0, **kwargs) # upside up
    def rollingDown(self, **kwargs): return self._facing(2, 180, **kwargs) # upside down

    # 6 points
    def pointingForward(self, **kwargs): return self._pointing((1, 0, 0), **kwargs)
    def pointingBackward(self, **kwargs): return self._pointing((-1, 0, 0), **kwargs)
    def pointingUp(self, **kwargs): return self._pointing((0, 0, 1), **kwargs)
    def pointingDown(self, **kwargs): return self._pointing((0, 0, -1), **kwargs)
    def pointingRight(self, **kwargs): return self._pointing((0, -1, 0), **kwargs)
    def pointingLeft(self, **kwargs): return self._pointing((0, 1, 0), **kwargs)

    def jolted(self, threshold=10):
        datagram = self.next()
        move_magnitude = math.sqrt(sum([a*a for a in IMU.accel(datagram)]))
        if move_magnitude > threshold: return True
        return False

    # combination functions
    def moving(self, text=False, **kwargs):
        if "datagram" not in kwargs: kwargs["datagram"] = self.next()
        moving_bits = 0
        if self.movingUp(**kwargs): moving_bits += 0b1
        if self.movingDown(**kwargs): moving_bits += 0b10
        if self.movingRight(**kwargs): moving_bits += 0b100
        if self.movingLeft(**kwargs): moving_bits += 0b1000
        if self.movingForward(**kwargs): moving_bits += 0b10000
        if self.movingBackward(**kwargs): moving_bits += 0b100000
        if text:
            return self._moving_to_text(moving_bits)
        return moving_bits

    @staticmethod
    def _moving_to_text(moving_bits):
        text = list()
        if moving_bits & (1<<0): text.append("UP")
        if moving_bits & (1<<1): text.append("DN")
        if moving_bits & (1<<2): text.append("RT")
        if moving_bits & (1<<3): text.append("LT")
        if moving_bits & (1<<4): text.append("FW")
        if moving_bits & (1<<5): text.append("BW")
        return text


    def rotating(self, text=False, **kwargs):
        if "datagram" not in kwargs: kwargs["datagram"] = self.next()
        rotating_bits = 0
        if self.rotatingUp(**kwargs): rotating_bits += 0b1
        if self.rotatingDown(**kwargs): rotating_bits += 0b10
        if self.rotatingRight(**kwargs): rotating_bits += 0b100
        if self.rotatingLeft(**kwargs): rotating_bits += 0b1000
        if self.twistingRight(**kwargs): rotating_bits += 0b10000
        if self.twistingLeft(**kwargs): rotating_bits += 0b100000
        if text:
            return self._rotating_to_text(rotating_bits)
        return rotating_bits

    @staticmethod
    def _rotating_to_text(rotating_bits):
        text = list()
        if rotating_bits & (1<<0): text.append("UP")
        if rotating_bits & (1<<1): text.append("DN")
        if rotating_bits & (1<<2): text.append("RT")
        if rotating_bits & (1<<3): text.append("LT")
        if rotating_bits & (1<<4): text.append("TR")
        if rotating_bits & (1<<5): text.append("TL")
        return text

    def pitching(self, text=False, **kwargs):
        if "datagram" not in kwargs: kwargs["datagram"] = self.next()
        pitching_bits = 0
        if self.pitchingUp(**kwargs): pitching_bits += 0b1
        if self.pitchingDown(**kwargs): pitching_bits += 0b10
        if self.pitchingForward(**kwargs): pitching_bits += 0b100
        if self.pitchingBackward(**kwargs): pitching_bits += 0b1000
        if text:
            return self._facings_to_text(pitching_bits)
        return pitching_bits

    def yawing(self, text=False, **kwargs):
        if "datagram" not in kwargs:
            kwargs["datagram"] = self.next()
        yawing_bits = 0
        if self.yawingRight(**kwargs): yawing_bits += 0b1
        if self.yawingLeft(**kwargs): yawing_bits += 0b10
        if self.yawingForward(**kwargs): yawing_bits += 0b100
        if self.yawingBackward(**kwargs): yawing_bits += 0b1000
        if text:
           return self._facings_to_text(yawing_bits)
        return yawing_bits

    def rolling(self, text=False, **kwargs):
        if "datagram" not in kwargs: kwargs["datagram"] = self.next()
        rolling_bits = 0
        if self.rollingRight(**kwargs): rolling_bits += 0b1
        if self.rollingLeft(**kwargs): rolling_bits += 0b10
        if self.rollingUp(**kwargs): rolling_bits += 0b100
        if self.rollingDown(**kwargs): rolling_bits += 0b1000
        if text:
            return self._facings_to_text(rolling_bits)
        return rolling_bits

    @staticmethod
    def _facings_to_text(facing_bits):
        text = list()
        if facing_bits & (1<<0): text.append("RT")
        if facing_bits & (1<<1): text.append("LT")
        if facing_bits & (1<<2): text.append("FW")
        if facing_bits & (1<<3): text.append("BW")
        return text

    # returns which quadrant is being pointed at
    def pointing(self, text=False, **kwargs):
        if "datagram" not in kwargs: kwargs["datagram"] = self.next()
        pointing_at = normalise_point(self._quat_facing(kwargs["datagram"]))
        if "pointing_at" not in kwargs: kwargs["pointing_at"] = pointing_at
        pointing_bits = 0
        if self.pointingUp(**kwargs): pointing_bits += 0b1
        if self.pointingDown(**kwargs): pointing_bits += 0b10
        if self.pointingRight(**kwargs): pointing_bits += 0b100
        if self.pointingLeft(**kwargs): pointing_bits += 0b1000
        if self.pointingForward(**kwargs): pointing_bits += 0b10000
        if self.pointingBackward(**kwargs): pointing_bits += 0b100000
        if text:
            return self._pointing_to_text(pointing_bits)
        return pointing_bits

    @staticmethod
    def _pointing_to_text(pointing_bits):
        text = list()
        if pointing_bits & (1<<0): text.append("UP")
        if pointing_bits & (1<<1): text.append("DN")
        if pointing_bits & (1<<2): text.append("RT")
        if pointing_bits & (1<<3): text.append("LT")
        if pointing_bits & (1<<4): text.append("FW")
        if pointing_bits & (1<<5): text.append("BW")
        return text

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
    )
    orientation  = (1, 0, 0)
    dimensions = (0.8, 0.5, 0.2)
    mugic_1_dimensions = (0.8, 0.5, 0.4)

    def __init__(self, port=4000, buffer_size=10, legacy=None):
        super().__init__(buffer_size)
        if legacy == True: # Mugic 1.0
            self.dimensions = self.mugic_1_dimensions
            self.legacy = True
        self.legacy = legacy
        self.port = port
        self._mugic_init()
        return

    def _update_state(self, datagram):
        datagram = super()._update_state(datagram)
        # Differences between Mugic 1.0 and Mugic 2.0
        # also - we fit the values to a different frame of reference
        if not self.legacy: # Mugic 2.0
            datagram['EZ'] = -datagram['EZ']
            datagram['GX'], datagram['GZ'] = -datagram['GZ'], datagram['GX']
        else: # Mugic 1.0 - yaw is inverted
            # ref: https://gamedev.stackexchange.com/questions/201977
            datagram['QZ'], datagram['QX'] = -datagram['QZ'], -datagram['QX']
            datagram['EY'] = -datagram['EY']
            datagram['GX'], datagram['GZ'] = datagram['GZ'], -datagram['GX']
        datagram['GY'] = -datagram['GY']
        return datagram

    def _mugic_init(self):
        # prepare for connection
        if self.port is None: return
        address = '0.0.0.0'
        self._osc_server = OSCThreadServer()
        self._socket = self._osc_server.listen(
                address=address, port=self.port, default=True)
        self._osc_server.bind(b'/mugicdata', self._callback)
        return

    def close(self):
        if not hasattr(self, '_osc_server'):
            return
        self._osc_server.stop_all()
        self._osc_server.terminate_server()

    def toggleLegacy(self):
        self.legacy = (bool) (not self.legacy)
        if self.legacy:
            self.dimensions = self.mugic_1_dimensions
        else:
            self.dimensions = self.__class__.dimensions

    def autoDetectMugicType(self):
        if not self.connected(): return
        md = self.next()
        if md is None: return
        # Mugic 1.0 has a crazy high mV value
        if md['mV'] > 100 and not self.legacy: self.toggleLegacy()
        elif md['mV'] < 100 and self.legacy: self.toggleLegacy()

    def __del__(self):
        self.close()
        return

    def __str__(self):
        mugic_str = "Mugic 1.0" if self.legacy else "Mugic 2.0"
        if not hasattr(self, '_osc_server'):
            return f"{mugic_str} Device @ nowhere"
        try:
            return f"{mugic_str} Device @ {self._socket.getsockname()}"
        except:
            return f"{mugic_str} Device @ {self.port}"

    def _smooth(self, datagrams, raw=False):
        ret_val = super()._smooth(datagrams, raw)
        ret_val['seqnum'] = datagrams[0]['seqnum']
        return ret_val

    def calibrate(self, *args, **kwargs):
        if self.legacy is None:
            self.autoDetectMugicType()
        super().calibrate(*args, **kwargs)
        # don't want to calibrate these values
        self._zero['Battery'] = 0
        self._zero['mV'] = 0
        self._zero['seqnum'] = 0
        self._zero['seconds'] = 0
        self._zero['calib_sys'] = 0
        self._zero['calib_accel'] = 0
        self._zero['calib_gyro'] = 0
        self._zero['calib_mag'] = 0

# mock mugic device - used to simulate a mugic device
class MockMugicDevice(MugicDevice):
    def __init__(self, port=4000, datafile=None, legacy=None):
        super().__init__(port, legacy)
        self._reserve = None
        self._data = deque()
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
        if datagram is None: return False
        elapsed = time.time() - self._start_time + self._base_time/1000
        datagram_time = datagram['seconds']/1000
        if elapsed < datagram_time: return False
        self._connected = True
        self._dirty = True
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

    def next(self, *args, **kwargs):
        ret_val = super().next(*args, **kwargs)
        if self._datagram_is_ready(ret_val):
            self.popDatagram()
        return ret_val

    def sendData(self, datafile):
        print(f"{self}: sending data in file", datafile)
        for data in open(datafile, 'r'):
            values = [t(v) for t, v in zip(MugicDevice.types,
                                           data.split(','))]
            if self.port is None:
                self._callback(*values)
            else:
                self._osc_client.send_message(b'/mugicdata', values)
        self._base_time = self._data[-1]["seconds"]
        print(f"{self}: completed sending", datafile)
        self._start_time = time.time()

    def __str__(self):
        return "Mock " + super().__str__()

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
        if w is None and h is None:
            return self._image_size
        use_new_surface = False
        if w is None: w = self._image_size[0]
        elif w != self._image_size[0]:
            self._image_size = (w, self._image_size[1])
            use_new_surface = True
        if h is None: h = self._image_size[1]
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
            self._init_image_objects()
        self._imu.dirty = True

    def rotateImageY(self, angle=1):
        try:
            self._camera.rotateY(angle)
        except AttributeError:
            self._init_image_objects()
        self._imu.dirty = True

    def rotateImageZ(self, angle=1):
        try:
            self._camera.rotateZ(angle)
        except AttributeError:
            self._init_image_objects()
        self._imu.dirty = True

    def zoomImage(self, distance):
        try:
            self._camera.zoom(distance)
        except AttributeError:
            self._init_image_objects()
        self._imu.dirty = True

    def resetImage(self):
        del self._image_cube
        self._init_image_objects()
        self._imu.dirty = True

    def _init_image_objects(self):
        if hasattr(self, '_image_cube'): return
        # objects to draw
        self._image_cube = graph3d.Cube(Color.magenta, Color.cyan, Color.orange)
        self._image_cube += (-0.5, -0.5, -0.5)
        self._image_accel = graph3d.Axis(Color.red, width = 2)
        self._image_gyro = graph3d.Axis(Color.blue, width = 2)
        self._image_magnet = graph3d.Axis(Color.white, width = 2) * (0.1, 0.1, 0.1)
        self._image_facing = graph3d.Axis(Color.magenta, width = 2, p1=self._imu.orientation)
        self._image_axes = graph3d.PositiveAxes(Color.red, Color.green, Color.blue)
        # camera initialization
        self._camera = graph3d.Camera()
        # orient to the right direction
        o = self._imu.orientation
        #self._camera.crot *= quat.Rotator(pi/2, o[1], o[2], o[0])
        #self._camera.crot *= quat.Rotator(pi/2, o[2], o[0], o[1])
        # apply a slight tilt so you can see all the axes
        self._camera.crot *= quat.Rotator(-pi/4, 1, 1, 1)
        self._camera["accel"] = self._image_accel
        self._camera["compass"] = self._image_magnet
        self._camera["gyro"] = self._image_gyro
        self._camera["facing"] = self._image_facing
        self._camera["cube"] = self._image_cube
        self._camera["axes"] = self._image_axes

    def getImage(self, w=None, h=None, datagram=None):
        w, h = self._set_image_size(w, h)
        if not self._imu.dirty: return self._image
        try:
            _ = self._image_cube
        except AttributeError as e:
            if hasattr(self, "_image_cube"): raise AttributeError(e)
            self._init_image_objects()
            return self.getImage(w, h)
        self._image.fill(Color.black)
        if not self._imu.connected():
            pygame.draw.circle(self._image, (255, 0, 0), (w-w//16, h-h//16), max(w//32, 3))
            self._camera.show(self._image, "axes")
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
            #print(quat.euler(data_quat))
            #data_quat = data_quat.normalise() # cause
            self._camera["accel"] = self._image_accel * accel_data
            self._camera["gyro"] = self._image_gyro * gyro_data
            self._camera["compass"] = self._image_magnet * magnet_data
            self._camera["cube"] = self._image_cube * self._imu.dimensions\
                    @ data_quat
            self._camera["facing"] = self._image_facing @ data_quat
        self._camera.show(self._image)
        return self._image

    def _init_text(self):
        self._text = "No Connection"
        self._action_text = "No Connection"
        data_labels= ["quaternion", "euler", "accel",
                      "gyro", "magnetometer",
                      "battery", "frame", "calib (SAGM)"]
        self._data_format_text = '\n'.join(
            [value+": {}" for value in data_labels])
        self._action_format_text = "Moving: {}\nRotating: {}\n"
        self._action_format_text += "Pointing: {:3s} Yaw {:3s} Pitch {:3s} Roll {:3s}"

    def getDataText(self):
        if not self._imu.dirty: return self._text
        md = self._imu.next(raw=False)
        if md is None: return self._text
        quat = "{:>5.2f}, {:>5.2f}, {:>5.2f}, {:>5.2f}"\
                .format(md['QW'], md['QX'], md['QY'], md['QZ'])
        data_row = "{:>6.2f}, {:>6.2f}, {:>6.2f}"
        euler = data_row.format(md['EX'], md['EY'], md['EZ'])
        accel = data_row.format(md['AX'], md['AY'], md['AZ'])
        gyro = data_row.format(md['GX'], md['GY'], md['GZ'])
        mag = data_row.format(md['MX'], md['MY'], md['MZ'])
        battery_and_mv = "{:5.2f} {}mV".format(
                md['Battery'], md['mV'])
        frame = md['seqnum']
        calib_status = " & ".join(
                [":(" if md[c] < 1.0 else ":|" if md[c] < 2.0 else ":)" if md[c] < 3.0 else ":D"
                for c in ['calib_sys', 'calib_accel', 'calib_gyro', 'calib_mag']])
        self._text = self._data_format_text.format(quat, euler, accel, gyro,
                                                   mag, battery_and_mv, frame, calib_status)
        self._text = str(self._imu) + '\n' + self._text
        return self._text

    def getActionText(self):
        if not self._imu.dirty: return self._action_text
        datagram = self._imu.next(raw=False)
        if datagram is None: return self._action_text
        moving = ", ".join(self._imu.moving(text=True, datagram=datagram))
        rotating = ", ".join(self._imu.rotating(text=True, datagram=datagram))
        yawing = ", ".join(self._imu.yawing(text=True, datagram=datagram))
        pitching = ", ".join(self._imu.pitching(text=True, datagram=datagram))
        rolling = ", ".join(self._imu.rolling(text=True, datagram=datagram))
        pointing = ", ".join(self._imu.pointing(text=True, datagram=datagram))
        self._action_text = self._action_format_text.format(moving, rotating,
                                                            pointing, yawing,
                                                            pitching, rolling)
        return self._action_text


    @property
    def image(self):
        return self.getImage()

    @property
    def text(self):
        return self.getDataText() + "\n" + self.getActionText()

# TESTING FUNCTIONS BELOW
def _recordMugicDevice(mugic, datafile, seconds=60):
    print("waiting for mugic to be connected...")
    total_wait_time = 0
    wait_period = 0.5
    while not mugic.connected():
        time.sleep(wait_period)
        total_wait_time += wait_period
        if total_wait_time > 60:
            print("aborting... waited too long!")
            return
    print("Recording", mugic, "for the next", seconds, "seconds...")
    file = open(datafile, "w")
    recordTimer = Timer(
            seconds,
            lambda: _write_recorded_data(mugic, file))
    recordTimer.start()
    return

def _write_recorded_data(mugic, file):
    store = mugic._reserve if mugic._reserve is not None else mugic._data
    print("preparing to write", len(store), "datagrams...")
    for datagram in reversed(list(store)):
        datagram = MugicDevice._datagram_to_string(datagram)
        # print("writing datagram:", datagram)
        file.write(datagram+'\n')
    print("Recording complete")
    file.close()

def _viewMugicDevice(mugic_device):
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
    mugic_movement_text= TextSprite()
    display_screen.addSprite(fps_text)
    display_screen.addSprite(mugic_data_text)
    display_screen.addSprite(mugic_movement_text)
    fps_text.setFormatString("fps: {}")
    fps_text.setText("NOT CONNECTED").setFontSize(30)
    fps_text.moveTo(50, 50)
    mugic_data_text.setFormatString("{}").moveTo(50, 100).setFontSize(20).hide()
    mugic_movement_text.setFormatString("{}").moveTo(50, 350).setFontSize(20).hide()
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
            Window().quit()
            break
        elif event.type == pygame.VIDEORESIZE:
            Window()._resize_window(event.w, event.h)
            mugic_device.dirty = True
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_f:
                mugic_data_text.toggleVisibility()
            elif event.key == pygame.K_g:
                mugic_movement_text.toggleVisibility()
            elif event.key == pygame.K_l:
                mugic_device.toggleLegacy()
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
            if mugic_device.legacy is None:
                mugic_device.autoDetectMugicType()

        if mugic_device.dirty:
            mugic_image = mugic_display.getImage()
            display_screen._redraw()
            mugic_image = pygame.transform.scale_by(mugic_image,
                                                 display_screen._scale)
            display.blit(mugic_image, (0, 0))
            if mugic_data_text.visible:
                mugic_data_text.setText(mugic_display.getDataText())
            if mugic_movement_text.visible:
                mugic_movement_text.setText(mugic_display.getActionText())
            mugic_device.dirty = False
        else:
            time.sleep(.01)
        fps_text.setText(round(fps_value, 3))
        pygame.display.flip()
    pygame.quit()


# MAIN FUNCTION - for use with testing / recording
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=int, default=4000, nargs="?",
                        help="port of the mugic device to connect to, default 4000")
    parser.add_argument('-p', '--playback', action='store_true',
                        help="playback mugic device data from a file")
    parser.add_argument('-r', '--record', action='store_true',
                        help="record mugic device data to a file")
    parser.add_argument('-s', '--seconds', type=int, default=10,
                        help="amount of seconds to record")
    parser.add_argument('-d', '--datafile', default="recording.txt",
                        help="datafile to playback/record to")
    parser.add_argument('-l', '--legacy', action='store_true',
                        help="flag to use Mugic 1.0")
    args = parser.parse_args()
    mugic = None
    legacy = True if args.legacy else None
    if args.record:
        mugic = MugicDevice(port=args.port, buffer_size=None, legacy=legacy)
        _recordMugicDevice(mugic, args.datafile, args.seconds)
    if args.playback:
        mugic = MockMugicDevice(datafile=args.datafile, legacy=legacy)
    if mugic is None:
        mugic = MugicDevice(port=args.port, legacy=legacy)
    print(mugic)
    print("Running mugic_helper display...")
    print("== Instructions ==")
    print("* use QEWASDZX to orient the view")
    print("* C to zero the values, R to reset orientation")
    print("* F to show raw values, G to show interpreted movements")
    print("* L to switch between Mugic 1.0 and Mugic 2.0")
    _viewMugicDevice(mugic)


if __name__ == "__main__":
    main()
