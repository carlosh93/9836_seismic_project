import numpy as np
import matplotlib.pyplot as plt
import scipy.io
from Function import *
from skimage.metrics import structural_similarity as ssim

import scipy

# ----------------- --------------------
# x = np.load('../data/data.npy')
data_name = 'spii15s.npy'
x = np.load('../data/' + data_name)
if len(x.shape) > 2:
    x = x[:, :, int(x.shape[-1] / 2)]

if data_name == 'data.npy':
    x = x.T
x = x / np.abs(x).max()
max_itr = 100

'''
---------------  SAMPLING --------------------
'''
sr_rand = 0.3  # 1-compression
y_rand, pattern_rand, pattern_index = random_sampling(x, sr_rand)
H = pattern_index

'''
---------------- RECOVERY ALGORITHM -----------------
Select the Algorithm: FISTA , GAP , TWIST , ADMM
'''
case = 'FISTA'
alg = Algorithms(x, H, 'DCT2D', 'IDCT2D')

parameters = {}
if case == 'FISTA':
    parameters = {'max_itr': max_itr,
                  'lmb': 0.1,
                  'mu': 0.3
                  }

elif case == 'GAP':
    parameters = {'max_itr': max_itr,
                  'lmb': 1e-0
                  }

elif case == 'TwIST':
    parameters = {'max_itr': max_itr,
                  'lmb': 0.5,
                  'alpha': 1.2,
                  'beta': 1.998
                  }

elif case == 'ADMM':
    parameters = {'max_itr': max_itr,
                  'lmb': 5e-4,
                  'rho': 1,
                  'gamma': 1
                  }

x_result, hist = alg.get_results(case, **parameters)

# -------------- Visualization ----------------

temp = np.asarray(range(0, pattern_rand.shape[0]))
pattern_rand_b2 = np.asarray(pattern_rand, dtype=bool) == 0
H_elim = temp[pattern_rand_b2]

# x = Alg.x

fig, axs = plt.subplots(2, 2, dpi=150)
fig.suptitle('Results from the ' + case + ' Algorithm')

axs[0, 0].imshow(x, cmap='seismic', aspect='auto')
axs[0, 0].set_title('Reference')

ytemp = y_rand.copy()
ytemp[:, H_elim] = None
axs[1, 0].imshow(ytemp, cmap='seismic', aspect='auto')
axs[1, 0].set_title('Measurements')

# axs[1, 0].sharex(axs[0, 0])
metric = PSNR(x[:, H_elim], x_result[:, H_elim])
metric_ssim = ssim(x[:, H_elim], x_result[:, H_elim])
axs[0, 1].imshow(x_result, cmap='seismic', aspect='auto')
axs[0, 1].set_title(f'Reconstructed \n PSNR: {metric:0.2f} dB, SSIM:{metric_ssim:0.2f}')
print(metric_ssim)
index = 5
axs[1, 1].plot(x[:, H_elim[index]], 'r', label='Reference')
axs[1, 1].plot(x_result[:, H_elim[index]], 'b', label='Recovered')
axs[1, 1].legend(loc='best')
plt.title('Trace ' + str("{:.0f}".format(H_elim[index])))

fig.tight_layout()
plt.show()
