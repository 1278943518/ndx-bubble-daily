# -*- coding: utf-8 -*-
"""倍数定投 v6: 倍数夹在 [0,2], 且"把钱投完"
机制: 每月预算 core 固定; 少投进池吃息; 池子超过 cap 个月预算 → 强制投出超额部分
      (解决 v5 的死法: 减投后钱一直躺着, 剔除2022轮后 -9.6pp)
评估: vs无脑 pp / 期末池 / 平均池 / MDD / 滚动窗口正比例 / 剔除2022稳健性
"""
import csv, datetime as dt, itertools
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2016-03-01' <= r['date'] < '2026-09-01']
CASH_M = 0.02 / 12

def mk(hi, hm, lo, lm):
    def cf(t):
        if t >= hi: return hm
        if t < lo: return lm
        return 1.0
    return cf

def run2(rows, cf, cap_months=6, core=1000.0):
    """cap_months: 池子最多攒几个月预算, 超出强制投出; 期末强制清空"""
    cap = cap_months * core
    shares = 0.0; pool = 0.0; tot = 0.0; flows = []; peak = 0.0; mdd = 0.0
    poolsum = 0.0; maxpool = 0.0
    flows_all = []
    for i, r in enumerate(rows):
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx']); t = float(r['total'])
        m = cf(t)
        pool = pool * (1 + CASH_M) + core
        want = core * m
        avail = pool
        if avail > cap:                      # 池子超限 → 强制投出超额部分
            want = max(want, avail - cap)
        if i == len(rows) - 1:               # 期末清空
            want = avail
        buy = min(avail, want)
        pool -= buy
        tot += core
        shares += buy / ndx
        flows_all.append((d, -core))
        poolsum += pool; maxpool = max(maxpool, pool)
        val = shares * ndx + pool
        if val > 0:
            peak = max(peak, val)
            if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + pool
    flows_all.append((dt.date.fromisoformat(rows[-1]['date'][:10]), final))
    return dict(ret=final / tot - 1, xirr=xirr(flows_all), mdd=mdd, pool=pool,
                avgpool=poolsum / len(rows), maxpool=maxpool)

B = naive(ALL)
print('=== 主口径 2016-03 起 (126月) 无脑: 收益 %.1f%%  XIRR %.2f%%  MDD %.1f%% ==='
      % (B['ret'] * 100, B['xirr'] * 100, B['mdd'] * 100))
print()
grid = []
for hi, hm, lo, lm, capm in itertools.product([70, 75, 80, 85, 90], [0.0, 0.5],
                                              [40, 45, 50, 55], [1.5, 2.0], [3, 6, 12, 999]):
    v = run2(ALL, mk(hi, hm, lo, lm), capm)
    grid.append(((v['ret'] - B['ret']) * 100, hi, hm, lo, lm, capm, v))
grid.sort(reverse=True)
print('=== 网格 Top15 (倍数限制 0~2, 池上限机制) ===')
print('%-26s%9s%9s%9s%9s%9s' % ('参数 hi/hm/lo/lm/cap', '收益率', 'vs无脑', 'XIRR', 'MDD', '期末池'))
for d, hi, hm, lo, lm, capm, v in grid[:15]:
    print('%-26s%9.1f%%%+8.1fpp%9.2f%%%9.1f%%%9.0f'
          % ('%d/%.1f/%d/%.1f/cap%d' % (hi, hm, lo, lm, capm),
             v['ret'] * 100, d, v['xirr'] * 100, v['mdd'] * 100, v['pool']))
print('%-26s%9.1f%%%8s%9.2f%%%9.1f%%%9s' % ('① 无脑', B['ret'] * 100, '—', B['xirr'] * 100, B['mdd'] * 100, '—'))

print()
print('=== Top5 稳健性检验 ===')
top = grid[:5]
wins = []
i = 0
while i + 60 <= len(ALL):
    wins.append(ALL[i:i + 60]); i += 3
print('%-26s%9s%9s%10s%12s%12s' % ('参数', '滚动均值', '正窗口', '剔除2022', '前半', '后半'))
for d, hi, hm, lo, lm, capm, v in top:
    cf = mk(hi, hm, lo, lm)
    ds = []
    for w in wins:
        b = naive(w)['ret']; ds.append((run2(w, cf, capm)['ret'] - b) * 100)
    pos = sum(1 for x in ds if x > 0)
    # 剔除2022
    shares = 0.0; pool = 0.0; tot = 0.0; cap = capm * 1000.0
    for j, r in enumerate(ALL):
        ndx = float(r['ndx']); t = float(r['total']); m = cf(t)
        if r['date'] >= '2022-06-01' and m > 1: m = 1.0
        pool = pool * (1 + CASH_M) + 1000.0
        want = 1000.0 * m
        if pool > cap: want = max(want, pool - cap)
        if j == len(ALL) - 1: want = pool
        buy = min(pool, want); pool -= buy; tot += 1000.0; shares += buy / ndx
    noc = ((shares * float(ALL[-1]['ndx']) + pool) / tot - 1 - B['ret']) * 100
    # 前后半
    H = []
    for d0, d1 in [('2016-03-01', '2021-01-01'), ('2021-01-01', '2026-09-01')]:
        w = [r for r in ALL if d0 <= r['date'] < d1]
        b = naive(w)['ret']; H.append((run2(w, cf, capm)['ret'] - b) * 100)
    print('%-26s%+9.1f%6s/%-2d%+10.1f%+12.1f%+12.1f'
          % ('%d/%.1f/%d/%.1f/cap%d' % (hi, hm, lo, lm, capm),
             sum(ds) / len(ds), '', pos, noc, H[0], H[1]))

print()
print('=== 池上限机制的效果对比 (85/0/45/2.0) ===')
for capm in [3, 6, 12, 999]:
    v = run2(ALL, mk(85, 0.0, 45, 2.0), capm)
    print('  cap%3d月: vs无脑%+.1fpp  期末池%6.0f  平均池%7.0f  最大池%8.0f  MDD %.1f%%'
          % (capm, (v['ret'] - B['ret']) * 100, v['pool'], v['avgpool'], v['maxpool'], v['mdd'] * 100))
v0 = run(ALL, mk(85, 0.0, 45, 2.0))   # 无池上限的 v5 版本
print('  无上限(v5): vs无脑%+.1fpp  期末池%6.0f' % ((v0['ret'] - B['ret']) * 100, v0['pool']))
