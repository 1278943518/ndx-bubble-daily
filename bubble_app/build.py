# -*- coding: utf-8 -*-
"""构建「定投量化策略」H5（动态加载版）

产出:
  1. data.json   —— 纯数据（美股周频/月频 + A股双读数 + meta 时间戳）
                    前端优先 fetch 此文件 → 云端自动化只更新它即可
  2. index.html  —— 首页：三张卡片（我的定投方案 / 美股温度计 / A股温度计）
  3. us.html     —— 美股温度计详情页
  4. cn.html     —— A股温度计详情页
  每个 html 内嵌一份**裁剪过的**快照作兜底（本地/离线/构建失败也可用）

数据源: bubble_out/scores_weekly.csv + scores_monthly.csv + cn_scores.json

⚠️ 改页面必须改 *.template.html，不要直接改 index.html（构建产物会被覆盖）。
⚠️ cn 节点向后兼容：cn_scores.json 不存在时，**保留 data.json 里已有的 cn**，
   绝不清空（否则某天 A股抓取失败会把手机上的 A股卡片清成空白）。
"""
import datetime
import json
import math
import os

import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
OUT = os.path.join(ROOT, "bubble_out")

JSON_PATH = os.path.join(BASE, "data.json")
CN_PATH = os.path.join(OUT, "cn_scores.json")

# 内嵌兜底的裁剪长度（data.json 仍是全量）
FB_WEEK, FB_MONTH, FB_CN = 320, 72, 320


def load_series(name):
    """读取 CSV，返回 [{d, ndx, total, s1..s8, f5}, ...]（过滤非有限数值行）"""
    df = pd.read_csv(os.path.join(OUT, name), index_col=0)
    df.index = df.index.astype(str)
    recs = []
    for d, r in df.iterrows():
        try:
            vals = {"ndx": float(r["ndx"]), "total": float(r["total"])}
            for k in ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]:
                vals[k] = float(r[k])
            vals["f5"] = float(r.get("f5_raw", 0) or 0)
        except (ValueError, TypeError):
            continue
        if not all(math.isfinite(v) for v in vals.values()):
            continue                       # 非法数值整行丢弃, 保证 JSON 合法
        rec = {"d": d, "ndx": round(vals["ndx"], 0), "total": round(vals["total"], 1),
               "f5": round(vals["f5"], 1)}
        for k in ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]:
            rec[k] = round(vals[k], 1)
        recs.append(rec)
    return recs


def load_cn():
    """读 A股模块产物；缺失则回退到 data.json 里已有的 cn（返回 (cn, 来源)）。"""
    if os.path.exists(CN_PATH):
        with open(CN_PATH, "r", encoding="utf-8") as f:
            cn = json.load(f)
        if cn.get("records"):
            return cn, "cn_scores.json"
    if os.path.exists(JSON_PATH):
        with open(JSON_PATH, "r", encoding="utf-8") as f:
            old = json.load(f)
        if old.get("cn", {}).get("records"):
            return old["cn"], "沿用 data.json 旧 cn"
    return None, "无"


def write(tpl, out_name, payload):
    tpl_path = os.path.join(BASE, tpl)
    out_path = os.path.join(BASE, out_name)
    with open(tpl_path, "r", encoding="utf-8") as f:
        html = f.read()
    assert "__DATA__" in html, f"{tpl} 缺少 __DATA__ 占位符"
    html = html.replace("__DATA__", payload)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return len(html)


def main():
    week = load_series("scores_weekly.csv")
    month = load_series("scores_monthly.csv")
    cn, cn_src = load_cn()

    now_bj = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
    meta = {"updated": now_bj.strftime("%Y-%m-%d %H:%M"),
            "asof": week[-1]["d"] if week else None}
    if cn:
        meta["cnAsof"] = cn.get("meta", {}).get("asof")
        meta["cnUpdated"] = cn.get("meta", {}).get("updated")

    data = {"week": week, "month": month, "meta": meta}
    if cn:
        data["cn"] = cn
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    assert "NaN" not in payload and "Infinity" not in payload, "payload 含非法数值!"

    # 1) data.json —— 全量，运行时数据源
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        f.write(payload)

    # 2) 三个页面，各自内嵌裁剪过的兜底快照
    def fb(w=FB_WEEK, m=FB_MONTH, c=FB_CN):
        d = {"week": week[-w:], "month": month[-m:], "meta": meta}
        if cn:
            d["cn"] = {"records": cn["records"][-c:], "meta": cn.get("meta", {})}
        return json.dumps(d, ensure_ascii=False, separators=(",", ":"))

    n_home = write("index.template.html", "index.html", fb())
    n_us = write("us.template.html", "us.html", fb(w=len(week), m=len(month), c=0))
    n_cn = write("cn.template.html", "cn.html", fb(w=40, m=8, c=len(cn["records"]) if cn else 0))

    # 3) 打印
    print(f"week : {len(week)} 条, 最新 {week[-1]['d']} total={week[-1]['total']} "
          f"ndx={week[-1]['ndx']}")
    print(f"month: {len(month)} 条, 最新 {month[-1]['d']} total={month[-1]['total']}")
    if cn:
        r = cn["records"][-1]
        print(f"cn   : {len(cn['records'])} 条, 最新 {r['d']} "
              f"市场={r['mkt']} 价值={r['val']}　(来源: {cn_src})")
    else:
        print(f"cn   : 缺失（{cn_src}）→ data.json 不含 cn 节点")
    print(f"data.json   {os.path.getsize(JSON_PATH)/1024:.0f} KB  "
          f"(updated={meta['updated']}, asof={meta['asof']})")
    for n, s in (("index.html", n_home), ("us.html", n_us), ("cn.html", n_cn)):
        print(f"{n:<12}{s/1024:.0f} KB")


if __name__ == "__main__":
    main()
