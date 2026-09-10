# -*- coding: utf-8 -*-
"""
第二轮: 优化候选指标设计
1. 现有 F1-F8 各自在2021时点的分位 + IC (找弱点)
2. 新候选:
   G. HYG/LQD 比值水平 (利差压缩代理, 高=贪婪)
   H. ARKK/NDX 相对动量 (投机vs大盘成长)
   I. ARKK 距12月高点回撤的绝对值分位
   J. HYG 距52周高点
3. 组合方案: 现有8特征 + 最佳新特征, 对比总分
"""
import pandas as pd, numpy as np, sys
sys.path.insert(0, "bubble")
from analyze import calc_pct

B = "bubble_data"
def load(name, col="close"):
    return pd.read_csv(f"{B}/{name}", index_col=0, parse_dates=True)[col]

ndx = load("ndx_month.csv"); inx = load("inx_month.csv")
vix = load("vix_daily.csv", "close").resample("ME").mean()
fed = load("fedfunds_daily.csv", "val").resample("ME").last()
cape = load("cape_month.csv", "cape")
margin = load("margin_month.csv", "debit")
arkk = load("arkk_month.csv"); hyg = load("hyg_month.csv")
jnk = load("jnk_month.csv"); lqd = load("lqd_month.csv")

df = pd.DataFrame(index=ndx.index)
df["ndx"] = ndx; df["inx"] = inx
df["vix"] = vix.reindex(df.index, method="ffill")
df["fed"] = fed.reindex(df.index, method="ffill")
df["cape"] = cape.reindex(df.index, method="ffill")
df["margin_lag"] = margin.reindex(df.index, method="ffill").shift(1)
df["arkk"] = arkk.reindex(df.index, method="ffill")
df["hyg"] = hyg.reindex(df.index, method="ffill")
df["jnk"] = jnk.reindex(df.index, method="ffill")
df["lqd"] = lqd.reindex(df.index, method="ffill")

vol = load("inx_month.csv", "vol")
df["vol"] = vol

# 现有特征 (对齐 analyze.py)
df["mom12"] = df["ndx"]/df["ndx"].shift(12)-1
vol6 = df["vol"].rolling(6, min_periods=3).mean()
vol6_prev12 = df["vol"].rolling(12, min_periods=6).mean().shift(6)
df["vol_chg12"] = vol6/vol6_prev12-1
df["hi52"] = df["ndx"].rolling(12, min_periods=6).max()
df["dd52"] = df["ndx"]/df["hi52"]-1
df["rel_mom12"] = (df["ndx"]/df["ndx"].shift(12)-1) - (df["inx"]/df["inx"].shift(12)-1)

feat = {
 "F1_cape": calc_pct(df["cape"], expanding=True),
 "F2_mom12": calc_pct(df["mom12"]),
 "F3_vixR": 100-calc_pct(df["vix"]),
 "F4_margin": calc_pct(df["margin_lag"]),
 "F5_vol": calc_pct(df["vol_chg12"]),
 "F6_dd52": calc_pct(df["dd52"]),
 "F8_relNDX": calc_pct(df["rel_mom12"]),
}

# 新候选
df["G_ratio"] = df["hyg"]/df["lqd"]                       # 利差压缩代理
df["H_arkkNDX"] = (df["arkk"]/df["arkk"].shift(12)-1) - (df["ndx"]/df["ndx"].shift(12)-1)
df["I_arkkDD"] = df["arkk"]/df["arkk"].rolling(12, min_periods=6).max()-1
df["J_hygDD"] = df["hyg"]/df["hyg"].rolling(12, min_periods=6).max()-1
df["K_hygrel"] = (df["hyg"]/df["hyg"].shift(12)-1) - (df["lqd"]/df["lqd"].shift(12)-1)
df["L_arkkMom"] = df["arkk"]/df["arkk"].shift(12)-1
df["M_arkkSPX"] = (df["arkk"]/df["arkk"].shift(12)-1) - (df["inx"]/df["inx"].shift(12)-1)

feat_new = {
 "G_hydRatio": calc_pct(df["G_ratio"]),
 "H_arkkNDX": calc_pct(df["H_arkkNDX"]),
 "I_arkkDD": calc_pct(df["I_arkkDD"]),
 "J_hygDD": calc_pct(df["J_hygDD"]),
 "K_hygRel12": calc_pct(df["K_hygrel"]),
 "L_arkkMom": calc_pct(df["L_arkkMom"]),
 "M_arkkSPX": calc_pct(df["M_arkkSPX"]),
}

fwd = df["ndx"].shift(-12)/df["ndx"]-1
df["fwd12"] = fwd

print("=== 现有特征 F1-F8 在关键时点分位 ===")
key = ["2021-02-26","2021-11-30","2022-10-31","2025-10-31","2026-08-31"]
print(f"{'时点':<12}" + "".join(f"{k:>9}" for k in feat))
for d in key:
    if d not in df.index: continue
    line = f"{d[:7]:<12}"
    for k, s in feat.items():
        line += f"{s.loc[d]:>9.0f}"
    print(line)

print("\n=== 现有特征 IC (分位 vs 未来12M收益) ===")
for k, s in feat.items():
    v = pd.concat([s, df["fwd12"]], axis=1).dropna()
    print(f"  {k}: IC = {v.iloc[:,0].corr(v['fwd12']):.3f} (n={len(v)})")

print("\n=== 新候选在关键时点分位 ===")
print(f"{'时点':<12}" + "".join(f"{k:>10}" for k in feat_new))
for d in key:
    if d not in df.index: continue
    line = f"{d[:7]:<12}"
    for k, s in feat_new.items():
        line += f"{s.loc[d]:>10.0f}"
    print(line)

print("\n=== 新候选 IC ===")
for k, s in feat_new.items():
    v = pd.concat([s, df["fwd12"]], axis=1).dropna()
    print(f"  {k}: IC = {v.iloc[:,0].corr(v['fwd12']):.3f} (n={len(v)})")

print("\n=== ARKK 原始走势参考 ===")
for d in ["2020-02-28","2021-02-26","2021-11-30","2022-10-31","2024-12-31","2026-08-31"]:
    if d in df.index:
        print(f"  {d}: ARKK={df['arkk'].loc[d]:.1f} (12M动量 {df['L_arkkMom'].loc[d]*100:+.0f}%)")
