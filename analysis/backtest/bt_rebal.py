# -*- coding: utf-8 -*-
"""再平衡规则对比：统一 8pp 绝对阈值 vs 相对阈值 vs 5/25 规则

回答：目标权重不同的资产（纳指 30% / 现金流 15%），用同一个 8pp 绝对阈值是否合理？
指标：CAGR / 波动 / MDD / Calmar / 年化单边换手 / 各腿触及的最大相对偏离
样本：2014-01 ~ 2025-08（四资产齐全），人民币全收益，年度/半年度检视
"""
import json, statistics as st

D = json.load(open("alloc_data.json", encoding="utf-8"))
FX = D["fx"]
K4 = ["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"]
CN = {"ndx_tr": "纳斯达克", "spx_tr": "标普500", "dvlow_tr": "红利低波", "fcf_tr": "自由现金流"}
W = {"ndx_tr": .30, "spx_tr": .30, "dvlow_tr": .25, "fcf_tr": .15}


def fx_at(k):
    if k in FX:
        return FX[k]
    c = [x for x in FX if x <= k]
    return FX[max(c)] if c else 6.8


keys = sorted(k for k in D["ndx_tr"] if "2013-12" <= k <= "2026-08")
SER = {}
for name in K4:
    v = [D[name].get(k) for k in keys]
    if name in ("ndx_tr", "spx_tr"):
        v = [(x * fx_at(k) if x else None) for k, x in zip(keys, v)]
    SER[name] = v
R = {k: [None] for k in K4}
for k in K4:
    for i in range(1, len(keys)):
        a, b = SER[k][i - 1], SER[k][i]
        R[k].append(b / a - 1 if (a and b) else None)

# 只保留四腿齐全的月份
idx = [i for i in range(len(keys)) if all(R[k][i] is not None for k in K4)]

# ---- 规则定义：返回 True 表示触发 ----
def mk_rule(kind):
    def f(month, dev, w):
        if kind == "none":      return False
        if kind == "semi":      return month in (6, 12)
        if kind == "annual":    return month == 12
        if kind == "abs8":      return max(abs(dev[k]) for k in w) > 0.08
        if kind == "abs5":      return max(abs(dev[k]) for k in w) > 0.05
        if kind == "abs10":     return max(abs(dev[k]) for k in w) > 0.10
        if kind == "rel30":     return any(abs(dev[k]) > 0.30 * w[k] for k in w)
        if kind == "rel25":     return any(abs(dev[k]) > 0.25 * w[k] for k in w)
        if kind == "rel40":     return any(abs(dev[k]) > 0.40 * w[k] for k in w)
        if kind == "r525":      return any(abs(dev[k]) > 0.05 or abs(dev[k]) > 0.25 * w[k] for k in w)
        if kind == "mix8rel40": return any(abs(dev[k]) > 0.08 or abs(dev[k]) > 0.40 * w[k] for k in w)
        raise ValueError(kind)
    return f


def sim(kind, check=(6, 12)):
    rule = mk_rule(kind)
    s = dict(W); out = []; trades = 0; turn = 0.0
    maxrel = {k: 0.0 for k in K4}
    maxabs = {k: 0.0 for k in K4}
    for i in idx:
        v0 = sum(s.values())
        for k in s:
            s[k] *= (1 + R[k][i])
        v = sum(s.values())
        out.append(v / v0 - 1)
        mm = int(keys[i][5:7])
        if mm in check:
            cur = {k: s[k] / v for k in s}
            dev = {k: cur[k] - W[k] for k in s}
            for k in K4:
                if abs(dev[k]) > maxabs[k]: maxabs[k] = abs(dev[k])
                rr = abs(dev[k]) / W[k]
                if rr > maxrel[k]: maxrel[k] = rr
            if rule(mm, dev, W):
                turn += sum(abs(dev[k]) for k in K4) / 2
                for k in K4: s[k] = v * W[k]
                trades += 1
    n = len(out); v = 1.0; pk = 1.0; mdd = 0.0
    for r in out:
        v *= (1 + r); pk = max(pk, v); mdd = min(mdd, v / pk - 1)
    mu = sum(out) / n
    sd = (sum((x - mu) ** 2 for x in out) / (n - 1)) ** 0.5 * (12 ** 0.5)
    cagr = v ** (12.0 / n) - 1
    yrs = n / 12.0
    return dict(cagr=cagr, sd=sd, mdd=mdd, calmar=cagr / abs(mdd),
                trades=trades, turn=turn / yrs, maxrel=maxrel, maxabs=maxabs, end=v)


RULES = [("none", "不再平衡（放任）"), ("annual", "年度固定（12月）"),
         ("semi", "半年固定（6/12月）"), ("abs10", "10pp 绝对阈值"),
         ("abs8", "8pp 绝对阈值 ←当前方案"), ("abs5", "5pp 绝对阈值"),
         ("rel40", "相对 40%"), ("rel30", "相对 30%"), ("rel25", "相对 25%"),
         ("r525", "5/25 规则"), ("mix8rel40", "8pp 或 相对40%")]

print(f"样本 {keys[idx[0]]} ~ {keys[idx[-1]]}，{len(idx)} 个月（半年度检视 {len(idx)//6} 次机会）")
print()
print(f"{'规则':22s} {'CAGR':>7s} {'波动':>7s} {'MDD':>8s} {'Calmar':>7s} {'年换手':>7s} {'调仓次数':>7s}")
print("-" * 74)
res = {}
for k, name in RULES:
    r = sim(k); res[k] = r
    print(f"{name:22s} {r['cagr']*100:6.2f}% {r['sd']*100:6.1f}% {r['mdd']*100:7.1f}% "
          f"{r['calmar']:7.2f} {r['turn']*100:6.1f}% {r['trades']:7d}")

print()
print("【各规则下，每条腿触及的最大绝对偏离 / 最大相对偏离】")
print(f"{'规则':22s} " + " ".join(f"{CN[k]:>10s}" for k in K4))
for k, name in RULES:
    r = res[k]
    cells = [f"{r['maxabs'][x]*100:4.1f}pp/{r['maxrel'][x]*100:3.0f}%" for x in K4]
    print(f"{name:22s} " + " ".join(f"{c:>10s}" for c in cells))

print()
print("【关键：8pp 对每条腿意味着多大的相对波动】")
for k in K4:
    print(f"   目标 {W[k]*100:2.0f}%  →  8pp = 相对 {8/W[k]/100*100:3.0f}%  "
          f"（相当于该腿涨到 {W[k]+0.08:.0%} 或跌到 {W[k]-0.08:.0%} 才触发）")
