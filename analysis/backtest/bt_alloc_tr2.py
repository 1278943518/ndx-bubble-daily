# -*- coding: utf-8 -*-
"""v15: 定投"最后一公里"回撤 + 集中度风险
E: 定投终值 vs 临近终点5年的回撤(真正该怕的回撤)
F: 集中度: 纳指 vs 标普 vs 组合 (2000-2026, 含2000-02互联网泡沫纳指-78%)
"""
import csv, math

DUR = 7.5
# ---------- 载入全收益序列(复用v14逻辑) ----------
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
last = 4.0; Y = []
for k in keys:
    if k in y10: last = y10[k]
    Y.append(last)

rs_all, rb_all = [], []
for i in range(1, len(P)):
    rs_all.append((P[i] + D[i] / 12.0) / P[i - 1] - 1)
    rb_all.append(Y[i - 1] / 100.0 / 12.0 - DUR * (Y[i] / 100.0 - Y[i - 1] / 100.0))
MK = keys[1:]

def seg(lo, hi='2026-08'):
    idx = [i for i, k in enumerate(MK) if lo <= k <= hi]
    return [rs_all[i] for i in idx], [rb_all[i] for i in idx], [MK[i] for i in idx]

def pct(lst, q):
    l = sorted(lst); i = (len(l) - 1) * q
    lo = int(i); hi = min(lo + 1, len(l) - 1)
    return l[lo] + (l[hi] - l[lo]) * (i - lo)

# ================= E. 定投 最后一公里 =================
print('=' * 80)
print('【E】定投30年: 终值 vs "最后一公里"回撤 (最后5年的最大回撤)')
print('   → 定投者真正该怕的不是中途浮亏, 而是接近目标时被打回')
RS, RB, K = seg('1950-01')
NW = 360
starts = list(range(0, len(RS) - NW + 1))

def dca_full(w, glide=None, tail=60):
    out = []
    for st in starts:
        s = 0.0; b = 0.0; cum = 0.0; uw = 0.0
        hist = []
        for i in range(st, st + NW):
            c = 1.0; cum += c
            wt = glide(i - st) if glide else w
            s += c                      # 新增资金先并入
            s *= (1 + RS[i]); b *= (1 + RB[i])
            v = s + b
            s = v * wt; b = v * (1 - wt)   # 整个组合再平衡到目标权重
            hist.append(v)
            if v / cum - 1 < uw: uw = v / cum - 1
        # 最后 tail 个月的回撤
        tailv = hist[-tail:]
        pk = tailv[0]; tm = 0.0
        for v in tailv:
            pk = max(pk, v); tm = min(tm, v / pk - 1)
        out.append((hist[-1], uw, tm))
    return out

def gp(whi, wlo, hold, k):
    def g(i):
        if i < hold: return whi
        t = min(1.0, (i - hold) / max(1, k - hold))
        return whi + (wlo - whi) * t
    return g

print('%-24s%11s%11s%13s%15s' % ('策略', '终值中位', 'vs纯股', '最深浮亏', '最后5年回撤'))
base = None
for nm, w, gl in [('100/0 纯股票', 1.0, None),
                  ('80/20 恒定', 0.8, None),
                  ('70/30 恒定', 0.7, None),
                  ('下滑 100→50 (末10年)', None, gp(1.0, 0.5, 240, NW)),
                  ('下滑 100→30 (末10年)', None, gp(1.0, 0.3, 240, NW)),
                  ('下滑 100→30 (末15年)', None, gp(1.0, 0.3, 180, NW))]:
    o = dca_full(w, gl)
    fv = [x[0] for x in o]; uwv = [x[1] for x in o]; tm = [x[2] for x in o]
    if base is None: base = (fv, tm)
    print('%-24s%11.0f%10.1f%%%12.1f%%%14.1f%%' % (
        nm, pct(fv, .5), (pct(fv, .5) / pct(base[0], .5) - 1) * 100,
        sum(uwv) / len(uwv) * 100, sum(tm) / len(tm) * 100))

print()
print('  最坏情况对比 (终值最差的10个窗口 + 最后一公里回撤最深的10个窗口):')
for nm, w, gl in [('100/0 纯股票', 1.0, None),
                  ('80/20 恒定', 0.8, None),
                  ('下滑 100→30 (末10年)', None, gp(1.0, 0.3, 240, NW))]:
    o = dca_full(w, gl)
    fv = sorted(x[0] for x in o); tm = sorted(x[2] for x in o)
    print('    %-22s 最差终值均值 %6.0f   最差最后一公里回撤均值 %6.1f%%' % (
        nm, sum(fv[:10]) / 10, sum(tm[:10]) / 10 * 100))

# ================= F. 集中度风险 =================
print()
print('=' * 80)
print('【F】集中度: 纳指 vs 标普 (2000-01 起, 含互联网泡沫)')
ndx = {}
for r in csv.DictReader(open('bubble_data/ndx_month.csv', encoding='utf-8')):
    try: ndx[r['date'][:7]] = float(r['close'])
    except: pass
ks = sorted(k for k in ndx if k >= '2000-01')
pn = [ndx[k] for k in ks]
rn = [pn[i] / pn[i - 1] - 1 for i in range(1, len(pn))]
KN = ks[1:]
# 对齐标普全收益
mx = [k for k in KN if k in set(MK)]
keep = [i for i, k in enumerate(KN) if k in set(MK)]
rn = [rn[i] for i in keep]
idx = [MK.index(k) for k in mx]
rsx = [rs_all[i] for i in idx]

def st(rets, lab):
    v = 1.0; pk = 1.0; mdd = 0.0
    for r in rets:
        v *= (1 + r); pk = max(pk, v); mdd = min(mdd, v / pk - 1)
    n = len(rets)
    mu = sum(rets) / n
    sd = (sum((x - mu) ** 2 for x in rets) / (n - 1)) ** 0.5 * (12 ** 0.5)
    cagr = v ** (12.0 / n) - 1
    print('  %-18s CAGR %6.2f%%   波动 %5.1f%%   最大回撤 %6.1f%%   Calmar %.2f' % (
        lab, cagr * 100, sd * 100, mdd * 100, cagr / abs(mdd)))
    return dict(cagr=cagr, sd=sd, mdd=mdd)

a = st(rn, '纳指100 (价格)')
b = st(rsx, '标普500 (全收益)')
# 50/50 年度再平衡
mix = []
s = 0.5; c = 0.5
for i in range(len(rn)):
    s *= (1 + rn[i]); c *= (1 + rsx[i]); v = s + c
    mix.append(v / (s + c) if False else 0)
s = 0.5; c = 0.5; mr = []
for i in range(len(rn)):
    pv = s + c
    s *= (1 + rn[i]); c *= (1 + rsx[i]); v = s + c
    mr.append(v / pv - 1)
    if (i + 1) % 12 == 0: s = v * 0.5; c = v * 0.5
st(mr, '50/50 纳指+标普')

print()
print('  定投对比 (2000-01 起每月投1份, 假设纳指股息率0.7%/年):')
rn_tr = [r + 0.007 / 12 for r in rn]
for nm, w in [('100% 纳指', 1.0), ('70%纳指+30%标普', 0.7), ('50/50', 0.5), ('100% 标普', 0.0)]:
    s = 0.0; c = 0.0; cum = 0.0; uw = 0.0; pk = 0.0; mdd = 0.0
    for i in range(len(rn_tr)):
        cum += 1.0; s += w; c += (1 - w)
        s *= (1 + rn_tr[i]); c *= (1 + rsx[i]); v = s + c
        if v / cum - 1 < uw: uw = v / cum - 1
        if (i + 1) % 12 == 0: s = v * w; c = v * (1 - w)
    print('    %-18s 终值 %6.0f (投入%4.0f)  倍数 %.2fx  最深浮亏 %6.1f%%' % (
        nm, v, cum, v / cum, uw * 100))

i0 = KN.index('2000-03') - 1
i1 = KN.index('2002-10')
cumn = [1.0]; cums = [1.0]
for i in range(i0, i1 + 1):
    cumn.append(cumn[-1] * (1 + rn[i]))
    cums.append(cums[-1] * (1 + rsx[i]))
print()
print('  2000-03 高点 → 2002-10 低点:')
print('    纳指100  %.1f%%   (回本需上涨 %.0f%%)' % (
    (min(cumn) / 1 - 1) * 100, (1 / min(cumn) - 1) * 100))
print('    标普500  %.1f%%   (回本需上涨 %.0f%%)' % (
    (min(cums) / 1 - 1) * 100, (1 / min(cums) - 1) * 100))
