from ..worker import Worker
from ...mesh.datatypes import *
from ...mesh.mesh_attributes import Attribute, ArrayAttribute
from ...attributes.misc_faces import face_area

from ...geometry import Vec
from ... import geometry as geom

import numpy as np

class SurfaceDistortion(Worker):

    @allowed_mesh_types(SurfaceMesh)
    def __init__(self, 
            mesh : SurfaceMesh,
            uv_attr : str = "uv_coords",
            save_on_mesh : bool = True,
            verbose : bool = False):
        super().__init__("SurfaceDistortion", verbose)
        self.mesh : SurfaceMesh = mesh
        try:
            self.UV = self.mesh.face_corners.get_attribute(uv_attr)
        except:
            self.log(f"Mesh has no attribute '{uv_attr}'. Cannot compute distortion.")
            raise Exception("Initialization failed")

        self.save_on_mesh = save_on_mesh

        self._summary : dict = None
        self._conformal : ArrayAttribute = None
        self._area : ArrayAttribute = None
        self._iso : ArrayAttribute = None
        self._shear : ArrayAttribute = None
        self._stretch : ArrayAttribute = None
        self._det : ArrayAttribute = None

    def run(self):
        self._init_containers()
        if {len(f) for f in self.mesh.faces} == {3} :
            self._run_triangle_mesh()
        elif {len(f) for f in self.mesh.faces} == {4}:
            self._run_quad_mesh()

    def _init_containers(self):
        if self.save_on_mesh:
            self._conformal = self.mesh.faces.create_attribute("conformal_dist", float, dense=True)
            self._area = self.mesh.faces.create_attribute("authalic_dist", float, dense=True)
            self._stretch = self.mesh.faces.create_attribute("stretch_dist", float, dense=True)
            self._shear = self.mesh.faces.create_attribute("shear_dist", float, dense=True)
            self._iso = self.mesh.faces.create_attribute("iso_dist", float, dense=True)
            self._det = self.mesh.faces.create_attribute("det", float, dense=True)
        else:
            N = len(self.mesh.faces)
            self._conformal = ArrayAttribute(float, N, dense=True)
            self._area = ArrayAttribute(float, N, dense=True)
            self._stretch = ArrayAttribute(float, N, dense=True)
            self._shear = ArrayAttribute(float, N, dense=True)
            self._iso = ArrayAttribute(float, N, dense=True)
            self._det = ArrayAttribute(float, N, dense=True)

    def _run_triangle_mesh(self):
        xy_area = 0.
        uv_area = 0.
        area = face_area(self.mesh, persistent=False)
        for T in self.mesh.id_faces:
            cnr = 3*T #self.mesh.connectivity.face_to_first_corner(T)
            xy_area += area[T]
            uvA,uvB,uvC = ( Vec( self.UV[cnr + i].x, self.UV[cnr + i].y, 0.) for i in range(3))
            uv_area += geom.triangle_area(uvA,uvB,uvC)

        scale_ratio = (xy_area / uv_area)

        conformalDist = 0. # ||J||² / det J
        authalicDist = 0. # det J + 1 / det J
        detDist = 0. # det J
        logDetDist = 0. # log(| det J |)
        isoDist = 0. # distance( (sigma_1, sigma_2), (1,1))
        shearDist = 0. # dot(c_1, c_2) of columns of jacobian 
        stretchDistMax = -float("inf") # sigma_1 / sigma_2
        stretchDistMean = 0

        for T in self.mesh.id_faces:
            try:
                A,B,C = self.mesh.faces[T]
                cnr = 3*T #self.mesh.connectivity.face_to_first_corner(T)
                pA,pB,pC = (self.mesh.vertices[x] for x in (A,B,C))
                X,Y,N = geom.face_basis(pA,pB,pC)

                # original coordinates of the triangle
                u0 = pB-pA
                v0 = pC-pA
                u0 = complex(X.dot(u0), Y.dot(u0))
                v0 = complex(X.dot(v0), Y.dot(v0))
                # new coordinates of the triangle
                qA,qB,qC = (self.UV[cnr + i] for i in range(3))
                u = qB - qA
                v = qC - qA
                # jacobian
                J0 = np.array([[u0.real, v0.real], 
                            [u0.imag, v0.imag]])
                J0 = np.linalg.inv(J0)

                J1 = np.array([[u.x, v.x], 
                            [u.y, v.y]])
                
                J = J1 @ J0

                try:
                    c1, c2 = Vec.normalized(J[:,0]), Vec.normalized(J[:,1])
                    shearDistT = abs(geom.dot(c1, c2))
                except:
                    shearDistT = 0.
                self._shear[T] = shearDistT
                shearDist += shearDistT * area[T] / xy_area

                sig = np.linalg.svd(J, compute_uv=False)
                detJ = np.linalg.det(J)
                
                if abs(detJ)<1e-8:
                    raise ZeroDivisionError

                normJ = np.linalg.norm(J)

                confDistT = ((normJ**2)/detJ)/2
                self._conformal[T] = confDistT
                conformalDist += confDistT * area[T] / xy_area

                detJ *= scale_ratio
                self._det[T] = detJ
                # detDist += detJ / len(self.mesh.faces)
                detDist += detJ * area[T] / xy_area
                logDetDist += np.log(abs(detJ)) * area[T] / xy_area
                
                authDistT = ( detJ + 1 / detJ)/2
                self._area[T] = authDistT
                authalicDist += authDistT * area[T]/xy_area

                #sigma1Attr[T] = sig[0] * np.sqrt(scale_ratio)
                #sigma2Attr[T] = sig[1] * np.sqrt(scale_ratio)

                stretchDistT = sig[0]/sig[1]
                self._stretch[T] = stretchDistT
                stretchDistMax = max(stretchDistMax, stretchDistT)
                stretchDistMean += stretchDistT * area[T] / xy_area

                isoDistT = geom.distance( Vec(sig[0]* np.sqrt(scale_ratio), sig[1]* np.sqrt(scale_ratio)), Vec(1.,1.))
                self._iso[T] = isoDistT
                isoDist += isoDistT * area[T] / xy_area

            except ZeroDivisionError:
                continue

        self._summary = {
            "conformal" : conformalDist,
            "authalic" : authalicDist,
            "det" : detDist,
            "log_det" : logDetDist,
            "iso" : isoDist,
            "shear" : shearDist,
            "stretch_max" : stretchDistMax,
            "stretch_mean" : stretchDistMean
        }

    def _run_quad_mesh(self):
        ref_area = len(self.mesh.faces)
        real_area = 0.
        area = face_area(self.mesh, persistent=False)
        for T in self.mesh.id_faces:
            real_area += area[T]

        scale_ratio = (ref_area / real_area)

        conformalDist = 0. # ||J||² / det J
        authalicDist = 0. # det J + 1 / det J
        detDist = 0. # det J
        stretchDistMean = 0

        for T in self.mesh.id_faces:
            try:
                A,B,C,D = self.mesh.faces[T]
                pA,pB,pC,pD = (self.mesh.vertices[x] for x in (A,B,C,D))
                
                for P1,P2,P3 in [(pA,pB,pD), (pB,pC,pA), (pC,pD,pB), (pD,pA,pC)]:
                    X,Y,_ = geom.face_basis(P1,P2,P3)

                    # new coordinates of the triangle
                    u = P2 - P1
                    v = P3 - P1
                    # jacobian
                    J = np.array([[X.dot(u), Y.dot(u)], 
                                  [X.dot(v), Y.dot(v)]])

                    sig = np.linalg.svd(J, compute_uv=False)
                    detJ = np.linalg.det(J)
                    
                    if abs(detJ)<1e-8:
                        raise ZeroDivisionError

                    normJ = np.linalg.norm(J)

                    confDistT = ((normJ*normJ)/detJ)/8
                    self._conformal[T] += confDistT
                    conformalDist += confDistT * area[T] / real_area

                    detJ *= scale_ratio
                    detDist += detJ / (4*len(self.mesh.faces))
                    self._det[T] += detJ/4
                    authDistT = ( detJ + 1 / detJ)/8

                    self._area[T] += authDistT
                    authalicDist += authDistT * area[T] / real_area

                    #sigma1Attr[T] = sig[0] * np.sqrt(scale_ratio)
                    #sigma2Attr[T] = sig[1] * np.sqrt(scale_ratio)

                    stretchDistT = sig[0]/sig[1]/4
                    self._stretch[T] += stretchDistT
                    stretchDistMean += stretchDistT * area[T] / real_area
            except ZeroDivisionError:
                continue
            except FloatingPointError:
                continue

        self._summary = {
            "conformal" : conformalDist,
            "authalic" : authalicDist,
            "det" : detDist,
            "stretch_mean" : stretchDistMean
        }

    @property
    def summary(self):
        if self._summary is None: self.run()
        return self._summary

    @property
    def conformal(self):
        if self._conformal is None: self.run()
        return self._conformal
    
    @property
    def area(self):
        if self._area is None: self.run()
        return self._area
    
    @property
    def stretch(self):
        if self._stretch is None: self.run()
        return self._stretch

    @property
    def det(self):
        if self._det is None: self.run()
        return self._det

    @property
    def iso(self):
        if self._iso is None: self.run()
        return self._iso

    @property
    def shear(self):
        if self._shear is None: self.run()
        return self._shear
