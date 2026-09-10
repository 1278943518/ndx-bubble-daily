# -*- coding: utf-8 -*-
"""v17: Faber 10月均线 × 定投者 — 76年长历史检验
问题: 趋势跟随被大样本验证有效(一次性投入口径), 对"每月定投"的人是否同样有效?
设计:
  A. 一次性投入对照: 100%股 vs Faber(跌破转现金, 收复回股票) —— 复现外部证据
  B. 定投口径(核心): 滚动30年窗口
     - 纯股票定投(基准)
     - Faber只管新增资金: 跌破时当月钱进现金池, 收复时池子一次投回
     - Faber管全部: 跌破时存量+新增全转现金, 收复时全回
     - 80/20恒定(参照)
"""
import csv, math

DUR = 7.5
px, dv, y10 = {}, {}, {}
for r in csv.DictReader(open('shiller.csv', encoding='utf-8')):
    try: px[r['Date'][:7]] = float(r['SP500'])
    except: pass
hdr = None
for r in csv.reader(open('shiller2.csv', encoding='utf-8')):
    if hdr is None: hdr = r; continue
    try:
        v = float(r[2])
        if v > 0: dv[r[0][:7]] = v
    except: pass
    try:
        v = float(r[9])
        if v > 0: y10[r[0][:7]] = v
    except: pass
for r in csv.DictReader(open('shiller.csv', encoding='utf-8')):
    try:
        v = float(r['Dividend'])
        if v > 0 and r['Date'][:7] not in dv: dv[r['Date'][:7]] = v
    except: pass
for r in csv.DictReader(open('bubble_data/dgs10.csv', encoding='utf-8')):
    try:
        v = float(r['DGS10'])
        if v > 0: y10.setdefault(r['observation_date'][:7], v)
    except: pass

keys = sorted(px)
P = [px[k] for k in keys]
lastdv = dv[max(dv)]
D = []
for k in keys:
    if k in dv: lastdv = dv[k]
    D.append(lastdv)
last = 4.0
Y = []
for k in keys:
    if k in y10: last = y10[k]
    Y.append(last)

# 月度序列: 股票全收益/债券收益/价格(算均线用)
RS, RB, PP = [], [], []
for i in range(1, len(P)):
    RS.append((P[i] + D[i] / 12.0) / P[i - 1] - 1)
    RB.append(Y[i - 1] / 100.0 / 12.0 - DUR * (Y[i] / 100.0 - Y[i - 1] / 100.0))
    PP.append(P[i])
MK = keys[1:]

# 切到 1950-01 起 (战后样本, 与 v14/v15 一致)
_i0 = MK.index('1950-01')
RS = RS[_i0:]; RB = RB[_i0:]; PP = PP[_i0:]; MK = MK[_i0:]
N = len(RS)

# 10月均线(价格口径, Faber原版)
SMA = [None] * N
for i in range(9, N):
    SMA[i] = sum(PP[i - 9:i + 1]) / 10.0

def pct(lst, q):
    l = sorted(lst); i = (len(l) - 1) * q
    lo = int(i); hi = min(lo + 1, len(l) - 1)
    return l[lo] + (l[hi] - l[lo]) * (i - lo)

print('=' * 86)
print('【A】一次性投入对照: 复现外部证据 (1950-01 ~ 2026-08, 76年, 全收益)')
print('  外部证据(Faber原论文1901-2012): 择时10.2% vs 持有9.3%, MDD -50% vs -83%')
# 一次性 100%股
v = 1.0; pk = 1.0; mdd = 0.0
for i in range(N):
    v *= (1 + RS[i]); pk = max(pk, v); mdd = min(mdd, v / pk - 1)
yrs = N / 12.0
cagr_b = v ** (1 / yrs) - 1
print('  100%%持有:      CAGR %5.2f%%   MDD %6.1f%%' % (cagr_b * 100, mdd * 100))

# Faber 一次性 (信号滞后1个月执行: 月末算信号, 下月生效)
v = 1.0; pk = 1.0; mdd = 0.0
in_stk = True
for i in range(N):
    if i > 0 and SMA[i - 1] is not None:
        in_stk = PP[i - 1] >= SMA[i - 1]
    if in_stk: v *= (1 + RS[i])
    else: v *= (1 + RB[i])
    pk = max(pk, v); mdd = min(mdd, v / pk - 1)
cagr_f = v ** (1 / yrs) - 1
print('  Faber(转10Y债): CAGR %5.2f%%   MDD %6.1f%%   (收益差 %+.2fpp)'
      % (cagr_f * 100, mdd * 100, (cagr_f - cagr_b) * 100))

print()
print('=' * 86)
print('【B】定投口径: 滚动30年窗口 (每月投1份, 起点 1950-01 ~ 1996-08)')
print('   → 这是与你身份匹配的检验')
NW = 360
starts = list(range(0, N - NW + 1))

def dca(mode):
    """mode: pure | faber_new | faber_all | mix80"""
    out = []
    for st in starts:
        s = 0.0; c = 0.0; cum = 0.0; uw = 0.0
        pool = 0.0           # faber_new 的现金池
        in_stk = True        # faber_all 的状态
        hist = []
        for k in range(NW):
            i = st + k
            # 信号取上一个月末 (无前视)
            if mode == 'faber_all' and i > 0 and SMA[i - 1] is not None:
                new_st = PP[i - 1] >= SMA[i - 1]
                if new_st != in_stk:
                    if new_st: s += c; c = 0.0             # 全部回股票
                    else: c += s; s = 0.0                  # 全部转现金
                in_stk = new_st
            below = (i > 0 and SMA[i - 1] is not None and PP[i - 1] < SMA[i - 1])
            # 投入
            cum += 1.0
            if mode == 'pure':
                s += 1.0
            elif mode == 'faber_new':
                if below: pool += 1.0
                else:
                    s += 1.0 + pool; pool = 0.0             # 收复, 池子里的钱一起投回
            elif mode == 'faber_all':
                if in_stk: s += 1.0
                else: c += 1.0
            elif mode == 'mix80':
                s += 0.8; c += 0.2
            # 收益
            s *= (1 + RS[i]); c *= (1 + RB[i])
            pool *= (1 + RB[i]) if mode == 'faber_new' else 1.0
            v = s + c + pool
            hist.append(v)
            if v / cum - 1 < uw: uw = v / cum - 1
        out.append((hist[-1], uw))
    return out

rows = []
for nm, m in [('100% 纯股票', 'pure'),
              ('Faber·只管新增资金', 'faber_new'),
              ('Faber·管全部(原版)', 'faber_all'),
              ('80/20 恒定', 'mix80')]:
    o = dca(m)
    fv = [x[0] for x in o]; uw = [x[1] for x in o]
    rows.append((nm, fv, uw))

base = rows[0]
print('%-24s%11s%11s%11s%13s' % ('策略', '终值中位', 'vs纯股', '最差10%', '平均最深浮亏'))
for nm, fv, uw in rows:
    print('%-24s%11.0f%10.1f%%%11.0f%12.1f%%' % (nm, pct(fv, .5),
          (pct(fv, .5) / pct(base[1], .5) - 1) * 100, pct(fv, .1), sum(uw) / len(uw) * 100))

print()
print('  胜率(该策略 > 同窗口纯股票定投的窗口数):')
for nm, fv, uw in rows[1:]:
    w = sum(1 for i in range(len(fv)) if fv[i] > base[1][i])
    print('    %-22s %d/%d (%.0f%%)' % (nm, w, len(fv), w / len(fv) * 100))

print()
print('  最差10%窗口的终值(保底能力):')
for nm, fv, uw in rows:
    print('    %-22s %.0f' % (nm, pct(fv, .1)))

# 分年代看: 哪些年代 Faber 有效
print()
print('  按起始年代分: Faber·只管新增 vs 纯股票 (终值比)')
for y0 in range(1950, 1997, 5):
    sel = [i for i, st in enumerate(starts) if MK[st][:4] == str(y0)]
    if not sel: continue
    r = [rows[1][1][i] / base[1][i] for i in sel]
    print('    %d年代起: %2d个窗口  中位比 %.3f  (>%s)' % (y0, len(sel), sorted(r)[len(r)//2],
          'Faber赢' if sorted(r)[len(r)//2] > 1 else '纯股赢'))
