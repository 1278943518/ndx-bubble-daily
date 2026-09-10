# -*- coding: utf-8 -*-
"""v18: Faber 存量版敏感性 — 排除"躲债顺风"的运气成分
维度:
  1) 避险资产: 10Y债 / 短债(近似) / 纯现金0%
  2) 转换比例: 跌破时转出 100% / 50% / 30%
  3) 均线窗口: 10 / 12 月
  4) 分年代稳健性
全部用定投滚动30年窗口 + 一次性投入双口径
"""
import csv

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

RS, RB10, PP, Yc = [], [], [], []
for i in range(1, len(P)):
    RS.append((P[i] + D[i] / 12.0) / P[i - 1] - 1)
    RB10.append(Y[i - 1] / 100.0 / 12.0 - DUR * (Y[i] / 100.0 - Y[i - 1] / 100.0))
    PP.append(P[i])
    Yc.append(Y[i])
MK = keys[1:]
_i0 = MK.index('1950-01')
RS = RS[_i0:]; RB10 = RB10[_i0:]; PP = PP[_i0:]; Yc = Yc[_i0:]; MK = MK[_i0:]
N = len(RS)

# 短债近似: 10Y - 2.5pp (历史期限溢价均值); 纯现金 = 0
RBs = [max(0.0, (y - 2.5) / 100.0 / 12.0) for y in Yc]
RB0 = [0.0] * N

def sma(w):
    out = [None] * N
    for i in range(w - 1, N):
        out[i] = sum(PP[i - w + 1:i + 1]) / w
    return out

def pct(lst, q):
    l = sorted(lst); i = (len(l) - 1) * q
    lo = int(i); hi = min(lo + 1, len(l) - 1)
    return l[lo] + (l[hi] - l[lo]) * (i - lo)

NW = 360
starts = list(range(0, N - NW + 1))

def dca_pure():
    out = []
    for st in starts:
        s = 0.0; c = 0.0; cum = 0.0; uw = 0.0
        for k in range(NW):
            i = st + k
            cum += 1.0; s += 1.0
            s *= (1 + RS[i]); c *= (1 + RB10[i])
            v = s + c
            if v / cum - 1 < uw: uw = v / cum - 1
        out.append((v, uw))
    return out

def dca_faber(S, RB, ratio, pure_ret=None):
    """存量版 Faber: 月初用上月末信号定目标权益比例 tgt=1-ratio(跌破时),
    存量与新钱都按 tgt 持仓, 信号滞后1个月, 无前视."""
    out = []
    for st in starts:
        s = 0.0; c = 0.0; cum = 0.0; uw = 0.0
        for k in range(NW):
            i = st + k
            tgt = 1.0
            if i > 0 and S[i - 1] is not None and PP[i - 1] < S[i - 1]:
                tgt = 1.0 - ratio
            v0 = s + c
            s = v0 * tgt; c = v0 * (1 - tgt)      # 存量先切到目标(上月末信号)
            cum += 1.0
            s += tgt; c += (1 - tgt)              # 新钱按同一目标
            s *= (1 + RS[i]); c *= (1 + RB[i])
            v = s + c
            if v / cum - 1 < uw: uw = v / cum - 1
        out.append((v, uw))
    return out

pure = None
print('=' * 90)
print('【一次性投入口径】1950-2026 全收益 (对照: 持有 CAGR 11.70% / MDD -49.0%)')
print('%-28s%9s%11s%10s' % ('配置', 'CAGR', 'MDD', '空仓占比'))
for w in [10, 12]:
    S = sma(w)
    for rname, RB in [('转10Y债', RB10), ('转短债', RBs), ('转现金0%', RB0)]:
        v = 1.0; pk = 1.0; mdd = 0.0; ncash = 0; nn = 0
        in_stk = 1.0
        for i in range(N):
            tgt = 1.0
            if i > 0 and S[i - 1] is not None and PP[i - 1] < S[i - 1]:
                tgt = 0.0
            in_stk = tgt
            nn += 1
            if in_stk < 0.5: ncash += 1
            v *= (1 + RS[i] * in_stk + RB[i] * (1 - in_stk))
            pk = max(pk, v); mdd = min(mdd, v / pk - 1)
        cagr = v ** (12.0 / N) - 1
        print('%-28s%8.2f%%%10.1f%%%9.0f%%' % ('%d月均线·%s' % (w, rname), cagr * 100, mdd * 100, ncash / nn * 100))

print()
print('=' * 90)
print('【定投口径】滚动30年窗口 (对照: 纯股票 终值中位2198 / 最差10% 1702 / 浮亏-9.4%)')
print('%-30s%10s%10s%10s%10s%8s' % ('策略', '终值中位', 'vs纯股', '最差10%', '浮亏', '胜率'))
pure_dca = dca_pure()
pure = [x[0] for x in pure_dca]
PURE_UW = sum(x[1] for x in pure_dca) / len(pure_dca)
res = {}
for w in [10, 12]:
    S = sma(w)
    for ratio in [1.0, 0.5, 0.3]:
        for rname, RB in [('10Y债', RB10), ('短债', RBs), ('现金0%', RB0)]:
            o = dca_faber(S, RB, ratio)
            fv = [x[0] for x in o]; uw = [x[1] for x in o]
            win = sum(1 for i in range(len(fv)) if fv[i] > pure[i]) / len(fv)
            nm = '%d月均线·转%d%%·%s' % (w, ratio * 100, rname)
            res[nm] = fv
            print('%-30s%10.0f%9.1f%%%10.0f%9.1f%%%7.0f%%' % (nm, pct(fv, .5),
                  (pct(fv, .5) / 2198 - 1) * 100, pct(fv, .1), sum(uw) / len(uw) * 100, win * 100))

print()
print('【分年代·转现金】(无债市顺风的干净检验, >1 = Faber赢)')
for rn, RBl in [('转现金0%', RB0), ('转10Y债', RB10)]:
    print('  ' + rn + ':')
    S = sma(10)
    o = dca_faber(S, RBl, 1.0)
    fv = [x[0] for x in o]
    for y0 in range(1950, 1997, 5):
        sel = [i for i, st in enumerate(starts) if MK[st][:4] == str(y0)]
        if not sel: continue
        r = [fv[i] / pure[i] for i in sel]
        print('    %d年代: %2d窗口  中位比 %.3f  赢 %d/%d' % (y0, len(sel), sorted(r)[len(r)//2],
              sum(1 for x in r if x > 1), len(r)))
