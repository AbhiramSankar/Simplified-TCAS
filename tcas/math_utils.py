import math
from typing import Tuple

Vec2 = Tuple[float, float]

def dot(a: Vec2, b: Vec2) -> float:
    return a[0]*b[0] + a[1]*b[1]

def norm(a: Vec2) -> float:
    return math.hypot(a[0], a[1])

def add(a: Vec2, b: Vec2) -> Vec2:
    return (a[0]+b[0], a[1]+b[1])

def sub(a: Vec2, b: Vec2) -> Vec2:
    return (a[0]-b[0], a[1]-b[1])

def mul(a: Vec2, k: float) -> Vec2:
    return (a[0]*k, a[1]*k)
