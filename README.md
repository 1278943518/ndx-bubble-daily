# 美股泡沫温度计 · 每日云端数据管线

本仓库承载「美股泡沫温度计」H5 的数据生产环节，**全部在 GitHub 云端执行，不依赖任何本地电脑**。

## 工作方式

- **GitHub Actions 每天 08:00（北京时间）自动运行**（`.github/workflows/daily.yml`）
- 执行管线：抓取基础数据（CBOE VIX / FRED 利率 / multpl CAPE / FINRA 保证金）→ 抓取周K（腾讯 NDX/INX + 东方财富 ARKK）→ 重算八特征滚动 520 周分位评分 → 构建 `bubble_app/data.json`
- 产物自动 commit 到本仓库 `main` 分支，并自动 purge jsDelivr CDN 缓存（数据即时生效）
- 前端页面通过 `https://cdn.jsdelivr.net/gh/1278943518/ndx-bubble-daily@main/bubble_app/data.json` 读取（jsDelivr 带 CORS，国内可直接访问）

## 页面

部署在 WorkBuddy：https://b6237b54dd36472bb9d1c59a92783ece.app.workbuddy.link

## 目录

| 路径 | 说明 |
|---|---|
| `bubble/fetch_data.py` | 抓 VIX/FRED/CAPE/FINRA（FINRA 读 `finra_margin.xlsx` 种子）|
| `bubble/fetch_weekly.py` | 抓 NDX/INX/ARKK 周K |
| `bubble/analyze_weekly.py` | 八特征滚动 520 周分位 → `bubble_out/scores_weekly.csv` |
| `bubble_app/build.py` | 合成周/月数据 → `bubble_app/data.json` + `index.html` |
| `bubble_out/scores_monthly.csv` | 月频种子（月末手动更新一次）|
| `finra_margin.xlsx` | FINRA 保证金债务种子（每月 FINRA 发布后手动更新）|
| `analysis/` | 研究与回测脚本归档（不参与线上管线，见 `analysis/README.md`）|
| `research/` | 研究报告、方案文档与数据来源快照（不参与线上管线，见 `research/README.md`）|

> `analysis/` 与 `research/` 为 2026-09-11 归档加入的**离线资料**，
> 仅供研究回溯与后续维护使用，**不影响每日管线与前端页面**。
> 其中 `analysis/tools/sync_repo.py` 是本地改动与仓库协作的关键工具。

## 手动更新

仓库页面 → Actions → 每日数据更新 → Run workflow，即可手动触发一次。

## 前端改版（本地流程）

改页面请在本地工作副本操作，不要直接改仓库里的 `index.html`：

1. 在工作目录下准备 `bubble_app/`（本地副本）与 `ndx-repo/`（本仓库克隆）
2. 改 `bubble_app/index.template.html`（页面模板）与 `plan.html`（说明页）
3. 跑 `python analysis/tools/sync_repo.py` —— 同步进 `ndx-repo/` 并用仓库最新 `data.json` 重建 `index.html`
4. 在 `ndx-repo/` 里 commit + push

> `index.html` 是构建产物，每日管线会用模板重新生成，**直接手改会被覆盖**。
> 详细约定见 `analysis/README.md`。

## 归档资料

`analysis/`（研究脚本）与 `research/`（研究报告）为离线资料，**不参与部署**，
仅用于结论回溯与后续维护。两者的目录说明见各自目录下的 `README.md`。
