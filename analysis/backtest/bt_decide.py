# -*- coding: utf-8 -*-
"""决定性检验: 在 [0,2] 倍 + 钱投完 的约束下, 是否存在"剔除2022后仍为正"的参数?
若最大值仍为负 → 倍数定投思路在 2016-2026 样本内不成立(除2022那一次外无正贡献)
"""
import csv, datetime as dt, itertools
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2016-03-01' <= r['date'] < '2026-09-01']
CASH_M = 0.02 / 12
B = naive(ALL)

def mk(hi, hm, lo, lm):
    def cf(t):
        if t >= hi: return hm
        if t < lo: return lm
        return 1.0
    return cf

def run2(rows, cf, capm=6, core=1000.0, block_from=None):
    """block_from: 该日期之后禁止加码(用于剔除某一轮)"""
    cap = capm * core
    shares = 0.0; pool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
    for i, r in enumerate(rows):
        ndx = float(r['ndx']); t = float(r['total']); m = cf(t)
        if block_from and r['date'] >= block_from and m > 1: m = 1.0
        pool = pool * (1 + CASH_M) + core
        want = core * m
        if pool > cap: want = max(want, pool - cap)
        if i == len(rows) - 1: want = pool
        buy = min(pool, want); pool -= buy
        tot += core; shares += buy / ndx
        val = shares * ndx + pool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    return dict(ret=(shares * float(rows[-1]['ndx']) + pool) / tot - 1, mdd=mdd, pool=pool)

grid = []
for hi, hm, lo, lm, capm in itertools.product([70, 75, 80, 85, 90], [0.0, 0.5],
                                              [40, 45, 50, 55], [1.5, 2.0], [6, 12, 999]):
    cf = mk(hi, hm, lo, lm)
    full = (run2(ALL, cf, capm)['ret'] - B['ret']) * 100
    no22 = (run2(ALL, cf, capm, block_from='2022-06-01')['ret'] - B['ret']) * 100
    no18 = (run2(ALL, cf, capm, block_from='2018-10-01')['ret'] - B['ret']) * 100
    grid.append((no22, full, no18, hi, hm, lo, lm, capm))

grid.sort(reverse=True)   # 按"剔除2022后"排序
print('=== 按【剔除2022轮后超额】排序 (看是否存在真正稳健的参数) ===')
print('%-26s%12s%12s%12s' % ('参数 hi/hm/lo/lm/cap', '剔除2022后', '完整超额', '剔除2022+2018'))
for no22, full, no18, hi, hm, lo, lm, capm in grid[:12]:
    print('%-26s%+12.1f%+12.1f%+12.1f'
          % ('%d/%.1f/%d/%.1f/cap%d' % (hi, hm, lo, lm, capm), no22, full, no18))
print('  ...')
for no22, full, no18, hi, hm, lo, lm, capm in grid[-3:]:
    print('%-26s%+12.1f%+12.1f%+12.1f'
          % ('%d/%.1f/%d/%.1f/cap%d' % (hi, hm, lo, lm, capm), no22, full, no18))

pos = [g for g in grid if g[0] > 0]
print()
print('剔除2022后仍为正的参数: %d / %d 个' % (len(pos), len(grid)))
if pos:
    print('  最好: %d/%.1f/%d/%.1f/cap%d  剔除后%+.1fpp  完整%+.1fpp'
          % (pos[0][3], pos[0][4], pos[0][5], pos[0][6], pos[0][7], pos[0][0], pos[0][1]))
else:
    print('  → 没有任何参数能在剔除2022那轮后仍跑赢无脑')

print()
print('=== 参考: 完全反向(高温加倍投/低温减投) 会怎样? ===')
for hi, hm, lo, lm in [(85, 2.0, 45, 0.0), (85, 1.5, 45, 0.5), (75, 2.0, 55, 0.0)]:
    v = run2(ALL, mk(hi, hm, lo, lm), 6)
    print('  高温%d倍/低温%.1f倍: vs无脑 %+.1fpp  MDD %.1f%%'
          % (hm, lm, (v['ret'] - B['ret']) * 100, v['mdd'] * 100))

print()
print('=== 参考: 纯"低温加码不动高温"(hm=1.0) 是否可行 ===')
for lo, lm in [(45, 2.0), (50, 2.0), (55, 2.0), (45, 1.5)]:
    v = run2(ALL, mk(999, 1.0, lo, lm), 6)
    print('  永不减投, 仅 t<%d 时 %.1f 倍: vs无脑 %+.1fpp (无弹药来源, 靠池上限)  MDD %.1f%%'
          % (lo, lm, (v['ret'] - B['ret']) * 100, v['mdd'] * 100))
