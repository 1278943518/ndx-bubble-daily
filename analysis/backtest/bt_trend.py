# -*- coding: utf-8 -*-
"""v9: 趋势跟随方案回测 (结论3的唯一被验证路径)
先诊断: 温度(估值/泡沫) 与 趋势(10月均线) 的时序关系
再回测: 纯趋势 / 双条件 / 温度预警+趋势确认 / 存量减仓
"""
import csv, datetime as dt, itertools
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2016-03-01' <= r['date'] < '2026-09-01']
CASH_M = 0.02 / 12
N = len(ALL)
ndx = [float(r['ndx']) for r in ALL]
T = [float(r['total']) for r in ALL]
D = [r['date'] for r in ALL]

def sma(arr, w=10):
    out = [None] * len(arr)
    for i in range(w - 1, len(arr)):
        out[i] = sum(arr[i - w + 1:i + 1]) / w
    return out

for W in [10, 12]:
    S = sma(ndx, W)
    below = [i for i in range(N) if S[i] and ndx[i] < S[i]]
    print('=== %d 月均线: 跌破 %d/%d 月 (%.0f%%) ===' % (W, len(below), N, len(below) / N * 100))
    if W == 10:
        print('跌破月份的温度值:')
        for i in below:
            print('   %s  温度 %5.1f   纳指 %8.0f  均线 %8.0f' % (D[i], T[i], ndx[i], S[i]))
        print()
        # 温度与跌破的交叉表
        for lo, hi in [(85, 999), (75, 85), (65, 75), (55, 65), (45, 55), (0, 45)]:
            n_below = sum(1 for i in below if lo <= T[i] < hi)
            n_all = sum(1 for i in range(N) if lo <= T[i] < hi)
            if n_all:
                print('   温度 %3d-%3s: 共%3d月, 其中跌破均线 %2d月 (%.0f%%)' %
                      (lo, '%d' % hi if hi < 999 else '+', n_all, n_below, n_below / n_all * 100))
    print()

S10 = sma(ndx, 10)
B = naive(ALL)
print('无脑基准: 收益 %.1f%%  XIRR %.2f%%  MDD %.1f%%' % (B['ret'] * 100, B['xirr'] * 100, B['mdd'] * 100))
print()

def run_trend(rows_idx, mode, temp_hi=None, mult=0.5, clear_end=True):
    """mode:
       faber     跌破均线 → 当月预算进池, 恢复时一次性投出
       dual      温度>=temp_hi 且 跌破 → 投 mult 倍
       either    温度>=temp_hi 或 跌破 → 投 mult 倍
       confirm   温度曾>=temp_hi(近12月) 且 当前跌破 → 投 mult 倍  (预警+确认)
    """
    shares = 0.0; pool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
    deployed = 0; maxdry = 0; dry = 0
    for k, i in enumerate(rows_idx):
        px = ndx[i]; t = T[i]
        above = (S10[i] is not None) and (px >= S10[i])
        if mode == 'faber':
            want = 1000.0 if above else 0.0
        elif mode == 'dual':
            want = 1000.0 * (mult if (t >= temp_hi and not above) else 1.0)
        elif mode == 'either':
            want = 1000.0 * (mult if (t >= temp_hi or not above) else 1.0)
        elif mode == 'confirm':
            recent_hi = any(T[j] >= temp_hi for j in rows_idx[max(0, k - 11):k + 1])
            want = 1000.0 * (mult if (recent_hi and not above) else 1.0)
        pool = pool * (1 + CASH_M) + 1000.0
        buy = min(pool, want)
        if clear_end and k == len(rows_idx) - 1: buy = pool
        pool -= buy
        tot += 1000.0; shares += buy / px
        if buy > 1: deployed += 1; dry = 0
        else: dry += 1; maxdry = max(maxdry, dry)
        val = shares * px + pool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * ndx[rows_idx[-1]] + pool
    return dict(ret=final / tot - 1, mdd=mdd, pool=pool, dep=deployed / len(rows_idx), maxdry=maxdry)

IDX = list(range(N))
print('=== 趋势类策略回测 (2016-03 起, 127月) ===')
print('%-38s%9s%9s%9s%9s' % ('策略', '超额', 'MDD', '部署率', '最长空仓'))
res = []
for mode, th, mult, nm in [
        ('faber', None, 0, '① Faber 纯趋势(跌破停投)'),
        ('dual', 85, 0.5, '② 双条件 AND: 温度>=85 且 跌破'),
        ('dual', 75, 0.5, '③ 双条件 AND: 温度>=75 且 跌破'),
        ('dual', 70, 0.5, '④ 双条件 AND: 温度>=70 且 跌破'),
        ('dual', 65, 0.5, '⑤ 双条件 AND: 温度>=65 且 跌破'),
        ('either', 85, 0.5, '⑥ OR: 温度>=85 或 跌破'),
        ('confirm', 80, 0.5, '⑦ 预警+确认: 近12月曾>=80 且 现跌破'),
        ('confirm', 85, 0.5, '⑧ 预警+确认: 近12月曾>=85 且 现跌破'),
        ('confirm', 85, 0.0, '⑨ 预警+确认(停投): 曾>=85 且 现跌破'),
]:
    v = run_trend(IDX, mode, th, mult)
    res.append(((v['ret'] - B['ret']) * 100, nm, v, mode, th, mult))
    print('%-38s%+8.1fpp%9.1f%%%9.0f%%%9d月' % (nm, (v['ret'] - B['ret']) * 100, v['mdd'] * 100,
                                                v['dep'] * 100, v['maxdry']))
print('%-38s%9s%9.1f%%%9s%9s' % ('  无脑定投(基准)', '—', B['mdd'] * 100, '100%', '—'))

print()
print('=== 稳健性: 滚动5年窗口 + 前后半段 ===')
wins = []
i = 0
while i + 60 <= N:
    wins.append(list(range(i, i + 60))); i += 3
H1 = list(range(0, N)); H1 = [x for x in H1 if D[x] < '2021-01-01']
H2 = [x for x in range(N) if D[x] >= '2021-01-01']
for d, nm, v, mode, th, mult in sorted(res, reverse=True)[:6]:
    ds = []
    for w in wins:
        b = naive([ALL[x] for x in w])['ret']
        ds.append((run_trend(w, mode, th, mult)['ret'] - b) * 100)
    b1 = naive([ALL[x] for x in H1])['ret']; b2 = naive([ALL[x] for x in H2])['ret']
    o1 = (run_trend(H1, mode, th, mult)['ret'] - b1) * 100
    o2 = (run_trend(H2, mode, th, mult)['ret'] - b2) * 100
    print('  %-36s 滚动%+.1f 正窗口%d/%d  前半%+.1f 后半%+.1f' %
          (nm, sum(ds) / len(ds), sum(1 for x in ds if x > 0), len(ds), o1, o2))
