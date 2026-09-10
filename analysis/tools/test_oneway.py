# -*- coding: utf-8 -*-
"""
第五轮: 单向加分方案 - F9 只在投机狂热时贡献, 消退不拖累
F9c = max(0, (f9-50)*2)  # 50分位以下=0, 100分位=100
对比: 基线A / 替换F5(B) / 单向加分(E)
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

s = {}
s["F1"] = calc_pct(df["cape"], expanding=True)
s["F2"] = calc_pct(df["mom12"])
s["F3"] = 100 - calc_pct(df["vix"])
s["F4"] = calc_pct(df["margin_lag"])
s["F5"] = calc_pct(df["vol_chg12"])
s["F6"] = calc_pct(df["dd52"])
s["F8"] = calc_pct(df["rel_mom12"])
s["F9"] = calc_pct(df["arkk_ndx_mom"])
for k, v in s.items():
    df[k] = v
df["F9c"] = np.clip((df["F9"] - 50) * 2, 0, 100)  # 单向加分

# 组合: E = F9c 10% 从F5拿10%
df["E"] = 0.20*df["F1"] + 0.12*df["F2"] + 0.10*df["F3"] + 0.18*df["F4"] + 0.00*df["F5"] \
          + 0.15*df["F6"] + 0.15*df["F8"] + 0.10*df["F9c"]
# 组合: F = F9c 15% (F5拿10% + F2拿5%)
df["F"] = 0.20*df["F1"] + 0.07*df["F2"] + 0.10*df["F3"] + 0.18*df["F4"] + 0.00*df["F5"] \
          + 0.15*df["F6"] + 0.15*df["F8"] + 0.15*df["F9c"]

fwd = df["ndx"].shift(-12)/df["ndx"]-1
df["fwd12"] = fwd

print("=== 关键时点: 基线A(旧) vs 单向E vs 单向F ===")
key = {"2018-01-31":"2018.1顶","2018-12-31":"2018.12底","2020-03-31":"2020.3崩盘",
       "2021-02-26":"2021.2成长顶","2021-11-30":"2021.11纳指顶","2022-10-31":"2022.10熊底",
       "2024-12-31":"2024.12高位","2025-10-31":"2025.10高位","2026-08-31":"当前"}
print(f"{'时点':<12}{'A基线':>7}{'E单向10%':>10}{'F单向15%':>10}{'F9原始':>7}{'F9c':>6}")
for d, label in key.items():
    if d not in df.index: continue
    r = df.loc[d]
    print(f"{label:<12}{df.loc[d,'T_A'] if 'T_A' in df.columns else '':>7}" + f"{r['E']:>10.1f}{r['F']:>10.1f}{r['F9']:>7.0f}{r['F9c']:>6.0f}")

# 手动算A
df["T_A"] = 0.20*df["F1"] + 0.12*df["F2"] + 0.10*df["F3"] + 0.18*df["F4"] + 0.10*df["F5"] \
            + 0.15*df["F6"] + 0.15*df["F8"]
print("\n(修正) 关键时点总分:")
print(f"{'时点':<12}{'A基线':>7}{'E单向10%':>10}{'F单向15%':>10}")
for d, label in key.items():
    if d not in df.index: continue
    print(f"{label:<12}{df['T_A'].loc[d]:>7.1f}{df['E'].loc[d]:>10.1f}{df['F'].loc[d]:>10.1f}")

print("\n=== 相同窗口2016+ 回测对比 ===")
d16 = df[df.index >= "2016-01-01"].dropna(subset=["fwd12"])
for name in ["T_A","E","F"]:
    v = d16[[name, "fwd12"]].dropna()
    ic = v[name].corr(v["fwd12"])
    hi = d16[d16[name] >= 70]["fwd12"].dropna()
    lo = d16[d16[name] <= 45]["fwd12"].dropna()
    hi3 = d16.loc[d16[name].rolling(3).mean() >= 70, "fwd12"].dropna()
    lo3 = d16.loc[d16[name].rolling(3).mean() <= 45, "fwd12"].dropna()
    print(f"  {name}: IC={ic:.3f} | ≥70 n={len(hi)} {hi.mean()*100:+.1f}% | ≤45 n={len(lo)} {lo.mean()*100:+.1f}% | 3月≥70 n={len(hi3)} {hi3.mean()*100:+.1f}% | 3月≤45 n={len(lo3)} {lo3.mean()*100:+.1f}%")

print("\n=== 2021-02 ~ 2022-03 逐月 (方案E) ===")
for d in ["2021-02-26","2021-03-31","2021-05-31","2021-07-30","2021-09-30","2021-11-30","2022-01-31","2022-03-31"]:
    if d in df.index:
        r = df.loc[d]
        print(f"  {d[:7]}: A={r['T_A']:.1f} E={r['E']:.1f} F9={r['F9']:.0f} F9c={r['F9c']:.0f}")
