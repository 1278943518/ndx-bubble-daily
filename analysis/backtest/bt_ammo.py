# -*- coding: utf-8 -*-
"""口径C: 冷月可用预算外闲钱加码(不受资金池限制) —— 20年 + 全样本
无脑: 每月固定 1000。加码版: 热时少买的钱只影响"预算内"部分?
简化忠实版(口径C定义): 每月预算内 1000 照投(无脑), 额外: 当温度低于阈值时,
从"闲钱账户"(虚拟, 无上限)额外加码 N 倍月投。闲钱成本=货基2%(等待机会成本不计)。
对比: 纯无脑 vs 无脑+冷月加码(额外本金1.0/1.5/2.0×1000 每次触发)
"""
import csv, datetime as dt
ROWS=[r for r in csv.DictReader(open('bubble_out/scores_monthly.csv',encoding='utf-8')) if r['date']<'2026-09-01' and r['date']>='2000-01-01']
CASH_M=0.02/12

def xirr(flows):
    def npv(r):
        t0=flows[0][0]
        return sum(a/(1+r)**((d-t0).days/365.0) for d,a in flows)
    lo,hi=-0.9999,5.0
    if npv(lo)*npv(hi)>0: return None
    for _ in range(300):
        mid=(lo+hi)/2
        if npv(lo)*npv(mid)<=0: hi=mid
        else: lo=mid
    return (lo+hi)/2

def run(rows, thr, extra, cap_extra=6):
    """无脑1000/月 + 温度<=thr 的月份额外加码 extra×1000(最多连续 cap_extra 个月)"""
    shares=0.0; tot=0.0; flows=[]; peak=0.0; mdd=0.0
    consec=0; n_extra=0; extra_total=0.0
    for r in rows:
        d=dt.date.fromisoformat(r['date'][:10]); ndx=float(r['ndx']); t=float(r['total'])
        buy=1000.0
        if t<=thr and consec<cap_extra:
            buy+=1000*extra; consec+=1; n_extra+=1; extra_total+=1000*extra
        else:
            consec=0
        shares+=buy/ndx; tot+=buy
        flows.append((d,-buy))
        val=shares*ndx
        peak=max(peak,val)
        if val/peak-1<mdd: mdd=val/peak-1
    final=shares*float(rows[-1]['ndx'])
    flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]),final))
    return dict(final=final, ret=final/tot-1, xirr=xirr(flows), mdd=mdd, extra_total=extra_total)

full=ROWS; last240=ROWS[-240:]
print('─'*100)
print('【无脑 + 冷月闲钱加码】最近20年段 (无脑基准 672.5% / MDD -32.0%)')
print('─'*100)
print(f"{'规则':<34}{'收益率':>9}{'vs无脑':>9}{'XIRR':>8}{'MDD':>9}{'加码总额':>10}")
for thr in (40,45,50,55):
    for extra in (1.0,1.5,2.0):
        v=run(last240,thr,extra)
        print(f"温度≤{thr} 加码{extra:g}×/月(最多连加6月):{v['ret']:>9.1%}{(v['ret']-6.725)*100:>+8.1f}pp{v['xirr']:>8.2%}{v['mdd']:>9.1%}{v['extra_total']:>10,.0f}")
print()
print('【同规则 · 全样本26.7年】(无脑基准 962.2% / MDD -41.7%)')
for thr in (40,50):
    for extra in (1.0,2.0):
        v=run(full,thr,extra)
        print(f"温度≤{thr} 加码{extra:g}×:{v['ret']:>9.1%}{(v['ret']-9.622)*100:>+8.1f}pp{v['xirr']:>8.2%}{v['mdd']:>9.1%}")
