# -*- coding: utf-8 -*-
"""v22: 日投 vs 月投 实证 (回答"场外限购只能按日投, 和月投差多少")
方法: 对每个标的, 比较
  A. 每月固定某个交易日投入 (1/5/10/15/20/月末) -> 结果离散度 = "选日子的运气"
  B. 每日均摊投入 -> 单一确定结果
分离两种效应: 资金时间加权(日投平均晚半月) vs 选日运气(离散度)
"""
import json, csv, urllib.request, random, statistics

UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www.csindex.com.cn/csindex-home/perf/index-perf?indexCode=%s&startDate=%s&endDate=20260908"

def csindex(code, start):
    req = urllib.request.Request(BASE % (code, start), headers=UA)
    d = json.loads(urllib.request.urlopen(req, timeout=60).read().decode("utf-8"))
    out = {}
    for r in d.get("data") or []:
        if r.get("close"): out[r["tradeDate"]] = float(r["close"])
    return out

def eastmoney(secid):
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=%s"
           "&fields1=f1,f2&fields2=f51,f53&klt=101&fqt=1&beg=20130101&end=20500101&lmt=6000" % secid)
    try:
        req = urllib.request.Request(url, headers=UA)
        d = json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8"))
        kl = (d.get("data") or {}).get("klines") or []
        out = {}
        for line in kl:
            p = line.split(",")
            out[p[0]] = float(p[1])
        return out
    except Exception as e:
        return {}

SER = {}
print("下载日频数据 ...")
SER["红利低波全收益"] = csindex("H20269", "20130101")
print("  H20269  %d 日" % len(SER["红利低波全收益"]))
SER["中证现金流"] = csindex("932365", "20130101")
print("  932365  %d 日" % len(SER["中证现金流"]))
for sid, nm in [("100.NDX", "纳指100"), ("105.QQQ", "纳指100"), ("100.NDX100", "纳指100")]:
    v = eastmoney(sid)
    if len(v) > 500:
        SER[nm] = v
        print("  %s(%s)  %d 日" % (nm, sid, len(v)))
        break
    else:
        print("  %s(%s) 失败" % (nm, sid))

# 统一交易日
allk = None
for v in SER.values():
    ks = set(v)
    allk = ks if allk is None else (allk & ks)
DAYS = sorted(allk)
DAYS = [d for d in DAYS if d >= "20140101"]
print("\n共同交易日 %d 天: %s ~ %s" % (len(DAYS), DAYS[0], DAYS[-1]))

def month_key(d):
    return d[:6]

def xirr(cashflows):
    """cashflows: [(天数偏移, 金额)], 最后一笔为终值正数"""
    def npv(r):
        return sum(cf * (1 + r) ** (-t / 365.0) for t, cf in cashflows)
    lo, hi = -0.95, 3.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(mid) > 0: lo = mid
        else: hi = mid
    return (lo + hi) / 2

def invest_daily(px, days, total_per_month):
    """每日均摊: 每月的天数平分该月投入"""
    cfs = []
    shares = 0.0
    months = {}
    for d in days:
        months.setdefault(d[:6], []).append(d)
    t0 = 0
    for i, d in enumerate(days):
        m = d[:6]
        amt = total_per_month / len(months[m])
        shares += amt / px[d]
        cfs.append((i, -amt))
    final = shares * px[days[-1]]
    cfs.append((len(days) - 1, final))
    return xirr(cfs), final

def invest_monthly(px, days, total_per_month, daypick):
    """每月选第 daypick 个交易日投入; daypick=-1 表示月末"""
    months = {}
    for d in days:
        months.setdefault(d[:6], []).append(d)
    cfs = []
    shares = 0.0
    idx_of = {d: i for i, d in enumerate(days)}
    for m, ds in months.items():
        d = ds[-1] if daypick == -1 else ds[min(daypick, len(ds) - 1)]
        shares += total_per_month / px[d]
        cfs.append((idx_of[d], -total_per_month))
    final = shares * px[days[-1]]
    cfs.append((len(days) - 1, final))
    return xirr(cfs), final

print()
print("=" * 84)
print("【1】单资产: 月投(不同投日) vs 日投  —— XIRR")
print("  %-16s%10s%10s%10s%10s%10s" % ("标的", "日投", "月投均值", "月投最差", "月投最好", "极差"))
for nm, px in SER.items():
    px2 = {k: v for k, v in px.items() if k in set(DAYS)}
    x_d, _ = invest_daily(px2, DAYS, 1000)
    xs = []
    for dp in [0, 4, 9, 14, 19, -1]:
        x, _ = invest_monthly(px2, DAYS, 1000, dp)
        xs.append(x)
    print("  %-16s%9.2f%%%9.2f%%%9.2f%%%9.2f%%%9.2f%%" % (
        nm, x_d * 100, statistics.mean(xs) * 100, min(xs) * 100, max(xs) * 100,
        (max(xs) - min(xs)) * 100))

print()
print("【2】月投的'选日运气': 随机选投日 1000 次 (每月随机一个交易日)")
print("  %-16s%10s%10s%10s%10s" % ("标的", "日投XIRR", "随机均值", "标准差", "95%区间"))
random.seed(7)
for nm, px in SER.items():
    px2 = {k: v for k, v in px.items() if k in set(DAYS)}
    months = {}
    for d in DAYS:
        months.setdefault(d[:6], []).append(d)
    x_d, _ = invest_daily(px2, DAYS, 1000)
    sims = []
    for _ in range(300):
        shares = 0.0
        cfs = []
        idx_of = {d: i for i, d in enumerate(DAYS)}
        for m, ds in months.items():
            d = random.choice(ds)
            shares += 1000 / px2[d]
            cfs.append((idx_of[d], -1000))
        final = shares * px2[DAYS[-1]]
        cfs.append((len(DAYS) - 1, final))
        sims.append(xirr(cfs))
    sims.sort()
    print("  %-16s%9.2f%%%9.2f%%%9.2f%%   [%.2f%%, %.2f%%]" % (
        nm, x_d * 100, statistics.mean(sims) * 100, statistics.stdev(sims) * 100,
        sims[15] * 100, sims[-16] * 100))

print()
print("【3】组合层面 (纳指30/标普30/红利低波25/现金流15, 简化为等权可比资产)")
# 用可得资产等权近似组合
keys = list(SER.keys())
if len(keys) >= 2:
    px = {}
    months = {}
    for d in DAYS:
        months.setdefault(d[:6], []).append(d)
    # 等权组合净值(日频, 每日再平衡到等权)
    combo = {}
    hold = {k: 0.0 for k in keys}
    for i, d in enumerate(DAYS):
        if i == 0:
            for k in keys: hold[k] = 1.0 / len(keys)
        for k in keys:
            hold[k] *= SER[k][d] / SER[k][DAYS[i - 1]] if i > 0 else 1.0
        v = sum(hold.values())
        for k in keys: hold[k] = v / len(keys)
        combo[d] = v
    x_d, _ = invest_daily(combo, DAYS, 1000)
    xs = []
    for dp in [0, 4, 9, 14, 19, -1]:
        x, _ = invest_monthly(combo, DAYS, 1000, dp)
        xs.append(x)
    print("  等权组合(%s): 日投 %.2f%%   月投均值 %.2f%%   极差 %.2fpp" % (
        "+".join(k[:4] for k in keys), x_d * 100, statistics.mean(xs) * 100, (max(xs) - min(xs)) * 100))
