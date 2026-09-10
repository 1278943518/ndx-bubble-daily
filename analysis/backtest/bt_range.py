# -*- coding: utf-8 -*-
"""区间敏感性: 同一策略, 只换起点 → 结论是否稳健
重点: 2016-03 起(8/8腿, 唯一完全可比) 与 其它区间对照
"""
import csv, datetime as dt
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2000-01-01' <= r['date'] < '2026-09-01']

def mk(hi, hm, lo, lm):
    def cf(t):
        if t >= hi: return hm
        if t < lo: return lm
        return 1.0
    return cf

cands = [('90/0.2/45/3.0 用户指定', mk(90, 0.2, 45, 3.0)),
         ('85/0.0/45/4.0 网格最优', mk(85, 0.0, 45, 4.0)),
         ('85/0.2/45/3.0 次优', mk(85, 0.2, 45, 3.0))]

STARTS = [('2000-01 (5腿起)', '2000-01-01'), ('2005-01', '2005-01-01'),
          ('2010-01 (7腿起)', '2010-01-01'), ('2016-03 (8腿起★)', '2016-03-01'),
          ('2018-01', '2018-01-01')]

print('=== 同一策略 × 不同起点：超额 vs 无脑 (pp, 口径A 预算恒定) ===')
print('%-22s' % '参数' + ''.join('%14s' % n for n, _ in STARTS))
for nm, cf in cands:
    row = []
    for _, d0 in STARTS:
        rows = [r for r in ALL if r['date'] >= d0]
        b = naive(rows)['ret']
        row.append((run(rows, cf)['ret'] - b) * 100)
    print('%-22s' % nm + ''.join('%+14.1f' % x for x in row))
print('%-22s' % '① 无脑(基准)' + ''.join('%14.1f' % 0 for _ in STARTS))

print()
print('=== 可信区间 2016-03 起 详细结果 ===')
rows = [r for r in ALL if r['date'] >= '2016-03-01']
b = naive(rows)
print('样本 %d 个月  纳指 %.0f → %.0f (%+.0f%%)  无脑收益 %.1f%%  XIRR %.2f%%  MDD %.1f%%'
      % (len(rows), float(rows[0]['ndx']), float(rows[-1]['ndx']),
         (float(rows[-1]['ndx']) / float(rows[0]['ndx']) - 1) * 100, b['ret'] * 100, b['xirr'] * 100, b['mdd'] * 100))
print('%-22s%9s%9s%9s%9s%9s' % ('参数', '收益率', 'vs无脑', 'XIRR', 'MDD', '期末池'))
for nm, cf in cands:
    v = run(rows, cf)
    print('%-22s%9.1f%%%+8.1fpp%9.2f%%%9.1f%%%9.0f'
          % (nm, v['ret'] * 100, (v['ret'] - b['ret']) * 100, v['xirr'] * 100, v['mdd'] * 100, v['pool']))
print('%-22s%9.1f%%%8s%9.2f%%%9.1f%%%9s' % ('① 无脑', b['ret'] * 100, '—', b['xirr'] * 100, b['mdd'] * 100, '—'))

print()
print('=== 该区间内 触发情况 ===')
lo = [r['date'] for r in rows if float(r['total']) < 45]
hi = [r['date'] for r in rows if float(r['total']) >= 85]
hi90 = [r['date'] for r in rows if float(r['total']) >= 90]
print('低温<45 触发 %d 个月: %s' % (len(lo), ', '.join(lo)))
print('高温>=85 触发 %d 个月: %s' % (len(hi), ', '.join(hi)))
print('高温>=90 触发 %d 个月: %s' % (len(hi90), ', '.join(hi90) if hi90 else '无'))
