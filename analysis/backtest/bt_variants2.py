# -*- coding: utf-8 -*-
"""补充：修正回撤符号 + 反向信号对照 + 2022 实测保护效果"""
import json, datetime as dt

D = json.load(open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bubble_app/data.json', encoding='utf-8'))
ROWS = [r for r in D['month'] if r['d'] >= '2016-05-01']
MONTHLY = 1000.0
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


def run(fn):
    shares = 0.0; pool = 0.0; tot = 0.0
    flows = []; series = []; peak = 0.0; mdd = 0.0; mdd_at = ''
    for r in ROWS:
        d = dt.date(*map(int, r['d'].split('-'))); ndx = float(r['ndx'])
        pool += MONTHLY
        buy = min(pool, MONTHLY * fn(float(r['total'])))
        shares += buy / ndx; tot += MONTHLY
        pool -= buy; pool *= (1 + CASH_M)
        flows.append((d, -MONTHLY))
        val = shares * ndx + pool
        if val > peak: peak = val
        if val / peak - 1 < mdd: mdd = val / peak - 1; mdd_at = r['d']
        series.append((r['d'], val, tot, ndx))
    final = shares * float(ROWS[-1]['ndx']) + pool
    flows.append((dt.date(*map(int, ROWS[-1]['d'].split('-'))), final))
    return dict(final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd, mdd_at=mdd_at, series=series)


def coef_new(t):
    return 0.2 if t >= 85 else 0.7 if t >= 75 else 0.85 if t >= 65 else 1.0 if t >= 55 else 1.3 if t >= 40 else 1.8


CAND = {
    '① 无脑定投':        lambda t: 1.0,
    '② 现版温和':        coef_new,
    '⑤ 只减速不加速':     lambda t: 0.2 if t >= 85 else 0.7 if t >= 75 else 0.85 if t >= 65 else 1.0,
    '⑩ 反向·热了多买':    lambda t: 1.8 if t >= 85 else 1.3 if t >= 75 else 1.0 if t >= 55 else 0.7 if t >= 40 else 0.2,
}

base = run(CAND['① 无脑定投'])
print('─' * 100)
print(f"{'规则':<18}{'总收益率':>9}{'vs①':>9}{'XIRR':>8}{'最大回撤':>9}{'回撤改善':>9}{'代价/pp回撤':>14}{'回撤底':>10}")
print('─' * 100)
for k, fn in CAND.items():
    v = run(fn)
    d_ret = (v['ret'] - base['ret']) * 100
    d_mdd = (v['mdd'] - base['mdd']) * 100          # 正=回撤变小(改善)
    cost = (-d_ret / d_mdd) if d_mdd > 0.05 else float('nan')
    cs = f'{cost:.1f}pp' if cost == cost else '—'
    print(f"{k:<18}{v['ret']:>9.1%}{d_ret:>+8.1f}pp{v['xirr']:>8.2%}{v['mdd']:>9.1%}"
          f"{d_mdd:>+8.1f}pp{cs:>14}{v['mdd_at']:>10}")

# 2022 熊市实测
print('\n【2022 熊市实测】纳指 2022 年最大回撤 -35.1%（2021-11-19 → 2022-12-28）')
print(f"{'规则':<18}{'2022最低点收益率':>18}{'2022年末收益率':>16}{'相对①的优势':>14}")
s22 = {}
for k, fn in CAND.items():
    v = run(fn)
    y22 = [s for s in v['series'] if s[0][:4] == '2022']
    lo = min(y22, key=lambda s: s[1] / s[2])
    end = y22[-1]
    s22[k] = (lo[1] / lo[2] - 1, end[1] / end[2] - 1)
for k, (a, b) in s22.items():
    adv = (a - s22['① 无脑定投'][0]) * 100
    print(f'{k:<18}{a:>18.1%}{b:>16.1%}{adv:>+13.1f}pp')
