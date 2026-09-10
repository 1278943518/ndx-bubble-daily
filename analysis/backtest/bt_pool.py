# -*- coding: utf-8 -*-
"""剖析: 温和节流的资金池为什么打不满 —— 池子余额轨迹 + 冷月打满率"""
import csv
ROWS=[r for r in csv.DictReader(open('bubble_out/scores_monthly.csv',encoding='utf-8')) if r['date']<'2026-09-01' and r['date']>='2000-01-01']
CASH_M=0.02/12

def coef(t):
    if t>=85: return 0.2
    if t>=75: return 0.7
    if t>=65: return 0.85
    if t>=55: return 1.0
    if t>=40: return 1.3
    return 1.8

pool=0.0; log=[]
for r in ROWS:
    t=float(r['total']); ndx=float(r['ndx'])
    pool+=1000
    c=coef(t)
    target=1000*c
    buy=min(pool,target)
    pool-=buy; pool*=(1+CASH_M)
    log.append((r['date'],t,c,target,buy,pool))

# 1) 池子余额统计
pools=[x[5] for x in log]
print(f"池子余额: 均值 {sum(pools)/len(pools):,.0f} | 中位 {sorted(pools)[len(pools)//2]:,.0f} | 0余额月占比 {sum(1 for p in pools if p<1)/len(pools):.0%}")
print(f"热月(>55)末平均池子: {sum(x[5] for x in log if x[1]>55)/sum(1 for x in log if x[1]>55):,.0f}")
print(f"冷月(<=55)末平均池子: {sum(x[5] for x in log if x[1]<=55)/sum(1 for x in log if x[1]<=55):,.0f}")

# 2) 冷月打满率: 目标1300(40-55)/1800(<=40) 实际买到多少
for lo,hi,lb,tgt in [(40,55,'40-55 (1.3×目标1300)',1300),(0,40,'<=40 (1.8×目标1800)',1800)]:
    rows=[x for x in log if lo<=x[1]<hi]
    if not rows: continue
    full=sum(1 for x in rows if x[4]>=tgt-1)
    partial=sum(1 for x in rows if 999<x[4]<tgt-1)
    none=sum(1 for x in rows if x[4]<=999)
    avg=sum(x[4] for x in rows)/len(rows)
    print(f"\n{lb}: {len(rows)}个月 | 打满 {full} ({full/len(rows):.0%}) | 部分 {partial} ({partial/len(rows):.0%}) | 只投1000 {none} ({none/len(rows):.0%}) | 平均实投 {avg:.0f}")

# 3) 连续冷月段: 长冷期是主因
print("\n冷月连续段(>=3个月连续 <=55):")
segs=[]; cur=[]
for x in log:
    if x[1]<=55: cur.append(x)
    else:
        if len(cur)>=3: segs.append(cur)
        cur=[]
if len(cur)>=3: segs.append(cur)
for s in segs:
    first=s[0]; 
    # 看这段里池子在前3个月的变化
    print(f"  {s[0][0]}~{s[-1][0]} ({len(s)}个月连续)  首月池前={1000-(s[0][4]- (1000-s[0][2]*0 if False else 0)) if False else ''}", end="")
    p0=[x for x in log if x[0]==s[0][0]][0]
    print(f" 首月买入 {p0[4]:.0f}/目标{p0[3]:.0f} | 次月买入 {s[1][4]:.0f}/{s[1][3]:.0f} | 第3月 {s[2][4]:.0f}/{s[2][3]:.0f} | 月末池 {s[-1][5]:,.0f}")

# 4) 池子轨迹(关键年份)
print("\n2022 熊市池子演变(每月):")
for x in log:
    if '2021-06'<=x[0]<='2023-03':
        mark=' <==' if x[1]<=40 else ''
        print(f"  {x[0]} 温度{x[1]:>5.1f} 目标{x[3]:>5.0f} 实买{x[4]:>5.0f} 池末{x[5]:>7,.0f}{mark}")
