# analysis/ — 研究与回测脚本归档

存放「美股泡沫温度计」在做指标研究、方案设计与回测时用到的全部 Python 脚本。
**这些脚本不参与线上每日管线**，线上管线只跑 `bubble/` 与 `bubble_app/` 下的几个脚本。

- 采集时间：2026-09-11
- 来源：本地工作副本（`WorkBuddy\2026-08-28-18-05-51\`）+ 恢复出的 `分析脚本/`
- 依赖：`pandas`、`numpy`、`openpyxl`（与线上管线一致）

## 目录

```
analysis/
├─ backtest/   53 个回测脚本（bt_*.py）
└─ tools/      18 个工具与实验脚本
```

### backtest/ — 回测脚本（53 个）

按用途大致分组，文件名自解释：

| 分组 | 脚本 |
|---|---|
| 配置与轮动 | `bt_alloc*.py` `bt_rebal*.py` `bt_balance.py` `bt_multi_asset.py` `bt_permanent.py` |
| 定投/加仓策略 | `bt_cape_dca.py` `bt_trend_dca*.py` `bt_bonus*.py` `bt_ammo.py` `bt_throttle_debug.py` |
| 择时与信号 | `bt_signal.py` `bt_trend.py` `bt_anchor.py` `bt_decide.py` `bt_event.py` `bt_vol.py` `bt_grid*.py` |
| 参数扫描与稳健性 | `bt_search.py` `bt_robust.py` `bt_variants*.py` `bt_freq.py` `bt_range.py` `bt_side.py` `bt_pool.py` |
| 方案对比与定稿 | `bt_compare*.py` `bt_models.py` `bt_multi*.py` `bt_final.py` `bt_final_plan.py` `bt_plan` 相关 |
| 长历史与校验 | `bt_longhist.py` `bt_valid*.py` `bt_20y.py` `bt_2010.py` `bt_2016main.py` `bt_now.py` `bt_detail.py` |

> 说明：`bt_*` 里有多个 `v2`/`2` 后缀版本，是同一次研究的迭代过程，保留以便回溯结论来源。

### tools/ — 工具与实验脚本（18 个）

| 脚本 | 用途 |
|---|---|
| **`sync_repo.py`** | ⭐ **关键工具**：把本地 `bubble_app` 的改动同步进仓库克隆，并用仓库最新 `data.json` 重建 `index.html` || `inject.py` | 把 `data.json` 注入 `index.template.html` → `index.html`（不依赖 pandas） |
| `fetch_alloc.py` | 下载并清洗配置回测数据（纳指100/标普500/中证红利低波/中证现金流等，人民币口径、分红再投资）|
| `fetch_arkk.py` | ARKK / TLT 历史**月**K 下载（Stooq 反爬 PoW 绕过）；周K 已并入 `bubble/fetch_weekly.py` |
| `fetch_tencent_ext.py` | 一次性：腾讯月K/周K 扩展到 1200 根，更新 `ndx_month`/`inx_month` 等 |
| `make_icon.py` | 纯 Python 生成图标 PNG（3x3 超采样抗锯齿，无第三方依赖）|
| `audit_range.py` | 数据成熟度审计：每个特征何时开始有真实值（而非 50 占位）|
| `check_s6.py` / `compare_s6.py` | 特征 6（新买家/ICI 资金流）定义检查与新旧体系对比 |
| `ici_process.py` / `merge_ici.py` / `probe_ici2.py` | ICI 资金流数据清洗、多版本拼接、异常度探测 |
| `test_candidates*.py` / `test_combos.py` / `test_fine.py` / `test_oneway.py` | 五轮候选指标实验：寻找能揭示 2021 泡沫的指标（ARKK 相对动量 F9 系列）|
| `check_hot.py` | 热度相关检查 |

## 使用建议

脚本多为**一次性研究代码**，路径多为硬编码，直接运行前请先确认输入文件位置。
如需重跑，建议先看 `bt_final*.py`（定稿方案）与 `sync_repo.py`（与仓库协作的方式）。

## 前端改版的协作方式（`sync_repo.py`）

改前端页面时的标准工作目录约定：

```
<工作目录>/
├─ bubble_app/      ← 本地工作副本（在这里改 index.template.html / plan.html）
├─ ndx-repo/        ← 本仓库的克隆（git clone 到这个名字）
└─ sync_repo.py
```

`sync_repo.py` 做四件事：

1. 把 `bubble_app/plan.html` 复制成版本化文件名（改版只需改脚本里的 `PLAN_VER` 一行，EdgeOne 按 URL 逐条缓存）
2. 把 `index.template.html`、`plan.html`、`plan-v*.html` 按 **CRLF** 同步进 `ndx-repo/bubble_app/`（本地是 LF，不转换会产生全文件 diff）
3. 用**仓库版本**的 `data.json`（云端每日更新，不要用本地旧数据）重建 `index.html`，即 `index.template.html` 里的 `__DATA__` 占位符替换为 data.json
4. 顺手把 `bubble_app/data.json` 刷新成仓库最新版

脚本的路径解析已改为**自动向上查找**同时含 `bubble_app/` 与 `ndx-repo/` 的目录，
也可用环境变量 `NDX_ROOT` 显式指定，因此放在 `analysis/tools/` 下也能正常工作。

> ⚠️ 注意：`index.html` 是**构建产物**，不要直接手改——
> 线上每日管线会用 `index.template.html` 重新生成它。要改页面请改模板。

## 未纳入本目录的内容

以下为临时探针/抓取中间产物，未纳入仓库，如有需要可回旧会话目录找：
`te_probe.html`、`sa_ndx.html`、`i/n/p/r*.html`、`wb*.html`、`live.html`、`shot_plan.png`、
以及大量临时 `*.json` / `*.csv` 中间文件。
