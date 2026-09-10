# -*- coding: utf-8 -*-
"""
第三轮: 组合测试 - 现有8特征 + 新F9(ARKK相对动量), 对比总分识别能力
组合:
  A. 基线: 现有 8 特征权重
  B. 8+F9(H_arkkNDX) 权重10% (从F5拿10%)
  C. 8+F9(H_arkkNDX) 权重15% (F5拿10% + F2拿5%)
  D. 8+F9 用 ARKK/SPX 相对动量(M) 权重10%
评估: 关键时点总分 + IC + 高低分区收益
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
arkk = load("arkk_month.csv")
vol = load("inx_month.csv", "vol")

df = pd.DataFrame(index=ndx.index)
df["ndx"] = ndx; df["inx"] = inx; df["vol"] = vol
df["vix"] = vix.reindex(df.index, method="ffill")
df["fed"] = fed.reindex(df.index, method="ffill")
df["cape"] = cape.reindex(df.index, method="ffill")
df["margin_lag"] = margin.reindex(df.index, method="ffill").shift(1)
df["arkk"] = arkk.reindex(df.index, method="ffill")

df["mom12"] = df["ndx"]/df["ndx"].shift(12)-1
vol6 = df["vol"].rolling(6, min_periods=3).mean()
vol6_prev12 = df["vol"].rolling(12, min_periods=6).mean().shift(6)
df["vol_chg12"] = vol6/vol6_prev12-1
df["hi52"] = df["ndx"].rolling(12, min_periods=6).max()
df["dd52"] = df["ndx"]/df["hi52"]-1
df["rel_mom12"] = (df["ndx"]/df["ndx"].shift(12)-1) - (df["inx"]/df["inx"].shift(12)-1)
df["arkk_ndx_mom"] = (df["arkk"]/df["arkk"].shift(12)-1) - (df["ndx"]/df["ndx"].shift(12)-1)
df["arkk_spx_mom"] = (df["arkk"]/df["arkk"].shift(12)-1) - (df["inx"]/df["inx"].shift(12)-1)

s = {}
s["F1"] = calc_pct(df["cape"], expanding=True)
s["F2"] = calc_pct(df["mom12"])
s["F3"] = 100 - calc_pct(df["vix"])
s["F4"] = calc_pct(df["margin_lag"])
s["F5"] = calc_pct(df["vol_chg12"])
s["F6"] = calc_pct(df["dd52"])
s["F8"] = calc_pct(df["rel_mom12"])
s["F9_ndx"] = calc_pct(df["arkk_ndx_mom"])
s["F9_spx"] = calc_pct(df["arkk_spx_mom"])
for k, v in s.items():
    df[k] = v

# 组合权重
combos = {
    "A 基线8特征":    {"F1":.20,"F2":.12,"F3":.10,"F4":.18,"F5":.10,"F6":.15,"F8":.15},
    "B 8+F9ndx@10%":  {"F1":.20,"F2":.12,"F3":.10,"F4":.18,"F5":0.0,"F6":.15,"F8":.15,"F9_ndx":.10},
    "C 8+F9ndx@15%":  {"F1":.20,"F2":.07,"F3":.10,"F4":.18,"F5":0.0,"F6":.15,"F8":.15,"F9_ndx":.15},
    "D 8+F9spx@10%":  {"F1":.20,"F2":.12,"F3":.10,"F4":.18,"F5":0.0,"F6":.15,"F8":.15,"F9_spx":.10},
}
for name, W in combos.items():
    assert abs(sum(W.values())-1) < 1e-9
    df[name] = sum(df[k]*w for k, w in W.items())

fwd = df["ndx"].shift(-12)/df["ndx"]-1
df["fwd12"] = fwd

print("=== 各组合在关键时点总分 ===")
key = ["2018-01-31","2018-12-31","2020-03-31","2021-02-26","2021-11-30",
       "2022-10-31","2024-12-31","2025-04-30","2025-10-31","2026-08-31"]
labels = {"2018-01-31":"2018.1顶","2018-12-31":"2018.12底","2020-03-31":"2020.3崩盘底",
          "2021-02-26":"2021.2成长顶","2021-11-30":"2021.11纳指顶","2022-10-31":"2022.10熊底",
          "2024-12-31":"2024.12高位","2025-04-30":"2025.4回调底","2025-10-31":"2025.10高位",
          "2026-08-31":"当前"}
print(f"{'时点':<12}" + "".join(f"{n[:6]:>10}" for n in combos))
for d in key:
    if d not in df.index: continue
    line = f"{labels[d]:<12}"
    for n in combos:
        line += f"{df[n].loc[d]:>10.1f}"
    print(line)

print("\n=== IC + 高低区收益对比 (≥70高热 / ≤45低估) ===")
for name in combos:
    v = df[[name, "fwd12"]].dropna()
    ic = v[name].corr(v["fwd12"])
    hi = df[df[name] >= 70]["fwd12"].dropna()
    lo = df[df[name] <= 45]["fwd12"].dropna()
    # 连续3月高低区
    hi3 = (df[name].rolling(3).mean() >= 70).values
    lo3 = (df[name].rolling(3).mean() <= 45).values
    hi3_fwd = df.loc[hi3, "fwd12"].dropna()
    lo3_fwd = df.loc[lo3, "fwd12"].dropna()
    print(f"  {name}: IC={ic:.3f} | 单月≥70 n={len(hi)} 后12M {hi.mean()*100:+.1f}% | ≤45 n={len(lo)} {lo.mean()*100:+.1f}% | 连续3月≥70 n={len(hi3_fwd)} {hi3_fwd.mean()*100:+.1f}% | ≤45 n={len(lo3_fwd)} {lo3_fwd.mean()*100:+.1f}%")

print("\n=== 2021-02 与 2021-11 各特征明细 (组合B) ===")
for d in ["2021-02-26","2021-11-30"]:
    r = df.loc[d]
    print(f"{d[:7]}: F1={r['F1']:.0f} F2={r['F2']:.0f} F3={r['F3']:.0f} F4={r['F4']:.0f} F5={r['F5']:.0f} F6={r['F6']:.0f} F8={r['F8']:.0f} F9={r['F9_ndx']:.0f} | 基线A={r['A 基线8特征']:.1f} 组合B={r['B 8+F9ndx@10%']:.1f}")
