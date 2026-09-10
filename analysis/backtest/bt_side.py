# -*- coding: utf-8 -*-
"""公平对照: 同一笔闲钱总额, 立即投 vs 等温度低再投 (核心月投恒为无脑)
结构: 每月 1000 核心无脑 + 闲钱池每月进 250 (20年共 60,000, 全样本 80,000)
闲钱策略A: 到账即投(池空) / B: 温度≤thr 投光池 / C: ≤thr+18月熔断 / D: ≤50+24月熔断
总本金一致 → 收益率可直接比
"""
import csv, datetime as dt
ROWS=[r for r in csv.DictReader(open('bubble_out/scores_monthly.csv',encoding='utf-8')) if r['date']<'2026-09-01' and r['date']>='2000-01-01']
CASH_M=0.02/12
CORE=1000.0; SIDE=250.0

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

def run(rows, mode, thr=50, cap=24):
    shares=0.0; pool=0.0; wait=0; tot=0.0; flows=[]; peak=0.0; mdd=0.0
    fires=0
    for r in rows:
        d=dt.date.fromisoformat(r['date'][:10]); ndx=float(r['ndx']); t=float(r['total'])
        buy=CORE
        pool+=SIDE*CASH_M  # 池内先吃息
        pool+=SIDE
        if mode=='A':
            buy+=pool; pool=0.0
        elif mode=='wait':
            if t<=thr:
                buy+=pool; pool=0.0; wait=0; fires+=1
            else:
                wait+=1
                if cap and wait>=cap:
                    buy+=pool; pool=0.0; wait=0; fires+=1
        shares+=buy/ndx
        tot+=buy
        flows.append((d,-buy))
        val=shares*ndx
        peak=max(peak,val)
        if val/peak-1<mdd: mdd=val/peak-1
    final=shares*float(rows[-1]['ndx'])
    flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]),final))
    return dict(final=final, ret=final/tot-1, xirr=xirr(flows), mdd=mdd, fires=fires)

full=ROWS; last240=ROWS[-240:]
for rows, lb, b_ref in [(last240,'最近20年',None),(full,'全样本26.7年',None)]:
    print('─'*96)
    print(f'【{lb}】核心 1000/月无脑 + 闲钱 250/月(合计 {SIDE*len(rows):,.0f})')
    print('─'*96)
    print(f"{'闲钱策略':<26}{'收益率':>9}{'vs闲钱立即投':>14}{'XIRR':>8}{'MDD':>9}")
    res={}
    res['A 到账即投(无脑)']=run(rows,'A')
    for thr,cap,lb in [(55,None,'B 等≤55投光'),(55,18,'C ≤55+18月熔断'),(50,24,'D ≤50+24月熔断'),(40,None,'E 等≤40投光'),(45,12,'F ≤45+12月熔断')]:
        res[lb]=run(rows,'wait',thr,cap)
    b=res['A 到账即投(无脑)']
    for k,v in res.items():
        print(f"{k:<26}{v['ret']:>9.1%}{(v['ret']-b['ret'])*100:>+13.1f}pp{v['xirr']:>8.2%}{v['mdd']:>9.1%}")
    print(f"  闲钱触发次数: " + '  '.join(f"{k.split(' ')[0]}={v['fires']}" for k,v in res.items() if k!='A 到账即投(无脑)'))
