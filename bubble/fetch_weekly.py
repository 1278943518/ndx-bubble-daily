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
    txt = http_get(f"https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param={code},week,,,800,qfq")
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
