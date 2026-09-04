# 美股泡沫温度计 · 每日云端数据管线

本仓库承载「美股泡沫温度计」H5 的数据生产环节，**全部在 GitHub 云端执行，不依赖任何本地电脑**。

## 工作方式

- **GitHub Actions 每天 08:00（北京时间）自动运行**（`.github/workflows/daily.yml`）
- 执行管线：抓取基础数据（CBOE VIX / FRED 利率 / multpl CAPE / FINRA 保证金）→ 抓取周K（腾讯 NDX/INX + 东方财富 ARKK）→ 重算八特征滚动 520 周分位评分 → 构建 `bubble_app/data.json`
- 产物自动 commit 到本仓库 `main` 分支
- 前端页面通过 `https://raw.githubusercontent.com/1278943518/ndx-bubble-daily/main/bubble_app/data.json` 读取（raw 带 CORS，浏览器可直接 fetch）

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

## 手动更新

仓库页面 → Actions → 每日数据更新 → Run workflow，即可手动触发一次。
