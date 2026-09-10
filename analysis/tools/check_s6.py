# -*- coding: utf-8 -*-
"""特征6(s6 新买家) 检查：定义、当前值来源、历史关键时点、预测力（纯python版）"""
import csv, datetime as dt

def load_close(fn):
    out = []
    with open(fn, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            d = dt.date.fromisoformat(row['date']) if 'date' in row else dt.datetime.strptime(row[list(row)[0]], '%Y-%m-%d').date()
            key = 'close' if 'close' in row else list(row)[-1]
            out.append((d, float(row[key])))
    return out

ndx = load_close('bubble_data/ndx_week.csv')
dates = [x[0] for x in ndx]
vals = [x[1] for x in ndx]
n = len(ndx)

def rolling_hi(vals, w=52, minp=26):
    out = []
    for i in range(n):
        lo = max(0, i - w + 1)
        seg = vals[lo:i+1]
        out.append(max(seg) if len(seg) >= minp else None)
    return out

hi52 = rolling_hi(vals)
dd52 = [vals[i]/hi52[i]-1 if hi52[i] else None for i in range(n)]

def calc_pct_series(s, window=520, min_p=52):
    out = []
    for i in range(n):
        v = s[i]
        if v is None: out.append(50.0); continue
        start = max(0, i - window)
        hist = [x for x in s[start:i] if x is not None]
        out.append(50.0 if len(hist) < min_p else sum(1 for x in hist if x < v)/len(hist)*100)
    return out

s6 = calc_pct_series(dd52)

def find(dstr):
    d = dt.date.fromisoformat(dstr)
    # 取 <= d 的最近一周
    i = max(j for j, x in enumerate(dates) if x <= d)
    return i

print('当前（最后一行）:')
i = n - 1
print(f"  {dates[i]}  ndx={vals[i]:,.0f}  hi52={hi52[i]:,.0f}  距高点={dd52[i]*100:+.2f}%  s6={s6[i]:.1f}")
print(f"  （s6=42：过去10年有 42% 的时间纳指比现在更接近52周高点；58% 的时间比现在离高点更远）")

print('\n关键时点 s6（周频）：')
for d in ['2018-01-26','2020-03-27','2021-11-26','2022-10-28','2024-12-20','2025-04-04','2026-03-27','2026-08-31','2026-09-04']:
    try:
        j = find(d)
        print(f"  {dates[j]}  距高点 {dd52[j]*100:+6.2f}%  s6={s6[j]:5.1f}  ndx={vals[j]:>9,.0f}")
    except Exception as e:
        print(f'  {d} not found')

print('\n2021-11 顶部前后 s6：')
for d in ['2021-08-06','2021-09-03','2021-10-01','2021-11-05','2021-11-19','2021-12-03','2022-01-07']:
    j = find(d)
    print(f"  {dates[j]}  距高点 {dd52[j]*100:+6.2f}%  s6={s6[j]:5.1f}  ndx={vals[j]:>9,.0f}")

# s6 四分位 → 未来 52 周收益
print('\ns6 四分位 → 未来 52 周收益：')
pairs = [(s6[j], vals[j+52]/vals[j]-1) for j in range(n-52) if s6[j] is not None]
qs = sorted(pairs, key=lambda x: x[0])
k = len(pairs)//4
for idx, lb in [(0,'Q1(s6 低)'), (k,'Q2'), (2*k,'Q3'), (3*k,'Q4(s6 高)')]:
    seg = qs[idx:idx+k]
    mean = sum(x[1] for x in seg)/len(seg)
    print(f"  {lb:<12} n={len(seg):>3}  未来52周均值 {mean:+.1%}")

import statistics as st
v = [p[0] for p in pairs]; r = [p[1] for p in pairs]
mv, mr = st.mean(v), st.mean(r)
num = sum((a-mv)*(b-mr) for a, b in pairs)
den = (sum((a-mv)**2 for a in v)*sum((b-mr)**2 for b in r))**.5
print(f"\n  s6 vs 未来52周 IC = {num/den:+.3f}")

# dd52 绝对值的分布
absv = [x*100 for x in dd52 if x is not None]
print('\ndd52 绝对值统计：')
print(f"  当前 dd52={dd52[i]*100:.2f}%  中位数 {st.median(absv):.2f}%  25%分位 {sorted(absv)[len(absv)//4]:.2f}%  75%分位 {sorted(absv)[3*len(absv)//4]:.2f}%")
near = sum(1 for x in absv if -3 <= x <= 0)
print(f"  历史上 dd52 在 -3%~0（接近新高区）时间占比: {near/len(absv):.0%}")
