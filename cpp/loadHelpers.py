import os
import time

import numpy as np
from scipy.sparse import coo_matrix

from numba import jit, double
from numba import types
from numba.extending import overload

from .buildBeams import buildBeams
from .buildEpsilon import buildEpsilon
from .multigridHelper import makeBoxmeshCoords, makeBoxmeshTets, setActiveFields


def makeBoxmesh(mesh, CFG):
    mesh.currentgrain = 1

    nx = CFG["BM_N"]
    dx = CFG["BM_GRAIN"]

    rin = CFG["BM_RIN"]
    mulout = CFG["BM_MULOUT"]
    rout = nx * dx * 0.5

    if rout < rin:
        print("WARNING in makeBoxmesh: Mesh BM_RIN should be smaller than BM_MULOUT*BM_GRAIN*0.5")

    mesh.setMeshCoords(makeBoxmeshCoords(dx, nx, rin, mulout))

    mesh.setMeshTets(makeBoxmeshTets(nx, mesh.currentgrain))

    mesh.var = setActiveFields(nx, mesh.currentgrain, True)


def loadMeshCoords(fcoordsname):
    """
    Load the vertices. Each line represents a vertex and has 3 float entries for the x, y, and z coordinates of the
    vertex.
    """

    # load the vertex file
    data = np.loadtxt(fcoordsname, dtype=float)

    # check the data
    assert data.shape[1] == 3, "coordinates in " + fcoordsname + " need to have 3 columns for the XYZ"
    print("%s read (%d entries)" % (fcoordsname, data.shape[0]))

    return data


def loadMeshTets(ftetsname):
    """
    Load the tetrahedrons. Each line represents a tetrahedron. Each line has 4 integer values representing the vertex
    indices.
    """
    # load the data
    data = np.loadtxt(ftetsname, dtype=int)

    # check the data
    assert data.shape[1] == 4, "vertex indices in " + ftetsname + " need to have 4 columns, the indices of the vertices of the 4 corners fo the tetrahedron"
    print("%s read (%d entries)" % (ftetsname, data.shape[0]))

    # the loaded data are the vertex indices but they start with 1 instead of 0 therefore "-1"
    return data - 1


def loadBeams(self, fbeamsname):
    return np.loadtxt(fbeamsname)


def loadBoundaryConditions(dbcondsname, N_c=None):
    """
    Loads a boundary condition file "bcond.dat".

    It has 4 values in each line.
    If the last value is 1, the other 3 define a force on a variable vertex
    If the last value is 0, the other 3 define a displacement on a fixed vertex
    """
    # load the data in the file
    data = np.loadtxt(dbcondsname)
    assert data.shape[1] == 4, "the boundary conditions need 4 columns"
    if N_c is not None:
        assert data.shape[0] == N_c, "the boundary conditions need to have the same count as the number of vertices"
    print("%s read (%d x %d entries)" % (dbcondsname, data.shape[0], data.shape[1]))

    # the last column is a bool whether the vertex is fixed or not
    var = data[:, 3] > 0.5
    # if it is fixed, the other coordinates define the displacement
    U = np.zeros((var.shape[0], 3))
    U[~var] = data[~var, :3]
    # if it is variable, the given vector is the force on the vertex
    f_ext = np.zeros((var.shape[0], 3))
    f_ext[var] = data[var, :3]

    # update the connections (as they only contain non-fixed vertices)
    return var, U, f_ext


def loadConfiguration(Uname, N_c=None):
    """
    Load the displacements for the vertices. The file has to have 3 columns for the displacement in XYZ and one
    line for each vertex.
    """
    data = np.loadtxt(Uname)
    assert data.shape[1] == 3, "the displacement file needs to have 3 columnds"
    if N_c is not None:
        assert data.shape[0] == N_c, "there needs to be a displacement for each vertex"
    print("%s read (%d entries)" % (Uname, data.shape[0]))

    # store the displacement
    return data