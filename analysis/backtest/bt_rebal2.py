# -*- coding: utf-8 -*-
"""再平衡规则：长样本稳健性检查（2006-2026，三资产近似，A股腿用 dvlow 代表）"""
import json

D = json.load(open("alloc_data.json", encoding="utf-8"))
FX = D["fx"]


def fx_at(k):
    if k in FX: return FX[k]
    c = [x for x in FX if x <= k]
    return FX[max(c)] if c else 6.8


def run(W, lo, hi, label):
    K = list(W)
    keys = sorted(k for k in D["ndx_tr"] if lo <= k <= hi)
    SER = {}
    for n in K:
        v = [D[n].get(k) for k in keys]
        if n in ("ndx_tr", "spx_tr"):
            v = [(x * fx_at(k) if x else None) for k, x in zip(keys, v)]
        SER[n] = v
    R = {n: [None] for n in K}
    for n in K:
        for i in range(1, len(keys)):
            a, b = SER[n][i - 1], SER[n][i]
            R[n].append(b / a - 1 if (a and b) else None)
    idx = [i for i in range(len(keys)) if all(R[n][i] is not None for n in K)]

    def mk(kind):
        def f(mm, dev, w):
            if kind == "none":   return False
            if kind == "annual": return mm == 12
            if kind == "abs8":   return max(abs(dev[k]) for k in w) > 0.08
            if kind == "abs6":   return max(abs(dev[k]) for k in w) > 0.06
            if kind == "abs5":   return max(abs(dev[k]) for k in w) > 0.05
            if kind == "rel40":  return any(abs(dev[k]) > 0.40 * w[k] for k in w)
            if kind == "rel50":  return any(abs(dev[k]) > 0.50 * w[k] for k in w)
            if kind == "r525":   return any(abs(dev[k]) > 0.05 or abs(dev[k]) > 0.25 * w[k] for k in w)
        return f

    def sim(kind):
        rule = mk(kind); s = dict(W); out = []; tr = 0; turn = 0.0
        for i in idx:
            v0 = sum(s.values())
            for k in s: s[k] *= (1 + R[k][i])
            v = sum(s.values()); out.append(v / v0 - 1)
            mm = int(keys[i][5:7])
            if mm in (6, 12):
                cur = {k: s[k] / v for k in s}; dev = {k: cur[k] - W[k] for k in s}
                if rule(mm, dev, W):
                    turn += sum(abs(dev[k]) for k in K) / 2
                    for k in K: s[k] = v * W[k]
                    tr += 1
        n = len(out); v = 1.0; pk = 1.0; mdd = 0.0
        for r in out:
            v *= (1 + r); pk = max(pk, v); mdd = min(mdd, v / pk - 1)
        cagr = v ** (12.0 / n) - 1
        return cagr, mdd, cagr / abs(mdd), turn / (n / 12.0), tr

    print(f"\n=== {label}   {keys[idx[0]]} ~ {keys[idx[-1]]}  ({len(idx)} 个月) ===")
    print(f"{'规则':16s} {'CAGR':>7s} {'MDD':>8s} {'Calmar':>7s} {'年换手':>7s} {'次数':>5s}")
    for k, nm in [("none", "不再平衡"), ("annual", "年度固定"), ("abs8", "8pp 绝对←当前"),
                  ("abs6", "6pp 绝对"), ("abs5", "5pp 绝对"), ("rel50", "相对50%"),
                  ("rel40", "相对40%"), ("r525", "5/25 规则")]:
        c, m, cal, t, tr = sim(k)
        print(f"{nm:16s} {c*100:6.2f}% {m*100:7.1f}% {cal:7.2f} {t*100:6.1f}% {tr:5d}")


run({"ndx_tr": .40, "spx_tr": .30, "dvlow_tr": .30}, "2005-12", "2026-08", "长样本·三资产近似")
run({"ndx_tr": .30, "spx_tr": .30, "dvlow_tr": .40}, "2005-12", "2026-08", "长样本·三资产近似")
run({"ndx_tr": .30, "spx_tr": .30, "dvlow_tr": .25, "fcf_tr": .15}, "2013-12", "2026-08", "四资产·均衡版")
