import scipy.io
import numpy as np
from skimage import transform
from scipy.io import loadmat
from scipy.sparse import csr_matrix
import inspect
import scipy.sparse.linalg as ln
from skimage.restoration import (denoise_tv_chambolle, denoise_bilateral,
                                 denoise_wavelet, estimate_sigma)
import time
from pymitter import EventEmitter

# Need to use this (EventEmitter) for comunication with the GUI, please don't remove it, I used this trough the code
ee = EventEmitter()


def random_sampling(x, sr):
    ''' Random Sampling
  x : full data
  sr: subsampling factor
  '''
    dim = x.shape
    batch = 1  # dim[0]
    M = dim[0]
    N = dim[1]
    # L = dim[3]

    tasa_compression = int(sr * N)
    pattern_vec = np.ones((N,))

    ss = np.random.permutation(list(range(1, N - 1)))
    pattern_vec[ss[0:tasa_compression]] = 0
    H0 = np.tile(pattern_vec.reshape(1, -1), (M, 1))

    out = x * H0

    pattern_bool = np.asarray(pattern_vec, dtype=bool)

    return out, pattern_vec, pattern_bool


def dct2():
    '''
    Returns a function to compute the Discrete Cosine
    Transform (DCT) for 2D signals.

    The DCT is a transform similar to the Discrete Fourier
    Transform, but using only real numbers. The DCT express
    a finite sequence of points in terms of cosine functions
    oscillating at different frequencies.

    The 1D DCT is computed as:

    .. math::
        y_{k} = 2\sum_{n=0}^{N-1} x_{n}\cos\left( \frac{\pi k (2n + 1)}{2N} \right)

    To compute the 2D transform, the 1D transform is applied
    to the rows and the columns of the input matrix.
    '''
    def dct2_function(x):
        return (scipy.fft.dct(scipy.fft.dct(x).T)).T

    return dct2_function

def idct2():
    '''
    Returns a function to compute the Inverse of the Discrete
    Cosine Transform (IDCT) for 2D signals.

    Formally, the Discrete Fourier Transform in a linear function
    that maps a real vector to another real vector of the same
    dimension. As the transform is a linear function, then
    invertible, it is possible to define an inverse function that
    allows to recover the original signal from the transformed
    values.

    The 1D IDCT is computed as:

    .. math::
        x_{k} = \frac{y_0}{2N} + \frac{1}{N}\sum_{n=1}^{N-1}y_{n}\cos\left( \frac{\pi (2k+1) n}{2N} \right)

    To compute the 2D transform, the 1D transform is applied
    to the rows and the columns of the input matrix.
    '''
    def idct2_function(x):
        return (scipy.fft.idct(scipy.fft.idct(x).T)).T

    return idct2_function

class Operator:
    '''
    A class to represent the matrix operators used in the
    forward model of the seismic reconstruction problem.

    Attributes
    ----------
    H : array-like
        The sensing matrix. A matrix with the positions of the
        missing elements.
    m : int
        The first dimension of the input data in a 2D form.
    n : int
        The second dimension of the input data in a 2D form.
    operator_dir : function
        This function applies a 2D transform to promote the
        sparsity of the signal in certain base of representation.
    operator_inv : function
        This function applies the inverse transform of the
        `operator_dir` function.

    Methods
    -------
    transpose(x)
        This method multiplies the input vector with the transpose
        of the operator.
    direct(x)
        This method multiplies the input vector with the equivalent
        of the operator for the model.
    '''
    def __init__(self, H, m, n, operator_dir, operator_inv):
        '''
        Parameters
        ----------
        H : array-like
            The sensing matrix. A matrix with the positions of the
            missing elements.
        m : int
            The first dimension of the input data in a 2D form.
        n : int
            The second dimension of the input data in a 2D form.
        operator_dir : function
            This function applies a 2D transform to promote the
            sparsity of the signal in certain base of representation.
        operator_inv : function
            This function applies the inverse transform of the
            `operator_dir` function.
        '''
        self.H = H
        self.m = m
        self.n = n
        self.operator_dir = operator_dir
        self.operator_inv = operator_inv

    def transpose(self, x):  # y = D'H' * x
        '''
        Applies the equivalent of the matricial transpose
        operator to the input vector.

        Mathematically is defined as

        .. math::
            y = D^T H^T x

        where H is the sensing matrix and D the transformation
        basis.

        Parameters
        ----------
        x : array-like
            An array to apply the operator.

        Returns
        -------
        y : array-like
            The traspose operation applied to the input
            vector.
        '''
        Ht = self.H.transpose()
        y = Ht * np.squeeze(x.T.reshape(-1))  # H' * x

        y = np.reshape(y, [self.m, self.n], order='F')

        y = self.operator_dir(y)

        return y

    def direct(self, x):  # y = H * D * x
        '''
        Applies the equivalent of the matricial direct
        operator to the input vector.

        Mathematically is defined as

        .. math::
            y = H D x

        where H is the sensing matrix and D the transformation
        basis.

        Parameters
        ----------
        x : array-like
            An array to apply the operator.

        Returns
        -------
        y : array-like
            The traspose operation applied to the input
            vector.
        '''
        x = np.reshape(x, [self.m, self.n], order='F')  # ordenar

        theta = self.operator_inv(x)  # D * x

        y = self.H * np.squeeze(theta.T.reshape(-1))  # H * D * x

        return y

# -------------------------------------------------------------------------
def soft_threshold(x, t):
    '''
    The Soft thresholding is a wavelet shrinkage operator.

    This operator is used in the area of compressive as the close
    solution of the proximal operator for the L1 norm.

    Parameters
    ----------
    x : array-like
        An array to apply the shrinkage operator.
    t : float
        The threshold value to compute the operator.

    Returns
    -------
    y : array-like
        The solution of the solf thresholding operator for the
        input array and threshold value.
    '''
    tmp = (np.abs(x) - t)
    tmp = (tmp + np.abs(tmp)) / 2
    y = np.sign(x) * tmp
    return y

def PSNR(original, compressed):
    '''
    The Peak Signal-to-Noise Ratio (PSNR) is an engineering term for
    the ratio between the maximum power of a signal and the power of the
    corrupting noise that affects the fidelity.

    This metrics is usually used to quantify the reconstruction quality
    for images and videos subject to a compression process.

    Mathematically, this term is defined as:

    .. math::
        PSNR = 10\log\left( \frac{MAX_I^2}{MSE} \right)

    Where:

    .. math::
        MSE = \frac{1}{mn} \sum_{i=0}^{m-1} \sum_{j=0}^{n-1}[ I(i,j) - K(i,j) ]^2

    Parameters
    ----------
    original   : array-like
                 The original signal to compare.
    compressed : array-like
                 The reconstructed signal.

    Returns
    -------
    psnr : float
           The solution of the solf thresholding operator for the
           input array and threshold value.
    '''
    mse = np.mean((original - compressed) ** 2)
    if (mse == 0):  # MSE is zero means no noise is present in the signal .
        # Therefore PSNR have no importance.
        return 100
    max_pixel = np.max(original)
    psnr = 20 * np.log10(max_pixel / np.sqrt(mse))
    return psnr

class Algorithms:
    '''
    A class that contains different algorithms solutions to solve the
    seismic data reconstruction problem.

    Mathematically, the reconstruction problem is defined as an
    optimization problem with the form:

    .. math::
        \underset{x}{\text{arg min}} \| g - HDx \|_2^2 + \lambda\| x \|_1

    where H is the sensing matrix, D is a transformation basis and
    x are the relative coefficients in the transformed domain.

    Attributes
    ----------
    x : array-like
        An 2D input image. The array is resized to the closest
        dimensions with the form 2^n.
    m : int
        The first dimension of the input data x in a 2D form.
    n : int
        The second dimension of the input data in a 2D form.
    H : array-like
        The sensing matrix. A matrix with the positions of the
        missing elements.
    operator_dir : function
        This function applies a 2D transform to promote the
        sparsity of the signal in certain base of representation.
        It could be a function or a string with the name of a
        predefined transform. Actually the only predefined transform
        is DCT and is used with the string 'DCT2D'.
    operator_inv : function
        This function applies the inverse transform of the
        `operator_dir` function.
        It could be a function or a string with the name of a
        predefined transform. Actually the only predefined transform
        is DCT and is used with the string 'IDCT2D'.

    Methods
    -------
    FISTA(lmb, mu, max_itr)
        Applies a Fast Iterative Shrinkage-Thresholding Algorithm (FISTA)
        to solve the optimization problem.
    GAP(lmb, max_itr)
        Applies a GAP Algorithm to solve the optimization problem.
    TwIST(lmb, alpha, beta, max_itr)
        Applies a Time to Walking Independently After Stroke (TwIST)
        algorithm to solve the optimization problem.
    '''

    def __init__(self, x, H, operator_dir, operator_inv):
        '''
        Parameters
        ----------
        x : array-like
            An 2D input image.
        H : array-like
            The sensing matrix. A matrix with the positions of the
            missing elements.
        operator_dir : function
            This function applies a 2D transform to promote the
            sparsity of the signal in certain base of representation.
        operator_inv : function
            This function applies the inverse transform of the
            `operator_dir` function.
        '''

        # ------- change the dimension of the inputs image --------
        m, n = x.shape
        # m = int(2 ** (np.ceil(np.log2(m)) - 1))
        # n = int(2 ** (np.ceil(np.log2(n)) - 1))
        x = transform.resize(x, (m, n))
        x = x / np.abs(x).max()
        self.x = x
        self.m, self.n = x.shape
        self.pattern = 0

        # ---------- Load or build the sensing matrix -------------
        if isinstance(H, (list, tuple, np.ndarray)):
            if (len(H.shape) == 1):
                # Create H from a given input pattern
                # The input H must be the pattern, i.e., H is a vector!
                temp0 = np.reshape(np.asarray(range(0, m * n)), [n, m]).T
                temp = temp0[:, H]
                self.pattern = H
                temp = temp.T.reshape(-1)  # Column Vectorization
                self.H = csr_matrix((np.ones(temp.shape), (range(0, len(temp)), temp)), shape=(len(temp), int(m * n)))
            else:
                # Takes the input H as the sampling matrix
                self.H = H
        else:
            # H here is a given subsampling value
            # Load a pre-determinated random pattern
            Nsub = int(np.round(m * (H)))
            # iava = np.random.permutation(m)
            iava = np.squeeze(loadmat('data/iava.mat')['iava']) - 1
            self.cort = np.sort(iava[Nsub:])
            iava = np.sort(iava[0:Nsub])
            self.pattern = iava
            temp0 = np.reshape(np.asarray(range(0, m * n)), [n, m]).T
            temp = temp0[:, iava]
            temp = temp.T.reshape(-1)  # Column Vectorization
            self.H = csr_matrix((np.ones(temp.shape), (range(0, len(temp)), temp)), shape=(len(temp), int(m * n)))

        # ---------- Load or create the basis function  ---------

        if (inspect.isfunction(operator_dir)):
            self.operator_dir = operator_dir
        else:
            if operator_dir == 'DCT2D':
                self.operator_dir = dct2()

        if (inspect.isfunction(operator_inv)):
            self.operator_inv = operator_inv
        else:
            if operator_inv == 'IDCT2D':
                self.operator_inv = idct2()

        # ------------ This is a special class of operator ------------
        self.A = Operator(self.H, self.m, self.n, self.operator_dir, self.operator_inv)

    def measurements(self):
        '''
        Operator measurement models the subsampled acquisition process given a
        sampling matrix H

        Returns
        -------
        measures : Y = H@x
        '''

        return self.H * np.squeeze(self.x.T.reshape(-1))

    # ---------------------------------------------FISTA----------------------------------------

    def FISTA(self, lmb, mu, max_itr):
        '''
        This is the python implementation of the FISTA (A Fast Iterative Shrinkage-Thresholding Algorithm )
        Beck, A., & Teboulle, M. (2009). A fast iterative shrinkage-thresholding algorithm for linear
        inverse problems. SIAM journal on imaging sciences, 2(1), 183-202.
        This one of the most well-known first-order optimization scheme in the literature, as it achieves
        the worst-case \mathbf{\mathit{O}}(1/k^{2}) optimal convergence rate in terms of objective function value.

        The FISTA is computed as:

        .. math::
              t_{k}=\frac{1+\sqrt{4t^{2}_{k-1}}}{2}
              a_{k}=\frac{t_{k-1}-1}{t_{k}}
              y_{k}=x_{k}+a_{k}(x_{k}-x_{k-1})
              x_{k+1}=prox_{\gamma R}(y_{k}-\gamma \bigtriangledown F(y_{k}))

        Input:
            self:       They have the variables of the Algorithm class, such as H,y, sparsity basis.
            lmb:        float
                        The sparsity regularizer
            mu :        type
                        The step-descent of the algorithm
            max_itr :   int
                        The maximum number of iterations
        '''

        y = self.measurements()

        print(' FISTA: \n')

        dim = self.x.shape
        x = np.zeros(dim)
        q = 1
        s = x
        hist = np.zeros((max_itr + 1, 2))
        print('itr \t ||x-xold|| \t PSNR \n')
        itr = 0
        while (itr < max_itr):
            x_old = x
            s_old = s
            q_old = q

            grad = self.A.transpose(self.A.direct(s_old) - y)  # Ht * (H * s_old - y)
            z = s_old - mu * (grad)

            # proximal
            x = soft_threshold(z, lmb)
            q = 0.5 * (1 + np.sqrt(1 + 4 * (q_old ** 2)))
            s = x + ((q_old - 1) / (q)) * (x - x_old)
            itr = itr + 1

            residualx = np.linalg.norm(x - x_old) / np.linalg.norm(x)

            psnr_val = PSNR(self.operator_inv(s), self.x)

            hist[itr, 0] = residualx
            hist[itr, 1] = psnr_val
            ee.emit("algorithm_update", itr, format(hist[itr, 0], ".4e"), format(hist[itr, 1], ".3f"))
            print(itr, '\t Error:', format(hist[itr, 0], ".4e"), '\t PSNR:', format(hist[itr, 1], ".3f"), 'dB \n')

        return self.operator_inv(s), hist

    # ---------------------------------------------GAP----------------------------------------
    def GAP(self, lmb, max_itr):
        '''
        Let \Phi \in \mathbb{R}^{r\times x}  with r < n be given and fixed, and z \in \mathbb{R}^{n}
        be an arbitrary S-sparse vector, which has at most S < r nonzero elements.
        Reconstruction of z from y = \Phi z is a problem that centers around the theory and practice
        of compressive sensing. The GAP algorithm extends classical alternating projection to the case in
        which projections are performed between convex sets that undergo a systematic sequence of changes.

        .. math::
                w_{t} = \theta_{t-1} + \Phi^{T}(\Phi\Phi^{T})(y - \Phi\theta_{t-1})

        The algorithm  can be interrupted anytime to return a valid solution and resumed subsequently to
        improve the  solution.

        Parameters
        ----------
        lmb :    float
                 The threshold value to compute the operator.
        max_itr : int
                  Maximum number of iterations
        '''
        y = self.measurements()

        print('---------GAP method---------- \n')

        dim = self.x.shape
        x = np.zeros(dim)
        hist = np.zeros((max_itr + 1, 2))

        residualx = 1
        tol = 1e-2

        print('itr \t ||x-xold|| \t PSNR \n')
        itr = 0
        while (itr < max_itr):  # & residualx>tol):
            x_old = x

            temp = self.A.direct(x) - y

            grad = self.A.transpose(temp)
            z = x - grad

            # proximal
            x = soft_threshold(z, lmb)
            itr = itr + 1

            residualx = np.linalg.norm(x - x_old) / np.linalg.norm(x)

            psnr_val = PSNR(self.operator_inv(x), self.x)

            hist[itr, 0] = residualx
            hist[itr, 1] = psnr_val
            ee.emit("algorithm_update", itr, format(hist[itr, 0], ".4e"), format(hist[itr, 1], ".3f"))
            print(itr, '\t Error:', format(hist[itr, 0], ".4e"), '\t PSNR:', format(hist[itr, 1], ".3f"), 'dB \n')

        return self.operator_inv(x), hist

    # ----------------TWIST----------------------------
    def TwIST(self, lmb, alpha, beta, max_itr):
        '''
        Stationary Two-Step Iterative Shrinkage/Thresholding (TWIST) for solving \mathbf{Ax=b}.
        Consider the linear system \mathbf{Ax=b}, with \mathbf{A} positive definite;
        define a so-called splitting of \mathbf{A} as \mathbf{A=C-R}, such that \mathbf{C}
        is positive definite and easy to invert. TWIST is defined as:

        .. math::
              \mathbf{x_{1}}=\mathbf{\Gamma_{\lambda}({x_{0})}}
              \mathbf{x_{t+1}}=(1-\alpha)\mathbf{x_{1}}+(\alpha-\beta)\mathbf{x_{t}}+\beta\mathbf{\Gamma_{\lambda}({x_{t})}}

        for t\geq 1, where \mathbf{x_{0}} is the initial vector, and \alpha, \beta,
        are the parameters of the algorithm.

        Parameters
        ----------
        lmb :   float
                The threshold value to compute the operator.
        alpha : float
                Convergence parameter
        beta :  float
                Convergence parameter
        max_itr : int
                Maximum number of iterations
        '''
        y = self.measurements()

        print('---------TwIST method---------- \n')

        dim = self.x.shape
        x = np.zeros(dim)
        hist = np.zeros((max_itr + 1, 2))

        residualx = 1
        tol = 1e-3

        print('itr \t ||x-xold|| \t PSNR \n')
        itr = 0
        x_old = x

        while (itr < max_itr):  # & residualx <= tol):

            temp = self.A.direct(x) - y

            grad = self.A.transpose(temp)
            z = x - grad

            # proximal
            s = soft_threshold(z, lmb)

            # Actualizacion
            temp = (1 - alpha) * x_old + (alpha - beta) * x + beta * s
            x_old = x
            x = temp

            itr = itr + 1

            residualx = np.linalg.norm(x - x_old) / np.linalg.norm(x)

            psnr_val = PSNR(self.operator_inv(x), self.x)

            hist[itr, 0] = residualx
            hist[itr, 1] = psnr_val
            ee.emit("algorithm_update", itr, format(hist[itr, 0], ".4e"), format(hist[itr, 1], ".3f"))
            print(itr, '\t Error:', format(hist[itr, 0], ".4e"), '\t PSNR:', format(hist[itr, 1], ".3f"), 'dB \n')

        return self.operator_inv(x), hist

    def ADMM(self, rho, gamma, lamnda, max_itr):

        s = 0

        y = self.measurements()

        print('---------ADMM method---------- \n')

        hist = np.zeros((max_itr + 1, 2))
        dim = self.x.shape
        x = np.zeros(dim)

        begin_time = time.time()

        residualx = 1
        tol = 1e-3

        v = x.ravel()
        u = x.ravel()

        print('itr \t ||x-xold|| \t PSNR \n')
        itr = 0

        HtY = self.A.transpose(y)

        while (itr < max_itr):  # & residualx <= tol):
            x_old = x

            # F-update
            temp = HtY.ravel() + np.sqrt(rho) * (v - u)
            x = ln.cgs(self.A, temp, x0=None, tol=1e-05, maxiter=20)

            # Proximal
            vtilde = x + u
            v = soft_threshold(vtilde, lamnda / rho)

            # Update langrangian multiplier
            u = u + (x - v)

            # update rho
            rho = rho * gamma

            itr += 1

            residualx = np.linalg.norm(x - x_old) / np.linalg.norm(x)

            x = np.reshape(x, [self.m, self.n])
            psnr_val = PSNR(self.operator_inv(x), x_old)
            hist[itr, 0] = residualx
            hist[itr, 1] = psnr_val

            if (itr + 1) % 5 == 0:
                # mse = np.mean(np.sum((y-A(v,Phi))**2,axis=(0,1)))
                end_time = time.time()
                # Error = %2.2f,
                ee.emit("algorithm_update", itr, residualx, psnr_val)
                print("ADMM-TV: Iteration %3d,  Error = %2.2f, PSNR = %2.2f dB,"
                      " time = %3.1fs."
                      % (itr + 1, residualx, psnr_val, end_time - begin_time))
                # % (ni + 1, psnr(v, X_ori), end_time - begin_time))

        return self.operator_inv(v), hist