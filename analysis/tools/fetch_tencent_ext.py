# -*- coding: utf-8 -*-
"""一次性：腾讯月K/周K 1200 根扩展 → 更新 ndx_month/inx_month/ndx_week/inx_week"""
import json, urllib.request, csv, io

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def http_get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")

def fetch(code, ktype):
    url = f"https://web.ifzq.gtimg.cn/appstock/app/usfqkline/get?param={code},{ktype},,,1200,qfq"
    d = json.loads(http_get(url))
    k = d["data"][code]
    for key in k:
        if isinstance(k[key], list):
            rows = k[key]
            break
    out = []
    for r in rows:
        out.append({"date": r[0], "close": float(r[2])})
    return out

for code, name in [("usNDX", "ndx"), ("usINX", "inx")]:
    for ktype, fn in [("month", f"{name}_month.csv"), ("week", f"{name}_week.csv")]:
        rows = fetch(code, ktype)
        with open(f"bubble_data/{fn}", "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "close"])
            for r in rows:
                w.writerow([r["date"], r["close"]])
        print(f"{fn}: {len(rows)} 行, {rows[0]['date']} → {rows[-1]['date']}")
