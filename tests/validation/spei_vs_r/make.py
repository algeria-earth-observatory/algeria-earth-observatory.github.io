import sys, numpy as np, pandas as pd
sys.path.insert(0, r'D:/algeria_earth_observatory/scripts/pipelines')
from aeo.spei import spei
rng=np.random.default_rng(11); years=65
months=np.tile(np.arange(1,13),years)
seasonal=np.tile(np.array([40,30,20,0,-40,-110,-160,-150,-80,-20,20,40.0]),years)
d=seasonal+rng.gamma(2,15,months.size)-30
ref=(np.arange(months.size)>=30*12)&(np.arange(months.size)<60*12)  # years 31-60
out={'d':d}
for k in (1,3,6,12): out[f'py{k}']=spei(d,months,k,ref)
pd.DataFrame(out).to_csv(sys.argv[1]+'/py.csv',index=False)
