# -*- coding: utf-8 -*-
"""v23b: 新旧方案的样本外稳健性检验
窗口1: 2005-01~2026-08 (现金流ETF无数据 -> 新版用三资产近似 纳30/标普30/红利低波40)
窗口2: 2013-01~2026-08 (四资产齐全, 比主样本多 1 年)
目的: 检验 2014-2026 主样本结论是否只是单一窗口的过拟合
"""
import json, csv, math, datetime, re

exec(open("bt_compare.py", encoding="utf-8").read().split("PLANS = [")[0])


def run(LO, HI, plans, use):
    keys = sorted(k for k in D["ndx_tr"] if LO <= k <= HI)
    S = {}
    for nm in use:
        v = [D[nm].get(k) for k in keys]
        if nm in ("ndx_tr", "spx_tr"):
            v = [(x * fx_at(k) if x else None) for k, x in zip(keys, v)]
        S[nm] = v
    S["gold"] = [gold_m.get(k) for k in keys]
    S["bond"] = [bond_cny.get(k) for k in keys]
    R = {k: [None] for k in S}
    for k in S:
        for i in range(1, len(keys)):
            a, b = S[k][i - 1], S[k][i]
            R[k].append(b / a - 1 if (a and b) else None)
    IDX = [i for i in range(len(keys)) if all(R[k][i] is not None for k in S)]
    out = []
    for nm, w in plans:
        st = stats(port(w, R, IDX))
        dc = dca(w, R, IDX)
        out.append((nm, st, dc))
    return keys, IDX, out


def port(w, R, IDX, rebal=12):
    s = dict(w)
    out = []
    for j, i in enumerate(IDX):
        v0 = sum(s.values())
        for k in s:
            s[k] *= (1 + R[k][i])
        v = sum(s.values())
        out.append(v / v0 - 1)
        if len(out) % rebal == 0:
            for k in s:
                s[k] = v * w[k]
    return out


def dca(w, R, IDX, rebal=12):
    s = {k: 0.0 for k in w}
    cum = 0.0
    peak = 0.0
    amdd = 0.0
    for j, i in enumerate(IDX):
        cum += 1.0
        for k in s:
            s[k] += w[k]
        for k in s:
            s[k] *= (1 + R[k][i])
        v = sum(s.values())
        peak = max(peak, v)
        amdd = min(amdd, v / peak - 1)
        if (j + 1) % rebal == 0:
            for k in s:
                s[k] = v * w[k]
    final = sum(s.values())
    n = len(IDX)

    def npv(r):
        return sum(-(1 + r) ** (-(m + 1) / 12.0) for m in range(n)) + final * (1 + r) ** (-(n - 1) / 12.0)
    lo, hi = -0.9, 2.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    return dict(mult=final / cum, xirr=(lo + hi) / 2, amdd=amdd)


def stats(rv):
    v = 1.0
    pk = 1.0
    mdd = 0.0
    for r in rv:
        v *= (1 + r)
        pk = max(pk, v)
        mdd = min(mdd, v / pk - 1)
    n = len(rv)
    mu = sum(rv) / n
    sd = (sum((x - mu) ** 2 for x in rv) / (n - 1)) ** 0.5 * (12 ** 0.5)
    cagr = v ** (12.0 / n) - 1
    return dict(cagr=cagr, sd=sd, mdd=mdd, calmar=cagr / abs(mdd) if mdd else 0,
                sharpe=(cagr - 0.02) / sd if sd else 0)


# ---------- 窗口1: 2005-2026, 三资产(无现金流) ----------
P1 = [
    ("旧版·债金各半", {"spx_tr": .50, "ndx_tr": .35, "bond": .075, "gold": .075, "dvlow_tr": 0}),
    ("旧版·全权益", {"spx_tr": .588, "ndx_tr": .412, "bond": 0, "gold": 0, "dvlow_tr": 0}),
    ("新版近似·三资产", {"spx_tr": .30, "ndx_tr": .30, "bond": 0, "gold": 0, "dvlow_tr": .40}),
    ("新版近似+防守15%", {"spx_tr": .255, "ndx_tr": .255, "bond": .075, "gold": .075, "dvlow_tr": .34}),
]
k1, i1, o1 = run("2005-01", "2026-08", P1, ["ndx_tr", "spx_tr", "dvlow_tr"])
print()
print("=" * 104)
print("【稳健性 1】2005-01 ~ 2026-08  (%d 月)  现金流ETF无数据, 新版用 纳30/标普30/红利低波40 近似" % len(i1))
print("  %-20s | %8s %8s %8s %8s | %8s %8s %9s" % ("方案", "CAGR", "波动", "回撤", "Calmar", "定投倍数", "XIRR", "账户回撤"))
for nm, st, dc in o1:
    print("  %-20s | %7.2f%% %7.1f%% %7.1f%% %8.2f | %7.2fx %7.2f%% %8.1f%%" % (
        nm, st["cagr"] * 100, st["sd"] * 100, st["mdd"] * 100, st["calmar"],
        dc["mult"], dc["xirr"] * 100, dc["amdd"] * 100))

# ---------- 窗口2: 2013-2026, 四资产齐全 ----------
P2 = [
    ("旧版·债金各半", {"spx_tr": .50, "ndx_tr": .35, "bond": .075, "gold": .075, "dvlow_tr": 0, "fcf_tr": 0}),
    ("旧版·全权益", {"spx_tr": .588, "ndx_tr": .412, "bond": 0, "gold": 0, "dvlow_tr": 0, "fcf_tr": 0}),
    ("新版·四资产", {"spx_tr": .30, "ndx_tr": .30, "bond": 0, "gold": 0, "dvlow_tr": .25, "fcf_tr": .15}),
    ("新版+防守15%", {"spx_tr": .255, "ndx_tr": .255, "bond": .075, "gold": .075, "dvlow_tr": .2125, "fcf_tr": .1275}),
]
k2, i2, o2 = run("2013-02", "2026-08", P2, ["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"])
print()
print("=" * 104)
print("【稳健性 2】2013-02 ~ 2026-08  (%d 月)  四资产齐全" % len(i2))
print("  %-20s | %8s %8s %8s %8s | %8s %8s %9s" % ("方案", "CAGR", "波动", "回撤", "Calmar", "定投倍数", "XIRR", "账户回撤"))
for nm, st, dc in o2:
    print("  %-20s | %7.2f%% %7.1f%% %7.1f%% %8.2f | %7.2fx %7.2f%% %8.1f%%" % (
        nm, st["cagr"] * 100, st["sd"] * 100, st["mdd"] * 100, st["calmar"],
        dc["mult"], dc["xirr"] * 100, dc["amdd"] * 100))
