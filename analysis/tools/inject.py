# -*- coding: utf-8 -*-
"""把 data.json 注入 index.template.html -> index.html（不依赖 pandas）"""
import json, os, sys

tpl = sys.argv[1]
dat = sys.argv[2]
out = sys.argv[3]

payload = open(dat, encoding="utf-8").read()
json.loads(payload)                      # 校验合法
html = open(tpl, encoding="utf-8").read()
assert "__DATA__" in html, "模板缺少 __DATA__ 占位符"
html = html.replace("__DATA__", payload)
open(out, "w", encoding="utf-8").write(html)
print("%s  %.0f KB  <- %s (%.0f KB)" % (out, os.path.getsize(out) / 1024, dat, os.path.getsize(dat) / 1024))
d = json.loads(payload)
print("  meta:", d.get("meta"))
