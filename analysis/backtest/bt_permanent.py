# -*- coding: utf-8 -*-
"""v25: 永续投资组合(永久组合) Harry Browne 25/25/25/25 vs 四资产方案
资产(人民币口径): 标普500全收益 / 30Y美债 / LBMA黄金 / 人民币现金
现金腿: 人民币货币基金, 基准 2.5%/年 (敏感性 2.0 / 3.0)
"""
import json, csv, math, datetime

D = json.load(open("alloc_data.json", encoding="utf-8"))
FX = D["fx"]


def fx_at(k):
    if k in FX:
        return FX[k]
    c = [x for x in FX if x <= k]
    return FX[max(c)] if c else 6.8


# ---------- 黄金: LBMA 美元月收盘 × 汇率 ----------
G = json.load(open("lbma_gold.json", encoding="utf-8"))
gm = {}
for it in G:
    v = it["v"][0]
    if v is None:
        continue
    gm[it["d"][:7]] = v                      # 同月取最后一条 = 月末
GK = sorted(gm)
gold_cny = {}
for k in GK:
    if k in FX:
        gold_cny[k] = gm[k] * fx_at(k)
print("黄金(LBMA×汇率): %s~%s  $%.0f → $%.0f" % (GK[0], GK[-1], gm[GK[0]], gm[GK[-1]]))

# ---------- 长债: 30Y 久期近似 ----------
DUR30 = 17.0
y30 = {}
for r in csv.DictReader(open("fred_DGS30.csv", encoding="utf-8")):
    try:
        v = float(r["DGS30"])
        if v > 0:
            y30[r["observation_date"][:7]] = v          # 同月取最后
    except Exception:
        pass
YK = sorted(y30)
bond_cny, v = {}, 1.0
prev = None
for k in YK:
    if prev is not None and k in FX:
        r_usd = prev / 100.0 / 12.0 - DUR30 * (y30[k] / 100.0 - prev / 100.0)
        v *= (1 + r_usd) * (fx_at(k) / fx_at(YK[YK.index(k) - 1]))
        bond_cny[k] = v
    prev = y30[k]
BK = sorted(bond_cny)


def series(lo, hi, cash_annual=0.025, use_ndx=False, use_spx=True):
    keys = sorted(k for k in D["spx_tr"] if lo <= k <= hi)
    S = {}
    if use_spx:
        S["stk"] = [(D["spx_tr"].get(k) or 0) * fx_at(k) if D["spx_tr"].get(k) else None for k in keys]
    if use_ndx:
        S["stk"] = [(D["ndx_tr"].get(k) or 0) * fx_at(k) if D["ndx_tr"].get(k) else None for k in keys]
    S["gold"] = [gold_cny.get(k) for k in keys]
    S["bond"] = [bond_cny.get(k) for k in keys]
    S["dvlow"] = [D["dvlow_tr"].get(k) for k in keys]
    S["fcf"] = [D["fcf_tr"].get(k) for k in keys]
    return keys, S


def returns(keys, S, cash_annual=0.025):
    R = {}
    for k in S:
        R[k] = [None]
        for i in range(1, len(keys)):
            a, b = S[k][i - 1], S[k][i]
            R[k].append(b / a - 1 if (a and b) else None)
    R["cash"] = [cash_annual / 12.0] * len(keys)
    return R


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


def port(w, R, idx, rebal=12, band=None):
    s = dict(w); out = []
    for j, i in enumerate(idx):
        v0 = sum(s.values())
        for k in s:
            s[k] *= (1 + (R[k][i] if R[k][i] is not None else 0.0))
        v = sum(s.values())
        out.append(v / v0 - 1)
        if band:
            for k in s:
                if abs(s[k] / v - w[k]) > band:
                    for kk in s:
                        s[kk] = v * w[kk]
                    break
        elif (len(out)) % rebal == 0:
            for k in s:
                s[k] = v * w[k]
    return out


def dca(w, R, idx, rebal=12, band=None):
    s = {k: 0.0 for k in w}; cum = 0.0; uw = 0.0; peak = 0.0; amdd = 0.0
    for j, i in enumerate(idx):
        cum += 1.0
        for k in s:
            s[k] += w[k]
        for k in s:
            s[k] *= (1 + (R[k][i] if R[k][i] is not None else 0.0))
        v = sum(s.values())
        uw = min(uw, v / cum - 1)
        peak = max(peak, v); amdd = min(amdd, v / peak - 1)
        if band:
            for k in s:
                if abs(s[k] / v - w[k]) > band:
                    for kk in s:
                        s[kk] = v * w[kk]
                    break
        elif (j + 1) % rebal == 0:
            for k in s:
                s[k] = v * w[k]
    final = sum(s.values()); n = len(idx)

    def npv(r):
        return sum(-(1 + r) ** (-(m + 1) / 12.0) for m in range(n)) + final * (1 + r) ** (-(n - 1) / 12.0)
    lo_, hi_ = -0.9, 2.0
    for _ in range(200):
        mid = (lo_ + hi_) / 2
        if npv(mid) > 0:
            lo_ = mid
        else:
            hi_ = mid
    return dict(mult=final / cum, xirr=(lo_ + hi_) / 2, uw=uw, amdd=amdd)


def run_window(lo, hi, title, use4=True, cash=0.025):
    keys, S = series(lo, hi, cash_annual=cash)
    R = returns(keys, S, cash)
    plans = []
    PP = {"stk": .25, "bond": .25, "gold": .25, "cash": .25}
    plans.append(("永续组合 25/25/25/25", PP, ["stk", "bond", "gold", "cash"]))
    if use4:
        plans.append(("四资产 30/30/25/15",
                      {"stk": .30, "ndx2": .30, "dvlow": .25, "fcf": .15},
                      ["stk", "bond", "gold", "cash", "dvlow", "fcf"]))
    # 四资产需要 ndx，重新建
    keys2, S2 = series(lo, hi)
    S2["ndx2"] = [(D["ndx_tr"].get(k) or 0) * fx_at(k) if D["ndx_tr"].get(k) else None for k in keys2]
    R2 = returns(keys2, S2, cash)
    R2["ndx2"] = [None]
    for i in range(1, len(keys2)):
        a, b = S2["ndx2"][i - 1], S2["ndx2"][i]
        R2["ndx2"].append(b / a - 1 if (a and b) else None)
    idx_pp = [i for i in range(len(keys)) if all(R[k][i] is not None for k in ["stk", "bond", "gold"])]
    idx_4 = [i for i in range(len(keys2)) if all(R2[k][i] is not None for k in ["stk", "ndx2", "dvlow", "fcf"])]
    idx_3 = [i for i in range(len(keys2)) if all(R2[k][i] is not None for k in ["stk", "ndx2", "dvlow"])]
    W3 = {"stk": .30, "ndx2": .30, "dvlow": .40}
    st3 = stats(port(W3, R2, idx_3))
    dc3 = dca(W3, R2, idx_3)
    print()
    print("=" * 104)
    print(title)
    print("  永续组合样本 %s~%s (%d 月) | 四资产样本 %s~%s (%d 月)" % (
        keys[idx_pp[0]], keys[idx_pp[-1]], len(idx_pp),
        keys2[idx_4[0]], keys2[idx_4[-1]], len(idx_4)))
    print("  %-24s | %8s %8s %8s %8s | %8s %8s %10s" % (
        "方案", "CAGR", "波动", "回撤", "Calmar", "定投倍数", "XIRR", "账户回撤"))
    st_pp = stats(port(PP, R, idx_pp))
    dc_pp = dca(PP, R, idx_pp)
    print("  %-24s | %7.2f%% %7.1f%% %7.1f%% %8.2f | %7.2fx %7.2f%% %9.1f%%" % (
        "永续组合(年再平衡)", st_pp["cagr"] * 100, st_pp["sd"] * 100, st_pp["mdd"] * 100,
        st_pp["calmar"], dc_pp["mult"], dc_pp["xirr"] * 100, dc_pp["amdd"] * 100))
    st_ppb = stats(port(PP, R, idx_pp, band=0.15))
    dc_ppb = dca(PP, R, idx_pp, band=0.15)
    print("  %-24s | %7.2f%% %7.1f%% %7.1f%% %8.2f | %7.2fx %7.2f%% %9.1f%%" % (
        "永续组合(±15pp触发带)", st_ppb["cagr"] * 100, st_ppb["sd"] * 100, st_ppb["mdd"] * 100,
        st_ppb["calmar"], dc_ppb["mult"], dc_ppb["xirr"] * 100, dc_ppb["amdd"] * 100))
    if use4:
        W4 = {"stk": .30, "ndx2": .30, "dvlow": .25, "fcf": .15}
        st4 = stats(port(W4, R2, idx_4))
        dc4 = dca(W4, R2, idx_4)
        print("  %-24s | %7.2f%% %7.1f%% %7.1f%% %8.2f | %7.2fx %7.2f%% %9.1f%%" % (
            "四资产 30/30/25/15", st4["cagr"] * 100, st4["sd"] * 100, st4["mdd"] * 100,
            st4["calmar"], dc4["mult"], dc4["xirr"] * 100, dc4["amdd"] * 100))
        print("  %-24s | %+7.2fpp %+7.1fpp %+7.1fpp %+8.2f | %+7.2fx %+7.2fpp %+9.1fpp" % (
            "四资产 - 永续(年平衡)",
            (st4["cagr"] - st_pp["cagr"]) * 100, (st4["sd"] - st_pp["sd"]) * 100,
            (st4["mdd"] - st_pp["mdd"]) * 100, st4["calmar"] - st_pp["calmar"],
            dc4["mult"] - dc_pp["mult"], (dc4["xirr"] - dc_pp["xirr"]) * 100,
            (dc4["amdd"] - dc_pp["amdd"]) * 100))
    if len(idx_3) > 24:
        print("  %-24s | %7.2f%% %7.1f%% %7.1f%% %8.2f | %7.2fx %7.2f%% %9.1f%%" % (
            "四资产近似(现金流并入)", st3["cagr"] * 100, st3["sd"] * 100, st3["mdd"] * 100,
            st3["calmar"], dc3["mult"], dc3["xirr"] * 100, dc3["amdd"] * 100))
        print("  %-24s | %+7.2fpp %+7.1fpp %+7.1fpp %+8.2f | %+7.2fx %+7.2fpp %+9.1fpp" % (
            "近似四资产 - 永续",
            (st3["cagr"] - st_pp["cagr"]) * 100, (st3["sd"] - st_pp["sd"]) * 100,
            (st3["mdd"] - st_pp["mdd"]) * 100, st3["calmar"] - st_pp["calmar"],
            dc3["mult"] - dc_pp["mult"], (dc3["xirr"] - dc_pp["xirr"]) * 100,
            (dc3["amdd"] - dc_pp["amdd"]) * 100))
    # 单资产
    print("  --- 单资产(人民币, 分红再投) ---")
    for k, nm in [("stk", "标普500"), ("gold", "黄金"), ("bond", "30Y美债"), ("cash", "人民币现金")]:
        rv = [R[k][i] for i in idx_pp]
        s1 = stats(rv)
        print("    %-12s CAGR %6.2f%%  波动 %5.1f%%  回撤 %7.1f%%  Calmar %.2f" % (
            nm, s1["cagr"] * 100, s1["sd"] * 100, s1["mdd"] * 100, s1["calmar"]))


run_window("2014-01", "2026-08", "【1】主样本 2014-01 ~ 2026-08（13.6 年）")
run_window("2006-01", "2026-08", "【2】扩展样本 2006-01 ~ 2026-08（20.6 年，含 2008 危机）")
run_window("2000-01", "2026-08", "【3】长样本 2000-01 ~ 2026-08（26.6 年，含互联网泡沫 + 2008）")

print()
print("=" * 104)
print("【4】现金腿敏感性（永续组合，扩展样本 2006-2026，年度再平衡）")
print("  %-16s %10s %10s %10s" % ("现金年化", "CAGR", "最大回撤", "定投 XIRR"))
for c in [0.015, 0.020, 0.025, 0.030, 0.040]:
    keys, S = series("2006-01", "2026-08", cash_annual=c)
    R = returns(keys, S, c)
    idx = [i for i in range(len(keys)) if all(R[k][i] is not None for k in ["stk", "bond", "gold"])]
    W = {"stk": .25, "bond": .25, "gold": .25, "cash": .25}
    s1 = stats(port(W, R, idx))
    d1 = dca(W, R, idx)
    print("  %-16s %9.2f%% %9.1f%% %9.2f%%" % ("%.1f%%" % (c * 100), s1["cagr"] * 100, s1["mdd"] * 100, d1["xirr"] * 100))
