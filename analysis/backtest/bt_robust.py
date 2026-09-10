# -*- coding: utf-8 -*-
"""稳健性检验：所有 60 个月滚动窗口，比较 ② 与 ①"""
import json, datetime as dt

D = json.load(open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bubble_app/data.json', encoding='utf-8'))
M = D['month']
MONTHLY = 1000.0
CASH_M = 0.02 / 12


def coef_new(t):
    return 0.2 if t >= 85 else 0.7 if t >= 75 else 0.85 if t >= 65 else 1.0 if t >= 55 else 1.3 if t >= 40 else 1.8


def run(rows, fn):
    shares = 0.0; pool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
    for r in rows:
        ndx = float(r['ndx'])
        pool += MONTHLY
        buy = min(pool, MONTHLY * fn(float(r['total'])))
        shares += buy / ndx; tot += MONTHLY
        pool -= buy; pool *= (1 + CASH_M)
        val = shares * ndx + pool
        peak = max(peak, val); mdd = min(mdd, val / peak - 1)
    return (shares * float(rows[-1]['ndx']) + pool) / tot - 1, mdd


for W in (60, 84, 120):
    win_a = 0; n = 0; gaps = []; mdd_a = 0
    for i in range(len(M) - W + 1):
        rows = M[i:i + W]; n += 1
        ra, ma = run(rows, lambda t: 1.0)
        rb, mb = run(rows, coef_new)
        gaps.append((rb - ra) * 100)
        if rb > ra: win_a += 1
        if mb > ma: mdd_a += 1
    gaps.sort()
    print(f'{W} 个月窗口（共 {n} 个）：② 跑赢 ① 的窗口 = {win_a}/{n} ({win_a/n:.0%})，'
          f'② 回撤更小的窗口 = {mdd_a}/{n} ({mdd_a/n:.0%})')
    print(f'    收益差分布：最差 {gaps[0]:+.1f}pp | 中位 {gaps[len(gaps)//2]:+.1f}pp | 最好 {gaps[-1]:+.1f}pp')

# 分窗口明细（120 个月）
print('\n【全部 120 个月窗口明细】')
for i in range(len(M) - 120 + 1):
    rows = M[i:i + 120]
    ra, ma = run(rows, lambda t: 1.0)
    rb, mb = run(rows, coef_new)
    print(f'  {rows[0]["d"]} ~ {rows[-1]["d"]}  纳指 {float(rows[-1]["ndx"])/float(rows[0]["ndx"])-1:+.1%}  '
          f'①{ra:>7.1%}  ②{rb:>7.1%}  差{(rb-ra)*100:>+6.1f}pp   回撤 ①{ma:.1%} ②{mb:.1%}')
