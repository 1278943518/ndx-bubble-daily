# -*- coding: utf-8 -*-
"""v19: CAPE 分档配置的 76 年长历史检验 + 纳指股息影响量级
回答: "回测里考虑 CAPE 了吗? 红利再定投算了吗?"
A. 一次性投入: 100/0 vs 恒定 70/30 vs CAPE 分档(激进/温和, 月检/年检)
B. 定投滚动30年: pure vs 80/20 vs CAPE 分档
C. 纳指股息量级: 0.7%/年 对十年择时回测的影响
"""
import csv, math

DUR = 7.5
px, dv, y10, cape = {}, {}, {}, {}
for r in csv.DictReader(open('shiller.csv', encoding='utf-8')):
    try: px[r['Date'][:7]] = float(r['SP500'])
    except: pass
    try:
        v = float(r['PE10'])
        if v > 0: cape.setdefault(r['Date'][:7], v)
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
    try:
        v = float(r[6])
        if v > 0: cape.setdefault(r[0][:7], v)
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
lastc = cape[max(cape)]
CC = []
for k in keys:
    if k in cape: lastc = cape[k]
    CC.append(lastc)

RS, RB, PP, MK2 = [], [], [], []
for i in range(1, len(P)):
    RS.append((P[i] + D[i] / 12.0) / P[i - 1] - 1)
    RB.append(Y[i - 1] / 100.0 / 12.0 - DUR * (Y[i] / 100.0 - Y[i - 1] / 100.0))
    PP.append(P[i])
    MK2.append(keys[i])
_i0 = MK2.index('1950-01')
RS = RS[_i0:]; RB = RB[_i0:]; MK2 = MK2[_i0:]
# cape 对齐 RS (cape 序列比 price 少1期, 从1950-02起有值)
cape2 = [None]
for i in range(1, len(MK2)):
    cape2.append(CC[MK2.index(MK2[i]) + 1 - 0] if MK2[i] in cape else None)
cape2 = []
for i in range(len(MK2)):
    k = MK2[i]
    # cape 值取自该月(月末已知, 无前视: 用上月值决定本月)
    j = keys.index(k) - 1   # keys[j] 是上月
    cape2.append(CC[j] if j >= 0 else None)
N = len(RS)

def wt_cape(c, mode):
    if c is None: return 0.8
    if mode == 'aggr':
        if c < 17: return 1.0
        if c < 22: return 0.9
        if c < 28: return 0.8
        if c < 35: return 0.6
        return 0.4
    else:  # gentle
        if c < 17: return 1.0
        if c < 22: return 0.95
        if c < 28: return 0.85
        if c < 35: return 0.75
        return 0.65

def pct(lst, q):
    l = sorted(lst); i = (len(l) - 1) * q
    lo = int(i); hi = min(lo + 1, len(l) - 1)
    return l[lo] + (l[hi] - l[lo]) * (i - lo)

def st_lumpsum(wfn, freq):
    """wfn(t_idx)->weight; freq: 'm' 月检 / 'y' 年检(1月)"""
    s = 0.0; c = 1.0
    w = wfn(0)
    s = w; c = 1 - w
    pk = 1.0; mdd = 0.0; wtot = 0.0
    for i in range(N):
        w = wfn(i)
        if freq == 'm' and i > 0:
            v0 = s + c; s = v0 * w; c = v0 * (1 - w)
        elif freq == 'y' and MK2[i][5:7] == '01':
            v0 = s + c; s = v0 * w; c = v0 * (1 - w)
        s *= (1 + RS[i]); c *= (1 + RB[i])
        v = s + c
        wtot += w
        pk = max(pk, v); mdd = min(mdd, v / pk - 1)
    yrs = N / 12.0
    cagr = v ** (1 / yrs) - 1
    return dict(cagr=cagr, mdd=mdd, avgw=wtot / N)

print('=' * 92)
print('【A】一次性投入 1950-2026 (76年, 全收益; 对照: 100/0 = 11.70% / -49.0%)')
print('%-30s%9s%9s%9s%9s' % ('策略', 'CAGR', 'MDD', '平均仓位', 'Sharpe'))
b = st_lumpsum(lambda i: 1.0, 'm')
print('%-30s%8.2f%%%8.1f%%%8.0f%%%9.2f' % ('100/0 纯股票', b['cagr'] * 100, b['mdd'] * 100, 100, (b['cagr'] - 0.02) / 0.13))
for nm, w, fr in [('恒定 80/20', 0.8, 'm'), ('恒定 70/30', 0.7, 'm'), ('恒定 60/40', 0.6, 'm')]:
    v = st_lumpsum(lambda i, ww=w: ww, fr)
    print('%-30s%8.2f%%%8.1f%%%8.0f%%%9.2f' % (nm, v['cagr'] * 100, v['mdd'] * 100, v['avgw'] * 100, (v['cagr'] - 0.02) / 0.12))
for mode in ['aggr', 'gentle']:
    for fr, frn in [('m', '月检'), ('y', '年检')]:
        v = st_lumpsum(lambda i, m=mode: wt_cape(cape2[i], m), fr)
        # 与平均仓位相近的恒定配置对比
        print('%-30s%8.2f%%%8.1f%%%8.0f%%%9.2f   ← CAPE %s %s' % (
            'CAPE分档(%s)' % ('激进' if mode == 'aggr' else '温和'), v['cagr'] * 100, v['mdd'] * 100,
            v['avgw'] * 100, (v['cagr'] - 0.02) / 0.12, '激进' if mode == 'aggr' else '温和', frn))

print()
print('=' * 92)
print('【B】定投滚动30年窗口 (对照: 纯股票 中位2198 / 最差10% 1702 / 浮亏-9.4%)')
NW = 360
starts = list(range(0, N - NW + 1))

def dca_cape(mode, freq):
    out = []
    for st in starts:
        s = 0.0; c = 0.0; cum = 0.0; uw = 0.0
        for k in range(NW):
            i = st + k
            w = wt_cape(cape2[i], mode) if freq == 'm' else None
            if freq == 'y':
                w = wt_cape(cape2[i], mode) if MK2[i][5:7] == '01' else None
                if w is None: w = last_w
            last_w = w
            v0 = s + c
            if freq == 'm':
                s = v0 * w; c = v0 * (1 - w)
            cum += 1.0
            s += w; c += (1 - w)
            s *= (1 + RS[i]); c *= (1 + RB[i])
            v = s + c
            if v / cum - 1 < uw: uw = v / cum - 1
        out.append((v, uw))
    return out

def dca_const(w):
    out = []
    for st in starts:
        s = 0.0; c = 0.0; cum = 0.0; uw = 0.0
        for k in range(NW):
            i = st + k
            cum += 1.0; s += w; c += (1 - w)
            s *= (1 + RS[i]); c *= (1 + RB[i])
            v = s + c
            if v / cum - 1 < uw: uw = v / cum - 1
        out.append((v, uw))
    return out

pure = dca_const(1.0)
pf = [x[0] for x in pure]; puw = sum(x[1] for x in pure) / len(pure)
print('%-30s%10s%10s%10s%11s%8s' % ('策略', '终值中位', 'vs纯股', '最差10%', '浮亏', '胜率'))
print('%-30s%10.0f%10s%10.0f%10.1f%%%8s' % ('100% 纯股票', pct(pf, .5), '—', pct(pf, .1), puw * 100, '—'))
for nm, w in [('恒定 80/20', 0.8), ('恒定 70/30', 0.7)]:
    o = dca_const(w)
    fv = [x[0] for x in o]
    print('%-30s%10.0f%9.1f%%%10.0f%10.1f%%%7.0f%%' % (nm, pct(fv, .5), (pct(fv, .5) / 2198 - 1) * 100,
          pct(fv, .1), sum(x[1] for x in o) / len(o) * 100, sum(1 for i in range(len(fv)) if fv[i] > pf[i]) / len(fv) * 100))
for mode in ['aggr', 'gentle']:
    for fr, frn in [('m', '月检'), ('y', '年检')]:
        o = dca_cape(mode, fr)
        fv = [x[0] for x in o]
        print('%-30s%10.0f%9.1f%%%10.0f%10.1f%%%7.0f%%' % ('CAPE分档(%s) %s' % ('激进' if mode == 'aggr' else '温和', frn),
              pct(fv, .5), (pct(fv, .5) / 2198 - 1) * 100, pct(fv, .1),
              sum(x[1] for x in o) / len(o) * 100, sum(1 for i in range(len(fv)) if fv[i] > pf[i]) / len(fv) * 100))

print()
print('CAPE 环境统计 (1950-2026, 月频):')
import collections
dist = collections.Counter()
for i in range(N):
    c = cape2[i]
    if c is None: continue
    if c < 17: dist['<17'] += 1
    elif c < 22: dist['17-22'] += 1
    elif c < 28: dist['22-28'] += 1
    elif c < 35: dist['28-35'] += 1
    else: dist['>=35'] += 1
tot = sum(dist.values())
for k in ['<17', '17-22', '22-28', '28-35', '>=35']:
    print('  CAPE %-5s: %4.0f%% 的时间' % (k, dist[k] / tot * 100))
