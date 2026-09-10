# -*- coding: utf-8 -*-
"""统一口径回测引擎 v3（正确口径: 预算全计 tot, 池子吃息, final 含池）
先与 bt_20y 已校准基准对照(自检)，再输出 C/A/B 三区间核心+闲钱结果
"""
import csv, datetime as dt
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if r['date'] < '2026-09-01' and r['date'] >= '2000-01-01']
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
    if t >= 85: return 0.2
    if t >= 75: return 0.7
    if t >= 65: return 0.85
    if t >= 55: return 1.0
    if t >= 40: return 1.3
    return 1.8

def run(rows, mode='naive', thr=55, cap=None, core=1000.0,
        side=0.0, side_thr=40, side_wait=False):
    shares = 0.0; pool = 0.0; spool = 0.0; wait = 0
    tot = 0.0; flows = []; peak = 0.0; mdd = 0.0
    for r in rows:
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx']); t = float(r['total'])
        pool = pool * (1 + CASH_M) + core          # 核心池吃息+预算
        if mode == 'naive':
            buy = core
        elif mode == 'coef':
            buy = min(pool, core * coef(t))
        else:  # wait
            if t <= thr or (cap is not None and wait >= cap):
                buy = pool; wait = 0
            else:
                buy = 0.0; wait += 1
        pool -= buy                                  # 只扣一次
        if side > 0:
            spool = spool * (1 + CASH_M) + side      # 闲钱池
            if not side_wait or t <= side_thr:
                buy += spool; spool = 0.0
        tot += core + side
        shares += buy / ndx
        flows.append((d, -(core + side)))
        val = shares * ndx + pool + spool
        if val > 0:
            peak = max(peak, val)
            if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + pool + spool
    flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]), final))
    return dict(final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd,
                pool=pool, spool=spool)

# ---- 自检: A段(2006-09起)应与 bt_20y 一致: ①672.5 ②669.0 ④665.2 ⑤663.3 ⑥664.7 ----
A = [r for r in ALL if r['date'] >= '2006-09-01']
exp = {'naive': 672.5, 'coef': 669.0}
chk = [('naive', run(A, 'naive')['ret'], 672.5), ('coef', run(A, 'coef')['ret'], 669.0),
       ('wait55', run(A, 'wait', thr=55)['ret'], 665.2), ('wait55c18', run(A, 'wait', thr=55, cap=18)['ret'], 663.3),
       ('wait50c24', run(A, 'wait', thr=50, cap=24)['ret'], 664.7)]
for nm, got, want in chk:
    flag = 'OK' if abs(got * 100 - want) < 0.3 else f'*** 不符! 期望 {want}'
    print(f'自检 {nm:<12} {got*100:>7.1f}%  {flag}')

print()
segs = [('C 2005-01起(窗5年+)', '2005-01-01'), ('A 2006-09起(20年主表)', '2006-09-01'),
        ('B 2010-01起(满10年窗)', '2010-01-01')]
for lb, d0 in segs:
    rows = [r for r in ALL if r['date'] >= d0]
    print('═' * 104)
    print(f'【{lb}】{len(rows)}个月 纳指 {float(rows[0]["ndx"]):,.0f}→{float(rows[-1]["ndx"]):,.0f} '
          f'({float(rows[-1]["ndx"])/float(rows[0]["ndx"])-1:+.0%})')
    print('═' * 104)
    S = [('① 无脑', dict(mode='naive')), ('② 温和节流', dict(mode='coef')),
         ('④ 等≤55', dict(mode='wait', thr=55)), ('⑤ ≤55+18月', dict(mode='wait', thr=55, cap=18)),
         ('⑥ ≤50+24月', dict(mode='wait', thr=50, cap=24))]
    res = {k: run(rows, **kw) for k, kw in S}
    b = res['① 无脑']
    print(f"{'核心策略':<14}{'收益率':>9}{'vs①':>8}{'XIRR':>8}{'MDD':>8}")
    for k, v in res.items():
        print(f"{k:<14}{v['ret']:>9.1%}{(v['ret']-b['ret'])*100:>+7.1f}pp{v['xirr']:>8.2%}{v['mdd']:>8.1%}")
    print('  ── 闲钱对照（核心 1000 无脑 + 闲钱 250/月，同总额公平比较）──')
    sa = run(rows, 'naive', side=250.0)
    for sth, nm in [(40, '闲钱等≤40投光'), (50, '闲钱等≤50投光'), (55, '闲钱等≤55投光')]:
        sv = run(rows, 'naive', side=250.0, side_thr=sth, side_wait=True)
        print(f"  {nm:<14}{sv['ret']:>8.1%}  vs即投 {(sv['ret']-sa['ret'])*100:>+6.1f}pp  "
              f"MDD {sv['mdd']:>6.1%}(即投 {sa['mdd']:.1%})  期末闲钱池 {sv['spool']:>8,.0f}")
