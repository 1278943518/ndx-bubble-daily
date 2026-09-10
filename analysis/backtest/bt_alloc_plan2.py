# -*- coding: utf-8 -*-
"""v21: 跨样本稳健性 + 温度计引入检验 + 相关性稳定性
1) 候选方案在两个样本的表现(现金流腿不足20年 -> 扩展样本并入红利低波, 相关0.87)
2) 定投账户改用"账户峰值回撤" + "最深浮亏"双指标
3) 温度计(泡沫分)作为权重调节条件是否有效
"""
import json, math, csv, itertools

D = json.load(open("alloc_data.json", encoding="utf-8"))
FX = D["fx"]
def fx_at(k):
    if k in FX: return FX[k]
    c = [x for x in FX if x <= k]
    return FX[max(c)] if c else 6.8

def build(lo, hi="2026-08", assets=None):
    keys = sorted(set(k for k in D["ndx_tr"] if lo <= k <= hi))
    S = {}
    for name in ["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"]:
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

K4 = ["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"]

def run(c4, keys, R, idx, rebal=12, dca_mode=False, tempw=None, T=None):
    """c4: 四资产权重(nxd,spx,dvlow,fcf); tempw: 可选(高分时纳指权重乘数)"""
    w0 = dict(zip(K4, c4))
    s = dict(w0); cum = 0.0; uw = 0.0
    peak = 0.0; amdd = 0.0
    rv = []
    for j, i in enumerate(idx):
        w = dict(w0)
        if tempw and T is not None:
            t = T.get(keys[i])
            if t is not None:
                if t >= tempw[0]:
                    w["ndx_tr"] *= tempw[1]
                    rest = 1 - sum(w.values())
                    w["spx_tr"] += rest
        v0 = sum(s.values()) if dca_mode else 1.0
        if dca_mode:
            cum += 1.0
            for k in s: s[k] += w[k]
        else:
            for k in s: s[k] = w[k]
        for k in s: s[k] *= (1 + (R[k][i] if R[k][i] is not None else 0.0))
        v = sum(s.values())
        if dca_mode:
            if v / cum - 1 < uw: uw = v / cum - 1
            peak = max(peak, v)
            if v / peak - 1 < amdd: amdd = v / peak - 1
        else:
            rv.append(v / v0 - 1)
        if (j + 1) % rebal == 0 and not dca_mode:
            for k in s: s[k] = v * w[k]
    if dca_mode:
        final = sum(s.values())
        n = len(idx)
        def npv(r):
            return sum(-1 * (1 + r) ** (-(m + 1) / 12.0) for m in range(n)) + final * (1 + r) ** (-(n - 1) / 12.0)
        lo_, hi_ = -0.9, 2.0
        for _ in range(120):
            mid = (lo_ + hi_) / 2
            if npv(mid) > 0: lo_ = mid
            else: hi_ = mid
        return dict(mult=final / cum, xirr=(lo_ + hi_) / 2, uw=uw, amdd=amdd)
    return stats(rv)

# ============ 1) 跨样本稳健性 ============
CAND = [
    ("全纳指",            (1.0, 0, 0, 0)),
    ("全标普",            (0, 1.0, 0, 0)),
    ("全红利低波",         (0, 0, 1.0, 0)),
    ("等权 25×4",        (.25, .25, .25, .25)),
    ("【推荐】30/30/25/15", (.30, .30, .25, .15)),
    ("美股60/A股40",      (.30, .30, .25, .15)),
    ("纳40/标30/红10/现20", (.40, .30, .10, .20)),
    ("纳30/标50/红0/现20",  (.30, .50, 0, .20)),
    ("纳25/标25/红35/现15", (.25, .25, .35, .15)),
    ("纳20/标20/红40/现20", (.20, .20, .40, .20)),
]
CAND = [c for c in CAND if c[1] != (0.30, 0.30, 0.25, 0.15) or c[0].startswith("【")]

print("=" * 92)
print("【1】主样本 2014-01~2026-08 (13.6年) 一次性投入 · 年度再平衡")
print("  %-22s%9s%9s%9s%9s%9s" % ("方案", "CAGR", "波动", "回撤", "Calmar", "Sharpe"))
k1, R1, i1 = build("2014-01")
for nm, c in CAND:
    st = run(c, k1, R1, i1)
    print("  %-22s%8.2f%%%8.1f%%%8.1f%%%9.2f%9.2f" % (nm, st["cagr"] * 100, st["sd"] * 100,
          st["mdd"] * 100, st["calmar"], st["sharpe"]))

print()
print("【1b】扩展样本 2006-01~2026-08 (20.6年) · 现金流腿并入红利低波(相关0.87) · 三资产")
print("  %-22s%9s%9s%9s%9s%9s" % ("方案", "CAGR", "波动", "回撤", "Calmar", "Sharpe"))
k2, R2, i2 = build("2006-01", assets=["ndx_tr","spx_tr","dvlow_tr"])
for nm, c in CAND:
    c3 = (c[0], c[1], c[2] + c[3], 0.0)     # 现金流并入红利低波
    st = run(c3, k2, R2, i2)
    print("  %-22s%8.2f%%%8.1f%%%8.1f%%%9.2f%9.2f" % (nm, st["cagr"] * 100, st["sd"] * 100,
          st["mdd"] * 100, st["calmar"], st["sharpe"]))

# ============ 2) 定投口径(双指标) ============
print()
print("=" * 92)
print("【2】定投口径 (每月投1份, 年度再平衡)")
print("  主样本 2014-01 起:")
print("  %-22s%10s%10s%12s%12s" % ("方案", "终值倍数", "XIRR", "账户峰值回撤", "最深浮亏"))
for nm, c in CAND:
    r = run(c, k1, R1, i1, dca_mode=True)
    print("  %-22s%9.2fx%9.2f%%%11.1f%%%11.1f%%" % (nm, r["mult"], r["xirr"] * 100, r["amdd"] * 100, r["uw"] * 100))
print("  扩展样本 2006-01 起:")
print("  %-22s%10s%10s%12s%12s" % ("方案", "终值倍数", "XIRR", "账户峰值回撤", "最深浮亏"))
for nm, c in CAND:
    c3 = (c[0], c[1], c[2] + c[3], 0.0)
    r = run(c3, k2, R2, i2, dca_mode=True)
    print("  %-22s%9.2fx%9.2f%%%11.1f%%%11.1f%%" % (nm, r["mult"], r["xirr"] * 100, r["amdd"] * 100, r["uw"] * 100))

# ============ 3) 相关性稳定性 ============
print()
print("=" * 92)
print("【3】纳指 vs 红利低波 滚动36月相关 (人民币口径, 分散效果的稳定性)")
k3, R3, i3 = build("2006-01", assets=["ndx_tr","spx_tr","dvlow_tr"])
pairs = [(K4[0], K4[2]), (K4[0], K4[1])]
for a, b in pairs:
    xs = [R3[a][i] for i in i3]; ys = [R3[b][i] for i in i3]
    n = min(len(xs), len(ys))
    if n < 40: print("  %s vs %s: 样本不足" % (a, b)); continue
    out = []
    for st in range(0, n - 36 + 1, 12):
        x = xs[st:st + 36]; y = ys[st:st + 36]
        mx = sum(x) / 36; my = sum(y) / 36
        cov = sum((x[i] - mx) * (y[i] - my) for i in range(36)) / 35
        sx = (sum((v - mx) ** 2 for v in x) / 35) ** 0.5
        sy = (sum((v - my) ** 2 for v in y) / 35) ** 0.5
        out.append(cov / sx / sy)
    print("  %-14s vs %-14s 滚动相关: min %.2f  中位 %.2f  max %.2f" % (
        a.replace("_tr", ""), b.replace("_tr", ""), min(out), sorted(out)[len(out)//2], max(out)))

# ============ 4) 温度计引入检验 ============
print()
print("=" * 92)
print("【4】温度计(泡沫分)作为权重调节条件是否值得引入?")
T = {}
for r in csv.DictReader(open("bubble_out/scores_monthly.csv", encoding="utf-8")):
    try:
        T[r["date"][:7]] = float(r["total"])
    except: pass
k4, R4, i4 = build("2016-03")
have = [i for i in i4 if k4[i] in T]
print("  样本: %s ~ %s (%d 月, 温度8腿完整期)" % (k4[i4[0]], k4[i4[-1]], len(have)))
print("  %-34s%10s%10s" % ("方案", "终值倍数", "XIRR"))
base_c = (0.30, 0.30, 0.25, 0.15)
tests = [("固定权重 30/30/25/15 (不择时)", None),
         ("温度>=70 纳指减半→标普", (70, 0.5)),
         ("温度>=80 纳指减半→标普", (80, 0.5)),
         ("温度>=70 纳指清零→标普", (70, 0.0)),
         ("温度>=85 纳指清零→标普", (85, 0.0))]
for nm, tw in tests:
    r = run(base_c, k4, R4, i4, dca_mode=True, tempw=tw, T=T)
    print("  %-34s%9.2fx%9.2f%%" % (nm, r["mult"], r["xirr"] * 100))
print()
print("  触发次数统计:")
for th in [70, 80, 85]:
    n = sum(1 for i in i4 if T.get(k4[i], 0) >= th)
    print("    温度 >= %d 的月份: %d / %d" % (th, n, len(i4)))
