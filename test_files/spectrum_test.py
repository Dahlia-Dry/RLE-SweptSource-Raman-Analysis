import sys
sys.path.append("..")
from gui_components.spectrum import *
import matplotlib.pyplot as plt

def test1():
    # 1. Test that recorded data looks like collected data
    data = []
    f = open('test/tisapph_nitrate_1000ppm_1hr_spad002008.spad')
    f.readline()
    upload_spec = pd.read_csv(f,index_col='n_sample')
    for i in range(len(upload_spec)):
        data = data + [float(x) for x in upload_spec[str(808.7)].iloc[i].split('~')]
    plt.plot(data)
    plt.show()

def test2():
    #2. Test that datafile in metadata matches original data
    spec = batch_process_folder('test/')[0]
    # df = pd.DataFrame(json.loads(spec.meta['spad_datafile']))
    # df.index = df.index.astype(int)
    # df = df.sort_index(ascending=True)
    # df.rename(columns={c:float(c) for c in df.columns},inplace=True)

    plt.plot(spec.fetch_raw_data().flatten())
    plt.show()
    #FIX: sample order not preserved because jsonify converts sample index values to strings and they get shuffled

test2()