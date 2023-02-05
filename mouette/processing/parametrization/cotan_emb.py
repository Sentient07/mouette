from scipy.optimize import fmin_l_bfgs_b
import scipy.sparse as sp
import numpy as np

from ..worker import Worker
from ...mesh.datatypes import *
from ...mesh.mesh import copy
from ...mesh.mesh_attributes import Attribute, ArrayAttribute
from ...geometry import Vec
from ... import geometry as geom
from ...attributes.glob import euler_characteristic
from ...attributes.misc_corners import cotangent
from ...operators import area_weight_matrix

def regul(x, eps=1e-18):
    return (x*x + eps)**(0.25)

def regul_prime(x, eps=1e-18):
    y = x*x + eps
    return 0.5 * x/ (y**0.75)

class CotanEmbedding(Worker):
    """
    Based on the paper
    "Embedding a triangular graph within a given boundary" by Xu et al. (2011)
    
    Given a parametrization of a disk where boundary is fixed, we can optimize the difference between unsigned and signed areas of triangles to compute a parametrization that is foldover-free.
    """

    @allowed_mesh_types(SurfaceMesh)
    def __init__(self, mesh : SurfaceMesh, uv_attr: Attribute, on_corner:bool, verbose:bool=True):
        super().__init__("CotanEmbedding", verbose=verbose)
        self.mesh : SurfaceMesh = mesh
        self.flat_mesh : SurfaceMesh = None
        self.uvs : ArrayAttribute = uv_attr
        self.on_corners : bool = on_corner

    def _energy(self,X):
        E = 0
        grad = np.zeros_like(X)
        nv = len(self.mesh.vertices)
        for (A,B,C) in self.mesh.faces:
            Et = 0
            iuA,ivA,iuB,ivB,iuC,ivC = A,nv+A,B,nv+B,C,nv+C
            uA,vA,uB,vB,uC,vC = (X[_x] for _x in (iuA,ivA,iuB,ivB,iuC,ivC))

            Et = uA * (vB - vC) + uB * (vC - vA) + uC * (vA - vB)
            if not self.mesh.is_vertex_on_border(A):
                grad[iuA] += 2*(vB - vC)
                grad[ivA] += 2*(uC - uB)
            if not self.mesh.is_vertex_on_border(B): 
                grad[iuB] += 2*(vC - vA)
                grad[ivB] += 2*(uA - uC)
            if not self.mesh.is_vertex_on_border(C): 
                grad[iuC] += 2*(vA - vB)
                grad[ivC] += 2*(uB - uA)
            
            l_bc = (uB-uC)**2 + (vB-vC)**2
            l_ac = (uA-uC)**2 + (vA-vC)**2  
            l_ab = (uA-uB)**2 + (vA-vB)**2

            L_ab = - l_ab + l_bc + l_ac 
            L_bc =   l_ab - l_bc + l_ac
            L_ac =   l_ab + l_bc - l_ac
            Eli = 2*l_bc*l_ac + 2*l_ac*l_ab + 2*l_bc*l_ab - l_bc*l_bc - l_ac*l_ac - l_ab*l_ab

            El = regul(Eli)
            Elp = regul_prime(Eli)
            if not self.mesh.is_vertex_on_border(A): 
                grad[iuA] += 4*Elp * ( (uA - uB)*L_ab + (uA - uC)*L_ac )
                grad[ivA] += 4*Elp * ( (vA - vB)*L_ab + (vA - vC)*L_ac )
            if not self.mesh.is_vertex_on_border(B): 
                grad[iuB] += 4*Elp * ( (uB - uA)*L_ab + (uB - uC)*L_bc )
                grad[ivB] += 4*Elp * ( (vB - vA)*L_ab + (vB - vC)*L_bc )
            if not self.mesh.is_vertex_on_border(C): 
                grad[iuC] += 4*Elp * ( (uC - uA)*L_ac + (uC - uB)*L_bc )
                grad[ivC] += 4*Elp * ( (vC - vA)*L_ac + (vC - vB)*L_bc )
            E += (El + 2*Et)
        return E, grad

    def run(self, mode:str="bfgs", tutte_if_convex:bool = False, solver_verbose=True):
        if euler_characteristic(self.mesh)!=1:
            raise Exception("Mesh is not a topological disk. Cannot run parametrization.")
        if not self.mesh.is_triangular():
            raise Exception("Mesh is not triangular.")
        
        if mode not in ["bfgs", "alternate"]:
            raise Exception("CotanEmbedding mode should either be 'bfgs' or 'alternate'")

        # Initialize variable vector from uvs
        nv = len(self.mesh.vertices)
        var = np.zeros(2*nv)
        if self.on_corners:
            for c,v in enumerate(self.mesh.face_corners):
                var[v] = self.uvs[c][0]
                var[nv+v] = self.uvs[c][1]
        else:
            for v in self.mesh.id_vertices:
                var[v] = self.uvs[v][0]
                var[nv+v] = self.uvs[v][1]

        # Call corresponding optimizer
        if mode=="bfgs":
            var = self._optimize_bfgs(var, solver_verbose) 
        elif mode=="alternate":
            var = self._optimize_alternate(var, tutte_if_convex, solver_verbose)

        # Write uvs in attribute
        if self.on_corners:
            # self.mesh.vertices.delete_attribute("uv_coords")
            for c,v in enumerate(self.mesh.face_corners):
                self.uvs[c] = Vec(var[v], var[nv+v])
        else:
            for v in self.mesh.id_vertices:
                self.uvs[v] = Vec(var[v], var[nv+v])
        self._build_flat_mesh(var)

    def _optimize_bfgs(self, var, solver_verbose:bool):
        # det_init = self.mesh.faces.create_attribute("det_init", float, dense=True)
        # for iT,(A,B,C) in enumerate(self.mesh.faces):
        #     iuA,ivA,iuB,ivB,iuC,ivC = 2*A,2*A+1,2*B,2*B+1,2*C,2*C+1
        #     uA,vA,uB,vB,uC,vC = (var[_x] for _x in (iuA,ivA,iuB,ivB,iuC,ivC))
        #     det_init[iT] = geom.sign(uA * (vB - vC) + uB * (vC - vA) + uC * (vA - vB))

        self.log("Optimize cotan energy")
        # return var
        var,energy,infos = fmin_l_bfgs_b(
            # self._energy_simple,        # function and gradient to optimize
            self._energy,        # function and gradient to optimize
            var,                 # Initial variables
            maxiter=2e4,         # maximum number of iterations
            pgtol=1e-6,          # stops if gradient norm is < pgtol
            m=11,                # number of inner iterations for hessian approx.
            factr=1E6,           # stops if improvement is < factr*EPS
            maxls=30,            # maximum number of linesearch
            disp=solver_verbose, # verbose level
            maxfun=1e7       # maximum number of function evaluation
        )
        self.log(f"Stopped after {infos['nit']} iterations")
        self.log(f"Final energy : {energy}")
        return var

        # Compute dets
        det_final = self.mesh.faces.create_attribute("det_final", float, dense=True)
        for iT,(A,B,C) in enumerate(self.mesh.faces):
            iuA,ivA,iuB,ivB,iuC,ivC = 2*A,2*A+1,2*B,2*B+1,2*C,2*C+1
            uA,vA,uB,vB,uC,vC = (var[_x] for _x in (iuA,ivA,iuB,ivB,iuC,ivC))
            det_final[iT] = geom.sign(uA * (vB - vC) + uB * (vC - vA) + uC * (vA - vB))
        
    def _optimize_alternate(self, var, tutte, verbose):

        def check_dets(var):
            for (A,B,C) in self.mesh.faces:
                uA,vA,uB,vB,uC,vC = (var[_x] for _x in (A,nv+A,B,nv+B,C,nv+C))
                if (uA * (vC - vB) + uB * (vA - vC) + uC * (vB - vA)) < 0 : 
                    return False
            return True

        nv = len(self.mesh.vertices)
        n_iter = 0
        n_iter_max = 100
        n_coeff_lap = 12*len(self.mesh.faces)
        rows = np.zeros(n_coeff_lap, dtype=np.int32)
        cols = np.zeros(n_coeff_lap, dtype=np.int32)
        coeffs = np.zeros(n_coeff_lap, dtype=np.float64)
        Iinds = np.array(self.mesh.interior_vertices, dtype=np.int32)
        Binds = np.array(self.mesh.boundary_vertices, dtype=np.int32)
        AreaW = area_weight_matrix(self.mesh, inverse=True).tocsc()
        if tutte:
            cot = cotangent(self.mesh, persistent=False)

        while n_iter<n_iter_max and not check_dets(var):
            n_iter += 1
            self.log(f"Iter {n_iter}/{n_iter_max}")
            # build cotan laplacian  
            _c = 0
            for iF,(A,B,C) in enumerate(self.mesh.faces):
                if tutte and n_iter==1:
                    cot_a,cot_b,cot_c = (cot[3*iF+_i]/2 for _i in range(3))
                else:
                    uA,vA,uB,vB,uC,vC = (var[_x] for _x in (A,nv+A,B,nv+B,C,nv+C))
                    l_bc = (uB-uC)**2 + (vB-vC)**2
                    l_ac = (uA-uC)**2 + (vA-vC)**2  
                    l_ab = (uA-uB)**2 + (vA-vB)**2
                    Eli = 2*l_bc*l_ac + 2*l_ac*l_ab + 2*l_bc*l_ab - l_bc*l_bc - l_ac*l_ac - l_ab*l_ab
                    # El = np.sqrt(Eli)
                    El =regul(Eli, 1e-18)
                    cot_a = (l_ac+l_ab-l_bc)/El/2
                    cot_b = (l_bc+l_ab-l_ac)/El/2
                    cot_c = (l_bc+l_ac-l_ab)/El/2
                for (i, j, v) in [(A, B, cot_c/2), (B, C, cot_a/2), (C, A, cot_b/2)]:
                    rows[_c], cols[_c], coeffs[_c], _c = i, i, v, _c+1
                    rows[_c], cols[_c], coeffs[_c], _c = j, j, v, _c+1
                    rows[_c], cols[_c], coeffs[_c], _c = i, j, -v, _c+1
                    rows[_c], cols[_c], coeffs[_c], _c = j, i, -v, _c+1 
            L = AreaW * sp.csc_matrix((coeffs,(rows,cols)), dtype= np.float64)
            LI = L[Iinds,:][:,Iinds]
            LB = L[Iinds,:][:,Binds] 
            # solve linear system
            var[Iinds] = sp.linalg.spsolve(LI, -LB.dot(var[Binds])) # first system for u
            var[Iinds+nv] = sp.linalg.spsolve(LI, -LB.dot(var[Binds+nv])) # second system for v
        return var
        
    def _build_flat_mesh(self, var):
        # build the flat mesh : vertex coordinates are uv of original mesh
        self.flat_mesh = copy(self.mesh)
        nv = len(self.mesh.vertices)
        for v in self.mesh.id_vertices:
            self.flat_mesh.vertices[v] = Vec(var[v], var[nv+v], 0.)