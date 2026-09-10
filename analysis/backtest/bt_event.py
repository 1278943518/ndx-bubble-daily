# -*- coding: utf-8 -*-
"""起点敏感性 + 信号成熟度诊断: 检验超额是否由单次事件驱动"""
import csv, datetime as dt, collections
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2000-01-01' <= r['date'] < '2026-09-01']

def mk(hi, hm, lo, lm):
    def cf(t):
        if t >= hi: return hm
        if t < lo: return lm
        return 1.0
    return cf

cands = [('用户指定 90/0.2/45/3.0', mk(90, 0.2, 45, 3.0)),
         ('用户指定 90/0.2/45/2.0', mk(90, 0.2, 45, 2.0)),
         ('网格最优 85/0.0/45/4.0', mk(85, 0.0, 45, 4.0)),
         ('网格次优 85/0.2/45/3.0', mk(85, 0.2, 45, 3.0))]

print('=== 起点敏感性: 从不同年份起投的超额 (vs无脑, pp) ===')
yrs = [2005, 2008, 2010, 2012, 2014, 2016, 2018, 2020]
print('%-24s' % '参数' + ''.join('%8s' % ('%d起' % y) for y in yrs))
for nm, cf in cands:
    out = []
    for y in yrs:
        rows = [r for r in ALL if r['date'] >= '%d-01-01' % y]
        b = naive(rows)['ret']; v = run(rows, cf)['ret']
        out.append((v - b) * 100)
    print('%-24s' % nm + ''.join('%+8.1f' % x for x in out))

print()
print('=== 信号成熟度: 各年 高温(>=85) / 低温(<45) 月数 ===')
c = collections.defaultdict(lambda: [0, 0])
for r in ALL:
    y = r['date'][:4]; t = float(r['total'])
    if t >= 85: c[y][0] += 1
    if t < 45: c[y][1] += 1
print('年份   高温月  低温月')
for y in sorted(c):
    if c[y][0] or c[y][1]:
        print('  %s     %d      %d' % (y, c[y][0], c[y][1]))
print()
print('有高温信号的年份:', [y for y in sorted(c) if c[y][0] > 0])
print('→ 2017 年前无高温信号 = 前期无法攒弹药, 低温加码必然空转')

print()
print('=== 终检: 若把 2022-2023 那一轮低温加码剔除, 超额还剩多少? ===')
for nm, cf in cands:
    # 屏蔽 2022-06 之后所有低温加码(视为不触发), 其余不变
    def cf2(t, d=None):
        return cf(t)
    rows = [r for r in ALL if r['date'] >= '2005-01-01']
    b = naive(rows)['ret']
    full = (run(rows, cf)['ret'] - b) * 100
    # 构造: 2022-06 起低温月按 1.0 投
    def cf3(t):
        return cf(t)
    class st:
        pass
    shares = 0.0; pool = 0.0; tot = 0.0
    for r in rows:
        ndx = float(r['ndx']); t = float(r['total'])
        m = cf(t)
        if r['date'] >= '2022-06-01' and m > 1: m = 1.0   # 屏蔽这一轮加码
        pool = pool * (1 + CASH_M) + 1000.0
        buy = min(pool, 1000.0 * m)
        pool -= buy
        tot += 1000.0
        shares += buy / ndx
    final = shares * float(rows[-1]['ndx']) + pool
    noc = (final / tot - 1 - b) * 100
    print('  %-24s 完整%+.1fpp   剔除2022轮后%+.1fpp   → 该轮贡献 %+.1fpp' % (nm, full, noc, full - noc))
