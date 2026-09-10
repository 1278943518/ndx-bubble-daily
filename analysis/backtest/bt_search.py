# -*- coding: utf-8 -*-
"""问题1确认 + 参数搜索：能否通过调倍率/门槛让节流跑赢无脑"""
import csv, datetime as dt, itertools

ROWS = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
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

def rule_coef(ths, cs, t):
    """ths 降序阈值列表, cs 与 ths 同长(该档系数); 低于最低阈值的用 cs[-1]? 约定: 高于 ths[0] 用 cs[0], ths[i-1]~ths[i] 用 cs[i], 低于最后阈值用 1.0(或cs尾) —— 由 cs 长度约定:
       实际规则: ths[i-1] > t >= ths[i] → cs[i]; t >= ths[0] → cs[0]; t < ths[-1] → cs[-1] 之后档"""
    if t >= ths[0]: return cs[0]
    for i in range(1, len(ths)):
        if t >= ths[i]: return cs[i]
    return cs[-1]

def run(rows, ths, cs, pool_mode='cap', budget=1000):
    """pool_mode: 'cap' 追投上限=1×budget; 'clear' 系数>1时清空池子"""
    shares = 0.0; pool = 0.0; tot = 0.0
    flows = []; peak = 0.0; mdd = 0.0
    invested = 0.0
    for r in rows:
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx']); t = float(r['total'])
        pool += budget
        c = rule_coef(ths, cs, t)
        if pool_mode == 'clear' and c > 1.0:
            buy = pool                      # 冷月清池加倍
        else:
            buy = min(pool, budget * c)
        shares += buy / ndx
        invested += buy
        pool -= buy; pool *= (1 + CASH_M)
        tot += budget
        flows.append((d, -budget))
        val = shares * ndx + pool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + pool
    flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]), final))
    return dict(final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd,
                invested=invested, tot=tot)

# ============ 问题1: 温和节流的总投入是否 < 无脑 ============
ths0 = [85, 75, 65, 55, 40]
cs0 = [0.2, 0.7, 0.85, 1.0, 1.3, 1.8]   # 注意 rule_coef 约定: t>=85→cs[0]; 75-85→cs[1]; 65-75→cs[2]; 55-65→cs[3]; 40-55→cs[4]; t<40→cs[5]? 我的 rule_coef: t>=ths[0]→cs[0]; t>=ths[1]→cs[1]... t<ths[-1]→cs[-1]。th0=[85,75,65,55,40] 5 阈值 → cs 应为 6 段: >=85, 75-85, 65-75, 55-65, 40-55, <40 → cs 长度 6 = len+1。调整 rule_coef。
# 修正: ths 表示各下界 [85,75,65,55,40], cs=[c_ge85, c_75, c_65, c_55, c_40, c_lt40]
def rule_coef2(ths, cs, t):
    if t >= ths[0]: return cs[0]
    for i in range(1, len(ths)):
        if t >= ths[i]: return cs[i]
    return cs[-1]

full = ROWS; last240 = ROWS[-240:]
r1_full = run(full, [85,75,65,55,40], [1,1,1,1,1,1])
r2_full = run(full, ths0, [0.2,0.7,0.85,1.0,1.3,1.8])
r1_20 = run(last240, [85,75,65,55,40], [1,1,1,1,1,1])
r2_20 = run(last240, ths0, [0.2,0.7,0.85,1.0,1.3,1.8])
print('='*70)
print('问题1 确认: 温和节流的总投入 vs 无脑')
print('='*70)
for lb, a, b in [('全样本26.7年', r1_full, r2_full), ('最近20年', r1_20, r2_20)]:
    print(f'{lb}: 无脑买入 {a["invested"]:>9,.0f} | 节流买入 {b["invested"]:>9,.0f} | '
          f'少投 {a["invested"]-b["invested"]:>8,.0f} ({b["invested"]/a["invested"]-1:+.1%}) | 期末池 {b["tot"]-b["invested"]:,.0f}')
print('  → 节流加速档(1.3×/1.8×)受池子上限约束, 冷月想加码但池子常不够 → 净买入偏少')

# ============ 参数搜索 ============
cands = []
# 结构1: 基线阈值, 系数变体
base_ths = [85, 75, 65, 55, 40]
coef_variants = [
    [0.2,0.7,0.85,1.0,1.3,1.8],  # 基线
    [0.0,0.5,0.8,1.0,1.5,2.0],
    [0.0,0.5,0.85,1.0,1.3,1.5],
    [0.0,0.7,1.0,1.0,1.5,2.0],
    [0.3,0.7,0.85,1.0,1.2,1.5],
    [0.0,0.3,0.6,1.0,1.5,2.0],
    [0.0,0.5,1.0,1.0,1.0,1.0],  # 只极端减
    [0.5,0.8,1.0,1.0,1.3,1.8],  # 温和减
    [0.0,1.0,1.0,1.0,1.0,1.0],  # ≥85停投
]
# 结构2: 更早减档
earlier_ths = [80, 70, 60, 50, 40]
# 结构3: 只有两档
two_ths = [80, 55]
two_cs_list = [[0.0, 1.0, 2.0], [0.0, 1.0, 1.5], [0.0, 1.0, 1.0],
               [0.3, 1.0, 1.8], [0.0, 0.7, 1.5], [0.5,1.0,1.8]]
# 结构4: 高阈值触发(更少减)
hi_ths = [90, 80, 70]
hi_cs_list = [[0.0,0.5,0.8,1.5], [0.0,0.7,1.0,1.5], [0.3,0.7,0.9,1.3]]
# 结构5: 减档低/加档高 只两区
sel_ths = [75, 50]
sel_cs_list = [[0.0, 1.0, 2.0], [0.0, 1.0, 1.8], [0.0, 0.5, 1.5], [0.3, 1.0, 2.0], [0.0, 1.2, 1.2]]

for ths, cs in [(base_ths, c) for c in coef_variants]:
    cands.append((ths, cs))
for ths, cs in [(earlier_ths, c) for c in coef_variants[:6]]:
    cands.append((ths, cs))
for ths, cs in [(two_ths, c) for c in two_cs_list]:
    cands.append((ths, cs))
for ths, cs in [(hi_ths, c) for c in hi_cs_list]:
    cands.append((ths, cs))
for ths, cs in [(sel_ths, c) for c in sel_cs_list]:
    cands.append((ths, cs))
# 每种规则再跑 clear 池模式(冷月清池) —— 只对含 >1 系数且有减档的规则
print(f'\n候选规则数: {len(cands)} × 2 池模式')

base20 = r1_20['ret']; base_full = r1_full['ret']
res = []
for ths, cs in cands:
    for pm in ('cap', 'clear'):
        v20 = run(last240, ths, cs, pm)
        vf = run(full, ths, cs, pm)
        res.append((ths, cs, pm, v20, vf))

# 排序: 20年段收益差
res.sort(key=lambda x: -(x[3]['ret'] - base20))
print('\n' + '='*90)
print('【Top 15 · 按最近20年段 vs 无脑(672.5%)】')
print('='*90)
print(f"{'规则(阈值/系数/池)':<44}{'20年收益':>9}{'vs①':>8}{'全样本':>9}{'vs①全':>8}{'20年MDD':>9}{'投入率':>8}")
for ths, cs, pm, v20, vf in res[:15]:
    tag = f"{ths} / {[round(c,2) for c in cs]} / {pm}"
    print(f"{tag:<44}{v20['ret']:>9.1%}{(v20['ret']-base20)*100:>+7.1f}pp{vf['ret']:>9.1%}"
          f"{(vf['ret']-base_full)*100:>+7.1f}pp{v20['mdd']:>9.1%}{v20['invested']/v20['tot']:>7.1%}")
