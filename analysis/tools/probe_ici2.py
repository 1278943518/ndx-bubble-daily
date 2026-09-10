# -*- coding: utf-8 -*-
"""ICI 月频 flows 归一化探测：flows 12月滚动和 + 相对60月滚动中位数的异常度"""
import csv, statistics as st

rows = list(csv.DictReader(open('bubble_data/ici_flows_monthly.csv', encoding='utf-8')))
dates = [r['Date'] for r in rows]
eq = [float(r['Total Equity']) for r in rows]

def rolling_median(x, w):
    out = []
    for i in range(len(x)):
        lo = max(0, i - w + 1)
        out.append(st.median(x[lo:i+1]))
    return out

med60 = rolling_median(eq, 60)
anom = [eq[i] - med60[i] for i in range(len(eq))]

def pct_rank(series, i, window=120, minp=36):
    v = series[i]
    lo = max(0, i - window)
    hist = series[lo:i]
    if len(hist) < minp: return None
    return sum(1 for x in hist if x < v) / len(hist) * 100

print('=== flows(百万$) / 60月滚动中位 / 异常度 / 120月分位 ===')
marks = ['2007-12-31','2008-12-31','2009-12-31','2015-12-31','2018-12-31','2020-03-31',
         '2021-02-28','2021-03-31','2022-12-31','2023-12-31','2024-12-31','2025-12-31','2026-05-31']
idx = {d: i for i, d in enumerate(dates)}
for d in marks:
    if d not in idx: continue
    i = idx[d]
    p = pct_rank(anom, i)
    print(f'  {d}  flows={eq[i]:>10,.0f}  med60={med60[i]:>10,.0f}  anom={anom[i]:>+10,.0f}  分位={p if p is None else f"{p:.0f}"}')
print()
# 异常度近5年行为（月度列表 2021-01 ~ 2026-05）
print('=== 2021-01 ~ 2026-05 异常度 ===')
for i, d in enumerate(dates):
    if '2021-01-31' <= d <= '2026-05-31':
        p = pct_rank(anom, i)
        mark = ' <==' if d in ('2021-02-28','2021-03-31','2022-06-30','2024-12-31','2026-05-31') else ''
        print(f'  {d}  flows={eq[i]:>+10,.0f}  anom={anom[i]:>+10,.0f}  分位={p if p is None else p:.0f}{mark}')
