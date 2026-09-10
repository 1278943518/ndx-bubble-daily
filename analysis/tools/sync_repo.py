# -*- coding: utf-8 -*-
"""把本地 bubble_app 的改动同步进 ndx-repo，并用仓库最新 data.json 重建 index.html。

约定:
  - 仓库 HTML 用 CRLF, 本地用 LF → 同步时统一转 CRLF, 避免 git 全文件 diff
  - 二进制/JSON 资源不转行尾
  - index.html 是构建产物 = index.template.html 里 __DATA__ 替换成 data.json
  - data.json 取仓库版本(云端 Actions 每日更新), 不用本地旧数据
  - 站点说明页用版本化文件名(EdgeOne 按 URL 逐条缓存), 改版只改 PLAN_VER 一行
"""
import os, shutil, json, sys


def _find_root(start):
    """从 start 向上查找同时含 bubble_app/ 与 ndx-repo/ 的工作目录"""
    d = start
    for _ in range(8):
        if (os.path.isdir(os.path.join(d, "bubble_app"))
                and os.path.isdir(os.path.join(d, "ndx-repo"))):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


# 工作目录 = 同时含 bubble_app/(本地工作副本) 与 ndx-repo/(仓库克隆) 的目录
# 优先读环境变量 NDX_ROOT, 否则从脚本位置自动向上查找
ROOT = (os.environ.get("NDX_ROOT")
        or _find_root(os.path.dirname(os.path.abspath(__file__)))
        or os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(ROOT, "bubble_app")
REPO = os.path.join(ROOT, "ndx-repo", "bubble_app")

if not (os.path.isdir(LOCAL) and os.path.isdir(REPO)):
    sys.exit(
        "找不到工作目录。\n"
        f"  当前推断: {ROOT}\n"
        f"  需要存在: {LOCAL}\n"
        f"            {REPO}\n"
        "请先 clone 仓库到 ndx-repo/, 或用环境变量 NDX_ROOT 指定工作目录。"
    )

PLAN_VER = "plan-v15.html"          # ← 说明页改版时改这里（并同步 index 模板里的链接）

TEXT = ["plan.html", PLAN_VER, "index.template.html"]
ASSETS = ["logo.svg", "apple-touch-icon.png", "icon-192.png", "icon-512.png",
          "favicon.png", "manifest.webmanifest"]


def to_crlf(b: bytes) -> bytes:
    return b.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def sync(name, convert=True):
    b = open(os.path.join(LOCAL, name), "rb").read()
    if convert:
        b = to_crlf(b)
    open(os.path.join(REPO, name), "wb").write(b)
    return len(b)


def build_index(target_dir, data_bytes):
    """用 target_dir 的模板 + 给定 data.json 重建 index.html（字节级替换，保留行尾）"""
    tpl = open(os.path.join(target_dir, "index.template.html"), "rb").read()
    assert b"__DATA__" in tpl, f"{target_dir} 模板缺 __DATA__ 占位符"
    json.loads(data_bytes.decode("utf-8"))
    out = tpl.replace(b"__DATA__", data_bytes)
    open(os.path.join(target_dir, "index.html"), "wb").write(out)
    return len(out)


# 0) 一致性检查 + 生成版本化说明页副本
tpl_txt = open(os.path.join(LOCAL, "index.template.html"), encoding="utf-8").read()
assert f'href="{PLAN_VER}"' in tpl_txt, f"index 模板里的说明页链接不是 {PLAN_VER}，请先同步"
shutil.copyfile(os.path.join(LOCAL, "plan.html"), os.path.join(LOCAL, PLAN_VER))
print(f"说明页版本: {PLAN_VER}")

data = open(os.path.join(REPO, "data.json"), "rb").read()

print("同步到仓库 (CRLF 文本):")
for f in TEXT:
    print(f"  {f:24s} {sync(f):>8d} B")

print("同步到仓库 (原样二进制):")
for f in ASSETS:
    print(f"  {f:24s} {sync(f, convert=False):>8d} B")

# 站点部署目录的 data.json 是旧快照(第3顺位兜底), 顺手刷新成仓库最新版
open(os.path.join(LOCAL, "data.json"), "wb").write(data)
print(f"  {'data.json (本地刷新)':24s} {len(data):>8d} B")

print("重建 index.html:")
print(f"  ndx-repo/  {build_index(REPO, data):>8d} B")
print(f"  bubble_app/{build_index(LOCAL, data):>8d} B")
print("done")
