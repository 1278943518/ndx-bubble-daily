# -*- coding: utf-8 -*-
"""节流策略细节解剖：钱在哪亏的、亏多少、什么环境才可能赢"""
import json, datetime as dt

D = json.load(open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bubble_app/data.json', encoding='utf-8'))
M = [r for r in D['month'] if r['d'] >= '2016-05-01']   # 124 个月，与主回测一致
MONTHLY = 1000.0
CASH_M = 0.02 / 12


def coef(t):
    if t >= 85:  return 0.2
    if t >= 75:  return 0.7
    if t >= 65:  return 0.85
    if t >= 55:  return 1.0
    if t >= 40:  return 1.3
    return 1.8


def run(fn):
    """固定预算递延口径：每月进 1000，投出 min(池子, 1000*系数)"""
    shares = 0.0; pool = 0.0; invested = 0.0; tot = 0.0
    logs = []
    for r in M:
        ndx = float(r['ndx']); t = float(r['total'])
        pool += MONTHLY
        buy = min(pool, MONTHLY * fn(t))
        shares += buy / ndx; invested += buy; tot += MONTHLY
        pool -= buy; pool *= (1 + CASH_M)
        logs.append(dict(d=r['d'], t=t, coef=fn(t), buy=buy, ndx=ndx, shares=shares,
                         avg_cost=invested / shares if shares else 0, pool=pool))
    final = shares * float(M[-1]['ndx']) + pool
    return dict(logs=logs, shares=shares, invested=invested, final=final, pool=pool)


naive = run(lambda t: 1.0)
thr = run(coef)

L1, L2 = naive['logs'], thr['logs']
print('=' * 100)
print(f"{'指标':<28}{'① 无脑':>14}{'② 节流':>14}{'差异':>14}")
print('=' * 100)
print(f"{'累计投入':<28}{naive['invested']:>14,.0f}{thr['invested']:>14,.0f}{thr['invested']-naive['invested']:>+14,.0f}")
print(f"{'期末份额(股数)':<26}{naive['shares']:>14,.3f}{thr['shares']:>14,.3f}{(thr['shares']/naive['shares']-1):>+13.1%}")
print(f"{'期末市值':<28}{naive['final']:>14,.0f}{thr['final']:>14,.0f}{(thr['final']-naive['final']):>+14,.0f}")
print(f"{'份额平均成本':<26}{naive['invested']/naive['shares']:>14.2f}{thr['invested']/thr['shares']:>14.2f}"
      f"{(thr['invested']/thr['shares']-naive['invested']/naive['shares']):>+13.2f}")

# 每月差异：② 比 ① 少投/多投
print('\n' + '=' * 100)
print('系数 vs 温度分布（② 各月系数使用情况）')
print('=' * 100)
buckets = [(85, 999, '≥85  →0.2×'), (75, 85, '75–85 →0.7×'), (65, 75, '65–75 →0.85×'),
           (55, 65, '55–65 →1.0×'), (40, 55, '40–55 →1.3×'), (0, 40, '≤40   →1.8×')]
for lo, hi, lb in buckets:
    rows = [l for l in L2 if lo <= l['t'] < hi]
    amt = sum(l['buy'] for l in rows)
    print(f"  {lb:<12}{len(rows):>4} 个月   投出 {amt:>10,.0f} 元   （若全额应投 {len(rows)*1000:,.0f}）")

# 少投的钱集中在哪些年月
print('\n' + '=' * 100)
print('② 比 ① 少投最多的 12 个月（= 踏空的具体位置）')
print('=' * 100)
diff = []
for a, b in zip(L1, L2):
    diff.append((b['d'], b['t'], b['buy'] - a['buy'], a['ndx']))
diff.sort(key=lambda x: x[2])
for d, t, dlt, ndx in diff[:12]:
    print(f"  {d}  温度 {t:>5}  少投 {dlt:>+7,.0f} 元  纳指当时 {ndx:,.0f}")

# 减投档位（≥65）月份之后的市场表现 → 减投当时市场还在涨吗
print('\n' + '=' * 100)
print('节流"少买"时点之后的纳指表现（减投那 52 个月的未来 3/6/12 个月）')
print('=' * 100)
cut = [(i, l) for i, l in enumerate(L2) if l['coef'] < 1.0]
print(f"  减投月份共 {len(cut)} 个（42% 的时间）")
for h, lb in ((3, '未来3个月'), (6, '未来6个月'), (12, '未来12个月')):
    rs = []
    for i, l in cut:
        if i + h < len(M):
            rs.append(M[i + h]['ndx'] / M[i]['ndx'] - 1)
    import statistics as st
    print(f"  {lb}: 均值 {st.mean(rs):+.1%} | 中位 {st.median(rs):+.1%} | 为正 {sum(1 for x in rs if x>0)/len(rs):.0%}")

# 加投档（≤55）月份之后的表现（对照）
print('\n' + '=' * 100)
print('节流"加倍"时点之后的纳指表现（加投那 39 个月）')
print('=' * 100)
add = [(i, l) for i, l in enumerate(L2) if l['coef'] > 1.0]
print(f"  加投月份共 {len(add)} 个")
for h, lb in ((3, '未来3个月'), (6, '未来6个月'), (12, '未来12个月')):
    rs = []
    for i, l in add:
        if i + h < len(M):
            rs.append(M[i + h]['ndx'] / M[i]['ndx'] - 1)
    import statistics as st
    print(f"  {lb}: 均值 {st.mean(rs):+.1%} | 中位 {st.median(rs):+.1%} | 为正 {sum(1 for x in rs if x>0)/len(rs):.0%}")

# 逐月累计缺口在哪年形成
print('\n' + '=' * 100)
print('差距逐年形成过程（12 月 31 日的累计市值差）')
print('=' * 100)
for y in sorted({l['d'][:4] for l in L1}):
    a = [l for l in L1 if l['d'][:4] == y][-1]
    b = [l for l in L2 if l['d'][:4] == y][-1]
    va = a['shares'] * a['ndx'] + 0; vb = b['shares'] * b['ndx']
    # 用日志最后一条的市值近似
    print(f"  {y}: ① 份额价值 {va:>10,.0f} | ② {vb:>10,.0f} | 差 {vb-va:>+10,.0f}")
