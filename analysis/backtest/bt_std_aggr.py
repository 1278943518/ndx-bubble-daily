# -*- coding: utf-8 -*-
"""v24: 均衡版(纳30/标30/红利低波25/现金流15) vs 进攻版(纳40/标30/红利低波10/现金流20)
多窗口 + 分阶段 + 极端月份检验, 判断"进攻版多出来的收益值不值多出来的回撤"
"""
import json, math

D = json.load(open("alloc_data.json", encoding="utf-8"))
FX = D["fx"]
K4 = ["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"]


def fx_at(k):
    if k in FX:
        return FX[k]
    c = [x for x in FX if x <= k]
    return FX[max(c)] if c else 6.8


def build(lo, hi="2026-08", assets=None):
    keys = sorted(k for k in D["ndx_tr"] if lo <= k <= hi)
    S = {}
    for name in K4:
        v = [D[name].get(k) for k in keys]
        if name in ("ndx_tr", "spx_tr"):
            v = [(x * fx_at(k) if x else None) for k, x in zip(keys, v)]
        S[name] = v
    R = {k: [None] for k in S}
    for k in S:
        for i in range(1, len(keys)):
            a, b = S[k][i - 1], S[k][i]
            R[k].append(b / a - 1 if (a and b) else None)
    use = assets or list(R.keys())
    idx = [i for i in range(len(keys)) if all(R[k][i] is not None for k in use)]
    return keys, R, idx


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


def port(w, R, idx, rebal=12):
    s = dict(w); out = []
    for j, i in enumerate(idx):
        v0 = sum(s.values())
        for k in s: s[k] *= (1 + (R[k][i] or 0.0))
        v = sum(s.values())
        out.append(v / v0 - 1)
        if len(out) % rebal == 0:
            for k in s: s[k] = v * w[k]
    return out


def dca(w, R, idx, rebal=12):
    s = {k: 0.0 for k in w}; cum = 0.0; uw = 0.0; peak = 0.0; amdd = 0.0
    for j, i in enumerate(idx):
        cum += 1.0
        for k in s: s[k] += w[k]
        for k in s: s[k] *= (1 + (R[k][i] or 0.0))
        v = sum(s.values())
        uw = min(uw, v / cum - 1)
        peak = max(peak, v); amdd = min(amdd, v / peak - 1)
        if (j + 1) % rebal == 0:
            for k in s: s[k] = v * w[k]
    final = sum(s.values()); n = len(idx)
    def npv(r):
        return sum(-(1 + r) ** (-(m + 1) / 12.0) for m in range(n)) + final * (1 + r) ** (-(n - 1) / 12.0)
    lo_, hi_ = -0.9, 2.0
    for _ in range(200):
        mid = (lo_ + hi_) / 2
        if npv(mid) > 0: lo_ = mid
        else: hi_ = mid
    return dict(mult=final / cum, xirr=(lo_ + hi_) / 2, uw=uw, amdd=amdd)


STD = (.30, .30, .25, .15)
AGR = (.40, .30, .10, .20)
NAMES = [("均衡版 30/30/25/15", STD), ("进攻版 40/30/10/20", AGR)]


def table(title, keys, R, idx, merge=False):
    print()
    print("=" * 100)
    print(title)
    print("  %-20s | %8s %8s %8s %8s %8s | %8s %8s %10s" % (
        "方案", "CAGR", "波动", "回撤", "Calmar", "Sharpe", "定投倍数", "XIRR", "账户回撤"))
    res = {}
    for nm, c in NAMES:
        if merge:
            c = (c[0], c[1], c[2] + c[3], 0.0)
        w = dict(zip(K4, c))
        st = stats(port(w, R, idx))
        dc = dca(w, R, idx)
        res[nm] = (st, dc)
        print("  %-20s | %7.2f%% %7.1f%% %7.1f%% %8.2f %8.2f | %7.2fx %7.2f%% %9.1f%%" % (
            nm, st["cagr"] * 100, st["sd"] * 100, st["mdd"] * 100, st["calmar"], st["sharpe"],
            dc["mult"], dc["xirr"] * 100, dc["amdd"] * 100))
    a, b = res[NAMES[0][0]], res[NAMES[1][0]]
    print("  %-20s | %+7.2fpp %+7.1fpp %+7.1fpp %+8.2f %+8.2f | %+7.2fx %+7.2fpp %+9.1fpp" % (
        "进攻版 - 均衡版",
        (b[0]["cagr"] - a[0]["cagr"]) * 100, (b[0]["sd"] - a[0]["sd"]) * 100,
        (b[0]["mdd"] - a[0]["mdd"]) * 100, b[0]["calmar"] - a[0]["calmar"],
        b[0]["sharpe"] - a[0]["sharpe"], b[1]["mult"] - a[1]["mult"],
        (b[1]["xirr"] - a[1]["xirr"]) * 100, (b[1]["amdd"] - a[1]["amdd"]) * 100))
    return res


# ===== 1) 三个窗口 =====
k, R, i = build("2014-01", assets=K4)
table("【1】主样本 2014-01 ~ 2026-08 (%d 月, 四资产齐全)" % len(i), k, R, i)

k, R, i = build("2013-02", assets=K4)
table("【2】2013-02 ~ 2026-08 (%d 月, 四资产齐全, 覆盖2015 A股牛熊)" % len(i), k, R, i)

k, R, i = build("2006-01", assets=["ndx_tr", "spx_tr", "dvlow_tr"])
table("【3】扩展样本 2006-01 ~ 2026-08 (%d 月, 现金流腿并入红利低波, 含2008)" % len(i), k, R, i, merge=True)

# ===== 4) 分阶段 =====
print()
print("=" * 100)
print("【4】分阶段年化（一次性投入口径，不做再平衡影响）")
SEGS = [("2014-01", "2018-12"), ("2019-01", "2021-12"), ("2022-01", "2026-08")]
k4, R4, _ = build("2013-02", assets=K4)
print("  %-22s %14s %14s %14s" % ("方案", "2014-2018", "2019-2021", "2022-2026"))
for nm, c in NAMES:
    w = dict(zip(K4, c))
    row = []
    for lo, hi in SEGS:
        kk, RR, ii = build(lo, hi, assets=K4)
        if len(ii) < 3:
            row.append("  n/a")
            continue
        row.append("%13.2f%%" % (stats(port(w, RR, ii))["cagr"] * 100))
    print("  %-22s %s" % (nm, " ".join(row)))

# ===== 5) 单资产分阶段（解释差异来源） =====
print()
print("  单资产分阶段年化:")
print("  %-12s %14s %14s %14s" % ("", "2014-2018", "2019-2021", "2022-2026"))
for a in K4:
    row = []
    for lo, hi in SEGS:
        kk, RR, ii = build(lo, hi, assets=K4)
        v = 1.0
        for j in ii:
            v *= (1 + RR[a][j])
        row.append("%13.2f%%" % ((v ** (12.0 / len(ii)) - 1) * 100))
    print("  %-12s %s" % (a.replace("_tr", ""), " ".join(row)))

# ===== 6) 极端月份 =====
print()
print("=" * 100)
print("【5】极端月份单月跌幅（一次性投入口径，四资产齐全期）")
BAD = ["2015-06", "2015-07", "2015-08", "2016-01", "2018-10", "2018-12", "2020-02", "2020-03", "2022-04", "2024-08"]
kk, RR, ii = build("2013-02", assets=K4)
pos = {kk[j]: j for j in ii}
print("  %-10s %12s %12s %12s" % ("月份", "均衡版", "进攻版", "差"))
for m in BAD:
    if m not in pos: continue
    j = pos[m]
    out = []
    for nm, c in NAMES:
        w = dict(zip(K4, c))
        out.append(sum(w[a] * RR[a][j] for a in K4))
    print("  %-10s %11.1f%% %11.1f%% %11.1f%%" % (m, out[0] * 100, out[1] * 100, (out[1] - out[0]) * 100))

# ===== 7) 相关性 =====
print()
print("=" * 100)
print("【6】相关性（2013-2026，人民币口径）")
kk, RR, ii = build("2013-02", assets=K4)
def corr(a, b):
    x = [RR[a][j] for j in ii]; y = [RR[b][j] for j in ii]
    n = len(x); mx = sum(x) / n; my = sum(y) / n
    cov = sum((x[t] - mx) * (y[t] - my) for t in range(n)) / (n - 1)
    sx = (sum((v - mx) ** 2 for v in x) / (n - 1)) ** 0.5
    sy = (sum((v - my) ** 2 for v in y) / (n - 1)) ** 0.5
    return cov / sx / sy
for a, b in [("ndx_tr", "spx_tr"), ("ndx_tr", "dvlow_tr"), ("ndx_tr", "fcf_tr"),
             ("spx_tr", "dvlow_tr"), ("spx_tr", "fcf_tr"), ("dvlow_tr", "fcf_tr")]:
    print("  %-10s × %-10s = %.2f" % (a.replace("_tr", ""), b.replace("_tr", ""), corr(a, b)))

# ===== 8) 组合有效分散度 =====
print()
print("=" * 100)
print("【7】组合集中度（HHI 倒数 = 有效资产数）")
for nm, c in NAMES:
    hhi = sum(x * x for x in c)
    print("  %-20s A股合计 %.0f%%  美股合计 %.0f%%  HHI %.3f  有效资产数 %.2f" % (
        nm, (c[2] + c[3]) * 100, (c[0] + c[1]) * 100, hhi, 1 / hhi))

# ===== 9) 2006-2013 子窗口（美股失落的十年尾部 + A股两轮牛熊） =====
print()
print("=" * 100)
k9, R9, i9 = build("2006-01", "2013-12", assets=["ndx_tr", "spx_tr", "dvlow_tr"])
table("【8】2006-01 ~ 2013-12 (%d 月, 无现金流腿, 并入红利低波) — 检验样本反转" % len(i9), k9, R9, i9, merge=True)
print()
print("  单资产 2006-2013 年化:")
for a in ["ndx_tr", "spx_tr", "dvlow_tr"]:
    v = 1.0
    for j in i9:
        v *= (1 + R9[a][j])
    print("    %-10s %7.2f%%" % (a.replace("_tr", ""), (v ** (12.0 / len(i9)) - 1) * 100))

# ===== 10) 2000-2013（纳指互联网泡沫破裂后的长周期） =====
k10, R10, i10 = build("2000-01", "2013-12", assets=["ndx_tr", "spx_tr", "dvlow_tr"])
if len(i10) > 24:
    print()
    print("=" * 100)
    table("【9】2000-01 ~ 2013-12 (%d 月, 无现金流腿) — 纳指失落13年" % len(i10), k10, R10, i10, merge=True)
    print()
    print("  单资产 2000-2013 年化:")
    for a in ["ndx_tr", "spx_tr", "dvlow_tr"]:
        v = 1.0
        for j in i10:
            v *= (1 + R10[a][j])
        print("    %-10s %7.2f%%" % (a.replace("_tr", ""), (v ** (12.0 / len(i10)) - 1) * 100))
