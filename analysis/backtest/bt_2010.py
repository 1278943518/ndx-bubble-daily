# -*- coding: utf-8 -*-
"""2010 起正式口径：主表 + 分阶段 + 多起点敏感性 + 换算（引擎与 bt_final 一致）
自检基准：① 473.6% ② 468.9% ④ 458.2% ⑤ 451.8% ⑥ 450.9%（bt_final B 段）
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
        pool = pool * (1 + CASH_M) + core
        if mode == 'naive':
            buy = core
        elif mode == 'coef':
            buy = min(pool, core * coef(t))
        else:
            if t <= thr or (cap is not None and wait >= cap):
                buy = pool; wait = 0
            else:
                buy = 0.0; wait += 1
        pool -= buy
        if side > 0:
            spool = spool * (1 + CASH_M) + side
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
                pool=pool, spool=spool, nfire=None)

# ============ 1) 主表: 2010-01 起 ============
B = [r for r in ALL if r['date'] >= '2010-01-01']
STRATS = [('① 无脑', dict(mode='naive')), ('② 温和节流', dict(mode='coef')),
          ('③ 只减不加速', dict(mode='coef', thr=0)) , ('④ 等≤55', dict(mode='wait', thr=55)),
          ('⑤ ≤55+18月', dict(mode='wait', thr=55, cap=18)), ('⑥ ≤50+24月', dict(mode='wait', thr=50, cap=24))]
def decoef(t):  # ③ 只减不加速
    if t >= 85: return 0.2
    if t >= 75: return 0.7
    if t >= 65: return 0.85
    return 1.0

def run3(rows):
    """③ 专用"""
    shares=0.0; pool=0.0; tot=0.0; flows=[]; peak=0.0; mdd=0.0
    for r in rows:
        d=dt.date.fromisoformat(r['date'][:10]); ndx=float(r['ndx']); t=float(r['total'])
        pool=pool*(1+CASH_M)+1000
        buy=min(pool,1000*decoef(t)); pool-=buy
        tot+=1000; shares+=buy/ndx
        flows.append((d,-1000))
        val=shares*ndx+pool
        if val>0:
            peak=max(peak,val)
            if val/peak-1<mdd: mdd=val/peak-1
    final=shares*float(rows[-1]['ndx'])+pool
    flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]),final))
    return dict(final=final,ret=final/tot-1,xirr=xirr(flows),mdd=mdd)

res={}
res['① 无脑']=run(B,'naive'); res['② 温和节流']=run(B,'coef'); res['③ 只减不加速']=run3(B)
res['④ 等≤55']=run(B,'wait',thr=55); res['⑤ ≤55+18月']=run(B,'wait',thr=55,cap=18)
res['⑥ ≤50+24月']=run(B,'wait',thr=50,cap=24)
b=res['① 无脑']
print('═'*100)
print(f'【正式口径主表】2010-01 ~ 2026-08 · {len(B)}个月(满10年窗) · 月投1000 · 纳指 +1592%')
print('═'*100)
print(f"{'策略':<14}{'期末':>11}{'收益率':>9}{'vs①':>8}{'XIRR':>8}{'MDD':>8}{'投入率':>8}")
for k in ['① 无脑','② 温和节流','③ 只减不加速','④ 等≤55','⑤ ≤55+18月','⑥ ≤50+24月']:
    v=res[k]
    print(f"{k:<14}{v['final']:>11,.0f}{v['ret']:>9.1%}{(v['ret']-b['ret'])*100:>+7.1f}pp{v['xirr']:>8.2%}{v['mdd']:>8.1%}{v['final']/(v['final']):>8.1%}")

# ============ 2) 分阶段(2010 后) ============
print()
print('【分阶段】(段内独立起算)')
segs=[('2010-01~2021-11 慢牛+成长牛','2010-01-01','2021-11-30'),
      ('2022-01~2022-12 加息熊市','2022-01-01','2022-12-31'),
      ('2023-01~2026-08 AI 周期','2023-01-01','2026-08-31')]
for lb,d0,d1 in segs:
    sg=[r for r in ALL if d0<=r['date']<=d1]
    rr={}
    rr['① 无脑']=run(sg,'naive'); rr['② 温和节流']=run(sg,'coef')
    rr['④ 等≤55']=run(sg,'wait',thr=55)
    bb=rr['① 无脑']
    print(f"  {lb}: ①{bb['ret']:>7.1%}  ②{(rr['② 温和节流']['ret']-bb['ret'])*100:+6.1f}pp  "
          f"④{(rr['④ 等≤55']['ret']-bb['ret'])*100:+6.1f}pp")

# ============ 3) 多起点敏感性 ============
print()
print('【多起点敏感性】(至 2026-08)')
for d0 in ['2010-01-01','2012-01-01','2014-01-01','2016-01-01','2018-01-01']:
    sg=[r for r in ALL if r['date']>=d0]
    r1=run(sg,'naive'); r2=run(sg,'coef'); r4=run(sg,'wait',thr=55)
    print(f"  {d0}起({len(sg):>3}个月): ①{r1['ret']:>7.1%}  ②{(r2['ret']-r1['ret'])*100:+6.1f}pp  "
          f"④{(r4['ret']-r1['ret'])*100:+6.1f}pp")

# ============ 4) 闲钱换算 ============
print()
print('【闲钱对照 2010 起】(核心1000+闲钱250/月, 同总额)')
sa=run(B,'naive',side=250.0)
for sth,nm in [(40,'等≤40'),(50,'等≤50'),(55,'等≤55')]:
    sv=run(B,'naive',side=250.0,side_thr=sth,side_wait=True)
    print(f"  闲钱{nm}: {sv['ret']:>7.1%}  vs即投 {(sv['ret']-sa['ret'])*100:+6.1f}pp  MDD {sv['mdd']:.1%} vs {sa['mdd']:.1%}")

print()
print('【换算 4,500/月 2010-2026】(累计本金 90 万)')
for k in ['① 无脑','② 温和节流','④ 等≤55','⑤ ≤55+18月','⑥ ≤50+24月']:
    v=res[k]
    print(f"  {k:<12} {v['final']*4.5/10000:>7.1f} 万")
