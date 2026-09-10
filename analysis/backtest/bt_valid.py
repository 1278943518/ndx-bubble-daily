# -*- coding: utf-8 -*-
"""温度可信度验证：不同起点重跑 6 策略 + 闲钱对照
窗长: 2000-01起积累, 2001-01 窗12月, 2010-01 满120月(10年)
区间: C=2005-01起(窗5年+), A=2006-09起(原20年表), B=2010-01起(满窗,最干净)
"""
import csv, datetime as dt
ALL=[r for r in csv.DictReader(open('bubble_out/scores_monthly.csv',encoding='utf-8')) if r['date']<'2026-09-01' and r['date']>='2000-01-01']
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

def coef(t):
    if t>=85: return 0.2
    if t>=75: return 0.7
    if t>=65: return 0.85
    if t>=55: return 1.0
    if t>=40: return 1.3
    return 1.8

def run(rows, mode, thr=55, cap=None, core=1000.0, side=0.0, side_mode='A', side_thr=40):
    """核心+可选闲钱(side=每期闲钱额)"""
    shares=0.0; pool=0.0; wait=0; tot=0.0; flows=[]; peak=0.0; mdd=0.0
    for r in rows:
        d=dt.date.fromisoformat(r['date'][:10]); ndx=float(r['ndx']); t=float(r['total'])
        # 核心
        if mode=='naive':
            buy=core
        elif mode=='coef':
            pool+=core; buy=min(pool,core*coef(t)); pool-=buy
        elif mode=='wait':
            pool+=core
            if t<=thr or (cap and wait>=cap):
                buy=pool; pool=0.0; wait=0
            else:
                buy=0.0; wait+=1
        # 闲钱(独立池, 预算外)
        if side>0:
            pool2 = locals().get('pool2',0.0)
        pool2 = locals().get('pool2',0.0) if side>0 else 0.0
        if side>0:
            pool2*= (1+CASH_M); pool2+=side
            if side_mode=='A': buy+=pool2; pool2=0.0
            elif side_mode=='wait':
                if t<=side_thr: buy+=pool2; pool2=0.0
        shares+=buy/ndx; tot+=buy
        flows.append((d,-buy))
        val=shares*ndx
        if val>0:
            peak=max(peak,val)
            if val/peak-1<mdd: mdd=val/peak-1
    final=shares*float(rows[-1]['ndx'])
    flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]),final))
    return dict(final=final, ret=final/tot-1, xirr=xirr(flows), mdd=mdd)

segs=[('C 2005-01 起(窗5年+)','2005-01-01'),('A 2006-09 起(原20年表)','2006-09-01'),('B 2010-01 起(满10年窗)','2010-01-01')]
for lb, d0 in segs:
    rows=[r for r in ALL if r['date']>=d0]
    print('═'*100)
    print(f'【{lb}】{rows[0]["date"]} ~ {rows[-1]["date"]} ({len(rows)}个月) 纳指 {float(rows[0]["ndx"]):,.0f}→{float(rows[-1]["ndx"]):,.0f} ({float(rows[-1]["ndx"])/float(rows[0]["ndx"])-1:+.0%})')
    print('═'*100)
    res={}
    res['① 无脑']=run(rows,'naive')
    res['② 温和节流']=run(rows,'coef')
    res['④ 等≤55']=run(rows,'wait',thr=55)
    res['⑤ ≤55+18月']=run(rows,'wait',thr=55,cap=18)
    res['⑥ ≤50+24月']=run(rows,'wait',thr=50,cap=24)
    b=res['① 无脑']
    print(f"{'策略':<14}{'收益率':>9}{'vs①':>8}{'XIRR':>8}{'MDD':>8}")
    for k,v in res.items():
        print(f"{k:<14}{v['ret']:>9.1%}{(v['ret']-b['ret'])*100:>+7.1f}pp{v['xirr']:>8.2%}{v['mdd']:>8.1%}")
    print('  ── 闲钱对照(核心1000无脑 + 闲钱250/月, 总本金同) ──')
    sa=run(rows,'naive',side=250.0,side_mode='A')
    for sth, lb2 in [(40,'等≤40投光'),(50,'等≤50投光')]:
        sv=run(rows,'naive',side=250.0,side_mode='wait',side_thr=sth)
        print(f"  闲钱{lb2:<12}{sv['ret']:>8.1%}  vs闲钱即投 {(sv['ret']-sa['ret'])*100:>+6.1f}pp   MDD {sv['mdd']:>7.1%} vs {sa['mdd']:.1%}")
