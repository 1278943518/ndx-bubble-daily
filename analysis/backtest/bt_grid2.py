# -*- coding: utf-8 -*-
"""倍数定投 扩展网格 v4.2 —— 检验 85/0.2/45/3.0 是否稳健(非过拟合)
新增维度: 中间档 mm(平时少投攒弹药), 高倍/低倍极端值
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

def make_cf(hi, hm, lo, lm, mm=1.0):
    def cf(t):
        if t >= hi: return hm
        if t < lo: return lm
        return mm
    return cf

def run(rows, cf, core=1000.0):
    shares = 0.0; pool = 0.0; tot = 0.0; flows = []; peak = 0.0; mdd = 0.0
    for r in rows:
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx']); t = float(r['total'])
        m = cf(t)
        pool = pool * (1 + CASH_M) + core
        buy = min(pool, core * m)
        pool -= buy
        tot += core
        shares += buy / ndx
        flows.append((d, -core))
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

grid = []
for hi, hm, lo, lm, mm in itertools.product([80, 85, 90], [0.0, 0.2, 0.5], [45, 50],
                                            [2.0, 3.0, 4.0], [0.85, 0.9, 1.0]):
    cf = make_cf(hi, hm, lo, lm, mm)
    ds = []; md = 0.0; pl = 0.0
    for k in ['C', 'A', 'B', 'D']:
        v = run(SETS[k], cf); ds.append((v['ret'] - BASE[k]['ret']) * 100)
        if k == 'A': md, pl = v['mdd'], v['pool']
    grid.append((sum(ds) / 4, min(ds), hi, hm, lo, lm, mm, ds, md, pl))
grid.sort(reverse=True)
print('【口径A 扩展网格】总投入相同 → vs无脑 pp (按四段均值排序, min=最差段)')
print('=' * 108)
print(f"{'hi/hm/lo/lm/mm':<20}{'C段':>8}{'A段':>8}{'B段':>8}{'D段':>8}{'均值':>8}{'最差段':>8}{'MDD_A':>8}{'期末池':>9}")
for m, mn, hi, hm, lo, lm, mm, ds, md, pl in grid[:15]:
    print(f"{hi:>3}/{hm:<4.1f}/{lo:>2}/{lm:<4.1f}/{mm:<4.2f}{'':>2}{ds[0]:>+7.1f}{ds[1]:>+7.1f}{ds[2]:>+7.1f}"
          f"{ds[3]:>+7.1f}{m:>+8.1f}{mn:>+8.1f}{md:>8.1%}{pl:>9,.0f}")
print(f"{'① 无脑(基准)':<20}{0.0:>7.1f}{0.0:>7.1f}{0.0:>7.1f}{0.0:>7.1f}{0.0:>+8.1f}{0.0:>+8.1f}"
      f"{BASE['A']['mdd']:>8.1%}{0:>9}")

print()
print('【稳健性: 高分位参数在邻域的表现 —— 是否孤立尖峰?】')
top = grid[0]
print(f'  最优: hi={top[2]} hm={top[3]} lo={top[4]} lm={top[5]} mm={top[6]}  均值{top[0]:+.1f}pp 最差段{top[1]:+.1f}pp')
nb = [g for g in grid if abs(g[2]-top[2]) <= 5 and abs(g[4]-top[4]) <= 5 and abs(g[6]-top[6]) < 0.01]
nb.sort(reverse=True)
print(f'  邻域内 {len(nb)} 个参数组合的均值分布: ', end='')
vals = [g[0] for g in nb]
print('最小%+.1f 中位%+.1f 最大%+.1f  全为正=%s'
      % (min(vals), sorted(vals)[len(vals)//2], max(vals), all(v > 0 for v in vals)))

print()
print('【样本外: 用前半段定参数, 后半段验证】(防过拟合)')
H1 = {k: [r for r in SETS[k] if r['date'] < '2015-01-01'] for k in SETS}
H2 = {k: [r for r in SETS[k] if r['date'] >= '2015-01-01'] for k in SETS}
B1 = {k: naive(H1[k]) for k in H1}; B2 = {k: naive(H2[k]) for k in H2}
res = []
for m, mn, hi, hm, lo, lm, mm, ds, md, pl in grid[:20]:
    cf = make_cf(hi, hm, lo, lm, mm)
    d1 = [ (run(H1[k], cf)['ret'] - B1[k]['ret'])*100 for k in ['C','A','B','D']]
    d2 = [ (run(H2[k], cf)['ret'] - B2[k]['ret'])*100 for k in ['C','A','B','D']]
    res.append((sum(d1)/4, sum(d2)/4, hi, hm, lo, lm, mm))
res.sort(reverse=True)
print(f"{'参数':<22}{'前半(至2014)':>12}{'后半(2015+)':>12}{'一致性':>10}")
for a, b, hi, hm, lo, lm, mm in res[:10]:
    ok = '✓两段同号' if a * b > 0 else ('后半转负 ✗' if a > 0 >= b else '前半负')
    print(f"{hi:>3}/{hm:<4.1f}/{lo:>2}/{lm:<4.1f}/{mm:<4.2f}{'':>4}{a:>+11.1f}{b:>+11.1f}   {ok}")
