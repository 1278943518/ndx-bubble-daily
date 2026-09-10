# -*- coding: utf-8 -*-
"""
ARKK / TLT 历史月K 下载脚本 (Stooq PoW 反爬绕过)
- Stooq 返回 HTML 含 SHA-256 PoW 挑战: 找 n 使 sha256(c+n) 前 d 位为 0
- 提交 /__verify 获取 cookie, 再带 cookie 下载 CSV
- 另备用: FRED 信用利差 (重试机制)
"""
import re, hashlib, urllib.request, urllib.parse, http.cookiejar, csv, io, time
import pandas as pd

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

def solve_pow(html):
    """解析 PoW 挑战, 返回 (c, d)"""
    c = re.search(r'const c="([^"]+)"', html)
    d = re.search(r',d="?(\d+)"?[,)]', html) or re.search(r'd=(\d+),', html) or re.search(r'",d=(\d+)', html)
    if not c:
        return None
    return c.group(1), int(d.group(1)) if d else 4

def fetch_stooq(symbol, period="m"):
    """下载 stooq CSV, 自动绕过 PoW"""
    url = f"https://stooq.com/q/d/l/?s={symbol}&i={period}"
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [(k, v) for k, v in UA.items()]
    for attempt in range(4):
        try:
            with opener.open(url, timeout=30) as r:
                body = r.read().decode("utf-8", "ignore")
            if body.startswith("<!DOCTYPE") or "<script" in body[:500]:
                # PoW 挑战页
                solved = solve_pow(body)
                if not solved:
                    print("  PoW 解析失败, 页面前缀:", body[:120].replace("\n", " "))
                    return None
                c, d = solved
                print(f"  PoW 挑战: d={d} 找 nonce...")
                n = 0
                prefix = "0" * d
                while True:
                    h = hashlib.sha256((c + str(n)).encode()).hexdigest()
                    if h.startswith(prefix):
                        break
                    n += 1
                    if n > 50_000_000:
                        print("  PoW 超时")
                        return None
                verify_url = "https://stooq.com/__verify"
                data = urllib.parse.urlencode({"c": c, "n": str(n)}).encode()
                req = urllib.request.Request(verify_url, data=data, headers={**UA, "Content-Type": "application/x-www-form-urlencoded"})
                with opener.open(req, timeout=30) as r:
                    r.read()
                print(f"  PoW 通过 (n={n}), 重试下载...")
                time.sleep(0.5)
                continue
            if body.strip():
                return body
        except Exception as e:
            print(f"  attempt {attempt+1} fail: {str(e)[:80]}")
            time.sleep(1)
    return None

def download(symbol, out_path):
    txt = fetch_stooq(symbol)
    if not txt:
        print(f"{symbol}: 下载失败")
        return None
    rows = list(csv.reader(io.StringIO(txt)))
    if len(rows) < 2:
        print(f"{symbol}: 无数据")
        return None
    df = pd.DataFrame(rows[1:], columns=["date", "open", "high", "low", "close", "vol"])
    df["date"] = pd.to_datetime(df["date"])
    for col in ["open", "high", "low", "close", "vol"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"]).set_index("date").sort_index()
    df.to_csv(out_path)
    print(f"{symbol}: {df.index[0].date()} → {df.index[-1].date()} ({len(df)}个月) → {out_path}")
    return df

if __name__ == "__main__":
    import os
    os.makedirs("bubble_data", exist_ok=True)
    download("arkk.us", "bubble_data/arkk_month.csv")
    download("tlt.us", "bubble_data/tlt_month.csv")
    download("iwm.us", "bubble_data/iwm_month.csv")
    download("xbi.us", "bubble_data/xbi_month.csv")
