# -*- coding: utf-8 -*-
"""三种『闲置资金处理口径』对比，确认此前结论的稳健性"""
import json, datetime as dt

D = json.load(open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bubble_app/data.json', encoding='utf-8'))
ROWS = [r for r in D['month'] if r['d'] >= '2016-05-01']
MONTHLY = 1000.0
CASH_M = 0.02 / 12

def coef_new(t):
    if t >= 85:  return 0.2
    if t >= 75:  return 0.7
    if t >= 65:  return 0.85
    if t >= 55:  return 1.0
    if t >= 40:  return 1.3
    return 1.8

RULES = {
    '①无脑':     lambda t: 1.0,
    '②温和':     coef_new,
    '③≥70停':    lambda t: 0.0 if t >= 70 else 1.0,
    '④≤55买':    lambda t: 1.0 if t <= 55 else 0.0,
}

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

def run(fn, mode):
    """mode: A=追投上限1倍月投(严格固定预算) B=允许时把攒的钱一次性补齐 C=无限本金(可超额投)"""
    shares = 0.0; pool = 0.0; invested = 0.0; tot = 0.0
    flows = []; series = []; peak = 0.0; mdd = 0.0
    for r in ROWS:
        d = dt.date(*map(int, r['d'].split('-'))); ndx = float(r['ndx']); c = fn(float(r['total']))
        if mode == 'C':
            buy = MONTHLY * c
        else:
            pool += MONTHLY
            buy = pool if (mode == 'B' and c > 0) else min(pool, MONTHLY * c)
            pool -= buy
            pool *= (1 + CASH_M)
        shares += buy / ndx; invested += buy; tot += MONTHLY
        flows.append((d, -MONTHLY))
        val = shares * ndx + pool
        peak = max(peak, val); mdd = min(mdd, val / peak - 1)
        series.append((r['d'], val, tot))
    final = shares * float(ROWS[-1]['ndx']) + pool
    flows.append((dt.date(*map(int, ROWS[-1]['d'].split('-'))), final))
    return dict(final=final, invested=invested, ret=final / tot - 1, xirr=xirr(flows),
                mdd=mdd, util=invested / tot, series=series)

for mode, desc in [('A', 'A 严格固定预算（追投上限 1×月投）'),
                   ('B', 'B 攒够一次性补齐（允许时投光资金池）'),
                   ('C', 'C 无限本金（可超额投 1.3×/1.8×）')]:
    print('─' * 96)
    print(f'【{desc}】')
    print(f"{'规则':<10}{'实际投入':>10}{'期末市值':>12}{'总收益率':>10}{'XIRR':>9}{'最大回撤':>10}{'资金利用率':>10}")
    for k, fn in RULES.items():
        v = run(fn, mode)
        print(f"{k:<10}{v['invested']:>10,.0f}{v['final']:>12,.0f}{v['ret']:>10.1%}"
              f"{v['xirr']:>9.2%}{v['mdd']:>10.1%}{v['util']:>10.1%}")
