# 定投量化策略 · 每日云端数据管线（美股 + A股温度计）

本仓库承载「定投量化策略」H5 的数据生产环节，**全部在 GitHub 云端执行，不依赖任何本地电脑**。

## 工作方式

- **GitHub Actions 每天 08:00（北京时间）自动运行**（`.github/workflows/daily.yml`）
- 执行管线：
  1. 抓取基础数据（CBOE VIX / FRED 利率 / multpl CAPE / FINRA 保证金）
  2. 抓取周K（腾讯 NDX/INX + 东方财富 ARKK）
  3. 重算八特征滚动 520 周分位评分 → `bubble_out/scores_weekly.csv`
  4. **抓取 A股数据（中证指数官网 PE/行情 + 东财两融）→ 计算双读数 → `bubble_out/cn_scores.json`**
  5. 构建 `bubble_app/data.json` 与三个页面（`index.html` / `us.html` / `cn.html`）
- 产物自动 commit 到本仓库 `main` 分支，并自动 purge jsDelivr CDN 缓存（数据即时生效）
- 前端页面通过 `https://cdn.jsdelivr.net/gh/1278943518/ndx-bubble-daily@main/bubble_app/data.json` 读取（jsDelivr 带 CORS，国内可直接访问）

> **★ 成分股调整无需人工介入。** 中证接口每次返回**全历史** PE 序列，
> `fetch_cn.py` 每次**全量重抓 → 全量重算** PE 跳变回溯校正，因此对成分股调整**天然幂等**，
> 不会因多次调整而累积放大。云端每天自动跑完并刷新 CDN，页面自动显示新值。

## 页面

部署在 WorkBuddy：https://ndx-bubble-thermometer-85426.app.workbuddy.host/

| 页面 | 说明 |
|---|---|
| `index.html` | 首页「定投量化策略」——系统同步/当前时间 + 三卡片横排（我的定投方案 / 美股温度计 / A股温度计）|
| `us.html` | 美股温度计详情（仪表 + 八特征分解 + 总分走势）|
| `cn.html` | A股温度计详情（市场温度 + 价值温度双线同图 + 取数指标分解 + 档位表现表）|

## 口径

### 美股（八特征滚动 520 周分位）
见 `bubble/analyze_weekly.py`。

### A股（双读数，2026-09-16 定稿）

```
市场温度 = pr( 中证全指 000985 PE校正, 520周 )

价值温度 = 0.55 × pr( 红利低波 H30269 PE校正, 520周 )
         + 0.30 × 全市场腿
         + 0.15 × pr( 红利低波成交额 ÷ 全A成交额, 520周 )

全市场腿 = (0.20×情绪 + 0.20×杠杆 + 0.15×新买家) / 55 × 100   ← 分母是 55
情绪     = √( pr(全A成交额÷流通市值) × pr(全A收盘÷52周最高) )
杠杆     = pr(两融余额 ÷ A股流通市值)
新买家   = pr(融资买入额 ÷ 全A成交额)
```

**三个必须固化的实现要点**

1. **PE 序列必须做「跳变回溯校正」**——成分股半年调整会让 PE 单周跳 ±13~59%。
   对跳变日 t，把 t 之前全部历史 × `PE_t / PE_{t−1}`。
   **只在算分位时用校正序列，展示的 PE 绝对值仍用原始值。**
2. **`pr()` 暖启动必须返回 NaN，不能填 50.0**——填 50 会让序列开头 52 周成为一整坨
   **精确的 50.0 质量点**，污染分位统计。代价：2015 年前段读数会为空，这是正确行为。
3. **不报固定阈值线，改报「历史百分位」**——实测 P80 对样本口径很敏感
   （价值温度在 n=592/332/232 下分别是 65.1 / 58.4 / 67.5）→ 与其报一条会漂的线，
   不如直接报历史百分位并让档位由分位数动态切，保证口径自洽。

## 目录

| 路径 | 说明 |
|---|---|
| `bubble/fetch_data.py` | 抓 VIX/FRED/CAPE/FINRA（FINRA 读 `finra_margin.xlsx` 种子）|
| `bubble/fetch_weekly.py` | 抓 NDX/INX/ARKK 周K |
| `bubble/analyze_weekly.py` | 八特征滚动 520 周分位 → `bubble_out/scores_weekly.csv` |
| `bubble_cn/fetch_cn.py` | **抓 A股数据 + 算双读数 → `bubble_out/cn_scores.json`** |
| `bubble_app/build.py` | 合成 → `bubble_app/data.json` + `index/us/cn.html` |
| `bubble_data/cn_raw.pkl` | **A股原始序列缓存（抓取失败时的回退源）**|
| `bubble_out/scores_monthly.csv` | 月频种子（月末手动更新一次）|
| `finra_margin.xlsx` | FINRA 保证金债务种子（每月 FINRA 发布后手动更新）|
| `analysis/` | 研究与回测脚本归档（不参与线上管线，见 `analysis/README.md`）|
| `research/` | 研究报告、方案文档与数据来源快照（不参与线上管线，见 `research/README.md`）|

> `analysis/` 与 `research/` 为 2026-09-11 归档加入的**离线资料**，
> 仅供研究回溯与后续维护使用，**不影响每日管线与前端页面**。

## 容灾（两层，保证「抓不到」不会把页面清空）

1. **抓取层**：`fetch_cn.py` 网络失败 → 回退已提交的 `bubble_data/cn_raw.pkl`；
   逐序列取「本次 / 缓存中更长的那份」，防止偶发分页截断。
2. **构建层**：`build.py` 缺 `cn_scores.json` 时**保留 `data.json` 里已有的 cn**，绝不清空。
3. **前端层**：jsDelivr CDN → GitHub raw → 本站 `data.json` → 内嵌兜底快照，四级降级。

## 手动更新

仓库页面 → Actions → 每日数据更新 → Run workflow，即可手动触发一次。

## 前端改版（本地流程）

改页面请改 `bubble_app/*.template.html`（**不要直接改 `index.html`，它是构建产物会被覆盖**）：

1. 改 `index.template.html` / `us.template.html` / `cn.template.html`
2. 跑 `python bubble_app/build.py` —— 重新生成 `data.json` 与三个 html
3. 跑 HTML 标签平衡校验（`_html_balance.py`）
4. commit + push

> **模板中数据以两种方式存在**：`__DATA__` 内嵌快照（首屏立即渲染用）+
> 运行时 `fetch` 远程 `data.json` 覆盖。因此**改页面后必须重新构建**，
> 否则内嵌快照不含最新数据。远端有新提交时**直接重新克隆**，
> 不要在 shallow clone 上 `git fetch` + `rebase`（实测 `.git/refs/` 会整体消失）。

## 归档资料

`analysis/`（研究脚本）与 `research/`（研究报告）为离线资料，**不参与部署**，
仅用于结论回溯与后续维护。两者的目录说明见各自目录下的 `README.md`。
