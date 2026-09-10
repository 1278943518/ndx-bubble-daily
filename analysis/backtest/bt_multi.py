# -*- coding: utf-8 -*-
"""倍数定投回测 v4（阈值拉宽: 高热90 / 低分45）
两种口径:
  A 预算恒定: 每月预算 core, 少投的钱进池吃息待补投 (buy=min(pool, core*倍)) → 总投入相同, 比收益率
  B 真倍数定投: 每月实际投 core*倍 (可 >core, 外部追加) → 总投入不同, 比 XIRR
"""
import csv, datetime as dt
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2000-01-01' <= r['date'] < '2026-09-01']
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

# ---------- 倍数档位 ----------
def coef_old(t):   # v1 原版: 高热85 / 低分40
    if t >= 85: return 0.2
    if t >= 75: return 0.7
    if t >= 65: return 0.85
    if t >= 55: return 1.0
    if t >= 40: return 1.3
    return 1.8

def coef_new(t):   # v4 用户指定: 高热90 / 低分45 (两端拉宽)
    if t >= 90: return 0.2
    if t >= 80: return 0.6
    if t >= 70: return 0.85
    if t >= 60: return 1.0
    if t >= 50: return 1.2
    if t >= 45: return 1.5
    return 2.0

def coef_new_lin(t):  # 连续线性版 (90→0.2, 45→2.0 之间线性, 两端封顶)
    lo, hi = 45.0, 90.0
    if t >= hi: return 0.2
    if t <= lo: return 2.0
    return 2.0 + (0.2 - 2.0) * (t - lo) / (hi - lo)

def run(rows, cf, cap_pool=True, core=1000.0):
    """cap_pool=True → 口径A(预算恒定, buy受池限制); False → 口径B(真倍数, 可追加)"""
    shares = 0.0; pool = 0.0; tot = 0.0; flows = []; peak = 0.0; mdd = 0.0
    n_up = n_dn = 0.0
    for r in rows:
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx']); t = float(r['total'])
        m = cf(t)
        if m > 1: n_up += 1
        if m < 1: n_dn += 1
        pool = pool * (1 + CASH_M) + core
        want = core * m
        buy = min(pool, want) if cap_pool else want
        pool -= buy
        # 口径A: 每月预算固定 core(少投进池), tot 记 core; 口径B: 实际投多少记多少
        tot += core if cap_pool else buy
        shares += buy / ndx
        flows.append((d, -core if cap_pool else -buy))
        val = shares * ndx + pool
        if val > 0:
            peak = max(peak, val)
            if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + pool
    flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]), final))
    return dict(final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd, pool=pool,
                up=n_up, dn=n_dn, invest=tot)

def naive(rows, core=1000.0):
    shares = 0.0; tot = 0.0; flows = []; peak = 0.0; mdd = 0.0
    for r in rows:
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx'])
        shares += core / ndx; tot += core; flows.append((d, -core))
        val = shares * ndx
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']); flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]), final))
    return dict(final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd, pool=0, up=0, dn=0, invest=tot)

# ---- 自检 ----
A6 = [r for r in ALL if r['date'] >= '2006-09-01']
chk = [('naive', naive(A6)['ret'], 672.5),
       ('coef_old 口径A', run(A6, coef_old)['ret'], 669.0)]
print('【自检 与 v3 基准对照】')
for nm, got, want in chk:
    flag = 'OK' if abs(got * 100 - want) < 0.5 else '*** 期望 %.1f' % want
    print('  %-14s%7.1f%%   %s' % (nm, got * 100, flag))
print()

segs = [('C 2005-01起', '2005-01-01'), ('A 2006-09起(20年主表)', '2006-09-01'),
        ('B 2010-01起(满10年窗)', '2010-01-01'), ('D 2000-01起(全窗)', '2000-01-01')]
for lb, d0 in segs:
    rows = [r for r in ALL if r['date'] >= d0]
    n = len(rows)
    print('═' * 100)
    print(f'【{lb}】{n}个月  纳指 {float(rows[0]["ndx"]):,.0f}→{float(rows[-1]["ndx"]):,.0f} '
          f'({float(rows[-1]["ndx"])/float(rows[0]["ndx"])-1:+.0%})')
    print('═' * 100)
    b = naive(rows)
    S = [('① 无脑(基准)', b),
         ('② 旧档85/40 A', run(rows, coef_old)),
         ('③ 新档90/45 A', run(rows, coef_new)),
         ('④ 新档线性90/45 A', run(rows, coef_new_lin)),
         ('⑤ 新档90/45 B真倍数', run(rows, coef_new, cap_pool=False)),
         ('⑥ 旧档85/40 B真倍数', run(rows, coef_old, cap_pool=False))]
    print(f"{'策略':<20}{'收益率':>9}{'vs①':>8}{'XIRR':>8}{'MDD':>8}{'投入':>10}{'加码月':>7}{'减投月':>7}")
    for k, v in S:
        print(f"{k:<20}{v['ret']:>9.1%}{(v['ret']-b['ret'])*100:>+7.1f}pp{v['xirr']:>8.2%}{v['mdd']:>8.1%}"
              f"{v['invest']:>10,.0f}{v['up']:>7.0f}{v['dn']:>7.0f}")
    print()
