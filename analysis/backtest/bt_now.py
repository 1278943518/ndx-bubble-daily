# -*- coding: utf-8 -*-
"""均衡版 vs 进攻版：按"当前温度"分组的未来 1 年收益分布

修正: 缺失资产不再当作 0% 收益(hack), 而是要求整条腿+整段前瞻窗口都有数据。
产出两个版本:
  (A) 精确四资产  2014-01 ~ 2026-08  (fcf_tr 2013-01 才有, 且有缺口)
  (B) 三资产近似  2006-01 ~ 2026-08  (A股腿统一用 dvlow_tr 代表, 拉长样本做稳健性)
"""
import json, statistics as st

D = json.load(open("alloc_data.json", encoding="utf-8"))
S = json.load(open("ndx-repo/bubble_app/data.json", encoding="utf-8"))
FX = D["fx"]


def fx_at(k):
    if k in FX:
        return FX[k]
    c = [x for x in FX if x <= k]
    return FX[max(c)] if c else 6.8


# 月末泡沫分: 取当月最后一根周线
score = {}
for r in S["week"]:
    score[r["d"][:7]] = r["total"]

ALL = sorted({k for name in ("ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr") for k in D[name]})


def series(name, keys, usd=False):
    out = []
    for k in keys:
        v = D[name].get(k)
        if v is None:
            out.append(None)
        else:
            out.append(v * fx_at(k) if usd else v)
    return out


def fwd_bh(legs, i, m=12):
    """从第 i 月末起, 按权重买入并持有 m 个月的总收益; 任一腿缺数据返回 None"""
    v = 1.0
    for name, w, s in legs:
        a, b = s[i], s[i + m]
        if a is None or b is None or a <= 0:
            return None
        v *= 1 + w * (b / a - 1)
    return v - 1


PLANS = {
    "均衡版 30/30/25/15": {"ndx_tr": .30, "spx_tr": .30, "dvlow_tr": .25, "fcf_tr": .15},
    "进攻版 40/30/10/20": {"ndx_tr": .40, "spx_tr": .30, "dvlow_tr": .10, "fcf_tr": .20},
}
PLANS3 = {   # A股 40%/30% 全部用 dvlow_tr 代表(与 fcf 相关 0.87, 同风格包)
    "均衡版·近似 30/30/40": {"ndx_tr": .30, "spx_tr": .30, "dvlow_tr": .40},
    "进攻版·近似 40/30/30": {"ndx_tr": .40, "spx_tr": .30, "dvlow_tr": .30},
}


def run(plans, lo, hi, label):
    keys = [k for k in ALL if lo <= k <= hi]
    ser = {n: series(n, keys, usd=n in ("ndx_tr", "spx_tr")) for n in ("ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr")}
    rows = []
    for i, k in enumerate(keys):
        if k not in score or i + 12 >= len(keys):
            continue
        r = {}
        for pn, w in plans.items():
            legs = [(n, wt, ser[n]) for n, wt in w.items()]
            r[pn] = fwd_bh(legs, i, 12)
        if all(v is not None for v in r.values()):
            rows.append((k, score[k], r))
    print(f"\n{'='*72}\n{label}   实际样本 {rows[0][0]} ~ {rows[-1][0]}，{len(rows)} 个月\n{'='*72}")
    names = list(plans)
    a, b = names[0], names[1]

    def rep(tag, sel):
        print(f"── {tag}  n={len(sel)} ──")
        if not sel:
            print("   (无样本)\n"); return
        for n in names:
            v = [r[n] for _, _, r in sel]
            pos = sum(1 for x in v if x > 0) / len(v)
            print(f"   {n:22s} 中位 {st.median(v)*100:+6.1f}%  均值 {st.mean(v)*100:+6.1f}%  "
                  f"上涨 {pos*100:3.0f}%  最差 {min(v)*100:+6.1f}%")
        d = [r[b] - r[a] for _, _, r in sel]
        print(f"   {'进攻 - 均衡':22s} 中位 {st.median(d)*100:+6.1f}pp  均值 {st.mean(d)*100:+6.1f}pp  "
              f"进攻胜率 {sum(1 for x in d if x>0)/len(d)*100:3.0f}%")
        print()

    rep("全样本", rows)
    rep("总分 >= 70  ←当前 74.4 所在区间", [x for x in rows if x[1] >= 70])
    rep("总分 >= 80", [x for x in rows if x[1] >= 80])
    rep("总分 45 ~ 70", [x for x in rows if 45 <= x[1] < 70])
    rep("总分 < 45", [x for x in rows if x[1] < 45])
    hi70 = [x[0] for x in rows if x[1] >= 70]
    print(f"   总分>=70 的月份: {', '.join(hi70)}\n")


run(PLANS, "2014-01", "2026-08", "(A) 精确四资产版")
run(PLANS3, "2006-01", "2026-08", "(B) 三资产近似版（拉长样本做稳健性）")
