# -*- coding: utf-8 -*-
"""
周频数据抓取: 腾讯 NDX/INX 周K + 东财(curl) ARKK 周K
其余(VIX/利率日度, CAPE/margin 月度)在 analyze_weekly.py 内重采样
"""
import json, urllib.request, subprocess, os, time
import pandas as pd

B = "bubble_data"
os.makedirs(B, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126"}

def http_get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=25) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception as e:
            print(f"  重试{i+1}: {str(e)[:60]}")
            time.sleep(2)
    raise RuntimeError(f"下载失败: {url[:80]}")

def parse_tx(text, code):
    d = json.loads(text)
    rows = d["data"][code]["week"]
    out = []
    for r in rows:
        # [date, open, close, high, low, volume, ...]
        out.append({"date": r[0], "open": float(r[1]), "close": float(r[2]),
                    "high": float(r[3]), "low": float(r[4]), "vol": float(r[5])})
    return out

def save(df, name):
    df.to_csv(os.path.join(B, name))
    print(f"  {name}: {len(df)} 行, {df.index[0].date()} → {df.index[-1].date()}")

# 1. 腾讯 NDX / INX 周K
for code, name in [("usNDX", "ndx_week.csv"), ("usINX", "inx_week.csv")]:
    print(f"拉取 {code} 周K...")
    txt = http_get(f"https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param={code},week,,,1200,qfq")
    rows = parse_tx(txt, code)
    df = pd.DataFrame(rows).set_index(pd.to_datetime(rows[0]["date"] if False else [r["date"] for r in rows]))
    df = df[["open", "close", "high", "low", "vol"]].sort_index()
    save(df, name)

# 2. 东财(curl) ARKK 周K (klt=102) —— urllib 被断连, 用 curl
print("拉取 ARKK 周K (curl)...")
url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=107.ARKK"
       "&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57"
       "&klt=102&fqt=1&beg=20100101&end=20261231&ut=fa5fd1943c7b386f172d6893dbfba10b")
tmp = os.path.join(B, "_arkk_w.json")
for i in range(3):
    r = subprocess.run(["curl", "-s", "--max-time", "25", "-A", "Mozilla/5.0", url, "-o", tmp],
                       capture_output=True, text=True)
    if os.path.exists(tmp) and os.path.getsize(tmp) > 1000:
        break
    print(f"  curl 重试{i+1}"); time.sleep(2)
with open(tmp, "r", encoding="utf-8") as f:
    d = json.load(f)
kl = d["data"]["klines"]
rows = []
for line in kl:
    p = line.split(",")
    rows.append({"date": p[0], "open": float(p[1]), "close": float(p[2]),
                 "high": float(p[3]), "low": float(p[4]), "vol": float(p[5])})
df = pd.DataFrame(rows).set_index(pd.to_datetime([r["date"] for r in rows]))
df = df[["open", "close", "high", "low", "vol"]].sort_index()
save(df, "arkk_week.csv")
os.remove(tmp)

print("\n周频数据全部就绪")

# ============ 3. FRED 历史补段 (可选增强) ============
# 腾讯接口仅返回 1200 根(周K=2003-08 起 / 月K=2000-01 起)。
# FRED NASDAQ100/SP500 日线全史可回溯到 1990s; 下载成功则拼接扩展历史,
# 失败(网络受限/境外源不可达)则静默保留腾讯段 —— 云端 GitHub runner 通常可用。
def patch_fred_history():
    import subprocess, io, os, csv
    def fred_series(series_id):
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        for _ in range(3):
            try:
                txt = subprocess.run(["curl", "-s", "--max-time", "30", "-H", "User-Agent: Mozilla/5.0", url],
                                     capture_output=True, check=True, timeout=60).stdout.decode("utf-8")
                rows = list(csv.reader(io.StringIO(txt)))
                if len(rows) < 100 or "date" not in rows[0][0].lower():
                    continue
                d = pd.DataFrame(rows[1:], columns=["date", "val"])
                d["date"] = pd.to_datetime(d["date"])
                d["val"] = pd.to_numeric(d["val"], errors="coerce")
                d = d.dropna().set_index("date")["val"].sort_index()
                d = d[d.index >= "1990-01-01"]
                return d
            except Exception:
                continue
        return None
    for sid, fn_week, fn_month, name in [
        ("NASDAQ100", "ndx_week.csv", "ndx_month.csv", "NDX"),
        ("SP500", "inx_week.csv", "inx_month.csv", "INX/SPX"),
    ]:
        try:
            s = fred_series(sid)
            if s is None:
                print(f"FRED {name}: 下载失败, 保留腾讯段")
                continue
            wk = s.resample("W-FRI").last().dropna()      # 周线(周五)
            mo = s.resample("M").last().dropna()          # 月线(月末)
            for ser, fn in ((wk, fn_week), (mo, fn_month)):
                path = os.path.join(B, fn)
                if not os.path.exists(path):
                    continue
                old = pd.read_csv(path, index_col=0, parse_dates=True)["close"]
                # 拼接: FRED 段只补腾讯起点之前的空档, 重叠/之后仍以腾讯为准
                old_start = old.index.min()
                hist = ser[ser.index < old_start]
                if len(hist) < 52:
                    print(f"FRED {name} {fn}: 补段过短({len(hist)}), 跳过")
                    continue
                # 重叠区比例对齐(FRED 与腾讯口径可能差常数倍)
                ov = ser[ser.index >= old_start].head(200)
                common = ov.index.intersection(old.index)
                if len(common) > 10:
                    ratio = (old.loc[common] / ov.loc[common]).median()
                    hist = hist * ratio
                    print(f"FRED {name} {fn}: 比例因子 {ratio:.4f}")
                merged = pd.concat([hist, old])
                merged = merged[~merged.index.duplicated(keep="last")].sort_index()
                out = pd.DataFrame({"close": merged})
                out.to_csv(path)
                print(f"FRED {name} {fn}: 扩展至 {merged.index.min().date()} ({len(merged)} 行)")
        except Exception as e:
            print(f"FRED {name} 补段异常(跳过):", e)

if __name__ == "__main__":
    patch_fred_history()
