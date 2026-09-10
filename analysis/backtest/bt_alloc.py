# -*- coding: utf-8 -*-
"""温度驱动的『仓位管理』（而非节流）：每月固定投入 + 按温度再平衡股/现比例"""
import json, datetime as dt

D = json.load(open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bubble_app/data.json', encoding='utf-8'))
ROWS = [r for r in D['month'] if r['d'] >= '2016-05-01']
MONTHLY = 1000.0
DEF_M = 0.02 / 12          # 防守端（货基/短债）年化 2%


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


def run(wfn, label, rebal=True):
    """wfn: 温度 -> 目标股票权重(0~1)。每月投入 MONTHLY 后按目标权重再平衡。"""
    stock = 0.0; defs = 0.0; tot = 0.0
    flows = []; series = []; peak = 0.0; mdd = 0.0; mdd_at = ''
    wsum = 0.0
    rows_txt = []
    for r in ROWS:
        d = dt.date(*map(int, r['d'].split('-'))); ndx = float(r['ndx']); t = float(r['total'])
        # 1) 先按上月市值随指数涨跌
        stock *= ndx / prev_ndx if 'prev_ndx' in dir() else 1.0
        stock = stock
        defs *= (1 + DEF_M)
        # 2) 新钱进场
        stock += MONTHLY; tot += MONTHLY
        # 3) 再平衡到目标权重
        w = wfn(t); wsum += w
        if rebal:
            v = stock + defs
            stock, defs = v * w, v * (1 - w)
        flows.append((d, -MONTHLY))
        val = stock + defs
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1; mdd_at = r['d']
        series.append((r['d'], val, tot))
        rows_txt.append((r['d'], t, w))
        prev_ndx = ndx
    final = stock + defs
    flows.append((dt.date(*map(int, ROWS[-1]['d'].split('-'))), final))
    return dict(label=label, final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd,
                mdd_at=mdd_at, avgw=wsum / len(ROWS), series=series, stock=stock, defs=defs)


# 修正：上面 prev_ndx 逻辑写错了，重写
def run2(wfn, label, rebal=True):
    stock = 0.0; defs = 0.0; tot = 0.0
    flows = []; series = []; peak = 0.0; mdd = 0.0; mdd_at = ''
    wsum = 0.0
    prev = None
    for r in ROWS:
        d = dt.date(*map(int, r['d'].split('-'))); ndx = float(r['ndx']); t = float(r['total'])
        if prev is not None:
            stock *= ndx / prev          # 股票端随纳指涨跌
        defs *= (1 + DEF_M)              # 防守端吃 2%
        stock += MONTHLY; tot += MONTHLY
        w = wfn(t); wsum += w
        if rebal:
            v = stock + defs
            stock, defs = v * w, v * (1 - w)
        flows.append((d, -MONTHLY))
        val = stock + defs
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1; mdd_at = r['d']
        series.append((r['d'], val, tot))
        prev = ndx
    final = stock + defs
    flows.append((dt.date(*map(int, ROWS[-1]['d'].split('-'))), final))
    return dict(label=label, final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd,
                mdd_at=mdd_at, avgw=wsum / len(ROWS), series=series, stock=stock, defs=defs)


def w_base(t):   return 1.0
def w_v1(t):     return 1.0 if t < 40 else .9 if t < 55 else .8 if t < 65 else .7 if t < 75 else .6 if t < 85 else .5
def w_v2(t):     return 1.0 if t < 45 else .95 if t < 60 else .85 if t < 70 else .75 if t < 80 else .6 if t < 85 else .45
def w_v3(t):     return 1.0 if t < 50 else .9 if t < 65 else .8 if t < 75 else .7 if t < 85 else .55
def w_v4(t):     return 1.0 if t < 55 else .9 if t < 70 else .8 if t < 80 else .65
def w_v5(t):     return 1.0 if t < 45 else .9 if t < 60 else .75 if t < 72 else .6 if t < 82 else .45

CAND = [('100% 股票（基准）', w_base), ('V1 激进调仓', w_v1), ('V2 温和调仓', w_v2),
        ('V3 中档调仓', w_v3), ('V4 保守调仓', w_v4), ('V5 强力调仓', w_v5)]

base = run2(w_base, '基准')
print('─' * 112)
print(f"{'方案':<18}{'期末市值':>11}{'总收益率':>10}{'vs基准':>9}{'XIRR':>8}{'最大回撤':>9}{'回撤改善':>9}{'平均股仓':>9}{'代价/pp':>9}")
print('─' * 112)
for lb, fn in CAND:
    v = run2(fn, lb)
    d_ret = (v['ret'] - base['ret']) * 100
    d_mdd = (v['mdd'] - base['mdd']) * 100
    cost = (-d_ret / d_mdd) if d_mdd > 0.05 else float('nan')
    cs = f'{cost:.2f}' if cost == cost else '—'
    print(f"{lb:<18}{v['final']:>11,.0f}{v['ret']:>10.1%}{d_ret:>+8.1f}pp{v['xirr']:>8.2%}"
          f"{v['mdd']:>9.1%}{d_mdd:>+8.1f}pp{v['avgw']:>9.1%}{cs:>9}")

# 再平衡 vs 不再平衡（只对新钱应用权重）
print('\n【对照：只对新钱按温度分配 vs 全仓再平衡】')
for lb, fn in [('V2 温和调仓', w_v2), ('V5 强力调仓', w_v5)]:
    a = run2(fn, lb, rebal=False)
    b = run2(fn, lb, rebal=True)
    print(f'  {lb}  仅新钱分配：{a["ret"]:.1%} 回撤{a["mdd"]:.1%}  |  全仓再平衡：{b["ret"]:.1%} 回撤{b["mdd"]:.1%}')

# 分年度
print('\n【分年度累计收益率】')
keys = ['100% 股票（基准）', 'V2 温和调仓', 'V5 强力调仓', 'V1 激进调仓']
sel = {lb: fn for lb, fn in CAND if lb in keys}
res = {lb: run2(fn, lb) for lb, fn in sel.items()}
years = sorted({r['d'][:4] for r in ROWS})
print(f"{'年份':<8}" + ''.join(f'{k[:8]:>12}' for k in keys))
for y in years:
    line = f'{y:<8}'
    for k in keys:
        s = [x for x in res[k]['series'] if x[0][:4] == y]
        line += f'{s[-1][1]/s[-1][2]-1:>12.1%}' if s else f'{"—":>12}'
    print(line)

# 2022 熊市
print('\n【2022 熊市实测】')
for lb, fn in sel.items():
    v = run2(fn, lb)
    y22 = [s for s in v['series'] if s[0][:4] == '2022']
    lo = min(y22, key=lambda s: s[1] / s[2])
    print(f'  {lb:<18} 最低点 {lo[1]/lo[2]-1:>7.1%}  年末 {y22[-1][1]/y22[-1][2]-1:>7.1%}')
