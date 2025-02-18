# graph3d.py 3D graphics demo of quaternion use
# code taken from https://github.com/peterhinch/micropython-samples/blob/master/quaternion/graph3d.py

# modified to use pygame screens instead of micropython (setup3d)

# Released under the MIT License (MIT). See LICENSE.
# Copyright (c) 2020 Peter Hinch

import gc
from math import pi
from quaternion.quat import Rotator, Point
from pygame import draw
# from setup3d import fill, line, show, DIMENSION

class Line:
    def __init__(self, p0, p1, color, width=1):
        #assert p0.isvec() and p1.isvec()
        self.start = p0
        self.end = p1
        self.color = color
        self.width = width

    def show(self, surface):
        _, xs, ys, zs = self.start
        _, xe, ye, ze = self.end
        if zs == 0 or ze == 0: return
        # Handle perspective and scale to display
        # Viewing area is square
        w = surface.get_width()//4
        h = surface.get_height()//4
        w = min(w, h)
        h = min(w, h)
        centerx = w
        centery = h
        xs = round((1 + xs/zs) * w + centerx)
        ys = round((1 - ys/zs) * h + centery)
        xe = round((1 + xe/ze) * w + centerx)
        ye = round((1 - ye/ze) * h + centery)
        # print("drawing line:", xs, ys, xe, ye)
        draw.line(
                surface,
                self.color,
                (xs, ys),
                (xe, ye),
                self.width)

    def __add__(self, to):  # to is a Point or 3-tuple
        return Line(self.start + to, self.end + to, self.color, self.width)

    def __sub__(self, v):  # to is a Point or 3-tuple
        return Line(self.start - v, self.end - v, self.color, self.width)

    def __mul__(self, by):  # by is a 3-tuple
        return Line(self.start * by, self.end * by, self.color, self.width)

    def __matmul__(self, rot):  # rot is a rotation quaternion
        #assert rot.isrot()
        return Line(self.start @ rot, self.end @ rot, self.color, self.width)

    def camera(self, rot, distance):  # rot is a rotation quaternion, distance is scalar
        #assert rot.isrot()
        gc.collect()
        ps = self.start @ rot
        ps = Point(ps.x * distance, ps.y * distance, distance - ps.z)
        pe = self.end @ rot
        pe = Point(pe.x * distance, pe.y * distance, distance - pe.z)
        return Line(ps, pe, self.color, self.width)

    def __str__(self):
        return 'start {} end {}'.format(self.start, self.end)

class Shape:
    def __init__(self, lines):
        self.lines = lines

    def __add__(self, to):
        return Shape([l + to for l in self.lines])

    def __sub__(self, v):
        return Shape([l - v for l in self.lines])

    def __mul__(self, by):
        return Shape([l * by for l in self.lines])

    def __matmul__(self, rot):
        l = []
        for line in self.lines:
            l.append(line @ rot)
        return Shape(l)

    def camera(self, rot, distance):
        l = []
        for line in self.lines:
            l.append(line.camera(rot, distance))
        return Shape(l)

    def show(self, surface):
        for line in self.lines:
            line.show(surface)

    def __str__(self):
        r = ''
        for line in self.lines:
            r = ''.join((r, '{}\n'.format(line)))
        return r

class Axes(Shape):
    def __init__(self, xcolor, ycolor=None, zcolor=None, width=1):
        if ycolor == None: ycolor = xcolor
        if zcolor == None: zcolor = xclolor
        l = (Line(Point(-1.0, 0, 0), Point(1.0, 0, 0), xcolor, width),
             Line(Point(0, -1.0, 0), Point(0, 1.0, 0), ycolor, width),
             Line(Point(0, 0, -1.0), Point(0, 0, 1.0), zcolor, width))
        super().__init__(l)

class Axis(Shape):
    def __init__(self, color, p0=(0, 0, 0), p1=(1, 0, 0), width=1):
        l = (Line(Point(*p0), Point(*p1), color, width),)
        super().__init__(l)

class Square(Shape):  # Unit square in XY plane
    def __init__(self, color, width=1):  # Corner located at origin
        l = (Line(Point(0, 0, 0), Point(1, 0, 0), color, width),
             Line(Point(1, 0, 0), Point(1, 1, 0), color, width),
             Line(Point(1, 1, 0), Point(0, 1, 0), color, width),
             Line(Point(0, 1, 0), Point(0, 0, 0), color, width))
        super().__init__(l)

class Cube(Shape):
    def __init__(self, color, front=None, sides=None, width=1):  # Corner located at origin
        front = color if front is None else front
        sides = color if sides is None else sides
        l = (Line(Point(0, 0, 0), Point(1, 0, 0), color, width),
             Line(Point(1, 0, 0), Point(1, 1, 0), color, width),
             Line(Point(1, 1, 0), Point(0, 1, 0), color, width),
             Line(Point(0, 1, 0), Point(0, 0, 0), color, width),
             Line(Point(0, 0, 1), Point(1, 0, 1), front, width),
             Line(Point(1, 0, 1), Point(1, 1, 1), front, width),
             Line(Point(1, 1, 1), Point(0, 1, 1), front, width),
             Line(Point(0, 1, 1), Point(0, 0, 1), front, width),
             Line(Point(0, 0, 0), Point(0, 0, 1), sides, width),
             Line(Point(1, 0, 0), Point(1, 0, 1), sides, width),
             Line(Point(1, 1, 0), Point(1, 1, 1), sides, width),
             Line(Point(0, 1, 0), Point(0, 1, 1), sides, width),
             )
        super().__init__(l)

class Cone(Shape):
    def __init__(self, color, segments=12, width=1):
        rot = Rotator(2*pi/segments, 0, 1, 0)
        p0 = Point(1, 1, 0)
        p1 = p0.copy()
        orig = Point(0, 0, 0)
        lines = []
        for _ in range(segments + 1):
            p1 @= rot
            lines.append(Line(p0, p1, color, width))
            lines.append(Line(orig, p0, color, width))
            p0 @= rot
        super().__init__(lines)

class Circle(Shape):  # Unit circle in XY plane centred on origin
    def __init__(self, color, segments=12, width=1):
        rot = Rotator(2*pi/segments, 0, 1, 0)
        p0 = Point(1, 0, 0)
        p1 = p0.copy()
        lines = []
        for _ in range(segments + 1):
            p1 @= rot
            lines.append(Line(p0, p1, color, width))
            p0 @= rot
        super().__init__(lines)

class Sphere(Shape):  # Unit sphere in XY plane centred on origin
    def __init__(self, color, segments=12, width=1):
        lines = []
        s = Circle(color, width=width)
        xrot = Rotator(2 * pi / segments, 1, 0, 0)
        for _ in range(segments / 2 + 1):
            gc.collect()
            lines.extend(s.lines[:])
            s @= xrot
        super().__init__(lines)

## Composition rather than inheritance as MP can't inherit builtin types.
#class DisplayDict:
#    def __init__(self, ssd, angle, distance):
#        self.ssd = ssd
#        self.distance = distance  # scalar
#        # Rotation quaternion for camera view
#        self.crot = Rotator(angle, 1, 1, 0)
#        self.d = {}
#
#    def __setitem__(self, key, value):
#        if not isinstance(value, Shape):
#            raise ValueError('DisplayDict entries must be Shapes')
#        self.d[key] = value
#
#    def __getitem__(self, key):
#        return self.d[key]
#
#    def __delitem__(self, key):
#        del self.d[key]
#
#    def show(self):
#        ssd = self.ssd
#        fill(0)
#        crot = self.crot
#        dz = self.distance
#        for shape in self.d.values():
#            s = shape.camera(crot, dz)
#            s.show(ssd)
#        show()

class Camera:
    def __init__(self, rot=0, distance = 2):
        self.distance = distance
        self.crotx = Rotator(rot, 1, 0, 0)
        self.croty = Rotator(rot, 0, 1, 0)
        self.d = {}

    def __setitem__(self, key, value):
        if not isinstance(value, Shape):
            raise ValueError('Camera only accepts Shapes')
        self.d[key] = value

    def __getitem__(self, key):
        return self.d[key]

    def __delitem__(self, key):
        del self.d[key]

    def show(self, surface):
        crot = self.croty * self.crotx
        dz = self.distance
        for shape in self.d.values():
            s = shape.camera(crot, dz)
            s.show(surface)

    def rotateX(self, angle):
        self.crotx = Rotator(angle, 1, 0, 0)

    def rotateY(self, angle):
        self.croty = Rotator(angle, 0, 1, 0)

    def zoom(self, distance):
        self.distance += distance
        if self.distance <= 1:
            self.distance = 1
        if self.distance > 3:
            self.distance = 3

