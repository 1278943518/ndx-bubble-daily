# -*- coding: utf-8 -*-
"""纳指定投规则回测：2016-05 ~ 2026-08，月度定投 1000 元"""
import json, datetime as dt

D = json.load(open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bubble_app/data.json', encoding='utf-8'))
M = D['month']
ROWS = [r for r in M if r['d'] >= '2016-05-01']          # 124 个月
MONTHLY = 1000.0
CASH_M = 0.02 / 12                                        # 闲置资金货基 2%/年

def coef_new(t):
    if t >= 85:  return 0.2
    if t >= 75:  return 0.7
    if t >= 65:  return 0.85
    if t >= 55:  return 1.0
    if t >= 40:  return 1.3
    return 1.8

RULES = {
    '① 无脑定投':      lambda t: 1.0,
    '② 新版温和规则':  coef_new,
    '③ 旧版≥70停投':   lambda t: 0.0 if t >= 70 else 1.0,
    '④ 只在≤55买':     lambda t: 1.0 if t <= 55 else 0.0,
}

def xirr(flows, guess=0.1):
    def npv(r):
        t0 = flows[0][0]
        return sum(a / (1 + r) ** ((d - t0).days / 365.0) for d, a in flows)
    lo, hi = -0.9999, 5.0
    if npv(lo) * npv(hi) > 0: return None
    for _ in range(300):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0: hi = mid
        else: lo = mid
    return (lo + hi) / 2

results = {}
for name, fn in RULES.items():
    shares = 0.0
    pool = 0.0          # 待投资金池（每月固定进 MONTHLY，按规则分批投出）
    invested = 0.0      # 实际投出的钱
    flows = []
    series = []         # (date, 组合总市值)
    peak = 0.0; mdd = 0.0
    invested_total = 0.0
    for r in ROWS:
        d = dt.date(*map(int, r['d'].split('-')))
        ndx = float(r['ndx']); t = float(r['total'])
        pool += MONTHLY                      # 当月预算入池
        buy = min(pool, MONTHLY * fn(t))     # 按规则投出（池里没钱就少投）
        shares += buy / ndx
        invested += buy
        pool -= buy
        pool *= (1 + CASH_M)                 # 池内余额吃货基收益
        invested_total += MONTHLY
        flows.append((d, -MONTHLY))
        val = shares * ndx + pool
        peak = max(peak, val)
        mdd = min(mdd, val / peak - 1)
        series.append((r['d'], val, invested_total))
    final = shares * float(ROWS[-1]['ndx']) + pool
    flows.append((dt.date(*map(int, ROWS[-1]['d'].split('-'))), final))
    results[name] = dict(
        final=final, invested=invested, total_in=invested_total,
        ret=final / invested_total - 1, xirr=xirr(flows), mdd=mdd,
        util=invested / invested_total, cash=pool, series=series)

print('=' * 92)
print(f"回测区间 {ROWS[0]['d']} ~ {ROWS[-1]['d']}  共 {len(ROWS)} 个月  NDX {ROWS[0]['ndx']:.0f} → {ROWS[-1]['ndx']:.0f} "
      f"(+{float(ROWS[-1]['ndx'])/float(ROWS[0]['ndx'])-1:.1%})")
print('=' * 92)
print(f"{'规则':<16}{'累计投入':>10}{'实际投入':>10}{'期末市值':>12}{'总收益率':>10}{'XIRR':>9}{'最大回撤':>10}{'资金利用率':>10}")
for k, v in results.items():
    print(f"{k:<16}{v['total_in']:>10,.0f}{v['invested']:>10,.0f}{v['final']:>12,.0f}"
          f"{v['ret']:>10.1%}{v['xirr']:>9.2%}{v['mdd']:>10.1%}{v['util']:>10.1%}")

# 分年度累计收益率
print('\n' + '=' * 92)
print('【分年度轨迹】每个自然年末的累计收益率（累计市值 / 累计投入 - 1）')
print('=' * 92)
years = sorted({r['d'][:4] for r in ROWS})
print(f"{'年份':<8}" + ''.join(f'{k:>16}' for k in results))
for y in years:
    line = f"{y:<8}"
    for k in results:
        ser = [s for s in results[k]['series'] if s[0][:4] == y]
        if ser:
            _, val, cin = ser[-1]
            line += f"{val/cin-1:>16.1%}"
        else:
            line += f"{'—':>16}"
    print(line)

# 温度分布
print('\n' + '=' * 92)
print('【月度温度分布】')
print('=' * 92)
buckets = [(85, 999, '≥85', 0.2), (75, 85, '75–85', 0.7), (65, 75, '65–75', 0.85),
           (55, 65, '55–65', 1.0), (40, 55, '40–55', 1.3), (0, 40, '≤40', 1.8)]
tot_w = 0
for lo, hi, lb, c in buckets:
    n = sum(1 for r in ROWS if lo <= r['total'] < hi)
    tot_w += n * c
    print(f"  {lb:<8} 系数 {c:<5}  {n:>3} 个月  {n/len(ROWS):>6.1%}")
print(f"  加权平均系数 = {tot_w/len(ROWS):.4f}  （≈1.0 → ②几乎不损失收益的原因）")

# 缩放至用户金额
print('\n' + '=' * 92)
print("【换算到你的资金】三种月投金额下的 10 年期终市值（按各规则总收益率等比缩放）")
print('=' * 92)
for amt in (4500, 7000, 7833):
    print(f'  月投 {amt:,} 元 / 10 年累计投入 {amt*124:,.0f} 元 →', end='')
    for k in results:
        print(f'  {k[0]}{amt*124*(1+results[k]["ret"])/10000:>6.1f}万', end='')
    print()

# 导出 JSON 供 HTML 使用
out = {}
for k, v in results.items():
    out[k] = dict(final=v['final'], ret=v['ret'], xirr=v['xirr'], mdd=v['mdd'],
                  util=v['util'], series=[[s[0], round(s[1], 1), s[2]] for s in v['series']])
json.dump(out, open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bt_result.json', 'w', encoding='utf-8'),
          ensure_ascii=False)
print('\n已导出 bt_result.json')
