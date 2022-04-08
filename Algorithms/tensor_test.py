import numpy as np
from numpy.linalg import inv as inv
import numpy.linalg as ng
import imageio
import matplotlib.pyplot as plt
from Function import *
import time
import cv2


def ten2mat(tensor, mode):
    return np.reshape(np.moveaxis(tensor, mode, 0), (tensor.shape[mode], -1), order='F')


def mat2ten(mat, tensor_size, mode):
    index = list()
    index.append(mode)
    for i in range(tensor_size.shape[0]):
        if i != mode:
            index.append(i)
    return np.moveaxis(np.reshape(mat, list(tensor_size[index]), order='F'), 0, mode)


def supergradient(s_hat, lambda0, theta):
    """Supergradient of the Geman function."""
    return (lambda0 * theta / (s_hat + theta) ** 2)


def GLTC_Geman(dense_tensor, sparse_tensor, alpha, beta, rho, theta, maxiter):
    """Main function of the GLTC-Geman."""
    dim0 = sparse_tensor.ndim
    dim1, dim2, dim3 = sparse_tensor.shape
    dim = np.array([dim1, dim2, dim3])
    binary_tensor = np.zeros((dim1, dim2, dim3))
    binary_tensor[np.where(sparse_tensor != 0)] = 1
    tensor_hat = sparse_tensor.copy()

    X = np.zeros((dim1, dim2, dim3, dim0))  # \boldsymbol{\mathcal{X}} (n1*n2*3*d)
    Z = np.zeros((dim1, dim2, dim3, dim0))  # \boldsymbol{\mathcal{Z}} (n1*n2*3*d)
    T = np.zeros((dim1, dim2, dim3, dim0))  # \boldsymbol{\mathcal{T}} (n1*n2*3*d)
    for k in range(dim0):
        X[:, :, :, k] = tensor_hat
        Z[:, :, :, k] = tensor_hat

    D1 = np.zeros((dim1 - 1, dim1))  # (n1-1)-by-n1 adjacent smoothness matrix
    for i in range(dim1 - 1):
        D1[i, i] = -1
        D1[i, i + 1] = 1
    D2 = np.zeros((dim2 - 1, dim2))  # (n2-1)-by-n2 adjacent smoothness matrix
    for i in range(dim2 - 1):
        D2[i, i] = -1
        D2[i, i + 1] = 1

    w = []
    for k in range(dim0):
        u, s, v = np.linalg.svd(ten2mat(Z[:, :, :, k], k), full_matrices=0)
        w.append(np.zeros(len(s)))
        for i in range(len(np.where(s > 0)[0])):
            w[k][i] = supergradient(s[i], alpha, theta)

    for iters in range(maxiter):
        for k in range(dim0):
            u, s, v = np.linalg.svd(ten2mat(X[:, :, :, k] + T[:, :, :, k] / rho, k), full_matrices=0)
            for i in range(len(np.where(w[k] > 0)[0])):
                s[i] = max(s[i] - w[k][i] / rho, 0)
            Z[:, :, :, k] = mat2ten(np.matmul(np.matmul(u, np.diag(s)), v), dim, k)
            var = ten2mat(rho * Z[:, :, :, k] - T[:, :, :, k], k)
            if k == 0:
                var0 = mat2ten(np.matmul(inv(beta * np.matmul(D1.T, D1) + rho * np.eye(dim1)), var), dim, k)
            elif k == 1:
                var0 = mat2ten(np.matmul(inv(beta * np.matmul(D2.T, D2) + rho * np.eye(dim2)), var), dim, k)
            else:
                var0 = Z[:, :, :, k] - T[:, :, :, k] / rho
            X[:, :, :, k] = np.multiply(1 - binary_tensor, var0) + sparse_tensor

            uz, sz, vz = np.linalg.svd(ten2mat(Z[:, :, :, k], k), full_matrices=0)
            for i in range(len(np.where(sz > 0)[0])):
                w[k][i] = supergradient(sz[i], alpha, theta)
        tensor_hat = np.mean(X, axis=3)
        for k in range(dim0):
            T[:, :, :, k] = T[:, :, :, k] + rho * (X[:, :, :, k] - Z[:, :, :, k])
            X[:, :, :, k] = tensor_hat.copy()

    return tensor_hat


if __name__ == '__main__':
    theta = 2
    alpha = 1000
    rho = 0.01
    beta = 0.1 * rho
    maxiter = 1000
    data_name = 'cube4.npy'

    x = np.load('../data/' + data_name)

    if data_name == 'data.npy':
        x = x.T
    # x = x / np.abs(x).max()

    '''
    ---------------  SAMPLING --------------------
    '''
    sr_rand = 0.4  # 1-compression
    y_rand, pattern_rand, pattern_index = random_sampling(x[:, int(x.shape[1] / 2), :], sr_rand)
    H = pattern_index
    y = x.copy()
    y[..., pattern_rand == 0] = 0
    x = np.transpose(x, [0, 2, 1])
    y = np.transpose(y, [0, 2, 1])
    mask = np.zeros(x.shape)
    mask[:, pattern_rand == 0, :] = 1
    x -= x.min()
    x /= x.max()
    x *= 255
    x = x.astype('uint8')
    mask = mask.astype('uint8')
    paint_method = cv2.INPAINT_TELEA
    output = np.zeros(x.shape)
    tmp = str(pattern_rand.astype('uint8')).split('1')
    t_m = 0
    for t in tmp:
        if t.strip().count('0') > t_m:
            t_m = t.strip().count('0')
    aux_s = np.zeros(x.shape[-1])
    for i in range(1, x.shape[-1] - 1):
        tmp = cv2.inpaint(x[:, :, [i - 1, i, i + 1]], mask[..., 0], t_m+1, flags=paint_method)
        output[..., [i - 1, i, i + 1]] += tmp
        aux_s[[i - 1, i, i + 1]] += 1
    output /= aux_s
    output = np.transpose(output, [0, 2, 1])
    x = np.transpose(x, [0, 2, 1])
    PSNR(x, output)
    # x = x[:, :3, :]
    # y = y[:, :3, :]
    # y = np.reshape(y, [x.shape[0] * x.shape[1], x.shape[2]])
    # x = np.reshape(x, [x.shape[0] * x.shape[1], x.shape[2]])
    # y = np.transpose(y, [0, 2, 1])
    # x = np.transpose(x, [0, 2, 1])
    # x = np.repeat(x[:, :, np.newaxis], 3, axis=2)
    # y = np.repeat(y[:, :, np.newaxis], 3, axis=2)
    '''
    print("Starting Algorithm")
    start = time.time()
    image_hat = GLTC_Geman(x, y, alpha, beta, rho, theta, maxiter)

    # image_hat = GLTC(x, y, alpha, beta, rho, maxiter)
    end = time.time()
    print(f"Duration: {end - start}")
    image_rec = np.round(image_hat).astype(int)
    image_rec[np.where(image_rec > 255)] = 255
    image_rec[np.where(image_rec < 0)] = 0
    pos = np.where((x != 0) & (y == 0))
    rse = np.linalg.norm(image_rec[pos] - x[pos], 2) / np.linalg.norm(x[pos], 2)
    np.savez("tmp.npz", image_rec=image_rec, rse=rse)
    '''
