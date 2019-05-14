import numpy as np


def saveEpsilon(epsilon, fname, CFG):
    """
    Save the material function to a file, e.g. for further plotting.
    """
    imax = int(np.ceil((CFG["EPSMAX"] + 1.0) / CFG["EPSSTEP"]))

    with open(fname, "w") as fp:
        for i in range(imax):
            lambd = (i * CFG["EPSSTEP"]) - 1.0

            fp.write(str(lambd) + " " + str(epsilon[i]) + "\n")

    lambd = (np.arange(imax) * CFG["EPSSTEP"]) - 1.0
    np.save(fname.replace(".dat", ".npy"), np.array([lambd, epsilon]).T)


def buildEpsilon(k1, ds0, s1, ds1, CFG):
    """
    Build a lookup table for the material function.
    """
    print("EPSILON PARAMETERS", k1, ds0, s1, ds1, CFG["EPSSTEP"])

    # calculate the number of steps (+1.0 because EPSMIN is defined as -1)
    # TODO define EPSMIN in the config?
    epsmin = -1.0
    epsmax = CFG["EPSMAX"]
    epsstep = CFG["EPSSTEP"]

    def indexToLambda(index):
        return index * epsstep + epsmin

    def lambdaToIndex(lambd):
        return np.ceil((lambd - epsmin) / epsstep).astype(int)

    # epsilon cannot be smaller than -1 because for lambda = -1 the fiber already has 0 length
    imax = lambdaToIndex(epsmax)

    lambd = indexToLambda(np.arange(imax))

    # define epsbarbar according to p 43 eq 4.1.5

    # the linear spring regime (0 < lambda < s1)
    epsbarbar = np.ones(imax) * k1

    # buckling for compression
    if ds0 != 0.0:
        buckling = lambd < 0
        epsbarbar[buckling] += k1 * (np.exp(lambd[buckling] / ds0) - 1)
    # and exponential strech for overstreching fibers
    if ds1 > 0.0:
        streching = lambd > s1
        epsbarbar[streching] = k1 * np.exp((lambd[streching] - s1) / ds1)

    # savety to prevent overflow
    epsbarbar[epsbarbar > 10e10] = 10e10

    # epsbar is the integral over epsbarbar
    epsbar = np.cumsum(epsbarbar * epsstep)

    # define the offset so that for lambda = 0 epsbar = 0
    imid = lambdaToIndex(0)
    epsbar -= epsbar[imid]

    # epsilon is the integral over epsbar
    epsilon = np.cumsum(epsbar * epsstep)

    # define the offset so that for lambda = 0 epsilon = 0
    epsilon -= epsilon[imid]

    from numba import jit
    @jit(nopython=True)
    def lookUpEpsilon(deltal):
        # we now have to pass this though the non-linearity function w (material model)
        # this function has been discretized and we interpolate between these discretisation steps

        # the discretisation step
        li = np.floor((deltal - epsmin) / epsstep)
        # the part between the two steps
        dli = (deltal - epsmin) / epsstep - li

        # if we are at the border of the discretisation, we stick to the end
        max_index = li > ((epsmax - epsmin) / epsstep) - 2
        li[max_index] = int(((epsmax - epsmin) / epsstep) - 2)
        dli[max_index] = 0

        # convert now to int after fixing the maximum
        li = li.astype(np.int64)

        # interpolate between the two discretisation steps
        epsilon_b = (1 - dli) * epsilon[li] + dli * epsilon[li + 1]
        epsbar_b = (1 - dli) * epsbar[li] + dli * epsbar[li + 1]
        epsbarbar_b = (1 - dli) * epsbarbar[li] + dli * epsbarbar[li + 1]

        return epsilon_b, epsbar_b, epsbarbar_b

    return epsilon, epsbar, epsbarbar, lookUpEpsilon

def buildEpsilon(k1, ds0, s1, ds1, CFG):
    """
    Build a lookup table for the material function.
    """
    print("EPSILON PARAMETERS", k1, ds0, s1, ds1)

    # calculate the number of steps (+1.0 because EPSMIN is defined as -1)
    # TODO define EPSMIN in the config?
    # epsilon cannot be smaller than -1 because for lambda = -1 the fiber already has 0 length
    imax = int(np.ceil((CFG["EPSMAX"] + 1.0) / CFG["EPSSTEP"]))

    # initialize the lists
    epsilon = np.zeros(imax)
    epsbar = np.zeros(imax)
    epsbarbar = np.zeros(imax)

    # iterate over all steps
    for i in range(imax):
        # calculate the current argument (-1 because we start with EPSMIN = -1)
        lambd = (i * CFG["EPSSTEP"]) - 1.0

        epsbarbar[i] = 0

        # define epsbarbar according to p 43 eq 4.1.5
        if lambd > 0:
            # constant
            epsbarbar[i] += k1

            # of larger than s1, it grows exponentially
            if lambd > s1 and ds1 > 0.0:
                epsbarbar[i] += k1 * (np.exp((lambd - s1) / ds1) - 1.0)
        else:
            # for negative values it decays exponentially
            if ds0 != 0.0:
                epsbarbar[i] += k1 * np.exp(lambd / ds0)
            else:
                epsbarbar[i] += k1

        # savety to prevent overflow
        if epsbarbar[i] > 10e10:
            epsbarbar[i] = 10e10

    # epsbar is the integral over epsbarbar
    # TODO perhaps we can do this with cumsum
    sum = 0.0
    for i in range(imax):
        sum += epsbarbar[i] * CFG["EPSSTEP"]
        epsbar[i] = sum

    # define the offset so that for lambda = 0 epsbar = 0
    imid = int(np.ceil(1.0 / CFG["EPSSTEP"]))
    off = epsbar[imid]
    for i in range(imax):
        epsbar[i] -= off

    # epsilon is the integral over epsbar
    # TODO simplify with cumsum?
    sum = 0.0
    for i in range(imax):
        sum += epsbar[i] * CFG["EPSSTEP"]
        epsilon[i] = sum

    # define the offset so that for lambda = 0 epsilon = 0
    off = epsilon[imid]
    for i in range(imax):
        epsilon[i] -= off

    return epsilon, epsbar, epsbarbar, None