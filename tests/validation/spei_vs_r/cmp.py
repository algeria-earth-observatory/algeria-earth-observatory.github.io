import sys, pandas as pd, numpy as np
S=sys.argv[1]
p=pd.read_csv(S+'/py.csv'); r=pd.read_csv(S+'/r.csv')
for k in (1,3,6,12):
    a=p[f'py{k}'].values; b=r[f'r{k}'].values; ok=np.isfinite(a)&np.isfinite(b)
    print(f'SPEI-{k}: n={ok.sum()} max|diff|={np.max(np.abs(a[ok]-b[ok])):.2e} corr={np.corrcoef(a[ok],b[ok])[0,1]:.6f} R-inf={np.isinf(b).sum()} nan py/r={np.isnan(a).sum()}/{np.isnan(b).sum()}')
