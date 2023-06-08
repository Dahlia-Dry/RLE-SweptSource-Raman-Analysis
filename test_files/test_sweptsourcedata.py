from gui_components.spectrum import *
import pandas as pd
import matplotlib.pyplot as plt


f=open('/Users/dahlia/Projects/RLE/data/october_ssr_nitrate_peak_lod_v2/data/nitrate_lod_10ppm_002001_redo.spad')
fp=open('/Users/dahlia/Projects/RLE/data/october_ssr_nitrate_peak_lod_v2/data/nitrate_lod_10ppm_002001_redo.power')
meta=f.readline()
fp.readline()
data=pd.read_csv(f,index_col='n_sample')
power = pd.read_csv(fp, index_col='n_sample')

spectrum = Spectrum(data,power,meta)
# rawdat = pd.DataFrame(json.loads(spectrum.meta['spad_datafile']))
# rawdat_numbers=[]
# for i in range(len(rawdat.values)):
#     for j in range(len(rawdat.values[0])):
#         rawdat_numbers.append([float(x) for x in rawdat.values[i][j].split('~')])
# print(rawdat_numbers)
# plt.plot(np.ar
# ray(rawdat_numbers).flatten())
# plt.show()
spectrum.plot_raw(show=True)