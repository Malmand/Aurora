"""Fairer baseline for the forecast: raw NWP after a simple bias correction (MOS).

    python -m aurora.forecast.mos_check

Monthly expanding-window linear fits (training truth ends 3 days before the test month), in GHI and in
clear-sky index, for ECMWF and the 3-model mean. Same sample as docs/validation_forecast.md (lead day 1 and 2,
daylight, full regime, Nov 2024 to Oct 2026). Daily block bootstrap for the skill of AURORA vs the best one.
"""
import numpy as np, pandas as pd
from aurora.forecast.backtest import EVAL_START
b = pd.read_parquet('data/itbayat/forecast/backtest_solar.parquet')
b = b[b.calibrated]
e = pd.read_parquet('data/itbayat/raw_small/previous_runs_ecmwf.parquet')
rows=[]
for ld in (1,2):
    d = b[b.lead_day==ld].copy()
    d['ecmwf'] = e[f'ghi_wm2_d{ld}'].reindex(d.index).to_numpy()
    d = d[(d.ghi_clear>=50) & d.ghi_ref.notna() & d.ecmwf.notna()]
    allr = d.copy()
    ev = d[(d.index>=EVAL_START) & (d.regime=='full') & d.ghi_nwp_mean.notna() & d.ghi_persist.notna()]
    rm = lambda x: float(np.sqrt(np.mean((x-ev.ghi_ref)**2)))
    out = {'aurora':rm(ev.ghi_p50),'ecmwf_raw':rm(ev.ecmwf),'mean_raw':rm(ev.ghi_nwp_mean),'n':len(ev)}
    # MOS: monthly expanding-window fits, training data strictly before the test month minus 3 days
    for src in ('ecmwf','ghi_nwp_mean'):
        for kind in ('lin','kidx'):
            pred = pd.Series(np.nan, index=ev.index)
            for m, g in ev.groupby(ev.index.tz_convert(None).to_period('M')):
                t0 = g.index.min() - pd.Timedelta(days=3)
                tr = allr[(allr.index < t0) & allr[src].notna()]
                if kind=='lin':
                    A = np.c_[np.ones(len(tr)), tr[src]]; c = np.linalg.lstsq(A, tr.ghi_ref, rcond=None)[0]
                    p = c[0] + c[1]*g[src]
                else:  # clear-sky index, linear, then back to GHI
                    kx, ky = (tr[src]/tr.ghi_clear).clip(0,1.5), (tr.ghi_ref/tr.ghi_clear).clip(0,1.5)
                    A = np.c_[np.ones(len(tr)), kx]; c = np.linalg.lstsq(A, ky, rcond=None)[0]
                    p = (c[0] + c[1]*(g[src]/g.ghi_clear).clip(0,1.5))*g.ghi_clear
                pred.loc[g.index] = p.clip(lower=0).to_numpy()
            out[f'mos_{src}_{kind}'] = rm(pred)
    # typhoon subset
    rows.append((ld,out))
for ld,o in rows: print(ld, {k:(round(v,1) if isinstance(v,float) else v) for k,v in o.items()})

# block bootstrap on days for skill of AURORA vs best MOS (NWP mean, clear-sky index)
rng=np.random.default_rng(2026)
for ld in (1,2):
    d = b[b.lead_day==ld].copy(); d['ecmwf']=e[f'ghi_wm2_d{ld}'].reindex(d.index).to_numpy()
    d = d[(d.ghi_clear>=50)&d.ghi_ref.notna()&d.ecmwf.notna()]
    ev = d[(d.index>=EVAL_START)&(d.regime=='full')&d.ghi_nwp_mean.notna()&d.ghi_persist.notna()].copy()
    pred=pd.Series(np.nan,index=ev.index)
    for m,g in ev.groupby(ev.index.tz_convert(None).to_period('M')):
        tr=d[(d.index<g.index.min()-pd.Timedelta(days=3))&d.ghi_nwp_mean.notna()]
        kx,ky=(tr.ghi_nwp_mean/tr.ghi_clear).clip(0,1.5),(tr.ghi_ref/tr.ghi_clear).clip(0,1.5)
        c=np.linalg.lstsq(np.c_[np.ones(len(tr)),kx],ky,rcond=None)[0]
        pred.loc[g.index]=((c[0]+c[1]*(g.ghi_nwp_mean/g.ghi_clear).clip(0,1.5))*g.ghi_clear).clip(lower=0).to_numpy()
    ev['mos']=pred; ev['day']=ev.index.floor('D')
    se=ev.assign(a=(ev.ghi_p50-ev.ghi_ref)**2,m=(ev.mos-ev.ghi_ref)**2).groupby('day')[['a','m']].agg(['sum','count'])
    days=se.index.to_numpy(); sk=[]
    for _ in range(500):
        s=se.loc[rng.choice(days,len(days))]
        a=np.sqrt(s[('a','sum')].sum()/s[('a','count')].sum()); m=np.sqrt(s[('m','sum')].sum()/s[('m','count')].sum())
        sk.append(1-a/m)
    a=np.sqrt(se[('a','sum')].sum()/se[('a','count')].sum()); m=np.sqrt(se[('m','sum')].sum()/se[('m','count')].sum())
    print(ld,'skill vs MOS',round(100*(1-a/m),1),'5-95',np.round(100*np.percentile(sk,[5,95]),1))
