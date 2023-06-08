import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
working_dir = "C:/Users/User/Dropbox (MIT)/Ram Lab Raman Data Repository/Dahlia Spectra"
def timeseries(filename):
    os.system('chmod 777 ' + working_dir+filename)
    spec = pd.read_csv(working_dir+filename)
    data = spec[spec.columns[1]][7:]
    numbers = []
    for i in range(len(data)):
        numbers.append(sum([float(x) for x in data.iloc[i].split('-')]))
    return numbers
numbers = timeseries('/nitrate_5000ppm_30s_peak')
plt.plot(numbers,marker='o')
plt.show()
