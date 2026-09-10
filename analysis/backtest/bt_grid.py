# -*- coding: utf-8 -*-
"""倍数定投 参数网格扫描 v4
核心发现: 高温信号是慢变量(未来12M +15.8% 不显灵, 24M 才塌到 +2.0%)
        低温信号是快变量(未来12M +15.6%/中位+27.6%, 24M +37.4%, 36M +55.8%)
故重点检验: 只做低温加码 / 高温几乎不减 是否优于两端都调
"""
import csv, datetime as dt, itertools
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2000-01-01' <= r['date'] < '2026-09-01']
CASH_M = 0.02 / 12

def xirr(flows):
    def npv(r):
        t0 = flows[0][0]
        return sum(a / (1 + r) ** ((d - t0).days / 365.0) for d, a in flows)
    lo, hi = -0.9999, 5.0
    if npv(lo) * npv(hi) > 0: return None
    for _ in range(300):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0: hi = mid
        else: lo = mid
    return (lo + hi) / 2

def make_cf(hi, hm, lo, lm):
    """三档: t>=hi → hm; t<lo → lm; 中间 1.0"""
    def cf(t):
        if t >= hi: return hm
        if t < lo: return lm
        return 1.0
    return cf

def run(rows, cf, cap_pool=True, core=1000.0):
    shares = 0.0; pool = 0.0; tot = 0.0; flows = []; peak = 0.0; mdd = 0.0
    for r in rows:
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx']); t = float(r['total'])
        m = cf(t)
        pool = pool * (1 + CASH_M) + core
        want = core * m
        buy = min(pool, want) if cap_pool else want
        pool -= buy
        tot += core if cap_pool else buy
        shares += buy / ndx
        flows.append((d, -core if cap_pool else -buy))
        val = shares * ndx + pool
        if val > 0:
            peak = max(peak, val)
            if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + pool
    flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]), final))
    return dict(ret=final / tot - 1, xirr=xirr(flows), mdd=mdd, pool=pool)

def naive(rows, core=1000.0):
    shares = 0.0; tot = 0.0; flows = []; peak = 0.0; mdd = 0.0
    for r in rows:
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx'])
        shares += core / ndx; tot += core; flows.append((d, -core))
        val = shares * ndx
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']); flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]), final))
    return dict(ret=final / tot - 1, xirr=xirr(flows), mdd=mdd, pool=0)

SEGS = [('C', '2005-01-01'), ('A', '2006-09-01'), ('B', '2010-01-01'), ('D', '2000-01-01')]
SETS = {k: [r for r in ALL if r['date'] >= d] for k, d in SEGS}
BASE = {k: naive(v) for k, v in SETS.items()}

print('【口径A 预算恒定】每月预算1000, 少投进池待补投 → 总投入相同, 比收益率 (vs无脑 pp)')
print('=' * 92)
print(f"{'参数 hi/hm/lo/lm':<20}{'C段':>9}{'A段':>9}{'B段':>9}{'D段':>9}{'均值':>9}{'XIRR_A':>9}")
gridA = []
for hi, hm, lo, lm in itertools.product([85, 90], [0.2, 0.5, 1.0], [40, 45, 50], [1.5, 2.0, 3.0]):
    cf = make_cf(hi, hm, lo, lm)
    ds = []
    for k in ['C', 'A', 'B', 'D']:
        v = run(SETS[k], cf); ds.append((v['ret'] - BASE[k]['ret']) * 100)
    xa = run(SETS['A'], cf)['xirr']
    gridA.append((sum(ds) / 4, hi, hm, lo, lm, ds, xa))
gridA.sort(reverse=True)
for m, hi, hm, lo, lm, ds, xa in gridA[:12]:
    print(f"{hi:>3}/{hm:<4.1f}/{lo:>2}/{lm:<4.1f}{'':>6}{ds[0]:>+8.1f}{ds[1]:>+8.1f}{ds[2]:>+8.1f}{ds[3]:>+8.1f}"
          f"{m:>+9.1f}{xa:>9.2%}")
print(f"{'① 无脑(基准)':<20}{0.0:>8.1f}{0.0:>8.1f}{0.0:>8.1f}{0.0:>8.1f}{0.0:>+9.1f}{BASE['A']['xirr']:>9.2%}")

print()
print('【口径B 真倍数】每月实际投 1000×倍(可追加) → 总投入不同, 比 XIRR (vs无脑 pp)')
print('=' * 92)
print(f"{'参数 hi/hm/lo/lm':<20}{'C段':>9}{'A段':>9}{'B段':>9}{'D段':>9}{'均值':>9}{'MDD_D':>9}")
gridB = []
for hi, hm, lo, lm in itertools.product([85, 90], [0.2, 0.5, 1.0], [40, 45, 50], [1.5, 2.0, 3.0]):
    cf = make_cf(hi, hm, lo, lm)
    ds = []; md = None
    for k in ['C', 'A', 'B', 'D']:
        v = run(SETS[k], cf, cap_pool=False); ds.append((v['xirr'] - BASE[k]['xirr']) * 100)
        if k == 'D': md = v['mdd']
    gridB.append((sum(ds) / 4, hi, hm, lo, lm, ds, md))
gridB.sort(reverse=True)
for m, hi, hm, lo, lm, ds, md in gridB[:12]:
    print(f"{hi:>3}/{hm:<4.1f}/{lo:>2}/{lm:<4.1f}{'':>6}{ds[0]:>+8.1f}{ds[1]:>+8.1f}{ds[2]:>+8.1f}{ds[3]:>+8.1f}"
          f"{m:>+9.1f}{md:>9.1%}")
print(f"{'① 无脑(基准)':<20}{0.0:>8.1f}{0.0:>8.1f}{0.0:>8.1f}{0.0:>8.1f}{0.0:>+9.1f}{BASE['D']['mdd']:>9.1%}")
