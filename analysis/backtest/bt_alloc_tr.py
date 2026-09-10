# -*- coding: utf-8 -*-
"""v14: 全收益口径下的长周期资产配置测试 (Shiller 1871-2026)
回答核心问题: 长期组合能不能"不减少收益、只减少回撤"?
资产: 标普500全收益(价+股息) / 10年期国债(久期近似) 
模式: A 一次性投入  B 定投滚动30年窗口  C 下滑轨道
"""
import csv, math, datetime as dt

DUR = 7.5          # 10Y国债修正久期近似
SRC = {}

# ---- 1) 合并数据 ----
def f(fn):
    return list(csv.DictReader(open(fn, encoding='utf-8')))

px = {}
for r in f('shiller.csv'):
    try: px[r['Date'][:7]] = float(r['SP500'])
    except: pass

# 股息(名义): shiller2 第3列是名义股息, 第4列是实际股息(DictReader会覆盖, 故按位置读)
dv = {}
hdr = None
for r in csv.reader(open('shiller2.csv', encoding='utf-8')):
    if hdr is None: hdr = r; continue
    try:
        v = float(r[2])
        if v > 0: dv[r[0][:7]] = v
    except: pass
# 兜底: shiller.csv 名义股息(1871-2023-06)
for r in f('shiller.csv'):
    try:
        v = float(r['Dividend'])
        if v > 0 and r['Date'][:7] not in dv: dv[r['Date'][:7]] = v
    except: pass
last_dv_k = max(dv) if dv else None

y10 = {}
for r in csv.reader(open('shiller2.csv', encoding='utf-8')):
    if r[0] == 'date_string': continue
    try:
        v = float(r[9])
        if v > 0: y10[r[0][:7]] = v
    except: pass
# FRED DGS10 补最新
for r in f('bubble_data/dgs10.csv'):
    try:
        v = float(r['DGS10'])
        if v > 0: y10[r['observation_date'][:7]] = y10.get(r['observation_date'][:7]) or v
    except: pass

keys = sorted(px)
P = [px[k] for k in keys]
# 股息外推
dvv = []
lastdv = dv.get(last_dv_k, 0)
for k in keys:
    if k in dv:
        lastdv = dv[k]; dvv.append(lastdv)
    else:
        dvv.append(lastdv)          # 用最后一期股息外推(2025-09之后)
# 利率: 前向填充
yy = []
last = None
for k in keys:
    if k in y10: last = y10[k]
    if last is None: last = 4.0
    yy.append(last)

def cut(lo, hi='2026-08'):
    idx = [i for i, k in enumerate(keys) if lo <= k <= hi]
    return idx

def build(lo, hi='2026-08'):
    idx = cut(lo, hi)
    K = [keys[i] for i in idx]
    p = [P[i] for i in idx]; d = [dvv[i] for i in idx]; y = [yy[i] for i in idx]
    rs = [None]; rb = [None]
    for i in range(1, len(p)):
        rs.append((p[i] + d[i] / 12.0) / p[i - 1] - 1)
        rb.append(y[i - 1] / 100.0 / 12.0 - DUR * (y[i] / 100.0 - y[i - 1] / 100.0))
    return K, rs[1:], rb[1:], y

def stats(rets):
    n = len(rets)
    v = 1.0; peak = 1.0; mdd = 0.0
    for r in rets:
        v *= (1 + r); peak = max(peak, v); mdd = min(mdd, v / peak - 1)
    mu = sum(rets) / n
    sd = (sum((x - mu) ** 2 for x in rets) / (n - 1)) ** 0.5 * (12 ** 0.5)
    yrs = n / 12.0
    cagr = v ** (1 / yrs) - 1
    return dict(final=v, cagr=cagr, sd=sd, mdd=mdd, sharpe=(cagr - 0.02) / sd,
                calmar=cagr / abs(mdd) if mdd else 0)

# ================= A. 资产基础统计 =================
for lo, nm in [('1950-01', '战后 1950-2026'), ('1926-01', '现代 1926-2026'), ('1871-01', '全样本 1871-2026')]:
    K, rs, rb, y = build(lo)
    ss, sb = stats(rs), stats(rb)
    cov = sum((rs[i] - sum(rs) / len(rs)) * (rb[i] - sum(rb) / len(rb)) for i in range(len(rs)))
    corr = cov / (len(rs) - 1) / ((sum((x - sum(rs) / len(rs)) ** 2 for x in rs) / (len(rs) - 1) * sum((x - sum(rb) / len(rb)) ** 2 for x in rb) / (len(rb) - 1)) ** 0.5)
    print('【%s】 %d年' % (nm, len(rs) // 12))
    print('  股票全收益 CAGR %.2f%%  波动 %.1f%%  最大回撤 %.1f%%' % (ss['cagr'] * 100, ss['sd'] * 100, ss['mdd'] * 100))
    print('  10Y国债    CAGR %.2f%%  波动 %.1f%%  最大回撤 %.1f%%' % (sb['cagr'] * 100, sb['sd'] * 100, sb['mdd'] * 100))
    print('  股债月收益相关性 %.2f' % corr)
    # 危机期: 股票最差的月份里债券表现
    pairs = sorted(zip(rs, rb))[:max(3, len(rs) // 20)]
    print('  股票最差的%d个月: 股均 %.1f%%  债均 %.1f%%' % (len(pairs), sum(a for a, _ in pairs) / len(pairs) * 100, sum(b for _, b in pairs) / len(pairs) * 100))
    print()

# ================= B. 固定权重 一次性投入 =================
print('=' * 78)
print('【B】一次性投入 + 年度再平衡 (1950-01 ~ 2026-08, 全收益口径)')
print('%-10s%9s%9s%10s%8s%8s%14s' % ('股/债', 'CAGR', '波动', '最大回撤', 'Sharpe', 'Calmar', '换回撤/pp收益'))
K, rs, rb, y = build('1950-01')
N = len(rs)

def lump(w, rebal=12, contrib=False, glide=None):
    s = w; b = 1.0 - w; v = 1.0
    peak = 1.0; mdd = 0.0; uw = 0.0
    mr = []
    cum = 0.0
    for i in range(N):
        if contrib:
            c = 1.0 / 12; cum += c
            s += c * w; b += c * (1 - w)
            v = s + b
            if v / cum - 1 < uw: uw = v / cum - 1
        s *= (1 + rs[i]); b *= (1 + rb[i])
        v = s + b
        if glide is not None:
            w_t = glide(i)
            s = v * w_t; b = v * (1 - w_t)
        elif rebal and (i + 1) % rebal == 0:
            s = v * w; b = v * (1 - w)
        if not contrib:
            peak = max(peak, v); mdd = min(mdd, v / peak - 1)
            mr.append(v)
    if contrib:
        return dict(final=v, cum=cum, uw=uw)
    yrs = N / 12.0
    cagr = (v) ** (1 / yrs) - 1
    mrr = []
    s2 = w; b2 = 1 - w
    for i in range(N):
        pv = s2 + b2
        s2 *= (1 + rs[i]); b2 *= (1 + rb[i]); vv = s2 + b2
        mrr.append(vv / pv - 1)
        if glide is not None:
            wt = glide(i); s2 = vv * wt; b2 = vv * (1 - wt)
        elif rebal and (i + 1) % rebal == 0:
            s2 = vv * w; b2 = vv * (1 - w)
    mu = sum(mrr) / len(mrr)
    sd = (sum((x - mu) ** 2 for x in mrr) / (len(mrr) - 1)) ** 0.5 * (12 ** 0.5)
    return dict(final=v, cagr=cagr, sd=sd, mdd=mdd, sharpe=(cagr - 0.02) / sd,
                calmar=cagr / abs(mdd) if mdd else 0)

base = None
rows = []
for w in [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]:
    r = lump(w)
    if base is None: base = r
    dc = (r['cagr'] - base['cagr']) * 100
    dm = (r['mdd'] - base['mdd']) * 100
    ratio = dm / abs(dc) if abs(dc) > 1e-9 else 0
    rows.append((w, r, dc, dm, ratio))
    print('%-10s%8.2f%%%8.1f%%%9.1f%%%8.2f%8.2f%13s' % (
        '%d/%d' % (w * 100, (1 - w) * 100), r['cagr'] * 100, r['sd'] * 100, r['mdd'] * 100,
        r['sharpe'], r['calmar'], ('%.1f' % ratio) if dc else '—'))

print()
print('  关键判据: 是否存在 CAGR >= 100/0 且回撤更小的配置?')
hit = [x for x in rows if x[2] >= -0.001 and x[3] > 0.001]
print('  →', '有: ' + ', '.join('%d/%d' % (x[0] * 100, (1 - x[0]) * 100) for x in hit) if hit else '没有。所有降低回撤的配置都付出收益代价。')

# ================= C. 定投滚动30年窗口 =================
print()
print('=' * 78)
print('【C】定投模式: 每月投入1份, 滚动30年窗口 (起点 1950-01 ~ 1996-08)')
Kfull, rsf, rbf, yf = build('1950-01')
NW = 360
starts = range(0, len(rsf) - NW + 1)

def dca(w, glide=None):
    out = []
    for st in starts:
        s = 0.0; b = 0.0; cum = 0.0; uw = 0.0
        for i in range(st, st + NW):
            c = 1.0; cum += c
            wt = glide(i - st) if glide else w
            s += c * wt; b += c * (1 - wt)
            v0 = s + b
            s *= (1 + rsf[i]); b *= (1 + rbf[i])
            v = s + b
            if v / cum - 1 < uw: uw = v / cum - 1
        out.append((v, uw))
    return out

def gp_factory(k, w_hi=1.0, w_lo=0.5, hold=240):
    def g(i):
        if i < hold: return w_hi
        t = min(1.0, (i - hold) / max(1, k - hold))
        return w_hi + (w_lo - w_hi) * t
    return g

def pct(lst, q):
    l = sorted(lst); i = (len(l) - 1) * q
    lo = int(i); hi = min(lo + 1, len(l) - 1)
    return l[lo] + (l[hi] - l[lo]) * (i - lo)

print('%-22s%12s%12s%12s%12s' % ('策略', '终值中位', '最差10%', '最好10%', '平均最深浮亏'))
res = {}
for nm, w, gl in [('100/0 纯股票', 1.0, None),
                  ('90/10', 0.9, None),
                  ('80/20', 0.8, None),
                  ('70/30', 0.7, None),
                  ('60/40', 0.6, None),
                  ('下滑轨道 100→50', None, gp_factory(NW))]:
    o = dca(w, gl)
    fv = [x[0] for x in o]; uw = [x[1] for x in o]
    res[nm] = (fv, uw)
    print('%-22s%12.0f%12.0f%12.0f%12.1f%%' % (nm, pct(fv, .5), pct(fv, .1), pct(fv, .9), sum(uw) / len(uw) * 100))

print()
print('  相对纯股票 100/0 的终值对比:')
b = res['100/0 纯股票'][0]
for nm in res:
    fv = res[nm][0]
    win = sum(1 for i in range(len(fv)) if fv[i] > b[i]) / len(fv)
    print('    %-22s 中位差 %+6.1f%%   最差10%%差 %+6.1f%%   胜率 %.0f%%' % (
        nm, (pct(fv, .5) / pct(b, .5) - 1) * 100, (pct(fv, .1) / pct(b, .1) - 1) * 100, win * 100))

# ================= D. 波动拖累归因 =================
print()
print('=' * 78)
print('【D】为什么配置能"少亏一点收益": 波动拖累的还账')
b1 = lump(1.0); b7 = lump(0.7)
print('  100/0 波动 %.1f%% → 波动拖累 %.2fpp' % (b1['sd'] * 100, b1['sd'] ** 2 / 2 * 100))
print('  70/30 波动 %.1f%% → 波动拖累 %.2fpp' % (b7['sd'] * 100, b7['sd'] ** 2 / 2 * 100))
print('  → 降低波动把 %.2fpp 的拖累"还"了回来, 抵消了部分让渡的收益' % ((b1['sd'] ** 2 - b7['sd'] ** 2) / 2 * 100))
print('  → 70/30 名义收益让渡 %.2fpp, 回撤改善 %.1fpp' % ((b7['cagr'] - b1['cagr']) * 100, (b7['mdd'] - b1['mdd']) * 100))
