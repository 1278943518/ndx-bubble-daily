# -*- coding: utf-8 -*-
"""20年定投策略回测：2006-09 ~ 2026-08（240个月） + 全样本 2000-01 ~ 2026-08
数据: scores_monthly.csv(月频温度, 2000-01 起) + ndx 月末收盘
"""
import csv, datetime as dt

ROWS = list(csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8')))
ROWS = [r for r in ROWS if r['date'] < '2026-09-01']   # 剔除未完成月
ROWS = [r for r in ROWS if r['date'] >= '2000-01-01']
print(f"可用月数: {len(ROWS)}, {ROWS[0]['date']} → {ROWS[-1]['date']}")

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

def coef(t):
    if t >= 85:  return 0.2
    if t >= 75:  return 0.7
    if t >= 65:  return 0.85
    if t >= 55:  return 1.0
    if t >= 40:  return 1.3
    return 1.8

def run(rows, mode, thr=55, cap=None):
    """mode: naive/coef/decay/wait。固定预算 1000/月，闲置资金池吃 2%"""
    shares = 0.0; pool = 0.0; wait_mo = 0
    tot = 0.0; flows = []; peak = 0.0; mdd = 0.0; series = []
    n_fire = 0; n_force = 0
    for r in rows:
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx']); t = float(r['total'])
        pool += 1000
        if mode == 'naive':
            buy = 1000.0
        elif mode == 'coef':
            buy = min(pool, 1000 * coef(t))
        elif mode == 'decay':           # 只减不加速
            c = 0.2 if t >= 85 else 0.7 if t >= 75 else 0.85 if t >= 65 else 1.0
            buy = min(pool, 1000 * c)
        elif mode == 'wait':
            if t <= thr:
                buy = pool; n_fire += 1; wait_mo = 0
            else:
                wait_mo += 1
                if cap and wait_mo >= cap:
                    buy = pool; n_force += 1; wait_mo = 0
                else:
                    buy = 0.0
        shares += buy / ndx
        pool -= buy; pool *= (1 + CASH_M)
        if buy < 999 and mode != 'wait':
            pass
        tot += 1000
        flows.append((d, -1000))
        val = shares * ndx + pool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
        series.append((r['date'], val, tot))
    final = shares * float(rows[-1]['ndx']) + pool
    flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]), final))
    return dict(final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd,
                util=(tot - pool) / tot, series=series)

STRATS = [
    ('① 无脑定投', dict(mode='naive')),
    ('② 温和节流(现版系数)', dict(mode='coef')),
    ('③ 只减不加速', dict(mode='decay')),
    ('④ 等≤55才投(无熔断)', dict(mode='wait', thr=55, cap=None)),
    ('⑤ 等≤55+18月熔断', dict(mode='wait', thr=55, cap=18)),
    ('⑥ 等≤50+24月熔断', dict(mode='wait', thr=50, cap=24)),
]

def report(rows, title):
    print('─' * 108)
    print(f'【{title}】{rows[0]["date"]} ~ {rows[-1]["date"]} · {len(rows)} 个月 · 月投 1,000')
    print(f"  纳指 {float(rows[0]['ndx']):,.0f} → {float(rows[-1]['ndx']):,.0f} "
          f"({float(rows[-1]['ndx'])/float(rows[0]['ndx'])-1:+.0%})")
    print('─' * 108)
    print(f"{'策略':<22}{'期末市值':>12}{'收益率':>10}{'vs无脑':>9}{'XIRR':>8}{'最大回撤':>9}{'资金利用':>9}")
    res = {}
    for lb, kw in STRATS:
        v = run(rows, **kw); res[lb] = v
    b = res['① 无脑定投']
    for lb, kw in STRATS:
        v = res[lb]
        print(f"{lb:<22}{v['final']:>12,.0f}{v['ret']:>10.1%}{(v['ret']-b['ret'])*100:>+8.1f}pp"
              f"{v['xirr']:>8.2%}{v['mdd']:>9.1%}{v['util']:>9.1%}")
    return res

full = ROWS
last240 = ROWS[-240:]
r_full = report(full, '全样本 26.7 年')
print()
r_20 = report(last240, '最近 20 年')

# 分段：市场十年
print()
print('═' * 108)
print('【分市场阶段对比】(每段独立起算, 月投1000)')
print('═' * 108)
segs = [
    ('2000-03~2002-10 互联网泡沫崩盘', '2000-03-01', '2002-10-31'),
    ('2003-01~2007-10 修复+大牛', '2003-01-01', '2007-10-31'),
    ('2007-11~2009-02 金融危机', '2007-11-01', '2009-02-28'),
    ('2009-03~2021-11 十二年牛市', '2009-03-01', '2021-11-30'),
    ('2022-01~2022-12 加息熊市', '2022-01-01', '2022-12-31'),
    ('2023-01~2026-08 AI 周期', '2023-01-01', '2026-08-31'),
]
for lb, d0, d1 in segs:
    seg = [r for r in ROWS if d0 <= r['date'] <= d1]
    if len(seg) < 12: continue
    print(f"\n--- {lb} ({len(seg)}个月, 纳指 {float(seg[0]['ndx']):,.0f}→{float(seg[-1]['ndx']):,.0f} "
          f"{float(seg[-1]['ndx'])/float(seg[0]['ndx'])-1:+.0%}) ---")
    out = {}
    for lb2, kw in STRATS:
        v = run(seg, **kw)
        out[lb2] = v
    bb = out['① 无脑定投']
    for lb2, kw in STRATS:
        v = out[lb2]
        print(f"  {lb2:<22}{v['ret']:>8.1%}  (vs无脑 {(v['ret']-bb['ret'])*100:+.1f}pp)  mdd {v['mdd']:>7.1%}")

# 用户资金换算（月投 4500 口径 20 年）
print()
print('─' * 108)
print('【换算到你的月投 4,500 / 20 年】(累计投入 108 万)')
for lb, kw in STRATS:
    v = run(last240, **kw)
    print(f"  {lb:<22} 期末 ≈ {v['final']*4.5/10000:>7.1f} 万  (vs无脑 {v['final']*4.5/10000 - r_20['① 无脑定投']['final']*4.5/10000:+.1f} 万)")
