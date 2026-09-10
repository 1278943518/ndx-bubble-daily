# -*- coding: utf-8 -*-
"""新旧体系关键时点对比：旧(s6=距高点) vs 新(s6=ICI流入异常度)"""
import csv

def load(fn):
    rows = list(csv.DictReader(open(fn, encoding='utf-8')))
    return {r['date'] if 'date' in r else r['Date']: r for r in rows}

# 旧版数据没存——从 git 不可得；改为直接对比 s6 新旧序列对 total 的影响：
# 用现网线上的旧 json？ 本地只有新生成的。用 git? 无。
# 替代：重新计算"旧版 s6"（dd52 分位）并在同权重下合成旧 total 对比
import pandas as pd, numpy as np

B = 'bubble_data'
ndx = pd.read_csv(f'{B}/ndx_week.csv', index_col=0, parse_dates=True)['close']
df = pd.DataFrame(index=ndx.index)
df['ndx'] = ndx
hi52 = df['ndx'].rolling(52, min_periods=26).max()
dd52 = df['ndx'] / hi52 - 1

def calc_pct(s, window=520, min_p=52):
    vals = s.values.astype(float); n = len(vals); out = np.full(n, np.nan)
    for i in range(n):
        v = vals[i]
        if np.isnan(v): out[i] = 50.0; continue
        start = max(0, i - window)
        hist = vals[start:i]; hist = hist[~np.isnan(hist)]
        out[i] = 50.0 if len(hist) < min_p else (hist < v).mean() * 100
    return pd.Series(out, index=s.index)

s6_old = calc_pct(dd52)
# 新版 s6 从 scores_weekly.csv 取
sw = pd.read_csv('bubble_out/scores_weekly.csv', index_col=0, parse_dates=True)
s6_new = sw['s6']
idx = sw.index

W = {'s1': 0.20, 's2': 0.12, 's3': 0.10, 's4': 0.18, 's5': 0.10, 's6': 0.15, 's8': 0.15}
total_old = sum(sw[k] * w for k, w in W.items() if k != 's6') + s6_old.reindex(idx).fillna(50) * W['s6']
total_new = sw['total']

print('=' * 108)
print('关键时点 | 旧 total(s6=距高点42) vs 新 total(s6=流入91) | 旧s6 vs 新s6 | 后52周收益')
print('=' * 108)
marks = ['2018-01-26', '2018-12-28', '2020-03-27', '2021-02-26', '2021-11-26', '2022-10-28',
         '2024-12-20', '2025-04-04', '2025-10-31', '2026-03-27', '2026-09-04']
fwd = ndx.shift(-52) / ndx - 1
for d in marks:
    if d not in idx: continue
    row = sw.loc[d]
    print(f"  {d}  旧 {total_old.loc[d]:5.1f} → 新 {total_new.loc[d]:5.1f}   s6 {s6_old.loc[d]:4.0f} → {s6_new.loc[d]:4.0f}"
          f"   后52周 {fwd.loc[d]*100:+6.1f}%")

# 旧/新 total 预测力对比（IC + 分位收益）
v = pd.DataFrame({'old': total_old, 'new': total_new, 'fwd': fwd}).dropna()
print('\nIC vs 未来52周收益:')
print(f"  旧 total: {v['old'].corr(v['fwd']):+.3f}")
print(f"  新 total: {v['new'].corr(v['fwd']):+.3f}")

import numpy as np
for col, lb in [('old', '旧(距高点)'), ('new', '新(流入异常)')]:
    q = pd.qcut(v[col], 4, labels=['Q1低', 'Q2', 'Q3', 'Q4高'])
    g = v.groupby(q, observed=True)['fwd'].mean() * 100
    print(f'  {lb}: ' + '  '.join(f'{k} {x:+.1f}%' for k, x in g.items()))
