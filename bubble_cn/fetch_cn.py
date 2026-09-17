# -*- coding: utf-8 -*-
"""A股温度计 · 数据抓取 + 四读数计算（云端管线模块）

用法:
    python bubble_cn/fetch_cn.py            # 抓取 + 计算 + 写 bubble_out/cn_scores.json

输出每条记录（周频）：
    d, mkt, val,                       # 主读数：市场温度 / 价值温度
    gro, sty,                          # ★ 参考读数：成长温度 / 风格温度（仅供参考，不参与决策）
    est, bkg, crowd, senti, lev, new,  # 价值温度的四条腿（用于页面拆解）
    groEst,                            # 成长温度的估值腿（参考）
    peVal, peAll, peGro,               # 展示用原始 PE（未经跳变校正）
    pxVal, pxValTr, pxAll, pxGro       # 标的走势：红利低波价格 / 红利低波全收益 / 中证全指 / 800成长

口径（2026-09-17 第 15 轮更新）:
    市场温度 = pr( 中证全指 000985 PE校正, 520周 )                   ← 纯单一指标
    价值温度 = 0.55 × pr( 红利低波估值腿PE校正, 520周 )
             + 0.30 × 全市场腿
             + 0.15 × pr( 红利低波成交额 ÷ 全A成交额, 520周 )
    成长温度 = 0.55 × pr( 中证800成长 H30355 PE校正, 520周 )        ← ★ 参考读数
             + 0.30 × 全市场腿 + 0.15 × pr( 800成长成交额 ÷ 全A成交额, 520周 )
    风格温度 = pr( zdet( 800成长PE校正 ÷ 红利低波估值腿PE校正, 260周 ), 520周 )   ← ★ 参考读数

    全市场腿 = (0.20×情绪 + 0.20×杠杆 + 0.15×新买家) / 55 × 100   ← 分母是 55
    情绪     = √( pr(全A成交额÷流通市值) × pr(全A收盘÷52周最高) )
    杠杆     = pr(两融余额 ÷ A股流通市值)
    新买家   = pr(融资买入额 ÷ 全A成交额)

★★ 第 15 轮两处口径变更（详见 `A股温度计-历史拓展到2005-验证-20260917.html`）

  【变更一 · 历史从 2015-02 拓到 2012-10】样本 592 → 715 周
    根因：原来的 build_weekly() 把 `pe_val`（红利低波 PE，只有 2013-12-05 起）放进了 dropna
    的必要列 → 整个周表被它拖到 2013-12 才开始。而 pr() 是 520 周滚动，
    **2015-02-27 时窗口只有 12 个点，到 2024-01 才第一次凑满 520 周** ——
    也就是说页面上 2015~2023 的历史读数长期处在暖启动期，噪声很大。
    改法：① dropna 不再要求 pe_val；② 2013-12-05 之前的估值腿用**中证红利 000922 的 PE
    按 junction 比值 k 拼接**（k ≈ 0.95084，见 build_pe_est）。
    ★ 副作用可控：520 周窗口的起点在 2016 年，**拼接段早已退出最新读数的窗口**，
      所以今天的读数与拓前逐位相同（价值 69.0 / 市场 55.2）。
    ★ 诚实标注：红利低波指数 2013-12-05 才发布，之前的历史是**中证事后回算**的（有前视/幸存者偏差），
      且 000922 与 H30269 组合不同（分位腿平均差 13 分）。拓展段的"收益"不能当当时真能拿到的，
      但它检验的是"当时的估值分位能不能预测后面"——这一点仍然有效。

  【变更二 · 成长/风格读数回归，标注「仅供参考」】
    2026-09-16 曾因"维护麻烦 + 与市场温度冗余"砍掉。实测两者与市场温度的 Spearman 分别是
    **+0.792（成长）** 与 +0.494（风格），确实高度冗余 → **不进仓位决策，只在页面上作参考**。
    标的判决（2026-09-17 复测，目标 = 自身价格指数后续 52 周）：
      H30355 中证800成长  −0.367（最好，P80+ 档 −15.1%/胜率 22%），但 PE 只到 2014-05-21
      000918 沪深300成长  −0.329，历史多 3.5 年（PE 自 2011-06-28），两者成长温度相关 0.872
      000958 创业成长     +0.043（无效，方向还反）→ 弃
    → 取 **H30355**；000918 作长样本备选。风格温度的目标指数用中证全指（价格）。

★ 三个必须固化的实现要点
  1. PE 序列必须做「跳变回溯校正」（成分股半年调整会让 PE 单周跳 ±13~59%）。
     原始 PE 序列每次全量重抓 → 全量重算校正 → **天然幂等**，不会重复放大。
     校正值只用于算分位；对外展示的 PE 绝对值仍用原始值。
     ⚠️ 拼接序列的校正口径是「**先拼接、再对整条序列 back_adjust**」，不是分段各自校正 ——
       因为拼接段是用 junction 当天的比值锚定到 H30269 的**跳变前**水平的，
       junction 之后出现的跳变必须一并缩放到拼接段，否则两段基准不一致。
  2. pr() 暖启动必须返回 NaN，不能填 50.0（否则形成精确 50.0 质量点污染统计）。
  3. ★ **收益口径用「全收益」而不是「价格」**（第 11 轮修正）：
     红利低波价格指数 H30269 **不含股息**，用户实持的 563020 含分红（≈4.94pp/年），
     用价格指数算"后续 52 周收益"会系统性低估约 5pp，且走势图与用户账户对不上。
     → 展示与统计统一改用 **H20269 中证红利低波全收益指数**（同组合、同 PE，只多了股息再投）。
       实测它与 563020 前复权净值年化只差 +0.13pp、周收益相关 0.9928 → 可以当 ETF 的完整历史用。
       ⚠️ ETF 本身只有 143 周（2023-12-15 上市），**不能**直接当走势图的线。
       ⚠️ 成长/风格是**参考**读数，其目标用价格指数（H30355 / 000985），口径与价值温度不同，
          页面必须注明，不要横向比收益数字。

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

# 读数所需：红利低波（价值）+ 中证全指（市场/分母）
CODES = {"val": "H30269", "all": "000985"}
# ★ 展示/统计用的「含股息」标的：中证红利低波动**全收益**指数。
#   与 H30269 同组合、同 PE，只多了股息再投（实测年化差 ≈ 4.94pp）。
#   它与用户实持的 563020 前复权净值几乎重合（年化差 +0.13pp、周相关 0.9928），
#   而 ETF 自身只有 143 周（2023-12-15 上市）→ 走势图用这条指数线代替 ETF。
TR_CODE = "H20269"
# ★ 第 15 轮：红利低波 PE 只有 2013-12-05 起（= 指数发布日），
#   用它当估值腿会把整个周表拖到 2013-12 才开始 → 用中证红利 000922 的 PE（2011-06-28 起）补前段。
PROXY_CODE = "000922"
# ★ 第 15 轮：参考读数的成长标的（中证800成长）。见文件头「标的判决」。
GRO_CODE = "H30355"
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
    """指数 PE 日频。字段名叫 peg，实际是 PE（滚动市盈率）。

    ⚠️ 不要给这个接口传 &startDate=20050101 之类去"延长历史" ——
       它只会让返回的首点日期跟着变，但 **值恒等于真实首日的值**（回声点），不是真数据。
       中证指数估值的硬地板是 2011-06-28（= 开始发布估值数据之日）。
    """
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
    raw["px_valtr"] = _csi_perf(TR_CODE, "close")
    log(f"  {TR_CODE} 红利低波全收益: 行情 {len(raw['px_valtr'])} 条")
    # ★ 估值腿的拼接代理（2011-06-28 起，比红利低波自己的 PE 早 2.4 年）
    raw["pe_proxy"] = _csi_pe(PROXY_CODE)
    log(f"  {PROXY_CODE} 中证红利 PE（拼接代理）: {len(raw['pe_proxy'])} 条, "
        f"起 {raw['pe_proxy'].index[0].date()}")
    # ★ 参考读数：成长标的
    raw["pe_gro"] = _csi_pe(GRO_CODE)
    raw["px_gro"] = _csi_perf(GRO_CODE, "close")
    raw["amt_gro"] = _csi_perf(GRO_CODE, "tradingValue")
    log(f"  {GRO_CODE} 中证800成长: PE {len(raw['pe_gro'])} 条"
        f"（起 {raw['pe_gro'].index[0].date()}）/ 行情 {len(raw['px_gro'])} 条")
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
    """滚动分位（只用历史窗口，无前视）。暖启动期返回 NaN —— 不能填 50。

    ⚠️ 副作用提醒：窗口没凑满时用的是「扩张窗口」（有多少用多少，只要 >= min_p）。
       所以**周表起点必须尽量早**，否则早期读数全在暖启动期。
       第 15 轮就是靠这个诊断发现「原版 2015-02 只有 12 个点」。
    """
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


def zdet(s, w=260):
    """去趋势：相对自身滚动均值/标准差的 z 分数（风格比价用）。"""
    m = s.rolling(w, min_periods=52).mean()
    d = s.rolling(w, min_periods=52).std()
    return (s - m) / d


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


def build_pe_est(df):
    """估值腿的 PE 序列（**未校正**）+ 拼接元信息。

    2013-12-05（红利低波 PE 的首日 = 指数发布日）之前，用中证红利 000922 的 PE
    按 junction 当天的比值 k 拼接。k 让拼接点在数值上连续。
    """
    if "pe_proxy" not in df.columns or df["pe_proxy"].isna().all():
        log("  ⚠️ 缓存缺 pe_proxy（000922）→ 不做拼接，估值腿仍从红利低波 PE 起点开始")
        return df["pe_val"], {"mode": "none"}
    junc = df["pe_val"].first_valid_index()
    if junc is None:
        return df["pe_val"], {"mode": "none"}
    k = float(df.loc[junc, "pe_val"] / df.loc[junc, "pe_proxy"])
    pe = df["pe_proxy"].copy()
    pe[pe.index < junc] = pe[pe.index < junc] * k
    pe[pe.index >= junc] = df.loc[df.index >= junc, "pe_val"]
    seg = pe[pe.index < junc]
    meta = {"mode": "spliced", "proxy": PROXY_CODE, "k": round(k, 5),
            "junction": str(junc.date()), "seg_n": int(len(seg)),
            "seg_from": str(seg.index[0].date()) if len(seg) else None}
    log(f"  估值腿拼接：k={k:.5f}，用 {PROXY_CODE} 补了 {len(seg)} 周"
        f"（{meta['seg_from']} ~ {junc.date()}）")
    return pe, meta


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
    # ★ 先把「拓展 / 参考」用的列挂到 df 上 —— 必须**在 dropna 之前**，
    #   否则 subset 里引用的列不存在会直接 KeyError。
    #   它们**不参与** 下面的 dropna 筛选（dropna 用显式 subset）：
    #   成长 PE 只到 2014-05，参与筛选会把整表拖短。
    if "pe_proxy" in raw:
        df["pe_proxy"] = al(raw["pe_proxy"])
    for k in ("pe_gro", "px_gro", "amt_gro"):
        if k in raw:
            df[k] = al(raw[k])
    # 全收益列同理：只挂上，不进 subset（某天缺数会把整行丢掉、静默改样本长度）
    if "px_valtr" in raw:
        df["px_valtr"] = al(raw["px_valtr"])

    # ⚠️ 这里必须显式写 subset。历史上一次裸 dropna() 被一列起点更晚的指数
    #    静默截掉了 60 周样本，实盘阈值一路算错（项目备忘 陷阱⑦）。
    # ⚠️⚠️ 第 15 轮：**不再要求 `pe_val`** —— 它 2013-12-05 才开始（指数发布日），
    #    放进必要性列会把整表拖到 2013-12 → pr() 在 2015~2023 长期窗口不足（暖启动）。
    #    改成由 pe_proxy（000922，2011-06-28 起）兜底 —— 这就是拓展的支点。
    need = ["px_val", "amt_val", "pe_all", "px_all", "amt_all", "ltsz", "rzrq", "rzmre"]
    if "pe_proxy" in raw:
        need.append("pe_proxy")
    else:
        need.append("pe_val")                    # 老缓存降级：行为与第 14 轮之前一致
    df = df.dropna(subset=need)
    # ★ 全收益标的列在 dropna **之后**再校验：它不参与上面的筛选，
    if "px_valtr" in raw:
        vtr = al(raw["px_valtr"]).reindex(df.index, method="ffill")
        assert vtr.notna().all(), "红利低波全收益序列对齐后仍有缺口"
        df["px_valtr"] = vtr
    else:
        log("  ⚠️ 缓存缺 px_valtr（H20269 全收益）→ 临时回落用价格指数，不影响管线")
        df["px_valtr"] = df["px_val"]
    return df


def compute(df):
    pe_est, ext_meta = build_pe_est(df)
    jumps_val = detect_jumps(pe_est, df["px_all"])
    jumps_all = detect_jumps(df["pe_all"], df["px_all"])
    pe_val_adj = back_adjust(pe_est, jumps_val)
    pe_all_adj = back_adjust(df["pe_all"], jumps_all)
    # ⚠️ 诊断用「首值」比值：末值永远未被调整，比值恒为 1，看不出放大倍数
    log(f"  跳变：估值腿 {len(jumps_val)} 次 / 全指 {len(jumps_all)} 次"
        f"（对最早历史累计 ×{float(pe_val_adj.iloc[0] / pe_est.iloc[0]):.3f} /"
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

    # ★★ 参考读数（不参与仓位决策）：成长温度 / 风格温度
    if "pe_gro" in df.columns and df["pe_gro"].notna().any():
        pe_gro_adj = back_adjust(df["pe_gro"], detect_jumps(df["pe_gro"], df["px_all"]))
        t["groEst"] = pr(pe_gro_adj)
        t["crowdGro"] = pr(df["amt_gro"] / df["amt_all"])
        t["gro"] = 0.55 * t["groEst"] + 0.30 * t["bkg"] + 0.15 * t["crowdGro"]
        # 风格 = 成长/价值 比价去趋势后的分位（纯单一指标）
        t["sty"] = pr(zdet(pe_gro_adj / pe_val_adj, 260))
        t["pe_gro"] = df["pe_gro"].round(2)
        if "px_gro" in df.columns:
            t["px_gro"] = df["px_gro"].round(2)
            t["fwd_gro"] = (df["px_gro"].shift(-52) / df["px_gro"] - 1) * 100
        log(f"  参考读数：成长 PE {int(df['pe_gro'].notna().sum())} 条"
            f"（起 {df['pe_gro'].first_valid_index().date()}）"
            f"→ 成长温度首值 {t['gro'].first_valid_index()}")
    t["fwd_all"] = (df["px_all"].shift(-52) / df["px_all"] - 1) * 100

    # ★ 标的走势：走势图上要把「温度」与「对应标的」画在一起，所以要把指数价格带出去
    #   市场温度 ← 中证全指 000985（价格指数）
    #   价值温度 ← 红利低波 **全收益** H20269（含股息，与用户实持的 563020 对上）
    t["px_val"] = df["px_val"].round(2)          # 价格指数（降级兜底 / 旧数据兼容）
    t["px_valtr"] = df["px_valtr"].round(2)      # 全收益指数（走势图用这条）
    t["px_all"] = df["px_all"].round(2)
    # 后续 52 周收益 —— ★ 第 11 轮改为**全收益口径（含股息）**：
    #   价格指数不含股息，会系统性低估约 5pp/年，与用户实得收益对不上。
    t["fwd_val"] = (df["px_valtr"].shift(-52) / df["px_valtr"] - 1) * 100
    # 价格口径留一份仅供对照排查，不进页面
    t["fwd_val_px"] = (df["px_val"].shift(-52) / df["px_val"] - 1) * 100
    return t, len(jumps_val), len(jumps_all), ext_meta


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
    t, n_jv, n_ja, ext_meta = compute(df)
    log(f"  周表 {len(df)} 周  {df.index[0].date()} ~ {df.index[-1].date()}")

    # 主读数两条都有效的部分（参考读数可以为空 → 逐条按需写入）
    ok = t.dropna(subset=["mkt", "val"])
    recs = []
    keys_main = ("est", "bkg", "crowd", "senti", "lev", "new")
    # ★ 参考读数：gro/sty 是分数本体，groEst/crowdGro 是它的两条腿（页面要做拆解）
    keys_extra = ("gro", "sty", "groEst", "crowdGro")
    for d, r in ok.iterrows():
        rec = {"d": d.strftime("%Y-%m-%d"), "mkt": round(float(r["mkt"]), 1),
               "val": round(float(r["val"]), 1)}
        for k in keys_main:
            rec[k] = round(float(r[k]), 1)
        # ★ 参考读数：有效才写，无效就不写这个 key（不能写 NaN，payload 会非法）
        for k in keys_extra:
            if k in r.index and pd.notna(r[k]):
                rec[k] = round(float(r[k]), 1)
        rec["peAll"] = float(r["pe_all"])
        # ★ peVal 在 2013-12-05 之前**不存在**（红利低波 PE 的硬起点）→ 不写这个 key，
        #   否则 float(nan) 会把 NaN 塞进 payload。前端对缺 key 有降级。
        if pd.notna(r["pe_val"]):
            rec["peVal"] = float(r["pe_val"])
        if "pe_gro" in r.index and pd.notna(r["pe_gro"]):
            rec["peGro"] = float(r["pe_gro"])
        rec["pxVal"] = float(r["px_val"])          # 红利低波 H30269 价格指数
        rec["pxValTr"] = float(r["px_valtr"])      # ★ 红利低波 H20269 全收益（走势图用）
        rec["pxAll"] = float(r["px_all"])          # 中证全指 000985 收盘（市场温度的标的）
        if "px_gro" in r.index and pd.notna(r["px_gro"]):
            rec["pxGro"] = float(r["px_gro"])      # 中证800成长 H30355（参考读数的标的）
        recs.append(rec)
    assert recs, "没有一条有效记录"

    hist = {"val": calibration(t["val"], t["fwd_val"]),
            "mkt": calibration(t["mkt"], t["fwd_val"])}
    # ★ 参考读数的档位表用**价格口径**目标（成长/风格是参考项，与价值的全收益口径不同，
    #   页面必须注明，不要横比收益数字）
    if "gro" in t.columns:
        hist["gro"] = calibration(t["gro"], t["fwd_gro"])
    if "sty" in t.columns:
        hist["sty"] = calibration(t["sty"], t["fwd_all"])

    now_bj = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    out = {
        "records": recs,
        "meta": {
            "updated": now_bj.strftime("%Y-%m-%d %H:%M"),
            "asof": recs[-1]["d"],
            "source": src,                                  # live / cache
            "jumps": {"val": n_jv, "all": n_ja},
            "hist": hist,
            "ext": ext_meta,                                # ★ 拼接元信息（可追溯）
            "grid": {"n": int(len(df)), "from": df.index[0].strftime("%Y-%m-%d"),
                     "to": df.index[-1].strftime("%Y-%m-%d")},
            "caliber": ("0.55/0.30/0.15 · 520周 · PE跳变回溯校正 · 价值收益=全收益口径(含股息)"
                        " · 估值腿2013-12前用000922拼接 · 成长/风格为参考读数"),
        },
    }
    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if "NaN" in payload or "Infinity" in payload:
        # 定位：把非法值所在的 key 路径打出来（否则只知道"有 NaN"，排查全靠猜）
        def _scan(o, path=""):
            if isinstance(o, dict):
                for k, v in o.items():
                    _scan(v, f"{path}.{k}")
            elif isinstance(o, list):
                for i, v in enumerate(o[:3] if len(o) > 3 else o):
                    _scan(v, f"{path}[{i}]")
            elif isinstance(o, float) and (np.isnan(o) or np.isinf(o)):
                log(f"  ❌ 非法数值 {path} = {o}")
        _scan(out)
        raise AssertionError("payload 含非法数值!")
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        f.write(payload)

    last = recs[-1]
    log(f"✅ 写入 {OUT_JSON}  ({os.path.getsize(OUT_JSON) / 1024:.0f} KB)")
    log(f"   样本 {len(recs)} 周  {recs[0]['d']} ~ {last['d']}  数据源={src}")
    log(f"   周表 {len(df)} 周（{df.index[0].date()} 起）—— 参考读数起点晚于此，属预期")
    for k, nm in (("mkt", "市场温度"), ("val", "价值温度")):
        h = out["meta"]["hist"][k]
        log(f"   {nm} {h['cur']}　历史百分位 {h['pos']}%　P80={h['q'][80]}　"
            f"P60={h['q'][60]}　(n={h['n']} 自 {h['from']})")
    for k, nm in (("gro", "成长温度"), ("sty", "风格温度")):
        h = out["meta"]["hist"].get(k)
        if h:
            log(f"   {nm}(参考) {h['cur']}　历史百分位 {h['pos']}%　P80={h['q'][80]}　"
                f"(n={h['n']} 自 {h['from']})")
    log(f"   分解：估值腿 {last['est']} × 0.55 + 全市场腿 {last['bkg']} × 0.30 "
        f"+ 拥挤度 {last['crowd']} × 0.15 = "
        f"{0.55 * last['est'] + 0.30 * last['bkg'] + 0.15 * last['crowd']:.1f}")
    log("   ★ 下方「后续52周」口径 = 红利低波全收益 H20269（含股息），与用户实得收益一致")
    for L in out["meta"]["hist"]["val"]["levels"]:
        log(f"   价值档 {L['name']} ({L['lab']}) n={L['n']}  后续52周 {L['ret']}%  胜率 {L['win']}%")


if __name__ == "__main__":
    main()
