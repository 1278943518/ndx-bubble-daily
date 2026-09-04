# -*- coding: utf-8 -*-
"""构建美股泡沫温度计 H5（动态加载版）
产出两个文件:
  1. data.json   —— 纯数据(周频+月频+meta时间戳)，前端优先 fetch 此文件 → 自动化只更新它即可
  2. index.html  —— 页面(内嵌同份数据作兜底，本地/离线/构建失败也可用)
数据源: bubble_out/scores_weekly.csv + scores_monthly.csv
"""
import pandas as pd, json, os, math, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
OUT = os.path.join(ROOT, "bubble_out")

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
        rec = {"d": d, "ndx": round(vals["ndx"], 0), "total": round(vals["total"], 1), "f5": round(vals["f5"], 1)}
        for k in ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]:
            rec[k] = round(vals[k], 1)
        recs.append(rec)
    return recs

week = load_series("scores_weekly.csv")
month = load_series("scores_monthly.csv")

# meta: 生成时间(北京时间) + 数据截止日期
now_bj = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
data = {
    "week": week,
    "month": month,
    "meta": {
        "updated": now_bj.strftime("%Y-%m-%d %H:%M"),
        "asof": week[-1]["d"] if week else None,
    },
}
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
assert "NaN" not in payload and "Infinity" not in payload, "payload 含非法数值!"

# 1) data.json (动态数据源)
json_path = os.path.join(BASE, "data.json")
with open(json_path, "w", encoding="utf-8") as f:
    f.write(payload)

# 2) index.html (页面 + 内嵌兜底)
tpl_path = os.path.join(BASE, "index.template.html")
html_path = os.path.join(BASE, "index.html")
with open(tpl_path, "r", encoding="utf-8") as f:
    html = f.read()
assert "__DATA__" in html, "模板缺少 __DATA__ 占位符"
html = html.replace("__DATA__", payload)
with open(html_path, "w", encoding="utf-8") as f:
    f.write(html)

for g, recs in (("week", week), ("month", month)):
    print(f"{g}: {len(recs)} 条, 最新 {recs[-1]['d']} total={recs[-1]['total']} ndx={recs[-1]['ndx']}")
print(f"data.json  {os.path.getsize(json_path)/1024:.0f} KB  (updated={data['meta']['updated']}, asof={data['meta']['asof']})")
print(f"index.html {os.path.getsize(html_path)/1024:.0f} KB")
