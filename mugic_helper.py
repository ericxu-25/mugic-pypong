from mugic import *
import argparse
import pygame
from mugic_pygame_helpers import Window, WindowScreen, TextSprite, Color, MONOSPACE

def _log_scale(number):
    return (math.log(abs(number)+1)/3.0) * sign(number)

class IMUDisplay:
    def __init__(self, imu, w=100, h=100):
        self._imu = imu
        self._init_text()
        self._init_image(w, h)

    def _init_image(self, w, h):
        self._image_size = (w, h)
        self._image = pygame.Surface(self._image_size)
        self._image.set_colorkey(Color.black)
        self._action_image = self._image.copy()
        # draw acceleration and gyroscope graph axes
        ag_top = 1
        ag_left = 1
        ag_right = w - ag_left
        ag_width = ag_right - ag_left
        ag_height = h // 2 - 10
        agrect = pygame.Rect(ag_top, ag_left, ag_width, ag_height)
        ggrect = agrect.move(0, (h - ag_height - ag_top))
        pygame.draw.line(self._action_image, color=Color.white,
                         start_pos=(agrect.left-1, agrect.top),
                         end_pos=(agrect.left-1, agrect.bottom))
        pygame.draw.line(self._action_image, color=Color.white,
                         start_pos=agrect.midleft,
                         end_pos=agrect.midright)
        pygame.draw.line(self._action_image, color=Color.white,
                         start_pos=(ggrect.left-1, ggrect.top),
                         end_pos=(ggrect.left-1, ggrect.bottom))
        pygame.draw.line(self._action_image, color=Color.white,
                         start_pos=ggrect.midleft,
                         end_pos=ggrect.midright)
        self._max_ay = 30
        self._max_fy = 30
        self._max_gy = 360 * 4
        self._ag_rect = agrect
        self._gg_rect = ggrect
        self._ag_graph_surface = self._action_image.subsurface(
                agrect)
        self._gg_graph_surface = self._action_image.subsurface(
                ggrect)

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
        self._image_accel = graph3d.Axis(Color.red, width = 2, p1=(1, 1, 1))
        self._image_gyro = graph3d.Axis(Color.blue, width = 2, p1=(1, 1, 1))
        self._image_magnet = graph3d.Axis(Color.white, width = 2, p1=(1, 1, 1)) * (0.1, 0.1, 0.1)
        self._image_facing = graph3d.Axis(Color.magenta, width = 2, p1=self._imu.orientation)
        self._image_axes = graph3d.PositiveAxes(Color.red, Color.green, Color.blue)
        # camera initialization
        self._camera = graph3d.Camera()
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
            pygame.draw.circle(self._image,
                               Color.red,
                               (w-w//16, h-h//16),
                               max(w//64, 3))
            self._camera.show(self._image, "axes")
            return self._image
        else:
            pygame.draw.circle(self._image,
                               Color.green,
                               (w-w//16, h-h//16),
                               max(w//64, 3))
        # apply datagram transformations
        if datagram is None:
            datagram = self._imu.peekDatagram()
        if datagram is not None:
            data_quat = self._imu.quat(datagram)
            accel_data = self._imu.accel(datagram) * 0.1
            magnet_data =  self._imu.mag(datagram) / 30
            gyro_data = self._imu.gyro(datagram) / 1080
            #print(quat.euler(data_quat))
            #data_quat = data_quat.normalise()
            self._camera["accel"] = self._image_accel * accel_data.xyz \
                    @ data_quat
            self._camera["gyro"] = self._image_gyro * gyro_data.xyz
            self._camera["compass"] = self._image_magnet * magnet_data.xyz
            self._camera["cube"] = self._image_cube * self._imu.dimensions\
                    @ data_quat
            self._camera["facing"] = self._image_facing @ data_quat
        self._camera.show(self._image)
        return self._image

    def _norm_graph_val(self, val, maxy, rect):
        y = val/maxy
        if abs(y) > 1:
            y = (-1 if y < 0 else 1)
        y *= rect.height//2
        y += rect.centery
        return (rect.left, y)

    # displays two graphs - accelerometer and gyrometer
    def getActionImage(self, w=None, h=None, datagram=None):
        w, h = self._set_image_size(w, h)
        if not self._imu.dirty: return self._action_image
        try:
            _ = self._image_cube
        except AttributeError as e:
            if hasattr(self, "_image_cube"): raise AttributeError(e)
            self._init_image_objects()
            return self.getActionImage(w, h)
        if datagram is None:
            datagram = self._imu.peekDatagram()
        if datagram is not None:
            #accel_data = self._imu.accel(datagram)
            #gyro_data =  self._imu.gyro(datagram)
            accel_data = self._imu.absoluteAccel(datagram)
            gyro_data =  self._imu.absoluteGyro(datagram)
            frame_data = self._imu.getFrame()
            # draw frame values
            frame_points = [self._norm_graph_val(
                val, self._max_fy, self._ag_rect)
                            for val in frame_data]
            self._action_image.fill(Color.black,
                                    (self._ag_rect.topleft,
                                     (1, self._ag_rect.height)))
            self._action_image.fill(Color.white,
                                    (self._ag_rect.midleft, (1, 1)))
            colors = [Color.red, Color.green, Color.blue]
            for point, color in zip(frame_points, colors):
                self._action_image.fill(color, (point, (1, 1)))
            # draw acceleration values
            accel_points = [self._norm_graph_val(
                val, self._max_ay, self._ag_rect)
                            for val in accel_data]
            for point, color in zip(accel_points, colors):
                self._action_image.fill(color, (point, (1, 3)))

            # draw gyroscope values
            gyro_points = [self._norm_graph_val(
                val,
                self._max_gy,
                self._gg_rect)
                           for val in gyro_data]
            self._action_image.fill(Color.black,
                                    (self._gg_rect.topleft,
                                     (1, self._gg_rect.height)))
            self._action_image.fill(Color.white,
                                    (self._gg_rect.midleft, (1, 1)))
            colors = [Color.cyan, Color.magenta, Color.yellow]
            for point, color in zip(gyro_points, colors):
                self._action_image.fill(color, (point, (1, 3)))
        # scroll graphs to the left
        self._ag_graph_surface.scroll(dx=1)
        self._gg_graph_surface.scroll(dx=1)
        return self._action_image

    def _init_text(self):
        self._text = "No Connection"
        self._action_text = "No Connection"
        data_labels= [" quat", "euler", "accel",
                      " gyro", " magn",
                      "battery", "frame", "calib (SAGM)"]
        self._data_format_text = '\n'.join(
                [value+": {}" for value in data_labels])
        self._action_format_text = "Moving: {}\nRotating: {}\n"
        self._action_format_text += "Pointing: {:3s}\nYaw {:3s} Pitch {:3s} Roll {:3s}\n"
        self._action_format_text += "Thrust: {:>6.2f}, Swing:{:>6.2f}\n"

    def getDataText(self):
        if not self._imu.dirty: return self._text
        md = self._imu.next(raw=False)
        if md is None: return self._text
        quat = "{:>5.2f}, {:>5.2f}, {:>5.2f}, {:>5.2f}"\
                .format(md['QW'], md['QX'], md['QY'], md['QZ'])
        data_row = "{:>6.2f}, {:>6.2f}, {:>6.2f}"
        euler = data_row.format(md['EX'], md['EY'], md['EZ'])
        accel = data_row.format(md['AX'], md['AY'], md['AZ'])
        gyro= data_row.format(md['GX'], md['GY'], md['GZ'])
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
        moving = ", ".join(self._imu.moving(text=True, datagram=datagram)) or "NO"
        rotating = ", ".join(self._imu.rotating(text=True, datagram=datagram)) or "NO"
        yawing = ", ".join(self._imu.yawing(text=True, datagram=datagram)) or "NO"
        pitching = ", ".join(self._imu.pitching(text=True, datagram=datagram))
        rolling = ", ".join(self._imu.rolling(text=True, datagram=datagram))
        pointing = ", ".join(self._imu.pointing(text=True, datagram=datagram))
        thrust = self._imu.thrustAccel(datagram=datagram)
        swing = self._imu.swingAccel(datagram=datagram)
        self._action_text = self._action_format_text\
                .format(moving, rotating,
                        pointing, yawing,
                        pitching, rolling,
                        thrust, swing)
        return self._action_text

    @property
    def image(self):
        return self.getImage()

    @property
    def text(self):
        return self.getDataText() + "\n" + self.getActionText()


def _viewMugicDevice(mugic_device):
    pygame.init()
    # window setup
    window_size = (1000, 500)
    pane_size = (500, 500)
    Window().rescale(*window_size)
    Window().name = "PyMugic IMU orientation visualization"
    display = pygame.display.get_surface()
    frames = 0
    ticks = pygame.time.get_ticks()
    # mugic display setup
    mugic_display = IMUDisplay(mugic_device)
    mugic_display.setImageSize(*pane_size)
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
    mugic_data_text.setFormatString("{}").moveTo(550, 100).setFontSize(20).hide()
    mugic_data_text.setFontType(MONOSPACE)
    mugic_movement_text.setFormatString("{}").moveTo(550, 350).setFontSize(20).hide()
    mugic_movement_text.setFontType(MONOSPACE)
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
        rot_amount = pi/90
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
            mugic_device.calibrate()
            frames = 0
            ticks = pygame.time.get_ticks() - 1

        next_datagram = mugic_device.next(raw=False)
        if next_datagram is not None and next_datagram.values() != last_datagram:
            last_datagram = list(next_datagram.values())
            frames += 1
            mugic_device.dirty = True
            fps_value = ((frames*1000)/(pygame.time.get_ticks()-ticks))
            if frames < 20:
                mugic_device.autoDetectMugicType()

        if mugic_device.dirty:
            mugic_image = mugic_display.getImage(datagram=next_datagram)
            action_image = mugic_display.getActionImage(datagram=next_datagram)
            display_screen._redraw()
            mugic_image = pygame.transform.smoothscale_by(mugic_image,
                                                 display_screen._scale)
            action_image = pygame.transform.smoothscale_by(action_image,
                                                 display_screen._scale)
            display.blit(mugic_image, (0, 0))
            display.blit(action_image, (500*display_screen._scale, 0))
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
    args = parser.parse_args()
    mugic = None
    if args.record:
        mugic = MugicDevice(port=args.port, buffer_size=None)
        _recordMugicDevice(args.port, args.datafile, args.seconds)
    if args.playback:
        mugic = MockMugicDevice(datafile=args.datafile)
    if mugic is None:
        mugic = MugicDevice(port=args.port)
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
