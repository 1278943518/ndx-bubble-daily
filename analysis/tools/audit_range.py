# -*- coding: utf-8 -*-
"""数据成熟度审计: 每个特征什么时候开始有真实值(而非50占位), 以及分位窗口参数"""
import csv, collections
MON = list(csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8')))
WK = list(csv.DictReader(open('bubble_out/scores_weekly.csv', encoding='utf-8')))

NAMES = {'s1': '估值 CAPE', 's2': '预期 动量', 's3': '情绪 VIX', 's4': '杠杆 融资余额',
         's5': '投机 ARKK', 's6': '新买家 资金流', 's7': '货币(不计分)', 's8': '科技 36月相对'}
WEIGHT = {'s1': .20, 's2': .12, 's3': .10, 's4': .18, 's5': .10, 's6': .15, 's7': 0, 's8': .15}

print('=== 一、月频各特征「真实值起点」审计 (50.0 = 占位/无数据) ===')
print('%-4s %-16s %-12s %-12s %-8s %s' % ('特征', '含义', '首个非50值', '50值最后出现', '50占比', '权重'))
for k in ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8']:
    vals = [(r['date'], r[k]) for r in MON]
    real = [d for d, v in vals if abs(float(v) - 50.0) > 1e-9]
    fifty = [d for d, v in vals if abs(float(v) - 50.0) <= 1e-9]
    first = real[0] if real else '—'
    last50 = fifty[-1] if fifty else '—'
    print('%-4s %-16s %-12s %-12s %-8s %.0f%%' % (
        k, NAMES[k], first, last50, '%.0f%%' % (len(fifty) / len(vals) * 100), WEIGHT[k] * 100))

print()
print('=== 二、原始指标列的可用起点 ===')
import os
for f in sorted(os.listdir('bubble_data')):
    if f.endswith('_month.csv'):
        rs = list(csv.DictReader(open('bubble_data/' + f, encoding='utf-8')))
        k = rs[0].keys()
        dk = [c for c in k if 'date' in c.lower()] or [list(k)[0]]
        print('  %-22s %5d 行   %s → %s' % (f, len(rs), rs[0][dk[0]], rs[-1][dk[0]]))

print()
print('=== 三、分位窗口参数 (analyze.py) ===')
src = open('bubble/analyze.py', encoding='utf-8').read()
for ln in src.splitlines():
    if 'def calc_pct' in ln or 'rolling' in ln or 'min_periods' in ln or 'window' in ln or 'W =' in ln or 'WIN' in ln:
        print('  ' + ln.strip())

print()
print('=== 四、各区间「有效特征数」与总分可比性 ===')
print('%-14s %-12s %-12s %s' % ('区间', '腿数/8', '缺失', '说明'))
def legs(d0, d1):
    seg = [r for r in MON if d0 <= r['date'] <= d1]
    miss = [k for k in ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8']
            if all(abs(float(r[k]) - 50.0) <= 1e-9 for r in seg)]
    return 8 - len(miss), ','.join(miss) if miss else '无'
for d0, d1, nm in [('2000-01-01', '2002-12-31', '2000-2002 互联网泡沫'),
                   ('2003-01-01', '2007-12-31', '2003-2007 复苏'),
                   ('2008-01-01', '2009-12-31', '2008-2009 金融危机'),
                   ('2010-01-01', '2015-12-31', '2010-2015'),
                   ('2016-01-01', '2019-12-31', '2016-2019'),
                   ('2020-01-01', '2026-08-31', '2020 至今')]:
    n, miss = legs(d0, d1)
    print('%-14s %-12s %-12s %s' % (nm, '%d/8' % n, miss, '★完全' if n == 8 else '缺腿'))

print()
print('=== 五、回测脚本实际使用的区间 ===')
for f in ['bt_final.py', 'bt_multi.py', 'bt_grid2.py', 'bt_event.py']:
    s = open(f, encoding='utf-8').read()
    for ln in s.splitlines():
        if 'ALL = ' in ln or 'scores_monthly' in ln:
            print('  %-14s %s' % (f, ln.strip()[:100]))
            break
