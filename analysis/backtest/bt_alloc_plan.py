# -*- coding: utf-8 -*-
"""v20: 不择时长期资产配置回测 (人民币口径, 分红再投资)
标的: 纳指100 / 标普500 / 中证红利低波全收益 / 中证现金流
A. 单资产统计  B. 相关性  C. 权重网格  D. 定投口径  E. 再平衡频率  F. 温度计引入测试
"""
import json, math, itertools

D = json.load(open("alloc_data.json", encoding="utf-8"))
FX = D["fx"]

def fx_at(k):
    if k in FX: return FX[k]
    c = [x for x in FX if x <= k]
    return FX[max(c)] if c else 6.8

def build(lo, hi="2026-08"):
    """返回 (月份列表, {资产: 人民币全收益指数})"""
    keys = sorted(set(k for k in D["ndx_tr"] if lo <= k <= hi))
    out = {}
    for name in ["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"]:
        s = D[name]
        ks = sorted(s)
        base_fx = None
        series = []
        for k in keys:
            if k not in s: series.append(None); continue
            series.append(s[k])
        out[name] = series
    # 转人民币: 指数(美元) * 汇率
    for name in ["ndx_tr", "spx_tr"]:
        out[name] = [(v * fx_at(k) if v else None) for k, v in zip(keys, out[name])]
    return keys, out

def rets(series):
    r = [None]
    for i in range(1, len(series)):
        a, b = series[i - 1], series[i]
        r.append(b / a - 1 if (a and b) else None)
    return r

def stats(rv):
    """rv: 月收益列表"""
    v = 1.0; pk = 1.0; mdd = 0.0
    for r in rv:
        v *= (1 + r); pk = max(pk, v); mdd = min(mdd, v / pk - 1)
    n = len(rv)
    mu = sum(rv) / n
    sd = (sum((x - mu) ** 2 for x in rv) / (n - 1)) ** 0.5 * (12 ** 0.5)
    cagr = v ** (12.0 / n) - 1
    return dict(cagr=cagr, sd=sd, mdd=mdd, calmar=cagr / abs(mdd) if mdd else 0,
                sharpe=(cagr - 0.02) / sd if sd else 0, final=v)

NAMES = {"ndx_tr": "纳指100", "spx_tr": "标普500", "dvlow_tr": "A股红利低波", "fcf_tr": "A股自由现金流"}

# ================= A + B: 两个样本 =================
for lo, tag in [("2014-01", "【主样本】2014-01 ~ 2026-08 (13.6年, 四资产)"),
                ("2006-01", "【扩展样本】2006-01 ~ 2026-08 (20.6年, 无现金流腿)")]:
    keys, S = build(lo)
    R = {k: [x for x in rets(v) if x is not None] for k, v in S.items()}
    avail = [k for k in ["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"] if len(R[k]) > 12]
    print("=" * 88)
    print(tag)
    print("%-16s%9s%9s%9s%9s%9s" % ("资产", "CAGR", "波动", "最大回撤", "Calmar", "Sharpe"))
    for k in avail:
        s = stats(R[k])
        print("%-16s%8.2f%%%8.1f%%%8.1f%%%9.2f%9.2f" % (NAMES[k], s["cagr"] * 100, s["sd"] * 100,
              s["mdd"] * 100, s["calmar"], s["sharpe"]))
    print()
    print("  相关性矩阵 (月度收益, 人民币口径):")
    print("  %-16s" % "" + "".join("%12s" % NAMES[k][:6] for k in avail))
    for a in avail:
        row = "  %-16s" % NAMES[a]
        for b in avail:
            x, y = R[a], R[b]
            n = min(len(x), len(y))
            x = x[:n]; y = y[:n]
            mx = sum(x) / n; my = sum(y) / n
            cov = sum((x[i] - mx) * (y[i] - my) for i in range(n)) / (n - 1)
            sx = (sum((v - mx) ** 2 for v in x) / (n - 1)) ** 0.5
            sy = (sum((v - my) ** 2 for v in y) / (n - 1)) ** 0.5
            row += "%12.2f" % (cov / sx / sy)
        print(row)
    print()

# ================= C: 权重网格 =================
keys, S = build("2014-01")
R = {k: rets(v) for k, v in S.items()}
N = len(keys)
ok = [i for i in range(N) if all(R[k][i] is not None for k in R)]
IDX = ok

def port(w, rebal=12):
    """w: dict 资产->权重; 返回组合月收益"""
    s = {k: w[k] for k in w}
    out = []
    last_reb = 0
    for i in IDX:
        v0 = sum(s.values())
        for k in s:
            s[k] *= (1 + R[k][i])
        v = sum(s.values())
        out.append(v / v0 - 1)
        if (len(out)) % rebal == 0:
            for k in s: s[k] = v * w[k]
    return out

def grid(step=10, cap=0.6):
    res = []
    ws = [x / 100.0 for x in range(0, int(cap * 100) + 1, step)]
    combos = [c for c in itertools.product(ws, repeat=4) if abs(sum(c) - 1.0) < 1e-9]
    for c in combos:
        w = dict(zip(["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"], c))
        rv = port(w)
        st = stats(rv)
        res.append((st, c))
    return res

print("=" * 88)
print("【C】权重网格 (2014-2026, 年度再平衡, 一次性投入, 步长10%, 单资产上限60%)")
G = grid()
G.sort(key=lambda x: -x[0]["calmar"])
print("  Calmar 前 12 (收益回撤比最高):")
print("  %-10s%10s%10s%10s%10s%10s" % ("纳指/标普/红利低波/现金流", "CAGR", "波动", "回撤", "Calmar", "Sharpe"))
for st, c in G[:12]:
    print("  %-10s%9.2f%%%9.1f%%%9.1f%%%10.2f%10.2f" % (
        "%d/%d/%d/%d" % (c[0] * 100, c[1] * 100, c[2] * 100, c[3] * 100),
        st["cagr"] * 100, st["sd"] * 100, st["mdd"] * 100, st["calmar"], st["sharpe"]))
G.sort(key=lambda x: -x[0]["cagr"])
print("  CAGR 前 8:")
for st, c in G[:8]:
    print("  %-10s%9.2f%%%9.1f%%%9.1f%%%10.2f%10.2f" % (
        "%d/%d/%d/%d" % (c[0] * 100, c[1] * 100, c[2] * 100, c[3] * 100),
        st["cagr"] * 100, st["sd"] * 100, st["mdd"] * 100, st["calmar"], st["sharpe"]))

# 候选方案对比
print()
print("【C2】候选方案对比 (2014-2026, 年度再平衡)")
CAND = [
    ("全纳指", (1, 0, 0, 0)),
    ("全标普", (0, 1, 0, 0)),
    ("全红利低波", (0, 0, 1, 0)),
    ("等权 25×4", (0.25, 0.25, 0.25, 0.25)),
    ("美股60/A股40", (0.3, 0.3, 0.25, 0.15)),
    ("纳20/标30/红35/现15", (0.2, 0.3, 0.35, 0.15)),
    ("纳25/标25/红30/现20", (0.25, 0.25, 0.3, 0.2)),
    ("纳15/标25/红40/现20", (0.15, 0.25, 0.4, 0.2)),
    ("纳20/标20/红40/现20", (0.2, 0.2, 0.4, 0.2)),
    ("纳10/标30/红40/现20", (0.1, 0.3, 0.4, 0.2)),
]
print("  %-22s%9s%9s%9s%9s%9s" % ("方案", "CAGR", "波动", "回撤", "Calmar", "Sharpe"))
for nm, c in CAND:
    w = dict(zip(["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"], c))
    st = stats(port(w))
    print("  %-22s%8.2f%%%8.1f%%%8.1f%%%9.2f%9.2f" % (nm, st["cagr"] * 100, st["sd"] * 100,
          st["mdd"] * 100, st["calmar"], st["sharpe"]))

# ================= D: 定投口径 =================
print()
print("=" * 88)
print("【D】定投口径 (2014-01 起每月投1份, 年度再平衡) —— 你的实际场景")
def dca(c, rebal=12):
    w = dict(zip(["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"], c))
    s = {k: 0.0 for k in w}
    cum = 0.0; uw = 0.0
    hist = []
    for j, i in enumerate(IDX):
        cum += 1.0
        for k in s: s[k] += w[k]
        for k in s: s[k] *= (1 + R[k][i])
        v = sum(s.values())
        hist.append(v)
        if v / cum - 1 < uw: uw = v / cum - 1
        if (j + 1) % rebal == 0:
            for k in s: s[k] = v * w[k]
    final = sum(s.values())
    # XIRR
    def npv(r):
        return sum(-1 * (1 + r) ** (-(m + 1) / 12.0) for m in range(len(IDX))) + final * (1 + r) ** (-(len(IDX) - 1) / 12.0)
    lo_, hi_ = -0.5, 1.0
    for _ in range(100):
        mid = (lo_ + hi_) / 2
        if npv(mid) > 0: lo_ = mid
        else: hi_ = mid
    return dict(final=final, cum=cum, mult=final / cum, xirr=(lo_ + hi_) / 2, uw=uw, hist=hist)

print("  %-22s%10s%10s%10s%10s" % ("方案", "终值倍数", "XIRR", "最深浮亏", "终值"))
for nm, c in CAND:
    r = dca(c)
    print("  %-22s%9.2fx%9.2f%%%9.1f%%%10.0f" % (nm, r["mult"], r["xirr"] * 100, r["uw"] * 100, r["final"]))

# ================= E: 再平衡频率 =================
print()
print("【E】再平衡频率 (以 纳20/标20/红40/现20 为例)")
for rb, nm in [(1, "月度"), (3, "季度"), (6, "半年"), (12, "年度"), (9999, "不再平衡")]:
    w = dict(zip(["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr"], (0.2, 0.2, 0.4, 0.2)))
    st = stats(port(w, rb))
    r = dca((0.2, 0.2, 0.4, 0.2), rb)
    print("  %-10s CAGR %6.2f%%  回撤 %6.1f%%  Calmar %.2f   定投倍数 %.2fx  浮亏 %.1f%%" % (
        nm, st["cagr"] * 100, st["mdd"] * 100, st["calmar"], r["mult"], r["uw"] * 100))
