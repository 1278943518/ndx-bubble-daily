# -*- coding: utf-8 -*-
"""倍数定投 v8: 锚定均分=1.0倍, 反解高温档 mL, 使整体配平(钱正好投完)
m(t) = mH (t < 下线L)        —— 加码, 封顶 2.0
     = 1.0 (L <= t < U)      —— 含均分 64.68 / 用户假设的 68, 正常投
     = mL (t >= 上线U)        —— 减投, 由配平解出: mL=(N - mH*n_lo - n_mid)/n_hi
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
print('均分 %.2f (中位 %.2f)  无脑收益 %.1f%%  XIRR %.2f%%  MDD %.1f%%'
      % (AVG, sorted(T)[len(T) // 2], B['ret'] * 100, B['xirr'] * 100, B['mdd'] * 100))
print()

def solve_mL(ts, U, L, mH):
    n_hi = sum(1 for x in ts if x >= U)
    n_lo = sum(1 for x in ts if x < L)
    n_mid = len(ts) - n_hi - n_lo
    if n_hi == 0: return None, n_hi, n_lo, n_mid
    mL = (len(ts) - mH * n_lo - 1.0 * n_mid) / n_hi
    return mL, n_hi, n_lo, n_mid

def backtest(rows, U, L, mH, mL, core=1000.0):
    shares = 0.0; pool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
    poolsum = 0.0; maxpool = 0.0; starved = 0
    for i, r in enumerate(rows):
        ndx = float(r['ndx']); t = float(r['total'])
        m = mL if t >= U else (mH if t < L else 1.0)
        pool = pool * (1 + CASH_M) + core
        want = core * m
        buy = min(pool, want)
        if want > pool + 1e-9: starved += 1
        if i == len(rows) - 1: buy = pool
        pool -= buy
        tot += core; shares += buy / ndx
        poolsum += pool; maxpool = max(maxpool, pool)
        val = shares * ndx + pool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + pool
    return dict(ret=final / tot - 1, mdd=mdd, pool=pool, avgpool=poolsum / len(rows),
                maxpool=maxpool, starved=starved)

grid = []
for U, L, mH in itertools.product([70, 75, 78, 80, 82, 85, 88], [35, 40, 45, 50, 55],
                                  [1.5, 1.75, 2.0]):
    mL, n_hi, n_lo, n_mid = solve_mL(T, U, L, mH)
    if mL is None or mL < -0.01 or mL > 1.0: continue     # 高温档需在 [0,1] 才合理
    v = backtest(ALL, U, L, mH, mL)
    grid.append(((v['ret'] - B['ret']) * 100, U, L, mH, mL, n_hi, n_lo, n_mid, v))
grid.sort(reverse=True)

print('=== 锚定均分=1.0倍, 反解高温档 (mH封顶2.0) ===')
print('%-34s%8s%9s%9s%9s%7s' % ('上线U/下线L/加码mH', '高温档mL', '超额', 'MDD', '最大池', '欠投月'))
for d, U, L, mH, mL, n_hi, n_lo, n_mid, v in grid[:15]:
    print('%-34s%8.2f%+8.1fpp%9.1f%%%9.0f%7d'
          % ('%d / %d / %.2f  (高%d 低%d 中%d月)' % (U, L, mH, n_hi, n_lo, n_mid),
             mL, d, v['mdd'] * 100, v['maxpool'], v['starved']))
print('%-34s%8s%8s%9.1f%%%9s%7s' % ('① 无脑', '—', '—', B['mdd'] * 100, '—', '—'))

print()
print('=== 推荐方案稳健性 (前半校准 mL → 后半样本外直接套用) ===')
T1 = [float(r['total']) for r in ALL if r['date'] < '2021-01-01']
H1 = [r for r in ALL if r['date'] < '2021-01-01']
H2 = [r for r in ALL if r['date'] >= '2021-01-01']
b1 = naive(H1)['ret']; b2 = naive(H2)['ret']
wins = []
i = 0
while i + 60 <= len(ALL):
    wins.append(ALL[i:i + 60]); i += 3
for d, U, L, mH, mL, n_hi, n_lo, n_mid, v in grid[:5]:
    mL1, *_ = solve_mL(T1, U, L, mH)
    mLu = mL1 if (mL1 is not None and 0 <= mL1 <= 1) else mL
    ins = (backtest(H1, U, L, mH, mLu)['ret'] - b1) * 100
    oos = (backtest(H2, U, L, mH, mLu)['ret'] - b2) * 100
    ds = [(backtest(w, U, L, mH, mL)['ret'] - naive(w)['ret']) * 100 for w in wins]
    print('  U%d/L%d/mH%.2f mL=%.2f(前半校准%.2f): 前半%+.1f 后半样本外%+.1f 滚动%+.1f 正窗口%d/%d 最大池%.0f'
          % (U, L, mH, mL, mLu, ins, oos, sum(ds) / len(ds),
             sum(1 for x in ds if x > 0), len(ds), v['maxpool']))

print()
print('=== 敏感性: 若用户坚持用 68 分做锚点(而非实测均分 64.68) ===')
print('注: 68 分落在中间档 [L,U) 内, 中间档恒为 1.0 倍 → 锚点取 64.68 或 68 对阶梯式无影响')
print('    只有把 68 设为「分界点」才会改变触发频次:')
for U, L in [(85, 45), (85, 40), (80, 45)]:
    n68 = sum(1 for x in T if x >= 68)
    print('    参考: 温度>=68 的月份共 %d 个 (%.0f%%)' % (n68, n68 / len(T) * 100))
    break
