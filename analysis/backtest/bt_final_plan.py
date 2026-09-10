# -*- coding: utf-8 -*-
"""v8 推荐方案终检: 验证"钱是否真的正好投完" + 完整指标
对比两套: A) L=45/mL=0.15 (超额高)  B) L=40/mL=0.54 (池浅稳健)
"""
import csv, datetime as dt
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2016-03-01' <= r['date'] < '2026-09-01']
CASH_M = 0.02 / 12
B = naive(ALL)

def sim(rows, U, L, mH, mL, core=1000.0, clear_end=True):
    shares = 0.0; pool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
    poolsum = 0.0; maxpool = 0.0; starved = 0; invested = 0.0
    traj = []
    for i, r in enumerate(rows):
        ndx = float(r['ndx']); t = float(r['total'])
        m = mL if t >= U else (mH if t < L else 1.0)
        pool = pool * (1 + CASH_M) + core
        want = core * m
        buy = min(pool, want)
        if want > pool + 1e-9: starved += 1
        if clear_end and i == len(rows) - 1: buy = pool
        pool -= buy
        invested += buy
        tot += core; shares += buy / ndx
        poolsum += pool; maxpool = max(maxpool, pool)
        traj.append((r['date'], pool))
        val = shares * ndx + pool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + pool
    return dict(ret=final / tot - 1, mdd=mdd, pool=pool, avgpool=poolsum / len(rows),
                maxpool=maxpool, starved=starved, invested=invested, budget=tot,
                traj=traj, final=final)

PLANS = [('A 激进: U85/L45/mH2.00/mL0.15', 85, 45, 2.0, 0.15),
         ('B 稳健: U85/L40/mH2.00/mL0.54', 85, 40, 2.0, 0.54),
         ('C 温和: U85/L45/mH1.75/mL0.37', 85, 45, 1.75, 0.37)]

print('无脑基准: 收益 %.1f%%  XIRR %.2f%%  MDD %.1f%%' % (B['ret'] * 100, B['xirr'] * 100, B['mdd'] * 100))
print()
print('%-32s%9s%9s%9s%9s%9s%9s' % ('方案', '超额', 'MDD', '平均池', '最大池', '投入/预算', '欠投月'))
for nm, U, L, mH, mL in PLANS:
    v = sim(ALL, U, L, mH, mL)
    print('%-32s%+8.1fpp%9.1f%%%9.0f%9.0f%9.3f%9d'
          % (nm, (v['ret'] - B['ret']) * 100, v['mdd'] * 100, v['avgpool'], v['maxpool'],
             v['invested'] / v['budget'], v['starved']))

print()
print('=== 配平验证: 不做期末清空时, 池子最终剩多少? (检验"正好投完") ===')
for nm, U, L, mH, mL in PLANS:
    v = sim(ALL, U, L, mH, mL, clear_end=False)
    print('  %-32s 期末残留池 %7.0f (占单月预算 %.2f 倍, 占总投入 %.2f%%)  最大池 %.0f'
          % (nm, v['pool'], v['pool'] / 1000.0, v['pool'] / v['budget'] * 100, v['maxpool']))

print()
print('=== 方案B 池子轨迹(每12个月) ===')
v = sim(ALL, 85, 40, 2.0, 0.54, clear_end=False)
for i in range(0, len(v['traj']), 12):
    d, p = v['traj'][i]
    print('  %s  池 %8.0f  (%.1f 个月预算)' % (d, p, p / 1000.0))
print('  末月 %s  池 %8.0f' % (v['traj'][-1][0], v['traj'][-1][1]))

print()
print('=== 方案B 逐月操作明细（触发月份） ===')
for r in ALL:
    t = float(r['total'])
    if t >= 85 or t < 40:
        act = '停投%.2f倍' % 0.54 if t >= 85 else '加码2.00倍'
        print('  %s  温度 %5.1f  %s' % (r['date'], t, act))

print()
print('=== 未来执行速查（方案B） ===')
print('  温度 >= 85  → 当月投 0.54 倍（约一半）')
print('  温度 <  40  → 当月投 2.00 倍（历史仅 6 次）')
print('  40 <= 温度 < 85 → 当月投 1.00 倍（正常，占 85% 的月份）')
print('  配平校验: 0.54×13 + 2.00×6 + 1.00×107 = %.1f ≈ 月数 126' % (0.54 * 13 + 2.0 * 6 + 107))
