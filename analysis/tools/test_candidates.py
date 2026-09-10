# -*- coding: utf-8 -*-
"""
候选指标评估 - 找出能揭示 2021 泡沫的指标
候选:
  A. ARKK/SPX 相对 12M 动量 (投机成长 vs 大盘)
  B. ARKK 12M 动量分位 (投机狂热本身)
  C. ARKK 距52周高点 (投机退潮)
  D. 信用利差代理: HYG/JNK 相对 LQD 12M 动量 (高收益债风险偏好)
  E. HYG 12M 动量 (信用风险偏好直接代理)
  F. NDX/SPX 相对动量 (已有 F8, 对照组)
评估: 每个指标在 2021-02/2021-11 的分位值 + 与未来12M收益的IC
"""
import pandas as pd, numpy as np
import sys
sys.path.insert(0, "bubble")
from analyze import calc_pct  # 复用分位函数

B = "bubble_data"
def load(name, col="close"):
    return pd.read_csv(f"{B}/{name}", index_col=0, parse_dates=True)[col]

ndx = load("ndx_month.csv")
inx = load("inx_month.csv")
arkk = load("arkk_month.csv")
hyg = load("hyg_month.csv")
jnk = load("jnk_month.csv")
lqd = load("lqd_month.csv")

df = pd.DataFrame(index=ndx.index)
df["ndx"] = ndx
df["inx"] = inx
df["arkk"] = arkk.reindex(df.index, method="ffill")
df["hyg"] = hyg.reindex(df.index, method="ffill")
df["jnk"] = jnk.reindex(df.index, method="ffill")
df["lqd"] = lqd.reindex(df.index, method="ffill")

# ---- 候选指标 ----
# A. ARKK/SPX 相对 12M 动量
df["A"] = (df["arkk"]/df["arkk"].shift(12)-1) - (df["inx"]/df["inx"].shift(12)-1)
# B. ARKK 12M 动量
df["B"] = df["arkk"]/df["arkk"].shift(12)-1
# C. ARKK 距52周高点
df["C"] = df["arkk"]/df["arkk"].rolling(12, min_periods=6).max()-1
# D. HY 相对 IG 12M 动量 (HYG vs LQD)
df["D"] = (df["hyg"]/df["hyg"].shift(12)-1) - (df["lqd"]/df["lqd"].shift(12)-1)
# E. HYG 12M 动量
df["E"] = df["hyg"]/df["hyg"].shift(12)-1
# F. NDX/SPX 相对 12M 动量 (对照组=已有F8)
df["F"] = (df["ndx"]/df["ndx"].shift(12)-1) - (df["inx"]/df["inx"].shift(12)-1)

# ---- 未来12M收益 (预测目标) ----
fwd = df["ndx"].shift(-12)/df["ndx"]-1
df["fwd12"] = fwd

print("=== 各指标在关键时点的滚动120月分位(高=泡沫信号强) ===")
print(f"{'时点':<12}" + "".join(f"{c:>8}" for c in "ABCDEF"))
key = {"2020-02-28":"2020.2疫情前顶", "2021-02-26":"2021.2成长顶", "2021-11-30":"2021.11纳指顶",
       "2022-10-31":"2022.10底部", "2025-10-31":"2025.10高位", "2026-08-31":"当前"}
for d, label in key.items():
    if d not in df.index: continue
    line = f"{label:<12}"
    for c in "ABCDEF":
        s = calc_pct(df[c].loc[:d], expanding=False)
        v = s.loc[d]
        line += f"{v:>8.0f}"
    print(line)

print("\n=== IC: 各指标分位 vs 未来12M收益 (越负越好, 高分预示低收益) ===")
for c in "ABCDEF":
    s = calc_pct(df[c])
    v = pd.concat([s, df["fwd12"]], axis=1).dropna()
    ic = v[0].corr(v["fwd12"]) if False else v.iloc[:,0].corr(v["fwd12"])
    print(f"  {c}: IC = {ic:.3f}  (n={len(v)})")

print("\n=== 原始指标值(非分位)在关键时点 ===")
pd.set_option("display.width", 200)
for c in "ABCDEF":
    print(f"\n[{c}] 描述: {df[c].describe()[['mean','std','min','50%','max']].round(3).to_dict()}")
    for d in ["2020-02-28","2021-02-26","2021-11-30","2022-10-31","2026-08-31"]:
        if d in df.index:
            print(f"  {d}: {df[c].loc[d]:.4f}")
