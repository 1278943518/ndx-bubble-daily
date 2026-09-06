# -*- coding: utf-8 -*-
"""
美股泡沫评分体系 v2.0 - 特征构造 + 打分公式 + 回测
逻辑: 九特征 → 月度指标 → 滚动10年分位 → 0-100分 → 加权总分(特征7不计入)
v2.0 变更: 新增 F9 投机狂热(ARKK/NDX 相对12M动量, 单向加分), 替换原 F5 成交量
  - F5 成交量在 2021 泡沫期严重失真(2021-11 仅18分, IC=+0.054 无预测力)
  - F9 在 2021-02 投机顶给出 97-100 分, 比纳指顶提前 9 个月预警; IC 提升 -0.195→-0.235
权重对齐 RiskWatch: 特征1/4/6 为三大核心高权重
"""
import pandas as pd, numpy as np, json, os

B = "bubble_data"
os.makedirs("bubble_out", exist_ok=True)

def load(name, idxcol=0):
    df = pd.read_csv(f"{B}/{name}", index_col=idxcol, parse_dates=True)
    return df

# ============ 1. 数据装载 ============
ndx = load("ndx_month.csv")["close"]
inx = load("inx_month.csv")["close"]
vix = load("vix_daily.csv")["close"]
fed = load("fedfunds_daily.csv")["val"]
t10y2y = load("t10y2y_daily.csv")["val"]
cape = load("cape_month.csv")["cape"]
margin = load("margin_month.csv")["debit"]
arkk = load("arkk_month.csv")["close"]  # v2.0 新增: 投机成长ETF
fng = load("fng_daily.csv")  # 1年, 仅展示

# 统一月频: VIX/利率用月均(避免月末恐慌尖峰), 其余日度取月末
def to_month_mean(s):
    return s.resample("ME").mean()

def to_month_end(s):
    return s.resample("ME").last()

vix_m = to_month_mean(vix)
fed_m = to_month_end(fed)
t10_m = to_month_end(t10y2y)

# 成交量(标普500月成交量)
vol = load("inx_month.csv")["vol"]

# ============ 2. 特征构造 (月度) ============
df = pd.DataFrame(index=ndx.index)
df["ndx"] = ndx
df["inx"] = inx
df["vol"] = vol
df["vix"] = vix_m.reindex(df.index, method="ffill")
df["fed"] = fed_m.reindex(df.index, method="ffill")
df["t10y2y"] = t10_m.reindex(df.index, method="ffill")
df["cape"] = cape.reindex(df.index, method="ffill")
df["margin"] = margin.reindex(df.index, method="ffill")
df["arkk"] = arkk.reindex(df.index, method="ffill")
# margin 滞后 1 个月 (发布滞后, 无前视偏差)
df["margin_lag"] = df["margin"].shift(1)

# --- 特征1: 估值 CAPE (标普500) ---
df["F1_cape"] = df["cape"]

# --- 特征2: 预期继续上涨 = 12个月动量 ---
df["mom12"] = df["ndx"] / df["ndx"].shift(12) - 1

# --- 特征3: 看涨情绪 = VIX 分位反转 ---
df["F3_vix"] = df["vix"]

# --- 特征4: 杠杆 = margin debt 水平(滞后1月, 滚动分位) ---
df["margin_lag"] = df["margin"].shift(1)

# --- 特征5: 投机提前买入 (v2.0 替换) = ARKK/NDX 相对12M动量 ---
# ARKK 2021-02 见顶(比纳指早9个月), 相对动量极端时=投机狂热
df["arkk_ndx_mom"] = (df["arkk"] / df["arkk"].shift(12) - 1) - (df["ndx"] / df["ndx"].shift(12) - 1)

# --- 特征6: 新买家 = ICI 美国股票基金月净流入异常度 (v2.2 替换原"距52周高点距离") ---
# 数据: bubble_data/ici_flows_monthly.csv (ICI 官方, 2007-01 起, 百万美元)
# 构造: flows − 过去60个月滚动中位数(不含当月) → 异常度; 高分 = 新钱异常涌入
ici_flows = load("ici_flows_monthly.csv")["Total Equity"]
df["ici_anom"] = (ici_flows - ici_flows.rolling(60, min_periods=36).median().shift(1)).reindex(df.index, method="ffill")

# --- 特征7: 货币宽松 (不计入总分) ---
df["F7_fed"] = df["fed"]

# --- 特征8: 科技泡沫 = 纳指100/标普500 相对12个月收益 ---
ndx_m12 = df["ndx"] / df["ndx"].shift(12) - 1
inx_m12 = df["inx"] / df["inx"].shift(12) - 1
df["rel_mom12"] = ndx_m12 - inx_m12

# ============ 3. 打分公式: 滚动10年分位 → 0-100 ============
def calc_pct(s, window=120, expanding=False):
    """每个时点: 过去window个月中 < 当前值 的占比 × 100 (滚动分位)"""
    vals = s.values.astype(float)
    n = len(vals)
    out = np.full(n, np.nan)
    for i in range(n):
        v = vals[i]
        if np.isnan(v):
            out[i] = 50.0          # 数据缺失期(ARKK/ICI 等未覆盖段)给中性分
            continue
        start = 0 if expanding else max(0, i - window)
        hist = vals[start:i]  # 不含当前(避免自引用)
        hist = hist[~np.isnan(hist)]
        if len(hist) < 12:
            out[i] = 50.0
        else:
            out[i] = (hist < v).mean() * 100
    return pd.Series(out, index=s.index)

# 特征1: CAPE 高分位 → 高分 (expanding, 历史够长)
f1 = calc_pct(df["cape"], expanding=True)
# 特征2: 动量高分位 → 高分
f2 = calc_pct(df["mom12"])
# 特征3: VIX 低分位 → 高分(情绪高涨)
f3 = 100 - calc_pct(df["F3_vix"])
# 特征4: margin 水平高分位 → 高分
f4 = calc_pct(df["margin_lag"])
# 特征5 (v2.0): ARKK/NDX 相对动量高分位 → 投机狂热高分 (单向加分)
f5_raw = calc_pct(df["arkk_ndx_mom"])
# ARKK 2014-10 才上市: 缺失期保持中性 50(否则 clip 会把中性压成 0)
arkk_na = df["arkk_ndx_mom"].isna().values
f5 = np.where(arkk_na, 50.0, np.clip((f5_raw - 50) * 2, 0, 100))  # 仅50分位以上贡献, 消退不拖累
# 特征6: 基金流入异常度高 → 高分 (新买家涌入)
f6 = calc_pct(df["ici_anom"])
# 特征7: 利率低分位 → 宽松高分 (不计入总分)
f7 = 100 - calc_pct(df["F7_fed"])
# 特征8: 科技相对动量高分位 → 高分
f8 = calc_pct(df["rel_mom12"])

df["s1"] = f1; df["s2"] = f2; df["s3"] = f3; df["s4"] = f4
df["s5"] = f5; df["s6"] = f6; df["s7"] = f7; df["s8"] = f8
df["f5_raw"] = f5_raw  # 保留原始分位供参考

# ============ 4. 总分 (特征7不计入, 权重对齐RiskWatch) ============
W = {"s1": 0.20, "s2": 0.12, "s3": 0.10, "s4": 0.18, "s5": 0.10,
     "s6": 0.15, "s8": 0.15}
assert abs(sum(W.values()) - 1.0) < 1e-9
df["total"] = sum(df[k] * w for k, w in W.items())

# 只保留 2000 起 (腾讯月K 1200根 = 2000-01 起)
df = df[df.index >= "2000-01-01"]
df.to_csv("bubble_out/scores_monthly.csv")
print("月度得分表已生成:", len(df), "个月,", df.index[0].date(), "→", df.index[-1].date())

# ============ 5. 关键时点检查 ============
key_dates = {
    "2018-01-31": "2018.1 高点(加息缩表前)",
    "2018-12-31": "2018.12 低点(紧缩恐慌)",
    "2020-03-31": "2020.3 疫情崩盘低点",
    "2021-02-26": "2021.2 投机成长顶(ARKK)",
    "2021-11-30": "2021.11 纳指顶(成长泡沫)",
    "2022-10-31": "2022.10 加息熊市底",
    "2024-12-31": "2024.12 AI牛市高点",
    "2025-04-30": "2025.4 关税回调低点",
    "2025-10-31": "2025.10 高位(PE36.4)",
    "2026-07-31": "2026.7 回调低点",
    "2026-08-31": "2026.8 当前",
}
print("\n=== 关键时点得分 ===")
print(f"{'日期':<12}{'总分':>6}{'F1估':>6}{'F2期':>6}{'F3绪':>6}{'F4杠':>6}{'F5狂':>6}{'F6新':>6}{'F7币':>6}{'F8科':>6}")
for d, label in key_dates.items():
    if d in df.index:
        r = df.loc[d]
        print(f"{d[:7]:<12}{r['total']:>6.1f}{r['s1']:>6.0f}{r['s2']:>6.0f}{r['s3']:>6.0f}"
              f"{r['s4']:>6.0f}{r['s5']:>6.0f}{r['s6']:>6.0f}{r['s7']:>6.0f}{r['s8']:>6.0f}  {label}")

# ============ 6. 回测验证 ============
print("\n=== 回测验证 ===")

# 6.1 分数 → 未来12个月收益(预测力检验, 样本外思想)
fwd = df["ndx"].shift(-12) / df["ndx"] - 1
df["fwd12"] = fwd
valid = df[["total", "fwd12"]].dropna()
bins = pd.qcut(valid["total"], 4, labels=["Q1低分", "Q2", "Q3", "Q4高分"])
grp = valid.groupby(bins, observed=True)["fwd12"].agg(["mean", "median", "count"])
print("\n总分四分位 → 未来12个月纳指100收益:")
print(grp.round(3))
ic = valid["total"].corr(valid["fwd12"])
print(f"\n总分与未来12M收益相关系数(IC): {ic:.3f} (负=高分预示低收益, 越负越有效)")

# 6.2 高低点识别: 连续3个月 ≥70分 → 高风险标记; ≤45分 → 低风险标记; 拐点(3月内降≥20分)
df["hi3"] = df["total"].rolling(3).mean() >= 70
df["lo3"] = df["total"].rolling(3).mean() <= 45
df["chg3"] = df["total"] - df["total"].shift(3)
df["inflect"] = df["chg3"] <= -20  # 3个月总分下降≥20 = 拐点预警
hi_periods = df[df["hi3"]].index
lo_periods = df[df["lo3"]].index
inf_periods = df[df["inflect"]].index
print("\n连续3月均≥70分(高风险区)月份数:", len(hi_periods), "| 连续3月均≤45分(低风险区)月份数:", len(lo_periods), "| 拐点预警月份数:", len(inf_periods))
# 高风险区后12个月的平均收益
hi_fwd = df.loc[hi_periods, "fwd12"].dropna()
lo_fwd = df.loc[lo_periods, "fwd12"].dropna()
print(f"高风险区(≥70)之后12M平均收益: {hi_fwd.mean()*100:.1f}% (n={len(hi_fwd)})")
print(f"低风险区(≤45)之后12M平均收益: {lo_fwd.mean()*100:.1f}% (n={len(lo_fwd)})")

# 6.3 高低点列表
print("\n高分区间(≥70, 连续3月)核心时点:")
seen = []
for d in hi_periods:
    if not seen or (d - seen[-1]).days > 200:
        seen.append(d)
        print(f"  {d.date()} 总分{df.loc[d,'total']:.1f} → 后12M {df.loc[d,'fwd12']*100:+.0f}%")
print("\n低分区间(≤45, 连续3月)核心时点:")
seen = []
for d in lo_periods:
    if not seen or (d - seen[-1]).days > 200:
        seen.append(d)
        print(f"  {d.date()} 总分{df.loc[d,'total']:.1f} → 后12M {df.loc[d,'fwd12']*100:+.0f}%")
print("\n拐点预警(3月降≥20分)核心时点:")
seen = []
for d in inf_periods:
    if not seen or (d - seen[-1]).days > 200:
        seen.append(d)
        print(f"  {d.date()} 总分{df.loc[d,'total']:.1f} (3月变化 {df.loc[d,'chg3']:+.1f})")

# 6.4 当前状态
cur = df.iloc[-1]
print(f"\n=== 当前({cur.name.date()}): 总分 {cur['total']:.1f} ===")
print(f"  特征: 估值{cur['s1']:.0f} 预期{cur['s2']:.0f} 情绪{cur['s3']:.0f} 杠杆{cur['s4']:.0f} 投机狂热{cur['s5']:.0f}(原始分位{cur['f5_raw']:.0f}) 新买家{cur['s6']:.0f} 货币{cur['s7']:.0f} 科技{cur['s8']:.0f}")
zone = "高热区(≥65)" if cur["total"] >= 65 else ("偏暖(50-65)" if cur["total"] >= 50 else ("中性(40-50)" if cur["total"] >= 40 else "低温区(<40)"))
print(f"  区域: {zone}")
print(f"  历史分位: {100*(df['total']<cur['total']).mean():.0f}%")
