# -*- coding: utf-8 -*-
"""奖金择时 · 修正口径版：收益 = 终值 / 全部进账（BASE+奖金，无论何时投出）
XIRR 按资金到账日计现金流（奖金到账即算可用，闲置吃 2% 也算在终值里）
"""
import json, datetime as dt

D = json.load(open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bubble_app/data.json', encoding='utf-8'))
M = [r for r in D['month'] if r['d'] >= '2016-05-01']
CASH_M = 0.02 / 12
BASE = 4500.0
BONUS = {2: 20000.0, 8: 10000.0}


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


def run(mode, thr=55, cap=None, base=BASE):
    shares = 0.0
    tranches = []; waitq = 0.0; wait_mo = 0.0
    tot = 0.0
    flows = []; series = []; peak = 0.0; mdd = 0.0
    n_fire = 0; n_force = 0; n_lowarrive = 0
    firelog = []
    for r in M:
        d = dt.date(*map(int, r['d'].split('-'))); ndx = float(r['ndx']); t = float(r['total'])
        mo = int(r['d'][5:7])
        waitq *= (1 + CASH_M)
        for tr in tranches: tr[0] *= (1 + CASH_M)
        # 资金到账（BASE + 奖金）→ 全部进 tot，作为 XIRR 现金流出
        inflow = base
        if mo in BONUS:
            b = BONUS[mo]; inflow += b
            if t <= thr or (cap and cap == 1):   # 到账时已冷（或一次性模式）→ 立即全投
                tranches.append([b, b]); n_lowarrive += 1
            else:
                waitq += b
        tot += inflow
        flows.append((d, -inflow))
        # 本期待投：BASE 永远当月投出，只有奖金走等待/分期
        deploy = base
        for tr in tranches:
            if tr[0] <= 0: continue
            x = min(tr[0], tr[1]); tr[0] -= x; deploy += x
        if waitq > 0:
            wait_mo += 1
            if t <= thr or (cap and wait_mo >= cap):
                deploy += waitq; waitq = 0.0
                n_fire += 1
                if not (t <= thr): n_force += 1
                firelog.append((r['d'], t, wait_mo))
                wait_mo = 0.0
        shares += deploy / ndx
        val = shares * ndx + waitq + sum(tr[0] for tr in tranches)
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
        series.append((r['d'], val, tot))
    left = waitq + sum(tr[0] for tr in tranches)
    final = shares * float(M[-1]['ndx']) + left
    flows.append((dt.date(*map(int, M[-1]['d'].split('-'))), final))
    return dict(final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd,
                tot=tot, left=left, series=series, n_fire=n_fire, n_force=n_force,
                n_lowarrive=n_lowarrive, firelog=firelog)


CASES = [
    ('① 到手即投（全额无脑）', dict(mode='lump', thr=99, cap=1)),
    ('③ 固定分 6 期',          dict(mode='fix6', thr=99, cap=1)),
    ('⑤ 温度 A 1/3/6/12',      dict(mode='tA',   thr=99, cap=1)),
    ('⑧ 等≤55，无熔断',        dict(mode='w', thr=55, cap=None)),
    ('⑩ 等≤55，18 个月熔断',    dict(mode='w', thr=55, cap=18)),
    ('⑪ 等≤55，12 个月熔断',    dict(mode='w', thr=55, cap=12)),
    ('⑫ 等≤50，18 个月熔断',    dict(mode='w', thr=50, cap=18)),
    ('⑬ 等≤60，18 个月熔断',    dict(mode='w', thr=60, cap=18)),
]

print('─' * 118)
print('修正口径：终值 / 全部进账（84,000/年）。124 个月，总进账 858,000。闲置资金货基 2%')
print('─' * 118)
print(f"{'方案':<22}{'期末总资产':>12}{'收益率':>9}{'vs①':>9}{'XIRR':>8}{'最大回撤':>9}{'触发':>6}{'强投':>5}{'低位到账':>8}")
print('─' * 118)
res = {}
for lb, kw in CASES:
    v = run(**kw)
    res[lb] = v
    b = res['① 到手即投（全额无脑）']
    extra = f"{v['n_fire']:>5}{v['n_force']:>5}{v['n_lowarrive']:>7}"
    print(f"{lb:<22}{v['final']:>12,.0f}{v['ret']:>9.1%}{(v['ret']-b['ret'])*100:>+8.1f}pp"
          f"{v['xirr']:>8.2%}{v['mdd']:>9.1%}{extra}")
print('─' * 118)

print('\n【⑩ 触发记录】温度触发 / 熔断强投：')
for d, t, wm in res['⑩ 等≤55，18 个月熔断']['firelog']:
    idx = next(i for i, r in enumerate(M) if r['d'] == d)
    f12 = (M[idx+12]['ndx']/M[idx]['ndx']-1) if idx+12 < len(M) else None
    f24 = (M[idx+24]['ndx']/M[idx]['ndx']-1) if idx+24 < len(M) else None
    kind = '温度触发' if t <= 55 else '熔断强投'
    print(f'  {d}  temp={t:>5}  等了 {wm:>2} 个月 [{kind}]  未来12m {f12:+.1%}  未来24m {f24 if f24 is not None else float("nan"):+.1%}')

print('\n【分年度累计收益率（修正口径）】')
keys = ['① 到手即投（全额无脑）', '③ 固定分 6 期', '⑧ 等≤55，无熔断', '⑩ 等≤55，18 个月熔断']
years = sorted({r['d'][:4] for r in M})
print(f"{'年份':<8}" + ''.join(f'{k[:9]:>14}' for k in keys))
for y in years:
    line = f'{y:<8}'
    for k in keys:
        s = [x for x in res[k]['series'] if x[0][:4] == y]
        line += f'{s[-1][1]/s[-1][2]-1:>14.1%}' if s else f'{"—":>14}'
    print(line)

# 滚动窗口（修正口径）
print('\n【滚动窗口稳健性（修正口径）】')
ALL = M
def rwin(rows, kw):
    return run(**kw) if False else None
# 简化：窗口内从 0 开始，同样口径
def run_rows(rows, thr=55, cap=None, base=BASE):
    shares=0.0; tranches=[]; waitq=0.0; wait_mo=0.0; tot=0.0; peak=0.0; mdd=0.0
    for r in rows:
        ndx=float(r['ndx']); t=float(r['total']); mo=int(r['d'][5:7])
        waitq*=(1+CASH_M)
        for tr in tranches: tr[0]*=(1+CASH_M)
        inflow=base
        if mo in BONUS:
            b=BONUS[mo]; inflow+=b
            if t<=55: tranches.append([b,b])
            else: waitq+=b
        tot+=inflow
        deploy=base
        for tr in tranches:
            if tr[0]<=0: continue
            x=min(tr[0],tr[1]); tr[0]-=x; deploy+=x
        if waitq>0:
            wait_mo+=1
            if t<=thr or (cap and wait_mo>=cap):
                deploy+=waitq; waitq=0.0; wait_mo=0.0
        shares+=deploy/ndx
        val=shares*ndx+waitq+sum(tr[0] for tr in tranches)
        peak=max(peak,val); mdd=min(mdd,val/peak-1)
    final=shares*float(rows[-1]['ndx'])+waitq+sum(tr[0] for tr in tranches)
    return final/tot-1
for W in (60, 84, 120):
    win=0; n=0; gaps=[]
    for i in range(len(M)-W+1):
        rows=M[i:i+W]
        n+=1
        r1=run_rows(rows, 99, 1)          # 无脑
        r2=run_rows(rows, 55, 18)         # ⑩
        gaps.append((r2-r1)*100)
        if r2>r1: win+=1
    gaps.sort()
    print(f'  {W} 个月窗口（{n} 个）：⑩ 跑赢 {win}/{n} ({win/n:.0%})，收益差 最差 {gaps[0]:+.1f}pp | 中位 {gaps[len(gaps)//2]:+.1f}pp | 最好 {gaps[-1]:+.1f}pp')
