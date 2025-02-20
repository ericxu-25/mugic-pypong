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
from mugic_pygame_helpers import Window, WindowScreen, TextSprite, Color
import time
import math
from math import pi
from collections import deque
import quaternion.quat as quat
import quaternion.graph3d as graph3d

import sys
import pygame
from threading import Timer

# helper functions
def _log_scale(number):
    sign = -1 if number < 0 else 1
    return (math.log(abs(number)+1)/2.0) * sign

# Base Classes

# interface for a generic IMU device
class IMU:
    # assumes 9-axis Datagram structure
    # Datagram types and structure
    types = [float] * 16
    datagram = (
        'AX', 'AY', 'AZ', # Accelerometer
        'EX', 'EY', 'EZ', # Euler angles
        'GX', 'GY', 'GZ', # Gyrometer
        'MX', 'MY', 'MZ', # Magnetometer
        'QW', 'QX', 'QY', 'QZ', # Quaternion angles
    )

    def __init__(self, buffer_size=100, smoothing=10):
        self.dirty = False
        if smoothing == None: smoothing = 1
        self.smoothing = smoothing
        if buffer_size == None:
            print("Warning - IMU unlimited buffer size!")
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

    def peekDatagram(self, raw=False, smooth=True):
        if len(self._data) == 0: return None
        if not smooth:
            datagrams = list(self._data[-1].copy())
        else:
            datagrams = [self._data[-i].copy() for i in range(min(len(self._data), self.smoothing))]
        return self._smooth(datagrams, raw)

    def popDatagram(self, raw=False, smooth=True):
        if len(self._data) == 0: return None
        datagrams = [self._data.pop()]
        if not smooth:
            return self._smooth(datagrams, raw)
        for i in range(self.smoothing):
            if i+1 > len(self._data): break
            datagrams.append(self._data[-i-1])
        return self._smooth(datagrams, raw)

    def popDatagrams(self, raw=False):
        datagrams = self._data.copy()
        self._data.clear()
        if raw: return datagrams
        return [self._calibrate(d) for d in datagrams]

    @staticmethod
    def _datagram_to_string(datagram):
        data_string = ",".join([str(v) for v in datagram.values()])
        return data_string

    def refresh(self):
        if len(self._data) == 0: return None
        self._dirty = True
        last_datagram = self._data[0]
        self._data.clear()
        self._data.appendleft(last_datagram)
        return last_datagram

    def zero(self, *args):
        args = list(args)
        while len(args) < len(IMU.datagram):
            args.append(0)
        for i in range(len(IMU.types)):
            args[i] = IMU.types[i](args[i])
        self._zero = dict(zip(IMU.datagram, args))

    def calibrate(self, *args):
        self.zero(*args)
        self._zero['MX'] = 0
        self._zero['MY'] = 0
        self._zero['MZ'] = 0

    def _calibrate(self, datagram):
        calibrated_quat = (IMU.to_quaternion(datagram) *
                           IMU.to_quaternion(self._zero).conjugate())
        for key, value in self._zero.items():
            datagram[key] -= value
        datagram['QW'] = calibrated_quat.w
        datagram['QX'] = calibrated_quat.x
        datagram['QY'] = calibrated_quat.y
        datagram['QZ'] = calibrated_quat.z
        return datagram

    # returns smoothed datagram via moving average
    def _smooth(self, datagrams, raw=False):
        if len(datagrams) == 1:
            if raw: return datagrams[0]
            return self._calibrate(datagrams[0])
        smoothed_datagram = datagrams[0]
        for datagram in datagrams[1:]:
            for value in self.__class__.datagram:
                smoothed_datagram[value] += datagram[value]
        for value in self.__class__.datagram:
            smoothed_datagram[value] /= len(datagrams)
        # technically should use nlerp, but
        # moving average should work fine with close quat values
        # as long as we make sure to normalize it
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

# TODO add methods to map datagrams to understandable motions
# methods to add:
# * Madgwick Filter? - no quats are done for us
# * current state (position + datagram)
# * accel, orientation, quat_orientation, gyro
# * movingLeft, movingRight, movingUp, movingDown
# * flippingLeft, flippingRight, flippingForward, flippingBack
# * facingForward, facingBackward, facingLeft, facingRight
# * facingUp, facingDown
# * compassAngle
class IMUController(IMU):
    def __init__(self, buffer_size=20):
        super().__init__(buffer_size)
        self._connected = False

    @classmethod
    def _parse_datagram(cls, *values):
        values = [t(v) for t, v in zip(cls.types, values)]
        datagram = dict(zip(cls.datagram, values))
        return datagram

    def _callback(self, *values):
        datagram = self._parse_datagram(*values)
        self._data.appendleft(datagram)
        self._dirty = True
        self._connected = True

    def connected(self):
        return self._connected or len(self._data) != 0

    def calibrate(self, *args):
        if len(self._data) != 0 and len(args) == 0:
            super().calibrate(*self.peekDatagram(raw=True).values())
        else:
            super().calibrate(*args)
        self._dirty = True

class MugicDevice(IMUController):
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

    def __init__(self, port=4000, buffer_size=20):
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

# mock mugic device - used to simulate a mugic device
class MockMugicDevice(MugicDevice):
    def __init__(self, port=None, datafile=None, buffer_size=None):
        super().__init__(port, buffer_size)
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
        if elapsed < next_datagram_time: return False
        return True

    def _next_datagram_is_available(self):
        if len(self._data) == 0: return False
        top = self._data[-1]
        if not self._datagram_is_ready(top): return False
        return True

    def popDatagram(self, raw=False, smooth=True):
        if not self._next_datagram_is_available(): return None
        return super().popDatagram(raw, smooth)

    def peekDatagram(self, raw=False, smooth=True):
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
    def __init__(self, imu):
        self._imu = imu
        self._init_text()
        self._init_image(100, 100)

    def _init_text(self):
        self._text = "No Connection"
        display_labels = ["quaternion", "accel", "gyro", "magnetometer", "battery", "frame"]
        self._format_text = '\n'.join(
            [value+": {}" for value in display_labels])

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
        self._imu.dirty = True

    def rotateImageY(self, angle=1):
        try:
            self._image_rotationy += angle
            self._image_rotationy %= (2*pi)
            self._camera.rotateY(self._image_rotationy)
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
        self._image_cube *= (0.8, 0.5, 0.2)
        self._image_accel = graph3d.Axis(Color.red, width = 2)
        self._image_gyro = graph3d.Axis(Color.blue, width = 2)
        self._image_magnet = graph3d.Axis(Color.white, width = 2) * (0.1, 0.1, 0.1)
        self._camera = graph3d.Camera()
        self._image_rotationx = -pi/2
        self._image_rotationy = pi/2
        #self._image_rotationx = 0
        #self._image_rotationy = 0
        self._camera.rotateY(self._image_rotationy)
        self._camera.rotateX(self._image_rotationx)
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
        self.image.fill(Color.black)
        # apply datagram transformations
        if datagram == None:
            datagram = self._imu.peekDatagram()
        if datagram is not None:
            # Y and X switched
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
                    _log_scale(datagram['GX']/360.0),
                    _log_scale(datagram['GY']/360.0),
                    _log_scale(datagram['GZ']/360.0))
            #print(quat.euler(data_quat))
            self._camera["accel"] = self._image_accel * accel_data
            self._camera["gyro"] = self._image_gyro * gyro_data
            self._camera["compass"] = self._image_magnet * magnet_data
            self._camera["cube"] = self._image_cube @ data_quat # + (quat.Vector(1, 0, 0) * accel_data)
        self._camera.show(self.image)
        return self.image

    def getText(self):
        if not self._imu.dirty: return self._text
        md = self._imu.peekDatagram()
        if md == None: return self._text
        quat = "{:>5.2f}, {:>5.2f}, {:>5.2f}, {:>5.2f}"\
                .format(md['QW'], md['QX'], md['QY'], md['QZ'])
        data_row = "{:>6.2f}, {:>6.2f}, {:>6.2f}"
        accel = data_row.format(md['AX'], md['AY'], md['AZ'])
        gyro = data_row.format(md['GX'], md['GY'], md['GZ'])
        mag = data_row.format(md['MX'], md['MY'], md['MZ'])
        battery = "{:.2f}".format(md['Battery'])
        seq = md['seqnum']
        self._text = self._format_text.format(quat, accel, gyro,
                                        mag, battery, seq)
        return self._text

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
    # main loop
    while True:
        event = pygame.event.poll()
        if (event.type == pygame.QUIT or
            (event.type == pygame.KEYDOWN
             and event.key == pygame.K_ESCAPE)):
            break
        elif event.type == pygame.VIDEORESIZE:
            Window()._resize_window(event.w, event.h)
        elif (event.type == pygame.KEYDOWN
              and event.key == pygame.K_f):
            mugic_data_text.toggleVisibility()
        state = pygame.key.get_pressed()
        rot_amount = pi/180
        if state[pygame.K_a]:
            mugic_display.rotateImageY(-rot_amount)
        elif state[pygame.K_d]:
            mugic_display.rotateImageY(rot_amount)
        if state[pygame.K_w]:
            mugic_display.rotateImageX(-rot_amount)
        elif state[pygame.K_s]:
            mugic_display.rotateImageX(rot_amount)
        elif state[pygame.K_z]:
            mugic_display.zoomImage(0.1)
        elif state[pygame.K_x]:
            mugic_display.zoomImage(-0.1)
        elif state[pygame.K_r]:
            mugic_display.resetImage()
        elif state[pygame.K_c]:
            mugic_device.calibrate(*last_datagram)

        next_datagram = mugic_device.peekDatagram(raw=True)
        if next_datagram is not None and next_datagram.values() != last_datagram:
            last_datagram = next_datagram.values()
            frames += 1
            mugic_device.dirty = True
            fps_value = ((frames*1000)/(pygame.time.get_ticks()-ticks))

        if mugic_device.dirty:
            mugic_image = mugic_display.getImage()
            mugic_device.popDatagram()
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


