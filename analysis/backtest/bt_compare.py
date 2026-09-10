# -*- coding: utf-8 -*-
"""v23: 旧版(标普50/纳指35/防守15) vs 新版(纳指30/标普30/红利低波25/现金流15)
防守腿拆成 美债 / 黄金 两个极端 + 各半, 用于框定旧版真实表现区间
口径: 人民币, 分红再投, 2014-01~2026-08
"""
import json, csv, math, datetime

D = json.load(open("alloc_data.json", encoding="utf-8"))
FX = D["fx"]
def fx_at(k):
    if k in FX: return FX[k]
    c = [x for x in FX if x <= k]
    return FX[max(c)] if c else 6.8

# ---------- 黄金: 用 equityReturn 累乘(复权序列) ----------
import re
s = open("g5.js", encoding="utf-8", errors="ignore").read()
arr = json.loads(re.search(r"Data_netWorthTrend\s*=\s*(\[.*?\]);", s, re.S).group(1))
gold_m, cur = {}, None
for it in arr:
    t = datetime.datetime.fromtimestamp(it["x"] / 1000, datetime.UTC).strftime("%Y-%m")
    r = it.get("equityReturn") or 0.0
    cur = 1.0 if cur is None else cur * (1 + r / 100.0)
    gold_m[t] = cur
gk = sorted(gold_m)
print("黄金(518880复权): %s~%s  倍数 %.3f  CAGR %.2f%%" % (
    gk[0], gk[-1], gold_m[gk[-1]], (gold_m[gk[-1]] ** (12.0 / (len(gk) - 1)) - 1) * 100))

# ---------- 美债: 10Y 久期近似(美元) -> 人民币 ----------
DUR = 7.5
px, dv, y10 = {}, {}, {}
for r in csv.DictReader(open("shiller.csv", encoding="utf-8")):
    try: px[r["Date"][:7]] = float(r["SP500"])
    except: pass
hdr = None
for r in csv.reader(open("shiller2.csv", encoding="utf-8")):
    if hdr is None: hdr = r; continue
    try:
        v = float(r[9])
        if v > 0: y10[r[0][:7]] = v
    except: pass
for r in csv.DictReader(open("bubble_data/dgs10.csv", encoding="utf-8")):
    try:
        v = float(r["DGS10"])
        if v > 0: y10.setdefault(r["observation_date"][:7], v)
    except: pass
KS = sorted(px)
last = 4.0
Ym = []
for k in KS:
    if k in y10: last = y10[k]
    Ym.append(last)
# 债券月收益(美元)
RB_usd = {}
for i in range(1, len(KS)):
    RB_usd[KS[i]] = Ym[i - 1] / 100.0 / 12.0 - DUR * (Ym[i] / 100.0 - Ym[i - 1] / 100.0)
# 债券指数(美元) -> 人民币
bond_cny, v = {}, 1.0
for i in range(1, len(KS)):
    v *= (1 + RB_usd[KS[i]]) * (fx_at(KS[i]) / fx_at(KS[i - 1]))
    bond_cny[KS[i]] = v

# ---------- 构建对比序列 ----------
LO, HI = "2014-01", "2026-08"
keys = sorted(k for k in D["ndx_tr"] if LO <= k <= HI)
S = {}
for nm in ["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"]:
    v = [D[nm].get(k) for k in keys]
    if nm in ("ndx_tr", "spx_tr"):
        v = [(x * fx_at(k) if x else None) for k, x in zip(keys, v)]
    S[nm] = v
S["gold"] = [gold_m.get(k) for k in keys]
S["bond"] = [bond_cny.get(k) for k in keys]
R = {}
for k in S:
    R[k] = [None]
    for i in range(1, len(keys)):
        a, b = S[k][i - 1], S[k][i]
        R[k].append(b / a - 1 if (a and b) else None)
IDX = [i for i in range(len(keys)) if all(R[k][i] is not None for k in R)]
print("样本: %s ~ %s (%d 月)" % (keys[IDX[0]], keys[IDX[-1]], len(IDX)))

def stats(rv):
    v = 1.0; pk = 1.0; mdd = 0.0
    for r in rv:
        v *= (1 + r); pk = max(pk, v); mdd = min(mdd, v / pk - 1)
    n = len(rv)
    mu = sum(rv) / n
    sd = (sum((x - mu) ** 2 for x in rv) / (n - 1)) ** 0.5 * (12 ** 0.5)
    cagr = v ** (12.0 / n) - 1
    return dict(cagr=cagr, sd=sd, mdd=mdd, calmar=cagr / abs(mdd) if mdd else 0,
                sharpe=(cagr - 0.02) / sd if sd else 0)

def port(w, rebal=12):
    s = dict(w); out = []
    for j, i in enumerate(IDX):
        v0 = sum(s.values())
        for k in s: s[k] *= (1 + R[k][i])
        v = sum(s.values())
        out.append(v / v0 - 1)
        if (len(out)) % rebal == 0:
            for k in s: s[k] = v * w[k]
    return out

def dca(w, rebal=12):
    s = {k: 0.0 for k in w}; cum = 0.0; uw = 0.0; peak = 0.0; amdd = 0.0
    for j, i in enumerate(IDX):
        cum += 1.0
        for k in s: s[k] += w[k]
        for k in s: s[k] *= (1 + R[k][i])
        v = sum(s.values())
        if v / cum - 1 < uw: uw = v / cum - 1
        peak = max(peak, v)
        if v / peak - 1 < amdd: amdd = v / peak - 1
        if (j + 1) % rebal == 0:
            for k in s: s[k] = v * w[k]
    final = sum(s.values()); n = len(IDX)
    def npv(r):
        return sum(-(1 + r) ** (-(m + 1) / 12.0) for m in range(n)) + final * (1 + r) ** (-(n - 1) / 12.0)
    lo, hi = -0.9, 2.0
    for _ in range(120):
        mid = (lo + hi) / 2
        if npv(mid) > 0: lo = mid
        else: hi = mid
    return dict(mult=final / cum, xirr=(lo + hi) / 2, uw=uw, amdd=amdd)

PLANS = [
    ("旧版·防守=美债",      {"spx_tr": .50, "ndx_tr": .35, "bond": .15, "gold": 0, "dvlow_tr": 0, "fcf_tr": 0}),
    ("旧版·防守=黄金",      {"spx_tr": .50, "ndx_tr": .35, "bond": 0, "gold": .15, "dvlow_tr": 0, "fcf_tr": 0}),
    ("旧版·债金各半(真实)", {"spx_tr": .50, "ndx_tr": .35, "bond": .075, "gold": .075, "dvlow_tr": 0, "fcf_tr": 0}),
    ("旧版·全权益(等权口径)", {"spx_tr": .588, "ndx_tr": .412, "bond": 0, "gold": 0, "dvlow_tr": 0, "fcf_tr": 0}),
    ("新版·四资产",        {"spx_tr": .30, "ndx_tr": .30, "bond": 0, "gold": 0, "dvlow_tr": .25, "fcf_tr": .15}),
    ("新版+防守15%(参考)",  {"spx_tr": .255, "ndx_tr": .255, "bond": .075, "gold": .075, "dvlow_tr": .2125, "fcf_tr": .1275}),
]

print()
print("=" * 96)
print("【一次性投入】2014-2026 人民币口径 年度再平衡")
print("  %-22s%9s%9s%9s%9s%9s" % ("方案", "CAGR", "波动", "回撤", "Calmar", "Sharpe"))
for nm, w in PLANS:
    st = stats(port(w))
    print("  %-22s%8.2f%%%8.1f%%%8.1f%%%9.2f%9.2f" % (nm, st["cagr"] * 100, st["sd"] * 100,
          st["mdd"] * 100, st["calmar"], st["sharpe"]))

print()
print("【定投口径】每月投1份")
print("  %-22s%10s%10s%12s%12s" % ("方案", "终值倍数", "XIRR", "账户回撤", "最深浮亏"))
for nm, w in PLANS:
    r = dca(w)
    print("  %-22s%9.2fx%9.2f%%%11.1f%%%11.1f%%" % (nm, r["mult"], r["xirr"] * 100, r["amdd"] * 100, r["uw"] * 100))

print()
print("【单资产补充】")
for k, nm in [("bond", "10Y美债(人民币)"), ("gold", "黄金(人民币)")]:
    rv = [R[k][i] for i in IDX]
    st = stats(rv)
    print("  %-22s CAGR %6.2f%%  波动 %5.1f%%  回撤 %6.1f%%   Calmar %.2f" % (
        nm, st["cagr"] * 100, st["sd"] * 100, st["mdd"] * 100, st["calmar"]))
for a in ["ndx_tr", "spx_tr", "dvlow_tr"]:
    for b in ["bond", "gold"]:
        x = [R[a][i] for i in IDX]; y = [R[b][i] for i in IDX]
        n = len(x); mx = sum(x) / n; my = sum(y) / n
        cov = sum((x[i] - mx) * (y[i] - my) for i in range(n)) / (n - 1)
        sx = (sum((v - mx) ** 2 for v in x) / (n - 1)) ** 0.5
        sy = (sum((v - my) ** 2 for v in y) / (n - 1)) ** 0.5
        print("  相关 %-10s × %-6s = %.2f" % (a.replace("_tr", ""), b, cov / sx / sy))
