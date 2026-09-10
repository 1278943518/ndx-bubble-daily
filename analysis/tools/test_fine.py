# -*- coding: utf-8 -*-
"""
第四轮: 精细验证
1. 相同窗口(2016+) 对比 IC
2. F9 权重敏感度 (5% / 8% / 10%)
3. 2021-02 后总分持续性 (是否持续高危)
4. F9 独立预警: F9≥85 的时点列表
5. 2021-11 时 F9 为什么低 → 检验两阶段泡沫
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

def total(w_f9, w_f5=0.10, w_f2=0.12):
    """F9 从 F5 拿权重; 若 F5 减到 0 再从 F2 拿"""
    f5 = max(0, w_f5 - w_f9)
    rem = w_f9 - w_f5
    f2 = w_f2 - max(0, rem)
    W = {"F1":.20,"F2":f2,"F3":.10,"F4":.18,"F5":f5,"F6":.15,"F8":.15,"F9":w_f9}
    assert abs(sum(W.values())-1) < 1e-9, W
    return sum(df[k]*w for k, w in W.items())

df["T_A"] = total(0.00)
df["T_B5"] = total(0.05)
df["T_B8"] = total(0.08)
df["T_B10"] = total(0.10)

fwd = df["ndx"].shift(-12)/df["ndx"]-1
df["fwd12"] = fwd

print("=== 相同窗口 2016+ 对比 ===")
d16 = df[df.index >= "2016-01-01"].dropna(subset=["fwd12"])
for name in ["T_A","T_B5","T_B8","T_B10"]:
    v = d16[[name, "fwd12"]].dropna()
    ic = v[name].corr(v["fwd12"])
    hi = d16[d16[name] >= 70]["fwd12"].dropna()
    lo = d16[d16[name] <= 45]["fwd12"].dropna()
    print(f"  {name}: IC={ic:.3f} (n={len(v)}) | ≥70 n={len(hi)} {hi.mean()*100:+.1f}% | ≤45 n={len(lo)} {lo.mean()*100:+.1f}%")

print("\n=== 2021-02 到 2021-11 月度总分走势 ===")
print(f"{'月份':<12}{'T_A':>7}{'T_B10':>8}{'F9':>6}{'F5':>6}")
for d in ["2021-02-26","2021-03-31","2021-05-31","2021-07-30","2021-09-30","2021-11-30","2022-01-31","2022-03-31"]:
    if d in df.index:
        r = df.loc[d]
        print(f"{d[:7]:<12}{r['T_A']:>7.1f}{r['T_B10']:>8.1f}{r['F9']:>6.0f}{r['F5']:>6.0f}")

print("\n=== F9 ≥ 85 (投机狂热预警) 历史时点 ===")
seen = []
for d, v in df["F9"].items():
    if v >= 85 and d >= "2016-01-01":
        if not seen or (d - seen[-1][0]).days > 200:
            seen.append((d, v))
            r = df.loc[d]
            print(f"  {d.date()} F9={v:.0f} 总分T_B10={r['T_B10']:.1f} → 后12M {r['fwd12']*100:+.0f}%" if not np.isnan(r['fwd12']) else f"  {d.date()} F9={v:.0f} 总分T_B10={r['T_B10']:.1f}")

print("\n=== 2021-11 为何识别弱: F3/F5 失真检查 ===")
for d in ["2021-11-30"]:
    r = df.loc[d]
    print(f"  VIX={df['vix'].loc[d]:.1f} (分位反转F3={r['F3']:.0f}) | 成交量chg12={df['vol_chg12'].loc[d]*100:+.0f}% (F5={r['F5']:.0f}) | ARKK相对NDX动量={df['arkk_ndx_mom'].loc[d]*100:+.0f}% (F9={r['F9']:.0f})")

# 检查2021-11时VIX与成交量的原始值
print("\n  VIX 2021全年: " + ", ".join(f"{m[0][:7]}={m[1]:.1f}" for m in df['vix'].loc['2021-01-31':'2021-12-31'].items()))
print("  VOL 2021: " + ", ".join(f"{m[0][:7]}={m[1]/1e6:.0f}M" for m in df['vol'].loc['2020-11-30':'2021-12-31'].items()))
