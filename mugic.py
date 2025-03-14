"""
mugic.py - python module used for interfacing with mugic IMU

ABOUT THE DEVELOPERS
    Team Mugical - UCI Informatics Senior Capstone Group, 2024-2025
    * Members: Eric Xu, Melody Chan-Yoeun, Bryan Matta Villatoro,
               Shreya Padisetty, Aj Singh
    * Project Sponsor: Mari Kimura, MugicMotion

CREDITS
    quaternion & 3d drawing module written by peter hinch (and modified by us)
    * https://github.com/peterhinch/micropython-samples/blob/master/QUATERNIONS.md
    inspiration for the visualizations and some code borrowed from the pymugic module
    * https://github.com/amiguet/pymugic

RESOURCES
    oscpy
    * https://github.com/kivy/oscpy
    mugic
    * https://mugic-motion.gitbook.io/mugic-r-documentation
    github repo
    * https://github.com/ericxu-25/mugic-pypong

QUICKSTART
    * see the mugic_helper.py file for a basic example
    * play our example project - pypong.py!

TODO:
    * implement reading from usb device
    * improve _update_frame for motion interpretation
    * add more robust interpretations to IMUController

WARNINGS:
    Testing was only performed with the Mugic 1.0 and 2.0 devices. The IMU and IMUController
    classes will need to be modified if you plan to utilize them with a different controller.
"""

#########################################
#           IMPORTS & HELPERS           #
#########################################
# IMPORTS
import oscpy as osc
from oscpy.server import OSCThreadServer
from oscpy.client import OSCClient
import time
import math
from math import pi, isclose
from collections import deque
import quaternion.quat as quat
import quaternion.vector as vec
import quaternion.graph3d as graph3d
from array import array
from threading import Timer

# HELPERS
def sign(number):
    return -1 if number < 0 else 1

def points_are_close(p0, p1, threshold):
    """returns if two points are closer together than a threshold value"""
    distance = math.sqrt(sum([(v1-v2)**2 for v1,v2 in zip(p0,p1)]))
    return distance < threshold

#########################################
#             BASE CLASSES              #
#########################################

class IMU:
    """An interface class for an IMU (intertial measurement unit) that handles datagram processing

    The IMU class packages datagrams received from an IMU device as a dictionary of key value pairs
    and stores them into a working deque buffer. It assumes a 9 axis data structure and provides methods
    to work with a continuous stream of IMU input.

    Class Attributes:
        types (list of types): list of types matching the datagram
        datagram (list of str): list of labels for each data item from the IMU
        buffer_limit (int): maximum allowed working buffer size
        orientation ((int) * 3): direction that the IMU points; Z axis is vertical
        dimensions ((int) * 3): dimension ratios of the IMU; default is a cube

    Attributes:
        _last_datagram_time (float): timestamp of the most recent datagram
        _data (deque of dicts): working deque buffer for IMU datagrams
        _reserve (None or dequeu of dicts): reserve deque for persistent datagram storage
        _zero (dict): reserve deque for persistent datagram storage

    """
    types = [float] * 25
    datagram = (
        'AX', 'AY', 'AZ', # Accelerometer
        'EX', 'EY', 'EZ', # Euler angles
        'GX', 'GY', 'GZ', # Gyrometer
        'MX', 'MY', 'MZ', # Magnetometer
        'QW', 'QX', 'QY', 'QZ', # Quaternion angles
    )
    buffer_limit = 30
    orientation = (1, 0, 0)
    dimensions = (1, 1, 1)

    def __init__(self, buffer_size=10):
        """initializes the deque for the IMU Device

        Args:
            buffer_size (int or None): length of the deque to use to store the IMU datagrams.
                If buffer_size is None or exceeds the maximum buffer_limit, then a separate reserve
                deque is created to ensure the working deque is manageable.

        """
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
        self._last_datagram_time = 0.0

    @property
    def dirty(self):
        """updated status of the data in the IMU

        dirty is set to True whenever new data is received. Or a change
        to how datagrams are returned are detected. This value is never
        set to False by any class methods; it is up to the user to query this
        value and manually set dirty to False after finishing with a data item.

        """
        return self._dirty

    @dirty.setter
    def dirty(self, val):
        self._dirty = bool(val)

    def _update_state(self, datagram):
        """overridable method called when updating an incoming datagram"""
        return datagram

    def _parse_datagram(self, *values):
        """constructs a datagram (dict) given a list of raw values"""
        values = [t(v) for t, v in zip(self.types, values)]
        datagram = dict(zip(self.datagram, values))
        return datagram

    def _add_datagram(self, datagram):
        """pushes the passed in datagram onto the data queue and updates dirty status"""
        datagram = self._update_state(datagram)
        self._data.appendleft(datagram)
        if self._reserve is not None:
            self._reserve.appendleft(datagram)
        self._dirty = True

    def peekDatagram(self, raw=False, smooth=3):
        """Returns the next datagram on the deque.

        Args:
            raw (bool): whether the next datagram returned is zeroed or not
            smooth (int): how many datagrams to average over

        Returns:
            None if there was no datagram, otherwise a copy of the datagram on the deque
        """

        if len(self._data) == 0: return None
        if not smooth or smooth <= 1:
            datagrams = [self._data[-1].copy()]
        else:
            datagrams = [self._data[-i-1].copy() for i in range(min(len(self._data), smooth))]
        return self._smooth(datagrams, raw)

    def popDatagram(self, raw=False, smooth=3):
        """Pops and returns the next datagram on the deque

        Note that the deque data structure automatically pops data from
        the other end when it is full.

        Args:
            raw (bool): whether the next datagram returned is zeroed or not
            smooth (int): how many datagrams to average over

        Returns:
            None if there was no datagram, otherwise a copy of the popped datagram
        """

        if len(self._data) == 0: return None
        datagrams = [self._data.pop()]
        if not smooth or smooth <= 1:
            return self._smooth(datagrams, raw)
        for i in range(smooth):
            if i+1 > len(self._data): break
            datagrams.append(self._data[-i-1])
        return self._smooth(datagrams, raw)

    def popDatagrams(self, raw=False):
        """Pops and returns ALL the datagrams from the deque, without smoothing

        Args:
            raw (bool): whether the next datagrams returned are zeroed or not

        Returns:
            a list of each of the datagrams
        """

        datagrams = self._data.copy()
        self._data.clear()
        if raw: return list(datagrams)
        return [self._calibrate(d) for d in datagrams]

    def refresh(self):
        """Removes all but the most recent datagram from the data queue.

        Returns:
            None if there were no datagrams, else the most recent datagram
        """
        if len(self._data) == 0: return None
        last_datagram = self._data[0]
        self._data.clear()
        if self._reserve is not None:
            self._reserve.clear()
        self._add_datagram(last_datagram)
        return last_datagram

    def zero(self, *args, **kwargs):
        """Updates the zero values of the IMU; used for calibration

        Args:
            *args: list of values corresponding to datagram values
            *kwargs: items to update the zero values to
        """
        self._zero = dict()
        for key in IMU.datagram:
            self._zero[key] = 0
        self._zero['QW'] = 1
        if len(args) != 0:
            for key, arg in zip(self.datagram, args):
                self._zero[key] = arg
        self._zero.update(kwargs)

    def calibrate(self, *args, **kwargs):
        """Updates the zero values of the IMU; ignores certain values"""
        self.zero(*args, **kwargs)
        # don't zero magnetometer
        self._zero['MX'] = 0
        self._zero['MY'] = 0
        self._zero['MZ'] = 0
        # don't zero accelerometer
        self._zero['AX'] = 0
        self._zero['AY'] = 0
        self._zero['AZ'] = 0

    def _calibrate(self, datagram):
        """Uses the zero values of the IMU to zero/calibrate a datagram"""
        calibrated_quat = (IMU.to_quaternion(self._zero).inverse()
                           * IMU.to_quaternion(datagram)).normalise()
        for key, value in self._zero.items():
            datagram[key] -= value
        datagram['QW'] = calibrated_quat.w
        datagram['QX'] = calibrated_quat.x
        datagram['QY'] = calibrated_quat.y
        datagram['QZ'] = calibrated_quat.z
        datagram['EX'] = (datagram['EX'] + 360) % 360
        datagram['EY'] = (datagram['EY'] + 360) % 360
        datagram['EZ'] = (datagram['EZ'] + 360) % 360
        return datagram

    # returns smoothed datagram via moving average
    # might want to look into madgwick/kalman filter in the future?
    def _smooth(self, datagrams, raw=False):
        """Returns a smoothed datagram using moving average

        Args:
            datagrams (list): list of datagrams to smooth
            raw (bool): if True, won't calibrate datagrams

        Returns:
            averaged datagram from list of datagrams, or None if there were none.
        """
        if len(datagrams) == 0: return None
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
        """creates a quaternion from the datagram values"""
        if datagram['QW'] == 0: return quat.Quaternion(1, 0, 0, 0)
        return quat.Quaternion(datagram['QW'], datagram['QX'],
                               datagram['QY'], datagram['QZ'])

    @staticmethod
    def _datagram_to_string(datagram):
        """Transforms a datagram to a simple comma separated string"""
        data_string = ",".join([str(v) for v in datagram.values()])
        return data_string

    @staticmethod
    def lerp(d1, d2, ratio=0.5):
        """lerps between two datagrams"""
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
        """extracts the accelerometer data from the datagram"""
        if datagram is None: return None
        return vec.Vector(datagram['AX'], datagram['AY'], datagram['AZ'])

    def absoluteAccel(self, datagram, raw=False):
        """calculates the absolute accelerometer data from the datagram

        Args:
            datagram (dict): datagram with raw relative accelerometer data
            raw (bool): if True, will not zero datagram values to zero heading
        """
        if datagram is None: return None
        quat_rot = IMU.to_quaternion(datagram)
        accel = IMU.accel(datagram)
        if not raw:
            # aligns the absolute accelerometer data to zero heading
            zero_heading = quat.Rotator(pi/180 * self._zero['EX'], 0, 0, 1)
            accel @= zero_heading
        return vec.Vector(*(accel @ quat_rot).xyz)

    @staticmethod
    def gyro(datagram):
        """extracts the gyrometer data from the datagram"""
        if datagram is None: return None
        return  vec.Vector(datagram['GX'], datagram['GY'], datagram['GZ'])

    def absoluteGyro(self, datagram, raw=False):
        """calculates the absolute gyrometer data from the datagram

        Args:
            datagram (dict): datagram with raw relative gyrometer data
            raw (bool): if True, will not zero datagram values to zero heading
        """
        if datagram is None: return None
        quat_rot = IMU.to_quaternion(datagram)
        gyro = IMU.gyro(datagram)
        if not raw:
            zero_heading = quat.Rotator(pi/180 * self._zero['EX'], 0, 0, 1)
            gyro @= zero_heading
        return vec.Vector(*(gyro @ quat_rot).xyz)

    @staticmethod
    def mag(datagram):
        """extracts the magnetometer data from the datagram"""
        if datagram is None: return None
        return  vec.Vector(datagram['MX'], datagram['MY'], datagram['MZ'])

    @staticmethod
    def quat(datagram):
        """extracts the quaternion from the datagram"""
        if datagram is None: return None
        return IMU.to_quaternion(datagram)

    @staticmethod
    def euler(datagram):
        """extracts the euler orientation from the datagram"""
        if datagram is None: return None
        return vec.Vector(datagram['EX'], datagram['EY'], datagram['EZ'])

    def _pointing_at(self, datagram):
        """converts the IMU's quaternion orientation to what point it is facing on a unit sphere"""
        if datagram is None: return (0, 0, 0)
        data_quat = IMU.to_quaternion(datagram).normalise()
        unit_vector = quat.Vector(*self.orientation) @ data_quat
        return vec.Vector(*unit_vector.xyz)

    def pointingAt(self, datagram=None):
        """returns where the IMU is pointing at on a unit sphere

            Args:
                datagram (dict): optional datagram to use. If not provided, defaults to the next datagram
        """
        if datagram is None: datagram = self.peekDatagram()
        return self._pointing_at(datagram)


class IMUController(IMU):
    """Extension of the IMU class which provides interpretation, connection status, and a simpler interface.

    Note:
        The additional attributes in this class are used for acceleration frame (movement)
        interpretation only.

    Class Attributes:
        _accel_delta (int): assumed max acceleration noise between each datagram
        _accel_low_pass (array('f', [int]*3)): accelerometer upper/lower limit for each axis
        _max_frame_size (int): assumed maximum duration of each movement frame in seconds

    """
    # configuration values used for basic frame interpretation
    _accel_delta = 2
    _accel_low_pass = array('f', [3, 5, 5])
    _max_frame_size = 2

    def __init__(self, buffer_size=10):
        super().__init__(buffer_size)
        self._last_datagram = None
        self._init_frame_data()

    def _init_frame_data(self):
        """initializes the data items used internally for movement frame interpretation"""
        self._rising_accel = vec.Vector(0, 0, 0)
        self._falling_accel = vec.Vector(0, 0, 0)
        self._last_accel = vec.Vector(0, 0, 0)
        self._last_accel_derivative = vec.Vector(0, 0, 0)
        self._last_accel_frame = [(0,0)] * 3
        self._last_frame_update = time.time()

    def _update_frame(self, datagram):
        """updates the last movement frame based on passed in datagrams

         Frame is the overall movement of the device; which can then be used as psuedo-velocity
         my algorithm isn't perfect... but it works okay. The working principle for the algorithm
         is that we identify pairs of opposite accelerometer values (accelerating and decelerating)
         aka the rising and falling edge - which can be interpreted as movement in one direction.

         For a more intuitive understanding of this, pay attention to the accelerometer graph values
         for Z (blue) when moving the sensor up and down.
        """
        # saves accelerometer max and min values
        accel = self.absoluteAccel(datagram)
        accel_magnitude = abs(accel)
        # detect peaks and valleys by finding where the derivative changes directions
        accel_derivative = accel - self._last_accel
        accel_derivative_long = (accel_derivative + self._last_accel_derivative)/2
        self._last_accel_derivative = accel_derivative
        self._last_accel = accel
        for i in range(3):
            # skip edge if value is negligible
            if abs(accel[i]) < self._accel_low_pass[i]:
                continue
            # skip if not a major component of the motion
            if abs(accel[i]) < accel_magnitude // 9:
                continue
            # reset rising/falling if expired or start of a new edge
            if (time.time()-self._last_frame_update > self._max_frame_size or
                not (self._rising_accel[i] == 0 or self._falling_accel[i] == 0)):
                self._rising_accel[i] = 0
                self._falling_accel[i] = 0
                self._last_frame_update = time.time()
            # skip if value is not a peak/valley
            if not (isclose(accel_derivative[i], 0, abs_tol=self._accel_delta) or
                    isclose(accel_derivative_long[i], 0, abs_tol=self._accel_delta)):
                continue
            # update rising and falling accel values
            if self._rising_accel[i] == 0:
                self._rising_accel[i] = accel[i]
                self._last_frame_update = time.time()
            elif self._falling_accel[i] == 0:
                # skip if value is in the same direction as rising, or just too close
                if sign(accel[i]) == sign(self._rising_accel[i]):
                    continue
                if isclose(accel[i], self._rising_accel[i], abs_tol=self._accel_low_pass[i]):
                    continue
                self._falling_accel[i] = accel[i]
                self._last_accel_frame[i] = (self._rising_accel[i], time.time()-self._last_frame_update)

    def _callback(self, *values):
        """callback method used when receiving a datagram from the IMU"""
        datagram = self._parse_datagram(*values)
        super()._add_datagram(datagram)

    # called when processing an incoming datagram
    def _update_state(self, datagram):
        """overridable method called when updating an incoming datagram"""
        super()._update_state(datagram)
        self._update_frame(datagram)
        return datagram

    def next(self, raw=False, smooth=6):
        """returns the next datagram from the controller

        Note that we never explicitly pop a datagram since the deque data
        structure does that for us when the deque fills up. This function
        is an extension of peekDatagram that also updates connection status

        Args:
            raw (bool): if True, doesn't zero the datagram
            smooth (int): how many datagrams to smooth over

        Returns:
            The next datagram on the deque, or None if unavailable.
        """
        next_datagram = self.peekDatagram(raw=raw, smooth=smooth)
        if next_datagram is None: return self._last_datagram
        # check if the next datagram is new
        if (self._last_datagram is None
            or next_datagram != self._last_datagram):
            self._last_datagram = next_datagram
            self._last_datagram_time = time.time()
        return self._last_datagram.copy()

    @property
    def data(self):
        """returns the next datagram"""
        return self.next()

    def getFrame(self):
        """returns the last movement frame"""
        return [a*dt for a, dt in self._last_accel_frame]

    def resetFrame(self):
        """clears the last movement frame"""
        self._last_accel_frame = [(0,0)] * 3

    @property
    def movement(self):
        """alias for getFrame()"""
        return self.getFrame()

    def connected(self):
        """queries and returns connection status"""
        self.next()
        if time.time() - self._last_datagram_time > 5:
            self._last_datagram = None
            return False
        return True

    def calibrate(self, *args, **kwargs):
        """calibrates using passed in args OR the next datagram and resets the movement frame"""
        if len(self._data) != 0 and len(args) == 0:
            next_datagram = self.peekDatagram(raw=True)
            if next_datagram is None: return
            super().calibrate(**next_datagram)
        else:
            super().calibrate(*args, **kwargs)
        self.resetFrame()

    # easy controller methods - query controller speed, gyro, facing
    def _moving(self, axis, direction=1, threshold=0.1, datagram=None):
        """returns if the IMU was moving along an axis

        This method does not reset the last movement frame - that must be done manually once the
        movement has been processed.

        Args:
            axis (int): axis of movement to query
            direction (-1 or 1): direction along the axis
            threshold (float): threshold of the movement to consider

        Returns:
            True if the controller's last movement frame did correspond with the passed in information
        """

        if datagram is None: datagram = self.next()
        if datagram is None: return False
        #axis = 'AX' if axis == 0 else 'AY' if axis == 1 else 'AZ'
        if self.getFrame()[axis] * direction > threshold:
            return True
        return False

    def _rotating(self, axis, direction=1, threshold=80, datagram=None):
        """returns if the IMU was rotating along an axis

        Args:
            axis (int): axis of movement to query
            direction (-1 or 1): direction along the axis
            threshold (float): threshold of the rotation to consider

        Returns:
            True if the controller's gyroscope did reflect a rotation along the axis of the specified
            magnitude
        """

        if datagram is None: datagram = self.next()
        if datagram is None: return False
        axis = 'GX' if axis == 0 else 'GY' if axis == 1 else 'GZ'
        if datagram[axis] * direction > threshold:
            return True
        return False

    def _facing(self, axis, direction, threshold=45, datagram=None):
        """returns if the IMU is facing towards the direction along an axis

        Note that using euler angles leads to gimbal lock problems... specifically with the Y axis

        Args:
            axis (int): axis to query facing on
            direction (-1 or 1): direction along the axis
            threshold (float): how far below or above the target angle is considered valid

        Returns:
            True if the controller's euler readings show the controller is facing in the right
            direction.
        """

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

    def _pointing(self, point, threshold=0.70, datagram=None, pointing_at=None):
        """returns if the IMU is pointing towards a given point on a unit sphere

        an alternative approach to facing using quaternions, more useful for controls

        Args:
            point (int *3): point on the unit sphere to check
            threshold (float): how far away from the target point is still considered valid
            datagram (dict): optional datagram to check; if None, uses the next datagram
            pointing_at (int * 3): optional provided point to check with. If provided, skips
                datagram processing

        Returns:
            True if where the IMU is pointing is close to the target point
        """

        if pointing_at is None and datagram is None:
            datagram = self.next()
            if datagram is None: return False
        if pointing_at is None:
            pointing_at = self._pointing_at(datagram)
        return points_are_close(point, pointing_at, threshold)


    # interface methods
    def movingUp(self, **kwargs): return self._moving(2, 1, **kwargs)
    def movingDown(self, **kwargs): return self._moving(2, -1, **kwargs)
    def movingRight(self, **kwargs): return self._moving(1, -1, **kwargs)
    def movingLeft(self, **kwargs): return self._moving(1, 1, **kwargs)
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

    def jolted(self, threshold=10, datagram=None):
        """Returns True if the magnitude of acceleration is over a threshold value"""
        if datagram is None:
            datagram = self.next()
            if datagram is None: return False
        if abs(self.accel(datagram)) > threshold: return True
        return False

    # combination functions
    def moving(self, text=False, **kwargs):
        """Returns bits or a list of strings corresponding to overall sensor movement"""
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
        """Returns bits or a list of strings corresponding to overall sensor rotation"""
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
        """Returns bits or a list of strings corresponding to sensor pitch facing"""
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
        """Returns bits or a list of strings corresponding to sensor yaw facing"""
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
        """Returns bits or a list of strings corresponding to sensor roll facing"""
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
        """Returns which directions (up, down, right, left, forward, backward) the sensor is pointing.

        Returns as as bits or a list of strings
        """

        if "datagram" not in kwargs: kwargs["datagram"] = self.next()
        pointing_at = self._pointing_at(kwargs["datagram"]).normalise()
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

    # acceleration in the direction of pointing
    def thrustAccel(self, datagram):
        if datagram is None: datagram = self.next()
        if datagram is None: return (0, 0, 0)
        return datagram['AX']
        #return self.accel(datagram).scalar_project(self._pointing_at(datagram))

    # acceleration not in the direction of pointing
    def swingAccel(self, datagram):
        if datagram is None: datagram = self.next()
        if datagram is None: return (0, 0, 0)
        return (datagram['AY'] + datagram['AZ'])/2
        #return (abs(self.accel(datagram)) - self.thrustAccel(datagram)) / 2.0

    # adjusted relative rotation values
    def forwardRotation(self, datagram):
        if datagram is None: datagram = self.next()
        if datagram is None: return 0
        return abs(datagram['GY'])

    def twistingRotation(self, datagram):
        if datagram is None: datagram = self.next()
        if datagram is None: return 0
        return abs(datagram['GX'])

    def turningRotation(self, datagram):
        if datagram is None: datagram = self.next()
        if datagram is None: return 0
        return abs(datagram['GZ'])

class MugicDevice(IMUController):
    # Datagram signature
    types = [float if t == 'f' else int for t in 'fffffffffffffffffiiiiifi']
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
    GRAVITY = 9.81

    def __init__(self, port=4000, buffer_size=10):
        super().__init__(buffer_size)
        self.legacy = False
        self.port = port
        self._mugic_init()
        return

    def _update_state(self, datagram):
        if self.legacy: # Mugic 1.0 - x rot is inverted
            # also note: Mugic 1.0 accel values are much noisier
            # ref: https://gamedev.stackexchange.com/questions/201977
            datagram['QZ'], datagram['QX'] = -datagram['QZ'], -datagram['QX']
            datagram['EY'] = -datagram['EY']
        if not self.legacy: # Mugic 2.0 - accel has gravity
            quat_rot = IMU.to_quaternion(datagram)
            accel = quat.Vector(
                datagram['AX'], datagram['AY'], datagram['AZ'])
            accel -= (quat.Vector(0, 0, self.GRAVITY) @ quat_rot.inverse())
            datagram['AX'], datagram['AY'], datagram['AZ'] = accel.xyz
            datagram['EZ'] = -datagram['EZ']
        datagram = super()._update_state(datagram)
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
        self.legacy = not self.legacy
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

    def absoluteGyro(self, datagram, raw=False):
        if datagram is None: return None
        if self.legacy: # Revert Mugic 1.0 quat changes
            datagram = datagram.copy()
            datagram['QX'], datagram['QZ'] = -datagram['QX'], -datagram['QZ']
        return super().absoluteGyro(datagram, raw)

# mock mugic device - used to simulate a mugic device
class MockMugicDevice(MugicDevice):
    def __init__(self, port=4000, datafile=None):
        super().__init__(port)
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

    def _datagram_is_ready(self, datagram):
        if datagram is None: return False
        elapsed = time.time() - self._start_time + self._base_time/1000
        datagram_time = datagram['seconds']/1000
        if elapsed < datagram_time: return False
        return True

    def _next_datagram_is_available(self):
        if len(self._data) == 0: return False
        top = self._data[-1]
        if not self._datagram_is_ready(top): return False
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

# Recording Functions
def recordMugicDevice(port, datafile, seconds=60):
    mugic = MugicDevice(port=port, buffer_size=None)
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
            lambda: _write_mugic_recorded_data(mugic, file))
    recordTimer.start()
    return

def _write_mugic_recorded_data(mugic, file):
    store = mugic._reserve if mugic._reserve is not None else mugic._data
    print("preparing to write", len(store), "datagrams...")
    for datagram in reversed(list(store)):
        datagram = MugicDevice._datagram_to_string(datagram)
        # print("writing datagram:", datagram)
        file.write(datagram+'\n')
    print("Recording complete")
    file.close()
