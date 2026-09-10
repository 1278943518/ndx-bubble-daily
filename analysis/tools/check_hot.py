# -*- coding: utf-8 -*-
import json
D = json.load(open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bubble_app/data.json', encoding='utf-8'))
M = [r for r in D['month'] if r['d'] >= '2016-05']
hot = [r for r in M if r['total'] >= 75]
print(f'温度>=75 共 {len(hot)} 个月：')
for r in hot:
    print(f"  {r['d']}  temp={r['total']:>5}  ndx={r['ndx']:>9,.0f}")
print()
rs17 = [r for r in M if r['d'][:4] == '2017']
hh17 = [r for r in rs17 if r['total'] >= 75]
rs21 = [r for r in M if '2020' <= r['d'][:4] <= '2021']
hh21 = [r for r in rs21 if r['total'] >= 75]
for lab, hh in [('2017(早期牛市)', hh17), ('2020-21(主升浪)', hh21)]:
    print(f'{lab}: 高温月 {len(hh)} 个，点位 {min(r["ndx"] for r in hh):,.0f} ~ {max(r["ndx"] for r in hh):,.0f}，期末指数 {M[-1]["ndx"]:,.0f}')
    if hh:
        later = M[M.index(hh[-1]) + 24] if M.index(hh[-1]) + 24 < len(M) else M[-1]
        print(f'  末个高温月 {hh[-1]["d"]} 后 24 个月纳指 = {later["ndx"]:,.0f}（+{later["ndx"]/hh[-1]["ndx"]-1:.0%}）')
