# -*- coding: utf-8 -*-
"""变体：等待模式 + 熔断上限 + 触发阈值灵敏度"""
import json, datetime as dt
exec(open('bt_bonus.py', encoding='utf-8').read().split('MODES = ')[0])  # 复用函数

def run2(mode, thr=55, cap=None):
    """thr=触发阈值；cap=最长等待月数，超过则无条件投出全部等待池"""
    shares = 0.0
    tranches = []; waitq = 0.0; wait_mo = 0.0
    tot = 0.0; flows = []; series = []; peak = 0.0; mdd = 0.0
    for r in M:
        d = dt.date(*map(int, r['d'].split('-'))); ndx = float(r['ndx']); t = float(r['total'])
        mo = int(r['d'][5:7])
        waitq *= (1 + CASH_M)
        for tr in tranches: tr[0] *= (1 + CASH_M)
        if mo in BONUS:
            b = BONUS[mo]; k = schedule(t, mode)
            if k == 999: waitq += b
            else: tranches.append([b, b / k])
        deploy = BASE
        for tr in tranches:
            if tr[0] <= 0: continue
            x = min(tr[0], tr[1]); tr[0] -= x; deploy += x
        # 触发：温度<=thr 或 等待超期
        forced = False
        if waitq > 0:
            wait_mo += 1
            if t <= thr or (cap and wait_mo >= cap):
                deploy += waitq; waitq = 0.0
                if not (t <= thr): forced = True
                wait_mo = 0.0
        shares += deploy / ndx; tot += deploy
        flows.append((d, -deploy))
        val = shares * ndx + waitq + sum(tr[0] for tr in tranches)
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
        series.append((r['d'], val, tot))
    left = waitq + sum(tr[0] for tr in tranches)
    final = shares * float(M[-1]['ndx']) + left
    flows.append((dt.date(*map(int, M[-1]['d'].split('-'))), final))
    return dict(final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd, left=left,
                series=series, n_force=forced and 1 or 0)

# 基准重跑
def run_ref():
    return run2('lump')
ref = run_ref()
print('─' * 108)
print(f"{'变体':<30}{'期末市值':>12}{'收益率':>9}{'vs①':>9}{'XIRR':>8}{'最大回撤':>9}")
print('─' * 108)
print(f"{'① 到手即投（基准）':<30}{ref['final']:>12,.0f}{ref['ret']:>9.1%}{0:>+9.1f}pp{ref['xirr']:>8.2%}{ref['mdd']:>9.1%}")
tests = [
    ('⑧ 等≤55 全池解冻',            dict(mode='wait55', thr=55, cap=None)),
    ('⑩ 等≤55，18个月熔断',         dict(mode='wait55', thr=55, cap=18)),
    ('⑪ 等≤55，12个月熔断',         dict(mode='wait55', thr=55, cap=12)),
    ('⑫ 等≤50，18个月熔断',         dict(mode='wait50', thr=50, cap=18)),
    ('⑬ 等≤60，18个月熔断',         dict(mode='wait55', thr=60, cap=18)),
    ('⑭ 等≤45，24个月熔断',         dict(mode='wait55', thr=45, cap=24)),
]
for lb, kw in tests:
    v = run2(**kw)
    print(f"{lb:<30}{v['final']:>12,.0f}{v['ret']:>9.1%}{(v['ret']-ref['ret'])*100:>+8.1f}pp"
          f"{v['xirr']:>8.2%}{v['mdd']:>9.1%}")

# 12 个月滚动窗口：⑩ vs 基准 的胜率
print('\n【滚动 60/84/120 个月窗口稳健性：⑩(≤55+18月熔断) vs ①】')
def rolling_run(rows, mode, thr=55, cap=None):
    def xirr_f(flows):
        def npv(r):
            t0 = flows[0][0]
            return sum(a/(1+r)**((d-t0).days/365.0) for d,a in flows)
        lo,hi=-0.9999,5.0
        if npv(lo)*npv(hi)>0: return None
        for _ in range(300):
            mid=(lo+hi)/2
            if npv(lo)*npv(mid)<=0: hi=mid
            else: lo=mid
        return (lo+hi)/2
    shares=0.0; tranches=[]; waitq=0.0; wait_mo=0.0; tot=0.0
    flows=[]; peak=0.0; mdd=0.0
    first = rows[0]['d'][:7]
    for r in rows:
        ndx=float(r['ndx']); t=float(r['total']); mo=int(r['d'][5:7])
        d=dt.date(*map(int,r['d'].split('-')))
        waitq*=(1+CASH_M)
        for tr in tranches: tr[0]*=(1+CASH_M)
        if mo in BONUS:
            b=BONUS[mo]; k=schedule(t,mode)
            if k==999: waitq+=b
            else: tranches.append([b,b/k])
        deploy=BASE
        for tr in tranches:
            if tr[0]<=0: continue
            x=min(tr[0],tr[1]); tr[0]-=x; deploy+=x
        if waitq>0:
            wait_mo+=1
            if t<=thr or (cap and wait_mo>=cap):
                deploy+=waitq; waitq=0.0; wait_mo=0.0
        shares+=deploy/ndx; tot+=deploy
        flows.append((d,-deploy))
        val=shares*ndx+waitq+sum(tr[0] for tr in tranches)
        peak=max(peak,val); mdd=min(mdd,val/peak-1)
    left=waitq+sum(tr[0] for tr in tranches)
    final=shares*float(rows[-1]['ndx'])+left
    flows.append((dt.date(*map(int,rows[-1]['d'].split('-'))),final))
    return final/tot-1, xirr_f(flows), mdd

ALL = [r for r in D['month'] if r['d'] >= '2014-01-01']
for W in (60, 84):
    win=0; n=0; gaps=[]
    for i in range(len(ALL)-W+1):
        rows=ALL[i:i+W]
        if rows[0]['d'] < '2016-05-31': 
            # 需要之前有温度数据的起点（2016-03 起）其实都行，但奖金节奏从起点月算
            pass
        n+=1
        r1,_,m1 = rolling_run(rows,'lump')
        r2,_,m2 = rolling_run(rows,'wait55',55,18)
        gaps.append((r2-r1)*100)
        if r2>r1: win+=1
    gaps.sort()
    print(f'  {W} 个月窗口（{n} 个）：⑩ 跑赢 ① 比例 {win}/{n} ({win/n:.0%})，差分布 {gaps[0]:+.1f}pp ~ 中位 {gaps[len(gaps)//2]:+.1f}pp ~ {gaps[-1]:+.1f}pp')
