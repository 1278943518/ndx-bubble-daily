# -*- coding: utf-8 -*-
"""v13: 长周期股债配置测试 (1954-2026, 约72年)
目的: 验证"不减少收益的情况下减少回撤"是否可能
资产: 标普500(价格指数) + 现金(联邦基金利率, 保守近似短债)
方法: 固定比例 + 定期再平衡, 扫描比例与再平衡频率
关键指标: CAGR / 年化波动 / 最大回撤 / Sharpe / Calmar(收益÷回撤)
"""
import csv, datetime as dt, math

fed = {}
for r in csv.DictReader(open('bubble_data/fedfunds_daily.csv', encoding='utf-8')):
    fed[r['date']] = float(r['val'])
inx = [(r['date'], float(r['close'])) for r in csv.DictReader(open('bubble_data/inx_month.csv', encoding='utf-8'))]
inx = [(d, c) for d, c in inx if d >= '1954-07-01']
D = [d for d, _ in inx]
PX = [c for _, c in inx]
N = len(PX)

def fed_at(d):
    """取该月之前最近的利率(避免前视)"""
    k = d[:7]
    if k in fed: return fed[k] / 100.0
    cand = [x for x in fed if x <= d]
    if not cand: return 0.02
    return fed[max(cand)] / 100.0

RATE = [fed_at(d) for d in D]

print('样本: %d 个月 (%s → %s)' % (N, D[0], D[-1]))
print('标普500(价格指数) %.2f → %.2f' % (PX[0], PX[-1]))
print()

def run(w_stock, rebal='yearly', start_val=1.0):
    """w_stock: 股票目标权重; rebal: monthly/quarterly/yearly/never"""
    s = start_val * w_stock            # 股票市值
    c = start_val * (1 - w_stock)      # 现金
    peak = start_val; mdd = 0.0
    rets = []
    for i in range(1, N):
        r = PX[i] / PX[i - 1] - 1
        s *= (1 + r)
        c *= (1 + RATE[i] / 12)
        v = s + c
        # 再平衡
        tgt_y = D[i][:4]
        prev_y = D[i - 1][:4]
        do = False
        if rebal == 'monthly': do = True
        elif rebal == 'quarterly': do = (int(D[i][5:7]) - 1) % 3 == 0
        elif rebal == 'yearly': do = tgt_y != prev_y
        if do:
            s = v * w_stock; c = v * (1 - w_stock)
        rets.append(v / (s + c) if False else None)
        peak = max(peak, v)
        if v / peak - 1 < mdd: mdd = v / peak - 1
        if i == 1: v0 = start_val
    v = s + c
    yrs = (dt.date.fromisoformat(D[-1]) - dt.date.fromisoformat(D[0])).days / 365.25
    cagr = (v / start_val) ** (1 / yrs) - 1
    # 年化波动
    mr = []
    s2 = start_val * w_stock; c2 = start_val * (1 - w_stock)
    for i in range(1, N):
        r = PX[i] / PX[i - 1] - 1
        prev = s2 + c2
        s2 *= (1 + r); c2 *= (1 + RATE[i] / 12)
        vv = s2 + c2
        mr.append(vv / prev - 1)
        tgt_y = D[i][:4]; prev_y = D[i - 1][:4]
        do = (rebal == 'monthly') or (rebal == 'quarterly' and (int(D[i][5:7]) - 1) % 3 == 0) \
             or (rebal == 'yearly' and tgt_y != prev_y)
        if do:
            s2 = vv * w_stock; c2 = vv * (1 - w_stock)
    mu = sum(mr) / len(mr)
    sd = (sum((x - mu) ** 2 for x in mr) / (len(mr) - 1)) ** 0.5 * (12 ** 0.5)
    rf = sum(RATE) / len(RATE)
    sharpe = (cagr - rf) / sd if sd else 0
    calmar = cagr / abs(mdd) if mdd else 0
    return dict(cagr=cagr, sd=sd, mdd=mdd, sharpe=sharpe, calmar=calmar, final=v)

print('=== 长周期股债配置 (1954-07 ~ 2026-08, 72年, 年度再平衡) ===')
print('%-14s%9s%9s%9s%9s%9s' % ('股票/现金', 'CAGR', '年化波动', '最大回撤', 'Sharpe', 'Calmar'))
base = None
for w in [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]:
    v = run(w, 'yearly')
    if base is None: base = v
    print('%-14s%9.2f%%%9.1f%%%9.1f%%%9.2f%9.2f' %
          ('%d/%d' % (w * 100, (1 - w) * 100), v['cagr'] * 100, v['sd'] * 100,
           v['mdd'] * 100, v['sharpe'], v['calmar']))

print()
print('=== 再平衡频率的影响 (70/30) ===')
print('%-14s%9s%9s%9s%9s' % ('频率', 'CAGR', '年化波动', '最大回撤', 'Sharpe'))
for rb, nm in [('monthly', '月度'), ('quarterly', '季度'), ('yearly', '年度'), ('never', '不再平衡')]:
    v = run(0.7, rb)
    print('%-14s%9.2f%%%9.1f%%%9.1f%%%9.2f' % (nm, v['cagr'] * 100, v['sd'] * 100, v['mdd'] * 100, v['sharpe']))

print()
print('=== 关键: 是否存在"收益不降、回撤下降"的配置? ===')
b = run(1.0, 'yearly')
for w in [0.9, 0.8, 0.7, 0.6]:
    v = run(w, 'yearly')
    dcagr = (v['cagr'] - b['cagr']) * 100
    dmdd = (v['mdd'] - b['mdd']) * 100     # 正数=回撤变小
    print('  %d/%d: CAGR %+.2fpp  回撤改善 %+.1fpp  → 每放弃1pp收益换回 %.1fpp回撤'
          % (w * 100, (1 - w) * 100, dcagr, dmdd, dmdd / abs(dcagr) if dcagr else 0))

print()
print('=== 波动拖累的量化 (几何 < 算术) ===')
print('%-12s%12s%12s%10s' % ('年化波动', '算术10%→几何', '算术12%→几何', '拖累'))
for sd in [0.10, 0.15, 0.20, 0.25, 0.30]:
    g10 = (1 + 0.10) / ((1 + sd ** 2) ** 0.5) - 1 if False else 0.10 - sd ** 2 / 2
    g12 = 0.12 - sd ** 2 / 2
    print('%-12s%12s%12s%10s' % ('%.0f%%' % (sd * 100), '%.2f%%' % (g10 * 100),
                                 '%.2f%%' % (g12 * 100), '%.2fpp' % (sd ** 2 / 2 * 100)))

print()
print('=== 回撤恢复表: 亏多少需要涨多少才回本 ===')
for dd in [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80]:
    print('  回撤 %.0f%% → 需上涨 %.0f%%' % (dd * 100, (1 / (1 - dd) - 1) * 100))
