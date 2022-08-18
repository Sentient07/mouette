import pygeomesh as GEO
import pytest
from math import cos, sin, pi
import os

### Surfaces ###

def surf_triangle():
    m = GEO.mesh.new_surface()
    m.vertices += [
        GEO.Vec(0., 0., 0.),
        GEO.Vec(1., 0., 0.),
        GEO.Vec(0., 0., 1.),
    ]
    m.edges += [(0,1), (0,2), (1,2)]
    m.faces.append((0,1,2))
    m.face_corners += [0,1,2]
    return m

def surf_square():
    m = GEO.mesh.new_surface()
    m.vertices += [
        GEO.Vec(1.,0.,0.),
        GEO.Vec(0.,1.,0.),
        GEO.Vec(1.,1.,0.),
        GEO.Vec(1.,0.,0.),
    ]
    m.edges += [(0,1), (1,2), (2,3), (0,3), (1,3)]
    m.faces += [(0,1,3), (1,2,3)]
    m.face_corners += [0,1,2,3,1,2,3]
    return m

def surf_cube():
    m = GEO.mesh.new_surface()
    m.vertices += [
        GEO.Vec(0., 0., 0.),
        GEO.Vec(1., 0., 0.),
        GEO.Vec(1., 1., 0.),
        GEO.Vec(0., 1., 0.),
        GEO.Vec(0., 0., 1.),
        GEO.Vec(1., 0., 1.),
        GEO.Vec(1., 1., 1.),
        GEO.Vec(0., 1., 1.),
    ]
    m.faces += [
        
    ]
    return m

def surf_tetrahedron():
    m = GEO.mesh.new_surface()
    m.vertices += [
        GEO.Vec(0., 0., 0.),
        GEO.Vec(1., 0., 0.),
        GEO.Vec(0., 0., 1.),
        GEO.Vec(0., 1., 0.),
    ]
    m.edges += [(0,1), (1,2), (0,2), (0,3), (1,3), (2,3)]
    m.faces += [[0,1,2], [0,1,3], [1,2,3], [2,0,3]]
    m.face_corners += [0,1,2,0,1,3,1,2,3,2,0,3]
    return m

def surf_one_ring():
    return GEO.procedural.ring(10,0.1)

def surf_circle():
    return GEO.mesh.load("tests/data/circle.mesh")

def surf_half_sphere():
    return GEO.mesh.load("tests/data/half_sphere1.obj")

def surf_spline():
    return GEO.mesh.load("tests/data/spline03.mesh")

def surf_feat():
    return GEO.mesh.load("tests/data/feature2.obj")

def surf_two_pieces():
    return GEO.mesh.load("tests/data/two_pieces.obj")

def surf_pointy():
    return GEO.mesh.load("tests/data/pointy.obj")

surfaces = [
    surf_triangle(),
    surf_one_ring(),
    surf_circle(),
    surf_half_sphere(),
    surf_spline(),
    surf_feat(),
    surf_two_pieces(),
    surf_pointy()
]