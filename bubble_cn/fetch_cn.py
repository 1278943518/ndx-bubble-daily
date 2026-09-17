# -*- coding: utf-8 -*-
"""A股温度计 · 数据抓取 + 双读数计算（云端管线模块）

用法:
    python bubble_cn/fetch_cn.py            # 抓取 + 计算 + 写 bubble_out/cn_scores.json

输出每条记录（周频）：
    d, mkt, val, est, bkg, crowd, senti, lev, new,
    peVal, peAll,          # 展示用原始 PE（未经跳变校正）
    pxVal, pxAll           # 标的走势：红利低波 / 中证全指 收盘，供走势图叠加

口径（2026-09-16 定稿，见《A股温度计-双读数口径回测-20260916》）:

    市场温度 = pr( 中证全指 000985 PE校正, 520周 )
    价值温度 = 0.55 × pr( 红利低波 H30269 PE校正, 520周 )
             + 0.30 × 全市场腿
             + 0.15 × pr( 红利低波成交额 ÷ 全A成交额, 520周 )

    全市场腿 = (0.20×情绪 + 0.20×杠杆 + 0.15×新买家) / 55 × 100   ← 分母是 55
    情绪     = √( pr(全A成交额÷流通市值) × pr(全A收盘÷52周最高) )
    杠杆     = pr(两融余额 ÷ A股流通市值)
    新买家   = pr(融资买入额 ÷ 全A成交额)

★ 两个必须固化的实现要点
  1. PE 序列必须做「跳变回溯校正」（成分股半年调整会让 PE 单周跳 ±13~59%）。
     原始 PE 序列每次全量重抓 → 全量重算校正 → **天然幂等**，不会重复放大。
     校正值只用于算分位；对外展示的 PE 绝对值仍用原始值。
  2. pr() 暖启动必须返回 NaN，不能填 50.0（否则形成精确 50.0 质量点污染统计）。

容灾设计：网络失败时回退到已提交的 bubble_data/cn_raw.pkl，
保证「A股抓不到」不会让整条云端管线挂掉，也不会清空页面上的 cn 节点。
"""
import datetime
import json
import os
import pickle
import urllib.request

import numpy as np
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
DATA = os.path.join(ROOT, "bubble_data")
OUT = os.path.join(ROOT, "bubble_out")
RAW_PKL = os.path.join(DATA, "cn_raw.pkl")
OUT_JSON = os.path.join(OUT, "cn_scores.json")

# 只保留两条读数所需：红利低波（价值）+ 中证全指（市场/分母）
CODES = {"val": "H30269", "all": "000985"}
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126",
      "Referer": "https://www.csindex.com.cn/"}


def log(*a):
    print("[cn]", *a, flush=True)


def _get(url, tries=4, timeout=60):
    """中证接口实测约 1/5 概率 read timeout，必须重试。"""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "ignore"))
        except Exception as e:                       # noqa: BLE001
            last = e
            log(f"  retry {i + 1}/{tries}: {type(e).__name__}")
    raise last


def _csi_pe(code):
    """指数 PE 日频。字段名叫 peg，实际是 PE（滚动市盈率）。"""
    d = _get(f"https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe?indexCode={code}")["data"]
    s = pd.Series({pd.to_datetime(x["tradeDate"]): float(x["peg"]) for x in d}).sort_index()
    return s[~s.index.duplicated(keep="last")]


def _csi_perf(code, field):
    """指数行情：close / tradingValue(成交额) / tradingVol / consNumber。"""
    d = _get("https://www.csindex.com.cn/csindex-home/perf/index-perf"
             f"?indexCode={code}&startDate=19900101&endDate=20261231")["data"]
    s = pd.Series({pd.to_datetime(x["tradeDate"]): pd.to_numeric(x.get(field), errors="coerce")
                   for x in d}).dropna().sort_index()
    return s[~s.index.duplicated(keep="last")]


def _margin():
    """东财两融历史。必须显式写 columns；LTSZ = A股流通市值。

    ⚠️ 这里不用 curl 子进程：云端 runner 与本地都要能跑，urllib 更稳。
    """
    rows, page = [], 1
    while page <= 25:
        url = ("https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPTA_RZRQ_LSHJ"
               "&columns=DIM_DATE,RZRQYE,RZMRE,LTSZ&sortColumns=DIM_DATE&sortTypes=-1"
               f"&pageSize=200&pageNumber={page}&source=WEB&client=WEB")
        j = None
        for i in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": UA["User-Agent"],
                                                           "Referer": "https://data.eastmoney.com/"})
                with urllib.request.urlopen(req, timeout=45) as r:
                    j = json.loads(r.read().decode("utf-8", "ignore"))
                break
            except Exception as e:                   # noqa: BLE001
                log(f"  两融 p{page} retry {i + 1}/3: {type(e).__name__}")
        rs = ((j or {}).get("result") or {}).get("data") or []
        if not rs:
            break
        rows += rs
        page += 1
    if not rows:
        raise RuntimeError("两融返回空")
    m = pd.DataFrame(rows)
    for c in ("RZRQYE", "RZMRE", "LTSZ"):
        m[c] = pd.to_numeric(m[c], errors="coerce")
    m["d"] = pd.to_datetime(m["DIM_DATE"])
    return m.sort_values("d").set_index("d")[["RZRQYE", "RZMRE", "LTSZ"]]


def fetch_raw():
    raw = {}
    for k, code in CODES.items():
        raw["pe_" + k] = _csi_pe(code)
        raw["px_" + k] = _csi_perf(code, "close")
        raw["amt_" + k] = _csi_perf(code, "tradingValue")
        log(f"  {code}: PE {len(raw['pe_' + k])} 条 / 行情 {len(raw['px_' + k])} 条")
    raw["margin"] = _margin()
    log(f"  两融: {len(raw['margin'])} 条, 最新 {raw['margin'].index[-1].date()}")
    return raw


def load_raw():
    """优先抓实时；失败回退到已提交的 pickle 缓存（并说明用了哪一份）。"""
    try:
        raw = fetch_raw()
        keep = {k: raw[k] for k in raw}
        old = {}
        if os.path.exists(RAW_PKL):
            with open(RAW_PKL, "rb") as f:
                old = pickle.load(f)
        # 逐序列取「更长的那份」：抓取偶发只返回部分分页时不会被截断
        for k, v in keep.items():
            if k in old and len(old[k]) > len(v):
                log(f"  {k}: 本次 {len(v)} 条 < 缓存 {len(old[k])} 条 → 用缓存")
                keep[k] = old[k]
        os.makedirs(DATA, exist_ok=True)
        with open(RAW_PKL, "wb") as f:
            pickle.dump(keep, f, protocol=4)
        return keep, "live"
    except Exception as e:                           # noqa: BLE001
        log(f"  ⚠️ 抓取失败({type(e).__name__}: {e}) → 回退缓存")
        if not os.path.exists(RAW_PKL):
            raise
        with open(RAW_PKL, "rb") as f:
            return pickle.load(f), "cache"


# ------------------------------------------------ 指标 -------------------------------------------------
def pr(s, window=520, min_p=52):
    """滚动分位（只用历史窗口，无前视）。暖启动期返回 NaN —— 不能填 50。"""
    v = s.values.astype(float)
    o = np.full(len(v), np.nan)
    for i in range(len(v)):
        if np.isnan(v[i]):
            continue
        h = v[max(0, i - window):i]
        h = h[~np.isnan(h)]
        if len(h) >= min_p:
            o[i] = (h < v[i]).mean() * 100
    return pd.Series(o, index=s.index)


def detect_jumps(s, mk, th=12.0, div=10.0):
    """口径跳变检测（周频，用全指作基准剔除真实市场波动）。"""
    chg, mkc = s.pct_change() * 100, mk.pct_change() * 100
    return chg[(chg.abs() >= th) & ((chg - mkc).abs() >= div)]


def back_adjust(s, jumps):
    """跳变回溯校正：跳变日 t 之前的全部历史 × (PE_t / PE_{t-1})。"""
    adj = s.copy().astype(float)
    for t in jumps.index:
        prev = s.index[s.index < t]
        if len(prev):
            adj[adj.index < t] *= s[t] / s[prev[-1]]
    return adj


def build_weekly(raw):
    m = raw["margin"]
    IDX = raw["px_all"].resample("W-FRI").last().dropna().index

    def al(s):
        return s.reindex(IDX, method="ffill")

    df = pd.DataFrame(index=IDX)
    for k in CODES:
        df["pe_" + k] = al(raw["pe_" + k])
        df["px_" + k] = al(raw["px_" + k])
        df["amt_" + k] = al(raw["amt_" + k])
    df["ltsz"] = al(m["LTSZ"] / 1e8)          # 亿元
    df["rzrq"] = al(m["RZRQYE"] / 1e8)
    df["rzmre"] = al(m["RZMRE"] / 1e8)
    return df.dropna()


def compute(df):
    jumps_val = detect_jumps(df["pe_val"], df["px_all"])
    jumps_all = detect_jumps(df["pe_all"], df["px_all"])
    pe_val_adj = back_adjust(df["pe_val"], jumps_val)
    pe_all_adj = back_adjust(df["pe_all"], jumps_all)
    # ⚠️ 诊断用「首值」比值：末值永远未被调整，比值恒为 1，看不出放大倍数
    log(f"  跳变：红利低波 {len(jumps_val)} 次 / 全指 {len(jumps_all)} 次"
        f"（对最早历史累计 ×{float(pe_val_adj.iloc[0] / df['pe_val'].iloc[0]):.3f} /"
        f" ×{float(pe_all_adj.iloc[0] / df['pe_all'].iloc[0]):.3f}）")

    turnover_all = df["amt_all"] / df["ltsz"] * 100
    pos_all = df["px_all"] / df["px_all"].rolling(52, min_periods=13).max()
    senti = np.sqrt(pr(turnover_all) * pr(pos_all))
    lev = pr(df["rzrq"] / df["ltsz"])
    new = pr(df["rzmre"] / df["amt_all"])
    mkt_leg = (0.20 * senti + 0.20 * lev + 0.15 * new) / 55 * 100

    t = pd.DataFrame(index=df.index)
    t["est"] = pr(pe_val_adj)                     # 估值腿
    t["bkg"] = mkt_leg                            # 全市场腿
    t["crowd"] = pr(df["amt_val"] / df["amt_all"])  # 板块拥挤度
    t["senti"], t["lev"], t["new"] = senti, lev, new
    t["val"] = 0.55 * t["est"] + 0.30 * t["bkg"] + 0.15 * t["crowd"]
    t["mkt"] = pr(pe_all_adj)                     # 市场温度（纯单一指标）
    t["pe_val"] = df["pe_val"].round(2)
    t["pe_all"] = df["pe_all"].round(2)
    # ★ 标的走势：走势图上要把「温度」与「对应标的」画在一起，所以要把指数价格带出去
    #   市场温度 ← 中证全指 000985；价值温度 ← 红利低波 H30269
    t["px_val"] = df["px_val"].round(2)
    t["px_all"] = df["px_all"].round(2)
    # 后续 52 周收益（红利低波价格指数，不含股息 → 绝对收益被低估，只看档间相对差）
    t["fwd_val"] = (df["px_val"].shift(-52) / df["px_val"] - 1) * 100
    return t, len(jumps_val), len(jumps_all)


LEVELS = [("P80-100", .80, 1.00, "警戒"), ("P60-80", .60, .80, "偏高"),
          ("P40-60", .40, .60, "中性"), ("P20-40", .20, .40, "偏低"),
          ("P0-20", 0.00, .20, "低位")]


def calibration(s, fwd):
    """★ 实盘口径：**该序列自己的全部有效样本**（≥52周窗口，即 pr() 有值）。

    为什么不用固定阈值线：实测 P80 对样本口径很敏感
    （价值温度在 n=592/332/232 下分别是 65.1 / 58.4 / 67.5）→ 与其报一条会漂的线，
    不如直接报「历史百分位」并让档位由分位数动态切，保证口径自洽。
    """
    v = s.dropna()
    q = {int(p * 100): round(float(v.quantile(p)), 1) for p in (0.20, 0.40, 0.60, 0.80)}
    cur = float(v.iloc[-1])
    out = {"n": int(len(v)), "from": v.index[0].strftime("%Y-%m-%d"),
           "cur": round(cur, 1), "pos": round(float((v < cur).mean()) * 100, 1),
           "q": q, "levels": []}
    f = fwd.reindex(v.index)
    for name, lo, hi, lab in LEVELS:
        left = v > v.quantile(lo) if lo > 0 else (v >= v.quantile(0.0))
        m = left & (v <= v.quantile(hi))
        r = f[m].dropna()
        if len(r) >= 5:
            out["levels"].append({"name": name, "lab": lab, "n": int(len(r)),
                                  "ret": round(float(r.mean()), 1),
                                  "win": round(float((r > 0).mean()) * 100)})
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    raw, src = load_raw()
    df = build_weekly(raw)
    t, n_jv, n_ja = compute(df)

    # 只输出两条读数都有效的部分（暖启动期自动被 NaN 剔除）
    ok = t.dropna(subset=["mkt", "val"])
    recs = []
    for d, r in ok.iterrows():
        rec = {"d": d.strftime("%Y-%m-%d"), "mkt": round(float(r["mkt"]), 1),
               "val": round(float(r["val"]), 1)}
        for k in ("est", "bkg", "crowd", "senti", "lev", "new"):
            rec[k] = round(float(r[k]), 1)
        rec["peVal"] = float(r["pe_val"])
        rec["peAll"] = float(r["pe_all"])
        rec["pxVal"] = float(r["px_val"])          # 红利低波 H30269 收盘（价值温度的标的）
        rec["pxAll"] = float(r["px_all"])          # 中证全指 000985 收盘（市场温度的标的）
        recs.append(rec)
    assert recs, "没有一条有效记录"

    now_bj = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    out = {
        "records": recs,
        "meta": {
            "updated": now_bj.strftime("%Y-%m-%d %H:%M"),
            "asof": recs[-1]["d"],
            "source": src,                                  # live / cache
            "jumps": {"val": n_jv, "all": n_ja},
            "hist": {"val": calibration(t["val"], t["fwd_val"]),
                     "mkt": calibration(t["mkt"], t["fwd_val"])},
            "caliber": "0.55/0.30/0.15 · 520周 · PE跳变回溯校正",
        },
    }
    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    assert "NaN" not in payload and "Infinity" not in payload, "payload 含非法数值!"
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(payload)

    last = recs[-1]
    log(f"✅ 写入 {OUT_JSON}  ({os.path.getsize(OUT_JSON) / 1024:.0f} KB)")
    log(f"   样本 {len(recs)} 周  {recs[0]['d']} ~ {last['d']}  数据源={src}")
    for k, nm in (("mkt", "市场温度"), ("val", "价值温度")):
        h = out["meta"]["hist"][k]
        log(f"   {nm} {h['cur']}　历史百分位 {h['pos']}%　P80={h['q'][80]}　"
            f"P60={h['q'][60]}　(n={h['n']} 自 {h['from']})")
    log(f"   分解：估值腿 {last['est']} × 0.55 + 全市场腿 {last['bkg']} × 0.30 "
        f"+ 拥挤度 {last['crowd']} × 0.15 = "
        f"{0.55 * last['est'] + 0.30 * last['bkg'] + 0.15 * last['crowd']:.1f}")
    for L in out["meta"]["hist"]["val"]["levels"]:
        log(f"   价值档 {L['name']} ({L['lab']}) n={L['n']}  后续52周 {L['ret']}%  胜率 {L['win']}%")


if __name__ == "__main__":
    main()
