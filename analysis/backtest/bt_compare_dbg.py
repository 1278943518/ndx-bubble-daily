# -*- coding: utf-8 -*-
"""v23-debug: 检查定投 XIRR 单调性"""
import json, csv, math, datetime
exec(open("bt_compare.py", encoding="utf-8").read().split("PLANS = [")[0])


def dca2(w, rebal=12):
    s = {k: 0.0 for k in w}
    cum = 0.0
    for j, i in enumerate(IDX):
        cum += 1.0
        for k in s:
            s[k] += w[k]
        for k in s:
            s[k] *= (1 + R[k][i])
        v = sum(s.values())
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
    return final / cum, (lo + hi) / 2


base = {"spx_tr": .30, "ndx_tr": .30, "dvlow_tr": .25, "fcf_tr": .15, "bond": 0, "gold": 0}
m, x = dca2(base)
print("新版四资产       倍数 %.2fx  XIRR %.2f%%" % (m, x * 100))
for d in [0.05, 0.10, 0.15, 0.20]:
    w = {k: v * (1 - d) for k, v in base.items()}
    w["bond"] = d / 2
    w["gold"] = d / 2
    m, x = dca2(w)
    print("新版+债金%.0f%%   倍数 %.2fx  XIRR %.2f%%" % (d * 100, m, x * 100))
for d in [0.05, 0.10, 0.15]:
    w = {k: v * (1 - d) for k, v in base.items()}
    w["bond"] = 0
    w["gold"] = d
    m, x = dca2(w)
    print("新版+黄金%.0f%%   倍数 %.2fx  XIRR %.2f%%" % (d * 100, m, x * 100))
old = {"spx_tr": .50, "ndx_tr": .35, "dvlow_tr": 0, "fcf_tr": 0, "bond": .075, "gold": .075}
m, x = dca2(old)
print("旧版债金各半     倍数 %.2fx  XIRR %.2f%%" % (m, x * 100))
w = {"spx_tr": .588, "ndx_tr": .412, "dvlow_tr": 0, "fcf_tr": 0, "bond": 0, "gold": 0}
m, x = dca2(w)
print("旧版全权益       倍数 %.2fx  XIRR %.2f%%" % (m, x * 100))

print()
print("各资产分段年化(前5年 2014-02~2019-01 / 后7.5年 2019-02~2026-08)")
for k in ["spx_tr", "ndx_tr", "dvlow_tr", "fcf_tr", "bond", "gold"]:
    a = [R[k][i] for i in IDX[:60]]
    b = [R[k][i] for i in IDX[60:]]
    ca = 1.0
    for r in a:
        ca *= (1 + r)
    cb = 1.0
    for r in b:
        cb *= (1 + r)
    print("  %-10s 前段 %7.2f%%  后段 %7.2f%%" % (k, (ca ** (12.0 / len(a)) - 1) * 100, (cb ** (12.0 / len(b)) - 1) * 100))
