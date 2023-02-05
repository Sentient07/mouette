from ...mesh.datatypes import *
from ...mesh.mesh_attributes import Attribute
from ..features import FeatureEdgeDetector
from ..connection import SurfaceConnection
from ...utils.argument_check import *

# 2D implementations
from .faces2d import *
from .vertex2d import *

# 3D implementations
from .vertex3d import *
from .cells import *

@allowed_mesh_types(SurfaceMesh)
def SurfaceFrameField(
    mesh : SurfaceMesh,
    elements : str,
    order : int = 4,
    features : bool = True,
    n_smooth : int = 10,
    smooth_attach_weight : float = None,
    # orthogonal : bool = True,
    # orthog_rigidity : float = 0.5,
    use_cotan : bool = True,
    cad_correction : bool = True,
    verbose : bool = False,
    singularity_indices : Attribute = None,
    custom_connection : SurfaceConnection = None,
    custom_feature : FeatureEdgeDetector = None
) -> FrameField :
    """
    Framefield implementation selector.
    A Frame field is a set of n directions 

    References for implementations : 
    [1] An Approach to Quad Meshing Based on Harmonic Cross-Valued Maps and the Ginzburg-Landau Theory, Viertel and Osting (2018)
    [2] Frame Fields for CAD models, Desobry et al. (2022)
    [3] Trivial Connections on Discrete Surfaces, Crane et al. (2010)

    Args:
        mesh (SurfaceMesh): the supporting mesh onto which the framefield is based

        elements (str): "vertices" or "faces", the mesh elements onto which the frames live.
        
        order (int, optional): Order of the frame field (number of branches). Defaults to 4.
        
        features (bool, optional): Whether to consider feature edges or not. 
            If no 'custom_features' argument is provided, features will be automatically detected (see the FeatureEdgeDetector class). Defaults to True.
        
        n_smooth (int, optional): Number of smoothing steps to perform. Defaults to 10.
        
        smooth_attach_weight (float, optional): Custom attach weight to previous solution during smoothing steps. 
            If not provided, will be estimated automatically during optimization. Defaults to None.

        use_cotan (bool, optional): whether to use cotan for a better approximation of the Laplace-Beltrami operator. 
            If False, will use a simple adjacency laplacian operator (See the _operators_ module). Defaults to True.

        cad_correction (bool, optional): Whether to modify the parallel transport as in [2] to prevent singularities to appear close to pointy areas. 
            Will overwrite any connection provided with the 'custom_connection' argument. Defaults to True.

        verbose (bool, optional): verbose mode. Defaults to False.
        
        singularity_indices (Attribute, optional): custom singularity indices for the frame field. If provided, will use the algorithm described in [3] to get the smoothest frame field with these singularities.
            If elements is "vertices", the attribute should be indexed by the faces (where singularities appear)
            If elements is "faces", the attribute should be indexed by the vertices
            /!\ Indices should respect the Poincarré-Hopf theorem. Defaults to None.
        
        custom_connection (SurfaceConnection, optional): custom connection object to be used for parallel transport. If not provided, a connection will be automatically computed (see SurfaceConnection class). Defaults to None.
        
        custom_feature (FeatureEdgeDetector, optional): custom feature edges to be used in frame field optimization. If not provided, feature edges will be automatically detected. If the 'features' flag is set to False, features of this object are ignored. Defaults to None.

    Raises:
        InvalidRangeArgumentError: 'order' should be >= 1
        InvalidRangeArgumentError: 'n_smooth' should be >= 0
        InvalidRangeArgumentError: 'smooth_attach_weight' should be >= 0

    Returns:
        FrameField: A framefield object with the correct specifications
    """

    ### Assert sanity of arguments
    check_argument("elements", elements, str, ["vertices", "faces"])
    check_argument("order", order, int)
    if order<=1: raise InvalidRangeArgumentError("order",order, ">1")  
    check_argument("n_smooth", n_smooth, int)
    if n_smooth<0: raise InvalidRangeArgumentError("n_smooth", n_smooth, ">=0")
    if smooth_attach_weight is not None and smooth_attach_weight<=0 :
        raise InvalidRangeArgumentError("smooth_attach_weight", smooth_attach_weight, ">=0")

    ### Build the correct FF class
    if elements=="vertices":
        if singularity_indices is not None:
            return TrivialConnectionVertices(mesh, singularity_indices, order, verbose, use_cotan=use_cotan, cad_correction=cad_correction, custom_connection=custom_connection, custom_feature=custom_feature)
        else:
            return FrameField2DVertices(mesh, order, features, verbose, n_smooth=n_smooth, smooth_attach_weight=smooth_attach_weight, use_cotan=use_cotan, custom_connection=custom_connection, custom_feature=custom_feature)
    elif elements=="faces":
        if singularity_indices is not None:
            return TrivialConnectionFaces(mesh, singularity_indices, order=order, verbose=verbose, custom_connection=custom_connection, custom_feature=custom_feature)
        return FrameField2DFaces(mesh, order, features, verbose, n_smooth=n_smooth, smooth_attach_weight=smooth_attach_weight,use_cotan=use_cotan,custom_connection=custom_connection,custom_feature=custom_feature)

@allowed_mesh_types(VolumeMesh)
def VolumeFrameField(
    mesh : VolumeMesh,
    elements : str,
    features : bool = True,
    n_smooth : int = 10,
    smooth_attach_weight : float = None, 
    verbose : bool = True,
    custom_boundary_features : FeatureEdgeDetector = None):

    check_argument("elements", elements, str, ["vertices", "cells"])
    
    if elements=="vertices":
        return FrameField3DVertices(mesh, features, verbose, 
        n_smooth=n_smooth, smooth_attach_weight=smooth_attach_weight, 
        custom_boundary_features=custom_boundary_features)
    elif elements=="cells":
        return FrameField3DCells(mesh, features, verbose, n_smooth=n_smooth, smooth_attach_weight=smooth_attach_weight,custom_boundary_features=custom_boundary_features)