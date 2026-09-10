# -*- coding: utf-8 -*-
"""下载并清洗配置回测所需数据 (全部人民币口径, 分红再投资)
标的: 纳指100 / 标普500 / 中证红利低波全收益(H20269) / 中证现金流(932365)
产出: alloc_data.json  (月度序列)
"""
import csv, json, urllib.request, datetime

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=%s&startDate=%s&endDate=20260908"

def csindex(code, start):
    url = BASE % (code, start)
    req = urllib.request.Request(url, headers=UA)
    raw = urllib.request.urlopen(req, timeout=60).read().decode("utf-8")
    d = json.loads(raw)
    out = {}
    for r in d.get("data") or []:
        c = r.get("close")
        if c: out[r["tradeDate"]] = float(c)
    return out

def monthly(series):
    """日频 -> 月末最后交易日"""
    m = {}
    for d in sorted(series):
        m[d[:6]] = series[d]
    return {k[:4] + "-" + k[4:6]: v for k, v in m.items()}

D = {}
# --- A股 ---
print("下载 H20269 红利低波全收益 ...")
D["dvlow_tr"] = monthly(csindex("H20269", "20050101"))
print("  %d 月, %s ~ %s" % (len(D["dvlow_tr"]), min(D["dvlow_tr"]), max(D["dvlow_tr"])))
print("下载 H30269 红利低波价格 ...")
D["dvlow_px"] = monthly(csindex("H30269", "20050101"))
print("下载 932365 中证现金流(价格) ...")
D["fcf_px"] = monthly(csindex("932365", "20130101"))
print("  %d 月, %s ~ %s" % (len(D["fcf_px"]), min(D["fcf_px"]), max(D["fcf_px"])))

# --- 汇率 CNY per USD ---
fx = {}
for r in csv.DictReader(open("bubble_data/usdcny.csv", encoding="utf-8")):
    try: fx[r["observation_date"][:7]] = float(r["EXCHUS"])
    except: pass
D["fx"] = fx
print("汇率 %d 月, %s ~ %s 最新 %.4f" % (len(fx), min(fx), max(fx), fx[max(fx)]))

# --- 标普500 全收益 (Shiller, 美元) ---
px, dv = {}, {}
for r in csv.DictReader(open("shiller.csv", encoding="utf-8")):
    try: px[r["Date"][:7]] = float(r["SP500"])
    except: pass
hdr = None
for r in csv.reader(open("shiller2.csv", encoding="utf-8")):
    if hdr is None: hdr = r; continue
    try:
        v = float(r[2])
        if v > 0: dv[r[0][:7]] = v
    except: pass
for r in csv.DictReader(open("shiller.csv", encoding="utf-8")):
    try:
        v = float(r["Dividend"])
        if v > 0 and r["Date"][:7] not in dv: dv[r["Date"][:7]] = v
    except: pass
lastdv = dv[max(dv)]
DV = []
for k in sorted(px):
    if k in dv: lastdv = dv[k]
    DV.append(lastdv)
KS = sorted(px)
spx = []
for i, k in enumerate(KS):
    d = dv.get(k, DV[i])
    spx.append((k, px[k], d))
# 全收益指数(美元, 股息再投)
tr = 1.0
SPX_TR = {}
prev_p = None; prev_d = None
for k, p, d in spx:
    if prev_p is not None:
        tr *= (p + d / 12.0) / prev_p
    SPX_TR[k] = tr
    prev_p, prev_d = p, d
D["spx_tr"] = SPX_TR
print("标普全收益 %d 月, %s ~ %s" % (len(SPX_TR), min(SPX_TR), max(SPX_TR)))

# --- 纳指100 (价格, 美元) + 股息再投近似 0.8%/年 ---
ndx = {}
for r in csv.DictReader(open("bubble_data/ndx_month.csv", encoding="utf-8")):
    try: ndx[r["date"][:7]] = float(r["close"])
    except: pass
NDX_TR = {}
t = 1.0
prev = None
for k in sorted(ndx):
    if prev is not None:
        t *= (ndx[k] / prev) * (1 + 0.008 / 12)     # 股息 0.8%/年 按月再投
    NDX_TR[k] = t
    prev = ndx[k]
D["ndx_tr"] = NDX_TR
print("纳指全收益(近似) %d 月, %s ~ %s" % (len(NDX_TR), min(NDX_TR), max(NDX_TR)))

# --- 中证现金流: 价格 -> 股息再投近似 3.5%/年 ---
FCF_TR = {}
t = 1.0
prev = None
for k in sorted(D["fcf_px"]):
    if prev is not None:
        t *= (D["fcf_px"][k] / prev) * (1 + 0.035 / 12)
    FCF_TR[k] = t
    prev = D["fcf_px"][k]
D["fcf_tr"] = FCF_TR

json.dump(D, open("alloc_data.json", "w", encoding="utf-8"), ensure_ascii=False)
print("\n已保存 alloc_data.json")
for k in ["ndx_tr", "spx_tr", "dvlow_tr", "fcf_tr", "fx"]:
    ks = sorted(D[k])
    print("  %-10s %4d月  %s ~ %s" % (k, len(ks), ks[0], ks[-1]))
