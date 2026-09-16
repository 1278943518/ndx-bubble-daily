# -*- coding: utf-8 -*-
"""
中证官网 + 东财 + 腾讯 可达性探测（纯标准库，无依赖）
用途：验证 GitHub Actions (ubuntu-latest, 海外 IP) 能否抓到 A股温度计所需数据源
输出：每个端点一行 PASS/FAIL + 状态码 + 字节数 + 记录数 + 样例
"""
import json
import socket
import sys
import time
import urllib.error
import urllib.request

UA_CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

HDRS_CSI = {"User-Agent": UA_CHROME,
            "Referer": "https://www.csindex.com.cn/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9"}

HDRS_PLAIN = {"User-Agent": UA_CHROME}

RESULTS = []


def probe(name, url, headers, timeout=45, expect="json", min_records=1, key_path="data"):
    """抓一次并判定。返回 (ok, 描述)"""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            status = r.status
            raw = r.read()
    except urllib.error.HTTPError as e:
        try:
            body = e.read()[:200]
        except Exception:
            body = b""
        msg = f"FAIL HTTP {e.code} | {body!r}"
        RESULTS.append((name, False, msg))
        print(f"[FAIL] {name}\n       HTTP {e.code}  耗时 {time.time()-t0:.1f}s  body={body!r}\n")
        return False
    except Exception as e:
        msg = f"FAIL {type(e).__name__}: {e}"
        RESULTS.append((name, False, msg))
        print(f"[FAIL] {name}\n       {type(e).__name__}: {e}  耗时 {time.time()-t0:.1f}s\n")
        return False

    dt = time.time() - t0
    text = raw.decode("utf-8", "ignore")

    if expect == "html" or expect == "any":
        head = text[:120].replace("\n", " ")
        ok = status == 200 and len(raw) > 0
        RESULTS.append((name, ok, f"HTTP {status} {len(raw)}B"))
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  HTTP {status}  {len(raw)}B  {dt:.1f}s")
        print(f"       首段: {head!r}\n")
        return ok

    # expect json
    try:
        j = json.loads(text)
    except Exception as e:
        head = text[:200].replace("\n", " ")
        RESULTS.append((name, False, f"非 JSON ({len(raw)}B): {head[:80]}"))
        print(f"[FAIL] {name}  HTTP {status} {len(raw)}B 但解析 JSON 失败: {e}")
        print(f"       首段: {head!r}\n")
        return False

    # 判断是否命中 WAF / 空返回
    node = j
    for k in key_path.split(".") if key_path else []:
        if isinstance(node, dict):
            node = node.get(k)
        else:
            node = None
            break
    n = len(node) if isinstance(node, list) else (1 if node else 0)

    code = j.get("code") if isinstance(j, dict) else None
    ok = n >= min_records
    desc = f"HTTP {status} {len(raw)}B code={code} records={n}"

    sample = ""
    if isinstance(node, list) and node:
        sample = json.dumps(node[0], ensure_ascii=False)[:160]
    elif isinstance(node, dict):
        sample = json.dumps(node, ensure_ascii=False)[:160]

    RESULTS.append((name, ok, desc))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print(f"       {desc}  耗时 {dt:.1f}s")
    if sample:
        print(f"       样例: {sample}")
    if isinstance(node, list) and len(node) > 1:
        print(f"       末例: {json.dumps(node[-1], ensure_ascii=False)[:160]}")
    print()
    return ok


def dns(name, host):
    try:
        t0 = time.time()
        ips = sorted({ai[4][0] for ai in socket.getaddrinfo(host, 443)})
        print(f"[PASS] DNS {name} -> {ips}  ({time.time()-t0:.2f}s)")
        RESULTS.append((f"DNS {name}", True, ",".join(ips)))
        return True
    except Exception as e:
        print(f"[FAIL] DNS {name}: {type(e).__name__}: {e}")
        RESULTS.append((f"DNS {name}", False, str(e)))
        return False


print("=" * 78)
print("  A股数据源 · GitHub 云端可达性探测")
print(f"  runner: {sys.platform}  python {sys.version.split()[0]}")
print("=" * 78)
print()

# ---------- 0. DNS ----------
dns("csindex.com.cn", "www.csindex.com.cn")
dns("eastmoney", "datacenter-web.eastmoney.com")
dns("tencent", "web.ifzq.gtimg.cn")
dns("github", "api.github.com")
print()

# ---------- 1. 中证官网：首页 ----------
probe("中证官网 首页", "https://www.csindex.com.cn/", HDRS_CSI,
      expect="html")
probe("中证官网 首页(无Referer)", "https://www.csindex.com.cn/", HDRS_PLAIN,
      expect="html")

# ---------- 2. 中证官网：指数 PE 日频序列（最关键） ----------
for code, label in [("H30269", "红利低波动"), ("000918", "中证800成长"), ("000985", "中证全指")]:
    probe(f"中证 PE 序列 {code} ({label})",
          f"https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe?indexCode={code}",
          HDRS_CSI, min_records=100)

# 无 Referer 再试一次（判断 Referer 是否为必需）
probe("中证 PE 序列 H30269 (无Referer)",
      "https://www.csindex.com.cn/csindex-home/perf/indexCsiDsPe?indexCode=H30269",
      HDRS_PLAIN, min_records=100)

# ---------- 3. 中证官网：指数全历史行情（含成交额） ----------
probe("中证 行情 000985 (1990-2026)",
      "https://www.csindex.com.cn/csindex-home/perf/index-perf"
      "?indexCode=000985&startDate=19900101&endDate=20261231",
      HDRS_CSI, min_records=1000)

# ---------- 4. 东财：两融余额（已在现有管线验证过，再确认） ----------
probe("东财 两融余额 RPTA_RZRQ_LSHJ",
      "https://datacenter-web.eastmoney.com/api/data/v1/get"
      "?reportName=RPTA_RZRQ_LSHJ&columns=DIM_DATE,RZRQYE,RZMRE,LTSZ"
      "&sortColumns=DIM_DATE&sortTypes=-1&pageSize=200&pageNumber=1&source=WEB&client=WEB",
      HDRS_PLAIN, min_records=100, key_path="result.data")

# ---------- 5. 腾讯：指数周K ----------
probe("腾讯 周K sh000300",
      "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000300,week,,,1200,qfq",
      HDRS_PLAIN, min_records=1, key_path="data.sh000300.week")

# ---------- 汇总 ----------
print("=" * 78)
print("  汇总")
print("=" * 78)
npass = sum(1 for _, ok, _ in RESULTS if ok)
for name, ok, desc in RESULTS:
    print(f"  {'PASS' if ok else 'FAIL'}  {name:<40}  {desc[:60]}")
print("-" * 78)
print(f"  合计 {npass}/{len(RESULTS)} 通过")

csi_ok = any("PE 序列 H30269" in n and ok for n, ok, _ in RESULTS)
print()
if csi_ok:
    print("  >>> 结论: 中证官网可从云端访问 —— 云端管线方案成立 ★主方案")
else:
    print("  >>> 结论: 中证官网 云端不可达 —— 需改走本机定时任务 + git push 的降级方案")
