# vector class
# WARNING: no testing has been done on the code below
from math import sqrt, isclose
from array import array
import quaternion.quat as quat

mdelta = 0.001  # 0.1% Minimum difference considered significant for graphics
adelta = 0.001  # Absolute tolerance for components near 0

class Vector:
    def __init__(self, *args):
        self.d = array('f', [*args])

    @property
    def x(self):
        return self[0]

    @x.setter
    def x(self, v):
        self[0] = v

    @property
    def y(self):
        return self[1]

    @y.setter
    def y(self, v):
        self[1] = v

    @property
    def z(self):
        return self[2]

    @z.setter
    def z(self, v):
        self[2] = v

    @property
    def xyz(self):
        return (self[0], self[1], self[2])

    def normalise(self):
        m = abs(self)  # Magnitude
        if m < mdelta:
            return Vector(*([0] * len(self.d)))
        if isclose(m, 1.0, rel_tol=mdelta):
            return self  # No normalisation necessary
        return Vector(*(a/m for a in self))

    def __getitem__(self, key):
        return self.d[key]

    def __setitem__(self, key, v):
        try:
            v1 = array('f', v)
        except TypeError:  # Scalar
            v1 = v
        self.d[key] = v1

    def copy(self):
        return Vector(*self)

    def __abs__(self):  # Return magnitude
        return sqrt(sum((d*d for d in self)))

    def __len__(self):
        return len(self.d)

    # Comparison: == and != perform equality test of all elements
    def __eq__(self, other):
        return all((isclose(a, b, rel_tol=mdelta, abs_tol=adelta) for a, b in zip(self, other)))

    def __ne__(self, other):
        return not self == other

    # < and > comparisons compare magnitudes.
    def __gt__(self, other):
        return abs(self) > abs(other)

    def __lt__(self, other):
        return abs(self) < abs(other)

    # <= and >= return True for complete equality otherwise magnitudes are compared.
    def __ge__(self, other):
        return True if self == other else abs(self) > abs(other)

    def __le__(self, other):
        return True if self == other else abs(self) < abs(other)

    def __str__(self):
        s = ", ".join([f'{d:4.2f}' for d in self.d])
        return f"<{s}>"

    def __format__(self, fmt):
        return f"{str(self):{fmt}}"

    def __pos__(self):
        return Vector(*self)

    def __neg__(self):
        return Vector(*(-a for a in self))

    def __truediv__(self, scalar):
        if isinstance(scalar, Vector):
            raise ValueError('Cannot divide by Vector')
        return Vector(*(a/scalar for a in self))

    # dot product, otherwise scalar multiply
    def __mul__(self, other):
        try:
            return sum([a*v for a,v in zip(self, other)])
        except TypeError:
            return Vector(*(a * other for a in self))

    def __rmul__(self, other):
        return self * other

    def __add__(self, other):
        try:
            return Vector(*(a+v for a,v in zip(self, other)))
        except TypeError:
            return Vector(*(a + other for a in self))

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        try:
            return Vector(*(a-v for a,v in zip(self, other)))
        except TypeError:
            return Vector(*(a - other for a in self))

    def __rsub__(self, other):
        return other + self.__neg__()  # via __radd__

    def project(self, other):
        return (self * other / abs(other)) * other.normalise()

    def scalar_project(self, other):
        return (self * other / abs(other))

    # override matmul to do projection or rotation
    def __matmul__(self, other):
        if isinstance(other, quat.Quaternion):
            return quat.Vector(*self.xyz) @ other
        other = Vector(*other)
        return self.project(other)

    def lerp(self, other, ratio):
        other = Vector(*other)
        return self + ((self - other) * ratio)

    def nlerp(self, other, ratio):
        return self.lerp(other, ratio).normalise()

    def distance(self, other):
        if isinstance(other, quat.Quaternion):
            other = Vector(*other.xyz)
        return abs(self-other)


