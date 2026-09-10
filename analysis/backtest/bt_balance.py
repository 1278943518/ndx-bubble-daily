# -*- coding: utf-8 -*-
"""倍数定投 v7: 配平内生 —— 上下线 + 倍率 + 中间档由配平方程解出
核心: m(t) = mL (t>=上线U) / mH (t<下线L) / c (中间)
      c 由 Σm = N 解出 → 长期总投入 = 预算总额, 钱自然投完, 池子最浅
      c = (N - mL*n_hi - mH*n_lo) / n_mid
锚点: 均分 64.68 (2016-03 起实测)
"""
import csv, datetime as dt, itertools
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2016-03-01' <= r['date'] < '2026-09-01']
CASH_M = 0.02 / 12
T = [float(r['total']) for r in ALL]
AVG = sum(T) / len(T)
B = naive(ALL)
print('主口径 2016-03 起 %d 个月  均分 %.2f  无脑收益 %.1f%%  XIRR %.2f%%  MDD %.1f%%'
      % (len(ALL), AVG, B['ret'] * 100, B['xirr'] * 100, B['mdd'] * 100))
print()

def solve_c(ts, U, L, mH, mL):
    """解中间档 c, 使 sum(m)=N"""
    n_hi = sum(1 for x in ts if x >= U)
    n_lo = sum(1 for x in ts if x < L)
    n_mid = len(ts) - n_hi - n_lo
    if n_mid == 0: return None
    c = (len(ts) - mL * n_hi - mH * n_lo) / n_mid
    return c

def backtest(rows, U, L, mH, mL, c, core=1000.0):
    shares = 0.0; pool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
    poolsum = 0.0; maxpool = 0.0; starved = 0
    for i, r in enumerate(rows):
        ndx = float(r['ndx']); t = float(r['total'])
        m = mL if t >= U else (mH if t < L else c)
        pool = pool * (1 + CASH_M) + core
        want = core * m
        buy = min(pool, want)
        if want > pool + 1e-9: starved += 1
        if i == len(rows) - 1: buy = pool      # 期末清空残差
        pool -= buy
        tot += core
        shares += buy / ndx
        poolsum += pool; maxpool = max(maxpool, pool)
        val = shares * ndx + pool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + pool
    return dict(ret=final / tot - 1, mdd=mdd, pool=pool, avgpool=poolsum / len(rows),
                maxpool=maxpool, starved=starved)

# ---------- 网格 ----------
grid = []
for U, L, mH, mL in itertools.product([75, 78, 80, 82, 85, 88, 90], [40, 45, 50, 55],
                                      [1.5, 1.75, 2.0], [0.0, 0.25, 0.5]):
    c = solve_c(T, U, L, mH, mL)
    if c is None or not (0.55 <= c <= 1.45): continue
    v = backtest(ALL, U, L, mH, mL, c)
    grid.append(((v['ret'] - B['ret']) * 100, U, L, mH, mL, c, v))
grid.sort(reverse=True)

print('=== 配平式三段阶梯: 网格 Top15 (中间档 c 由 Σm=N 解出) ===')
print('%-30s%9s%9s%9s%9s%7s' % ('上线U/下线L/高倍mH/低倍mL', '中间档c', '超额', 'MDD', '最大池', '欠投月'))
for d, U, L, mH, mL, c, v in grid[:15]:
    print('%-30s%9.3f%+8.1fpp%9.1f%%%9.0f%7d'
          % ('%d / %d / %.2f / %.2f' % (U, L, mH, mL), c, d, v['mdd'] * 100, v['maxpool'], v['starved']))
print('%-30s%9s%8s%9.1f%%%9s%7s' % ('① 无脑', '—', '—', B['mdd'] * 100, '—', '—'))

print()
print('=== 线性连续版: m(t)=clip(1+k*(A-t), 0, 2), A 由配平解出 ===')
def solve_A(ts, k, lo=0.0, hi=2.0):
    def sum_m(A):
        return sum(min(hi, max(lo, 1 + k * (A - x))) for x in ts)
    a0, a1 = 0.0, 150.0
    for _ in range(200):
        mid = (a0 + a1) / 2
        if sum_m(mid) < len(ts): a0 = mid
        else: a1 = mid
    return (a0 + a1) / 2

def bt_lin(rows, k, A, core=1000.0):
    shares = 0.0; pool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0; maxpool = 0.0; poolsum = 0.0
    for i, r in enumerate(rows):
        ndx = float(r['ndx']); t = float(r['total'])
        m = min(2.0, max(0.0, 1 + k * (A - t)))
        pool = pool * (1 + CASH_M) + core
        buy = min(pool, core * m)
        if i == len(rows) - 1: buy = pool
        pool -= buy
        tot += core; shares += buy / ndx
        poolsum += pool; maxpool = max(maxpool, pool)
        val = shares * ndx + pool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + pool
    return dict(ret=final / tot - 1, mdd=mdd, maxpool=maxpool, avgpool=poolsum / len(rows))

print('%-12s%10s%9s%9s%9s' % ('斜率k', '锚点A', '超额', 'MDD', '最大池'))
for k in [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]:
    A = solve_A(T, k)
    v = bt_lin(ALL, k, A)
    print('%-12s%10.1f%+8.1fpp%9.1f%%%9.0f' % (k, A, (v['ret'] - B['ret']) * 100, v['mdd'] * 100, v['maxpool']))

print()
print('=== Top3 稳健性 (含真样本外: 前半校准 c → 后半直接用) ===')
T1 = [float(r['total']) for r in ALL if r['date'] < '2021-01-01']
wins = []
i = 0
while i + 60 <= len(ALL):
    wins.append(ALL[i:i + 60]); i += 3
for d, U, L, mH, mL, c, v in grid[:3]:
    c1 = solve_c(T1, U, L, mH, mL)
    H1 = [r for r in ALL if r['date'] < '2021-01-01']
    H2 = [r for r in ALL if r['date'] >= '2021-01-01']
    b1 = naive(H1)['ret']; b2 = naive(H2)['ret']
    oos = (backtest(H2, U, L, mH, mL, c1 if c1 else c)['ret'] - b2) * 100
    ins = (backtest(H1, U, L, mH, mL, c1 if c1 else c)['ret'] - b1) * 100
    ds = []
    for w in wins:
        b = naive(w)['ret']
        ds.append((backtest(w, U, L, mH, mL, c)['ret'] - b) * 100)
    print('  U%d/L%d/%.2f/%.2f c=%.3f: 前半%+.1f 后半(样本外)%+.1f 滚动均值%+.1f 正窗口%d/%d 最大池%.0f'
          % (U, L, mH, mL, c, ins, oos, sum(ds) / len(ds), sum(1 for x in ds if x > 0), len(ds), v['maxpool']))
