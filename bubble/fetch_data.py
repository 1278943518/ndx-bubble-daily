# -*- coding: utf-8 -*-
"""
美股泡沫评分体系 - 数据拉取脚本
六大数据源 → 统一月度时间线（2016-01 ~ 2026-08）
数据源:
  1. 腾讯月K: usNDX(纳指100) + usINX(标普500)
  2. CBOE VIX 日度
  3. FRED: FEDFUNDS(联邦基金利率) + T10Y2Y(10Y-2Y利差)
  4. multpl CAPE 月度
  5. FINRA margin debt 月度
  6. CNN Fear&Greed 日度(含子指标: 市场宽度/动量/期权比等)
"""
import json, urllib.request, csv, io, datetime, ssl
import pandas as pd

OUT = "bubble_data"
import os
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

def http_get(url, headers=None, timeout=25, retries=3):
    ctx = ssl.create_default_context()
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={**UA, **(headers or {})})
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
                return r.read()
        except Exception as e:
            last = e
            print(f"  retry {i+1}/{retries} {url[:60]}... {e}")
    raise last

# ---------- 1. 腾讯月K ----------
def fetch_tencent(code):
    url = f"https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param={code},month,,,300,qfq"
    d = json.loads(http_get(url))
    rows = d["data"][code]["month"]
    out = []
    for r in rows:
        # [日期, 开, 收, 高, 低, 成交量, ...]
        out.append({"date": r[0], "open": float(r[1]), "close": float(r[2]),
                    "high": float(r[3]), "low": float(r[4]), "vol": float(r[5])})
    df = pd.DataFrame(out)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    return df

ndx = fetch_tencent("usNDX")
inx = fetch_tencent("usINX")
ndx.to_csv(f"{OUT}/ndx_month.csv")
inx.to_csv(f"{OUT}/inx_month.csv")
print("腾讯月K:", ndx.index[0].date(), "→", ndx.index[-1].date(), f"({len(ndx)}个月)")

# ---------- 2. VIX 日度 ----------
vix_raw = http_get("https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv", timeout=30)
vix_txt = vix_raw.decode("utf-8")
rows = list(csv.reader(io.StringIO(vix_txt)))
vix = pd.DataFrame(rows[1:], columns=["date", "open", "high", "low", "close"])
vix["date"] = pd.to_datetime(vix["date"], format="%m/%d/%Y")
vix["close"] = pd.to_numeric(vix["close"], errors="coerce")
vix = vix.dropna(subset=["close"]).set_index("date")["close"].sort_index()
vix.to_csv(f"{OUT}/vix_daily.csv")
print("VIX:", vix.index[0].date(), "→", vix.index[-1].date(), f"({len(vix)}个交易日)")

# ---------- 3. FRED (curl 下载, urllib 被 TLS 重置) ----------
import subprocess
def fetch_fred(series):
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    for i in range(3):
        try:
            txt = subprocess.run(["curl", "-s", "--max-time", "25", "-H", UA["User-Agent"], url],
                                 capture_output=True, check=True).stdout.decode("utf-8")
            rows = list(csv.reader(io.StringIO(txt)))
            df = pd.DataFrame(rows[1:], columns=["date", "val"])
            df["date"] = pd.to_datetime(df["date"])
            df["val"] = pd.to_numeric(df["val"], errors="coerce")
            return df.set_index("date")["val"].sort_index()
        except Exception as e:
            print(f"  FRED retry {i+1}: {e}")
    raise RuntimeError(f"FRED {series} 下载失败")

fedfunds = fetch_fred("FEDFUNDS")
t10y2y = fetch_fred("T10Y2Y")
fedfunds.to_csv(f"{OUT}/fedfunds_daily.csv")
t10y2y.to_csv(f"{OUT}/t10y2y_daily.csv")
print("FEDFUNDS:", fedfunds.index[0].date(), "→", fedfunds.index[-1].date())
print("T10Y2Y:", t10y2y.index[0].date(), "→", t10y2y.index[-1].date())

# ---------- 4. multpl CAPE ----------
cape_html = http_get("https://www.multpl.com/shiller-pe/table/by-month", timeout=30).decode("utf-8", "ignore")
import re
pairs = re.findall(r"<td[^>]*>([A-Z][a-z]{2} \d{1,2}, \d{4})</td>\s*<td[^>]*>\s*(?:&#x2002;)?\s*([\d.]+)", cape_html)
cape = pd.DataFrame(pairs, columns=["date", "cape"])
cape["date"] = pd.to_datetime(cape["date"], format="%b %d, %Y")
cape["cape"] = pd.to_numeric(cape["cape"])
cape = cape.set_index("date")["cape"].sort_index()
cape = cape[~cape.index.duplicated(keep="last")]
cape.to_csv(f"{OUT}/cape_month.csv")
print("CAPE:", cape.index[0].date(), "→", cape.index[-1].date(), f"({len(cape)}个月)")

# ---------- 5. FINRA margin debt ----------
import openpyxl
wb = openpyxl.load_workbook("finra_margin.xlsx", read_only=True)
ws = wb.active
rows = list(ws.iter_rows(values_only=True))
data = []
for r in rows[1:]:
    if r[0] and r[1] is not None:
        ym = str(r[0])
        try:
            dt = datetime.datetime.strptime(ym, "%Y-%m")
        except ValueError:
            continue
        data.append({"date": dt, "debit": float(r[1])})
margin = pd.DataFrame(data).set_index("date")["debit"].sort_index()
margin.to_csv(f"{OUT}/margin_month.csv")
print("FINRA margin:", margin.index[0].date(), "→", margin.index[-1].date(), f"({len(margin)}个月)")

# ---------- 6. CNN Fear&Greed ----------
fg_raw = http_get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                  headers={"Accept": "application/json", "Referer": "https://www.cnn.com/markets/fear-and-greed",
                           "Origin": "https://www.cnn.com",
                           "Cookie": "countryCode=US; isEU=false"}, timeout=30)
fg = json.loads(fg_raw)
hist = fg["fear_and_greed_historical"]["data"]
fg_df = pd.DataFrame(hist)
fg_df["x"] = pd.to_datetime(fg_df["x"], unit="ms")
fg_df = fg_df.set_index("x").sort_index()
fg_df.to_csv(f"{OUT}/fng_daily.csv")
print("Fear&Greed:", fg_df.index[0].date(), "→", fg_df.index[-1].date(), f"({len(fg_df)}个交易日) cols={list(fg_df.columns)}")
print("当前分:", fg["fear_and_greed"]["score"], fg["fear_and_greed"]["rating"])

print("\n全部数据源拉取完成 →", OUT)

# ---------- 7. ICI 股票基金月净流入 (新买家特征, s6 数据源) ----------
# 种子: bubble_data/ici_flows_monthly.csv (2007-01 起拼接版)
# 同步: 尝试从 datasets/investor-flow-of-funds-us 拉官方同步版; 有效则覆盖, 无效保留种子
import urllib.request as _ur
ici_path = f"{OUT}/ici_flows_monthly.csv"
try:
    _req = _ur.Request("https://raw.githubusercontent.com/datasets/investor-flow-of-funds-us/main/data/monthly.csv",
                       headers={"User-Agent": "Mozilla/5.0"})
    _raw = _ur.urlopen(_req, timeout=40).read().decode("utf-8")
    _lines = [l for l in _raw.strip().splitlines() if l.strip()]
    if len(_lines) > 50 and "Date" in _lines[0] and len(_lines[1].split(",")) >= 8:
        with open(ici_path, "w", encoding="utf-8") as f:
            f.write(_raw)
        print("ICI flows: 远程同步成功 →", len(_lines) - 1, "个月")
    else:
        print(f"ICI flows: 远程文件无效({len(_lines)}行), 保留本地种子")
except Exception as e:
    print("ICI flows: 同步失败(保留种子):", e)

# 本地种子兜底: 若文件不存在(首次云端运行且远程失败), 从仓库种子目录复制
import os as _os
if not _os.path.exists(ici_path):
    print("警告: ici_flows_monthly.csv 缺失, 请确认种子已提交至 bubble_data/")
