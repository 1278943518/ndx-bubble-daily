# -*- coding: utf-8 -*-
"""
美股泡沫评分体系 v2.1 - 周频版
变更:
  1. 月频 → 周频: 滚动10年分位(520周), 动量用52周, 距高点用52周窗口, margin滞后4周
  2. F5 单向加分修复: 原 clip((分位-50)*2,0,100) 把50-100分位压扁(72分位→44分)
     改为 s5 = max(原始分位, 50): 刻度与其它特征一致(50=中性), 消退期不再下探(单向思想保留)
"""
import pandas as pd, numpy as np, os

B = "bubble_data"
os.makedirs("bubble_out", exist_ok=True)

def load(name, idxcol=0):
    return pd.read_csv(f"{B}/{name}", index_col=idxcol, parse_dates=True)

# ============ 1. 数据装载 (周频) ============
ndx = load("ndx_week.csv")["close"]
inx = load("inx_week.csv")["close"]
arkk = load("arkk_week.csv")["close"]
vix = load("vix_daily.csv")["close"]
fed = load("fedfunds_daily.csv")["val"]
t10y2y = load("t10y2y_daily.csv")["val"]
cape = load("cape_month.csv")["cape"]
margin = load("margin_month.csv")["debit"]

# 周频化: VIX/利率取周均/周末值, CAPE/margin 月度ffill
# 注意: 先 .ffill() 再 reindex —— reindex 会精确匹配"存在的NaN行"而不向前填充
vix_w = vix.resample("W-FRI").mean().ffill()
fed_w = fed.dropna().resample("W-FRI").last().ffill()
t10_w = t10y2y.dropna().resample("W-FRI").last().ffill()

# ============ 2. 特征构造 (周频) ============
df = pd.DataFrame(index=ndx.index)
df["ndx"] = ndx
df["inx"] = inx.reindex(df.index, method="ffill")
df["arkk"] = arkk.reindex(df.index, method="ffill")
df["vix"] = vix_w.reindex(df.index, method="ffill")
df["fed"] = fed_w.reindex(df.index, method="ffill")
df["t10y2y"] = t10_w.reindex(df.index, method="ffill")
df["cape"] = cape.reindex(df.index, method="ffill")
df["margin"] = margin.reindex(df.index, method="ffill")
# margin 滞后 4 周 (发布滞后, 无前视偏差)
df["margin_lag"] = df["margin"].shift(4)

df["F1_cape"] = df["cape"]
# 特征2: 预期继续上涨 = 52周动量
df["mom52"] = df["ndx"] / df["ndx"].shift(52) - 1
df["F3_vix"] = df["vix"]
# 特征5: 投机狂热 = ARKK/NDX 相对52周动量
df["arkk_ndx_mom"] = (df["arkk"] / df["arkk"].shift(52) - 1) - (df["ndx"] / df["ndx"].shift(52) - 1)
# 特征6: 新买家 = ICI 美国股票基金月净流入异常度 (v2.2 替换原"距52周高点距离")
# 数据: bubble_data/ici_flows_monthly.csv (ICI 官方月度实际值, 2007-01 起, 百万美元)
# 构造: flows − 过去60个月滚动中位数(不含当月) → 异常度; 周频化用 ffill (同 CAPE/margin)
ici = pd.read_csv(f"{B}/ici_flows_monthly.csv", index_col=0, parse_dates=True)["Total Equity"]
ici_anom = ici - ici.rolling(60, min_periods=36).median().shift(1)
df["ici_anom"] = ici_anom.reindex(df.index, method="ffill")
df["F7_fed"] = df["fed"]
# 特征8: 科技泡沫 = NDX/INX 相对52周收益
df["rel_mom52"] = (df["ndx"] / df["ndx"].shift(52) - 1) - (df["inx"] / df["inx"].shift(52) - 1)

# ============ 3. 打分: 滚动520周分位 (10年) ============
def calc_pct(s, window=520, expanding=False, min_p=52):
    vals = s.values.astype(float)
    n = len(vals)
    out = np.full(n, np.nan)
    for i in range(n):
        v = vals[i]
        if np.isnan(v):
            out[i] = 50.0          # 数据不足(如ARKK早期)时给中性分, 避免NaN污染总分
            continue
        start = 0 if expanding else max(0, i - window)
        hist = vals[start:i]
        hist = hist[~np.isnan(hist)]
        out[i] = 50.0 if len(hist) < min_p else (hist < v).mean() * 100
    return pd.Series(out, index=s.index)

f1 = calc_pct(df["cape"], expanding=True)          # 估值: CAPE 高分位 → 高分
f2 = calc_pct(df["mom52"])                          # 预期: 动量高分位 → 高分
f3 = 100 - calc_pct(df["F3_vix"])                   # 情绪: VIX 低分位 → 高分
f4 = calc_pct(df["margin_lag"])                     # 杠杆: margin 高分位 → 高分
f5_raw = calc_pct(df["arkk_ndx_mom"])               # 投机: 相对动量高分位
f5 = np.maximum(f5_raw, 50)                         # 修复: 单向加分但刻度一致(50=中性)
f6 = calc_pct(df["ici_anom"])                           # 新买家: 基金流入异常度高 → 高分
f7 = 100 - calc_pct(df["F7_fed"])                   # 货币: 利率低 → 宽松 (不计分)
f8 = calc_pct(df["rel_mom52"])                      # 科技: 相对动量高分位

df["s1"] = f1; df["s2"] = f2; df["s3"] = f3; df["s4"] = f4
df["s5"] = f5; df["s6"] = f6; df["s7"] = f7; df["s8"] = f8
df["f5_raw"] = f5_raw

# ============ 4. 总分 ============
W = {"s1": 0.20, "s2": 0.12, "s3": 0.10, "s4": 0.18, "s5": 0.10, "s6": 0.15, "s8": 0.15}
assert abs(sum(W.values()) - 1.0) < 1e-9
df["total"] = sum(df[k] * w for k, w in W.items())

df = df[df.index >= "2003-01-01"]   # 周频数据 2003-08 起(腾讯1200根); FRED 补段后自动更早
df.to_csv("bubble_out/scores_weekly.csv")
print("周频得分表已生成:", len(df), "周,", df.index[0].date(), "→", df.index[-1].date())

# ============ 5. 关键时点 (周频对齐) ============
key_dates = {
    "2018-01-26": "2018.1 高点(加息缩表前)",
    "2018-12-28": "2018.12 低点(紧缩恐慌)",
    "2020-03-27": "2020.3 疫情崩盘低点",
    "2021-02-26": "2021.2 投机成长顶(ARKK)",
    "2021-11-26": "2021.11 纳指顶(成长泡沫)",
    "2022-10-28": "2022.10 加息熊市底",
    "2024-12-20": "2024.12 AI牛市高点",
    "2025-04-04": "2025.4 关税回调低点(4.7)",
    "2025-10-31": "2025.10 高位",
    "2026-03-27": "2026.3 回调低点",
    "2026-07-31": "2026.7 回调低点",
    "2026-08-31": "2026.8 当前",
}
print("\n=== 关键时点得分 ===")
print(f"{'日期':<12}{'总分':>6}{'F1估':>6}{'F2期':>6}{'F3绪':>6}{'F4杠':>6}{'F5狂':>6}{'F6新':>6}{'F7币':>6}{'F8科':>6}")
for d, label in key_dates.items():
    if d in df.index:
        r = df.loc[d]
        print(f"{d:<12}{r['total']:>6.1f}{r['s1']:>6.0f}{r['s2']:>6.0f}{r['s3']:>6.0f}"
              f"{r['s4']:>6.0f}{r['s5']:>6.0f}{r['s6']:>6.0f}{r['s7']:>6.0f}{r['s8']:>6.0f}  {label}")

# ============ 6. 回测验证 ============
print("\n=== 回测验证 (周频) ===")
fwd = df["ndx"].shift(-52) / df["ndx"] - 1
df["fwd52"] = fwd
valid = df[["total", "fwd52"]].dropna()
bins = pd.qcut(valid["total"], 4, labels=["Q1低分", "Q2", "Q3", "Q4高分"])
grp = valid.groupby(bins, observed=True)["fwd52"].agg(["mean", "median", "count"])
print("\n总分四分位 → 未来52周纳指100收益:")
print(grp.round(3))
ic = valid["total"].corr(valid["fwd52"])
print(f"\nIC(总分 vs 未来52周收益): {ic:.3f}")

df["hi13"] = df["total"].rolling(13).mean() >= 70
df["lo13"] = df["total"].rolling(13).mean() <= 45
df["chg13"] = df["total"] - df["total"].shift(13)
df["inflect"] = df["chg13"] <= -20
hi_periods = df[df["hi13"]].index
lo_periods = df[df["lo13"]].index
inf_periods = df[df["inflect"]].index
print(f"\n高风险周(13周均≥70): {len(hi_periods)} | 低风险周(13周均≤45): {len(lo_periods)} | 拐点预警(13周降≥20): {len(inf_periods)}")
hi_fwd = df.loc[hi_periods, "fwd52"].dropna()
lo_fwd = df.loc[lo_periods, "fwd52"].dropna()
print(f"高风险区后52周平均收益: {hi_fwd.mean()*100:.1f}% (n={len(hi_fwd)})")
print(f"低风险区后52周平均收益: {lo_fwd.mean()*100:.1f}% (n={len(lo_fwd)})")

print("\n拐点预警(13周降≥20分)核心时点:")
seen = []
for d in inf_periods:
    if not seen or (d - seen[-1]).days > 120:
        seen.append(d)
        print(f"  {d.date()} 总分{df.loc[d,'total']:.1f} (13周变化 {df.loc[d,'chg13']:+.1f})")

# 当前状态
cur = df.iloc[-1]
print(f"\n=== 当前({cur.name.date()}): 总分 {cur['total']:.1f} ===")
print(f"  特征: 估值{cur['s1']:.0f} 预期{cur['s2']:.0f} 情绪{cur['s3']:.0f} 杠杆{cur['s4']:.0f} 投机{cur['s5']:.0f}(原始分位{cur['f5_raw']:.0f}) 新买家流入{cur['s6']:.0f} 货币{cur['s7']:.0f} 科技{cur['s8']:.0f}")
zone = "高热区(≥70)" if cur["total"] >= 70 else ("偏高区(55-70)" if cur["total"] >= 55 else ("中性区(45-55)" if cur["total"] >= 45 else "低估区(<45)"))
print(f"  区域: {zone}")
