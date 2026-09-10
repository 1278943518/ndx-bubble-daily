# -*- coding: utf-8 -*-
"""s5 候选: 成交量异常度 (vol/滚动中位数) —— 月频验证
用 inx_month vol(标普月成交量) 与 ndx vol 分别测: 关键时点读数 + 与未来12M收益 IC
"""
import csv, statistics as st
rows = list(csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8')))
vol = {}
for r in csv.DictReader(open('bubble_data/inx_month.csv', encoding='utf-8')):
    vol[r['date']] = float(r['vol'])
ndxv = {}
for r in csv.DictReader(open('bubble_data/ndx_month.csv', encoding='utf-8')):
    ndxv[r['date']] = float(r['vol'])

dates = [r['date'] for r in rows]
def anomaly(series):
    out = []
    for i, d in enumerate(dates):
        v = series.get(d)
        if v is None or v <= 0: out.append(None); continue
        seg = [series.get(x) for x in dates[max(0, i-35):i]]
        seg = [x for x in seg if x]
        if len(seg) < 24: out.append(None); continue
        med = st.median(seg)
        out.append(v / med - 1)
    return out

def pct(arr, i, win=120):
    v = arr[i]
    if v is None: return 50
    hist = [x for x in arr[max(0,i-win):i] if x is not None]
    if len(hist) < 24: return 50
    return sum(1 for x in hist if x < v)/len(hist)*100

a1 = anomaly(vol)      # 标普月成交量异常
a2 = anomaly(ndxv)     # 纳指月成交量异常
print('关键时点 成交量异常分位 (SPX vol / NDX vol):')
for d in ['2021-02-26','2021-11-30','2020-03-31','2022-10-31','2007-10-31','2008-11-28','2000-12-29','2026-08-31']:
    i = dates.index(d) if d in dates else None
    if i is None: continue
    print(f'  {d}: SPX={pct(a1,i):.0f}  NDX={pct(a2,i):.0f}')
# IC: 异常度 vs 未来12个月收益
ndx = {r['date']: float(r['ndx']) for r in rows}
pairs = []
for i in range(len(dates)-12):
    d = dates[i]
    if a1[i] is None: continue
    fwd = ndx[dates[i+12]]/ndx[d]-1
    pairs.append((a1[i], fwd))
import statistics as st2
v = [p[0] for p in pairs]; f = [p[1] for p in pairs]
mv, mf = st2.mean(v), st2.mean(f)
num = sum((x-mv)*(y-mf) for x,y in pairs)
den = (sum((x-mv)**2 for x in v)*sum((y-mf)**2 for y in f))**.5
print(f'\nSPX vol 异常度 vs 未来12M IC = {num/den:+.3f}')
v2 = [a2[i] for i in range(len(dates)-12)]
f2 = f
mv2 = st2.mean([x for x in v2 if x is not None])
# ndx ic
p2 = [(a2[i], ndx[dates[i+12]]/ndx[dates[i]]-1) for i in range(len(dates)-12) if a2[i] is not None]
v3=[p[0] for p in p2]; f3=[p[1] for p in p2]
mv3, mf3 = st2.mean(v3), st2.mean(f3)
num3 = sum((x-mv3)*(y-mf3) for x,y in p2)
den3 = (sum((x-mv3)**2 for x in v3)*sum((y-mf3)**2 for y in f3))**.5
print(f'NDX vol 异常度 vs 未来12M IC = {num3/den3:+.3f}  (n={len(p2)})')
