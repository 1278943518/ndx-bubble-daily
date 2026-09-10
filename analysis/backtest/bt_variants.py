# -*- coding: utf-8 -*-
"""在『固定月投预算』真实约束下，搜索真正有效的规则变体"""
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
    shares = 0.0; pool = 0.0; invested = 0.0; tot = 0.0
    flows = []; series = []; peak = 0.0; mdd = 0.0
    for r in ROWS:
        d = dt.date(*map(int, r['d'].split('-'))); ndx = float(r['ndx'])
        pool += MONTHLY
        buy = min(pool, MONTHLY * fn(float(r['total'])))
        shares += buy / ndx; invested += buy; tot += MONTHLY
        pool -= buy; pool *= (1 + CASH_M)
        flows.append((d, -MONTHLY))
        val = shares * ndx + pool
        peak = max(peak, val); mdd = min(mdd, val / peak - 1)
        series.append((r['d'], val, tot))
    final = shares * float(ROWS[-1]['ndx']) + pool
    flows.append((dt.date(*map(int, ROWS[-1]['d'].split('-'))), final))
    return dict(final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd,
                util=invested / tot, series=series)


def coef_new(t):
    return 0.2 if t >= 85 else 0.7 if t >= 75 else 0.85 if t >= 65 else 1.0 if t >= 55 else 1.3 if t >= 40 else 1.8


CAND = {
    '① 无脑定投':            lambda t: 1.0,
    '② 现版温和(含加速)':     coef_new,
    '⑤ 只减速不加速':         lambda t: 0.2 if t >= 85 else 0.7 if t >= 75 else 0.85 if t >= 65 else 1.0,
    '⑥ 仅极端熔断≥85→0.5':    lambda t: 0.5 if t >= 85 else 1.0,
    '⑦ 仅≥80→0.6':           lambda t: 0.6 if t >= 80 else 1.0,
    '⑧ 仅≥75→0.7':           lambda t: 0.7 if t >= 75 else 1.0,
    '⑨ 极端熔断≥85→0.3':      lambda t: 0.3 if t >= 85 else 1.0,
}

base = run(CAND['① 无脑定投'])
print('─' * 104)
print(f"{'规则':<22}{'期末市值':>11}{'总收益率':>10}{'vs①差':>9}{'XIRR':>8}{'最大回撤':>9}{'回撤改善':>9}{'每1pp回撤的代价':>18}")
print('─' * 104)
for k, fn in CAND.items():
    v = run(fn)
    d_ret = v['ret'] - base['ret']
    d_mdd = base['mdd'] - v['mdd']          # 正数=回撤变小
    cost = (-d_ret * 100) / (d_mdd * 100) if d_mdd > 0.0001 else float('nan')
    cs = f'{cost:.1f} pp收益' if cost == cost else '—'
    print(f"{k:<22}{v['final']:>11,.0f}{v['ret']:>10.1%}{d_ret*100:>+8.1f}pp{v['xirr']:>8.2%}"
          f"{v['mdd']:>9.1%}{d_mdd*100:>+8.1f}pp{cs:>18}")
print('─' * 104)
print('注：「每1pp回撤的代价」= 少赚多少pp收益 ÷ 回撤改善多少pp。数值越小越划算。')

# 分年度：① vs ⑤ vs ⑥
print('\n【分年度累计收益率】')
keys = ['① 无脑定投', '② 现版温和(含加速)', '⑤ 只减速不加速', '⑥ 仅极端熔断≥85→0.5']
res = {k: run(CAND[k]) for k in keys}
years = sorted({r['d'][:4] for r in ROWS})
print(f"{'年份':<8}" + ''.join(f'{k[:6]:>14}' for k in keys))
for y in years:
    line = f'{y:<8}'
    for k in keys:
        ser = [s for s in res[k]['series'] if s[0][:4] == y]
        line += f"{ser[-1][1]/ser[-1][2]-1:>14.1%}" if ser else f"{'—':>14}"
    print(line)

# 换算到用户资金
print('\n【换算到月投 7,000 元 / 10 年】')
for k in keys:
    v = res[k]
    print(f'  {k:<22} 期末 {7000*124*(1+v["ret"])/10000:>6.1f} 万   （无脑基准 {7000*124*(1+base["ret"])/10000:.1f} 万，'
          f'差 {(v["ret"]-base["ret"])*7000*124/10000:+.1f} 万）')
