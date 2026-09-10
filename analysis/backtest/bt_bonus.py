# -*- coding: utf-8 -*-
"""奖金择时引擎（干净版 v2）
现金流：月盈余 4,500 无脑定投 + 奖金 2 月 2 万 / 8 月 1 万 → 年可投 84,000
问题：3 万奖金（占年投 36%）要不要按温度计择时投放？哪种节奏最优？
"""
import json, datetime as dt

D = json.load(open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bubble_app/data.json', encoding='utf-8'))
M = [r for r in D['month'] if r['d'] >= '2016-05-01']
CASH_M = 0.02 / 12
BASE = 4500.0
BONUS = {2: 20000.0, 8: 10000.0}


def xirr(flows):
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


def schedule(t, mode):
    """期数 k；999 = 不投，等待温度降到阈值"""
    if mode == 'lump':   return 1
    if mode == 'fix3':   return 3
    if mode == 'fix6':   return 6
    if mode == 'fix12':  return 12
    if mode == 'tA':     return 1 if t <= 55 else 3 if t < 70 else 6 if t < 80 else 12
    if mode == 'tB':     return 1 if t <= 50 else 2 if t < 60 else 4 if t < 72 else 8 if t < 82 else 12
    if mode == 'tC':     return 1 if t <= 60 else 4 if t < 72 else 8 if t < 82 else 12
    if mode == 'wait55': return 999 if t > 55 else 1
    if mode == 'wait50': return 999 if t > 50 else 1
    raise ValueError(mode)


def run(mode):
    shares = 0.0
    tranches = []        # [剩余本金(货基计息), 每期额]
    waitq = 0.0          # 等待池（wait 模式专用，货基计息）
    tot = 0.0
    flows = []; series = []; peak = 0.0; mdd = 0.0
    n_wait_events = 0; total_wait_months = 0.0; n_triggers = 0

    for r in M:
        d = dt.date(*map(int, r['d'].split('-'))); ndx = float(r['ndx']); t = float(r['total'])
        mo = int(r['d'][5:7])

        # 1) 吃息
        waitq *= (1 + CASH_M)
        for tr in tranches: tr[0] *= (1 + CASH_M)

        # 2) 奖金入池
        if mo in BONUS:
            b = BONUS[mo]
            k = schedule(t, mode)
            if k == 999:
                waitq += b
                n_wait_events += 1
            else:
                tranches.append([b, b / k])

        # 3) 本期待投：BASE 永远全额 + 到期分期 + 温度触发时解冻等待池
        deploy = BASE
        for tr in tranches:
            if tr[0] <= 0: continue
            x = min(tr[0], tr[1]); tr[0] -= x; deploy += x
        if mode in ('wait55', 'wait50') and waitq > 0:
            thr = 55 if mode == 'wait55' else 50
            if t <= thr:
                deploy += waitq; waitq = 0.0; n_triggers += 1
        if waitq > 0: total_wait_months += 1

        # 4) 投入 + 记账
        shares += deploy / ndx
        tot += deploy
        flows.append((d, -deploy))
        val = shares * ndx + waitq + sum(tr[0] for tr in tranches)
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
        series.append((r['d'], val, tot))

    left = waitq + sum(tr[0] for tr in tranches)
    final = shares * float(M[-1]['ndx']) + left
    flows.append((dt.date(*map(int, M[-1]['d'].split('-'))), final))
    return dict(final=final, ret=final / tot - 1, xirr=xirr(flows), mdd=mdd,
                tot=tot, left=left, series=series,
                n_wait=n_wait_events, n_trig=n_triggers, wait_mo=total_wait_months)


MODES = [('① 奖金到手即投', 'lump'), ('② 固定分 3 期', 'fix3'), ('③ 固定分 6 期', 'fix6'),
         ('④ 固定分 12 期', 'fix12'), ('⑤ 温度 A 1/3/6/12', 'tA'),
         ('⑥ 温度 B 1/2/4/8/12', 'tB'), ('⑦ 温度 C 1/4/8/12', 'tC'),
         ('⑧ 等≤55 才投', 'wait55'), ('⑨ 等≤50 才投', 'wait50')]

print('─' * 116)
print('引擎：月投 4,500 无脑 + 奖金 2万/1万 按方案投放 | 2016-05 ~ 2026-08（124 个月），未投资金货基 2%')
print('─' * 116)
print(f"{'方案':<22}{'期末市值':>12}{'收益率':>9}{'vs①':>9}{'XIRR':>8}{'最大回撤':>9}{'等待月数':>9}{'触发次数':>9}")
print('─' * 116)
res = {}
for lb, md in MODES:
    v = run(md); res[lb] = v
    b = res['① 奖金到手即投']
    extra = f"{v['wait_mo']:>9.0f}{v['n_trig']:>9.0f}" if md.startswith('wait') else f"{'—':>9}{'—':>9}"
    print(f"{lb:<22}{v['final']:>12,.0f}{v['ret']:>9.1%}{(v['ret']-b['ret'])*100:>+8.1f}pp"
          f"{v['xirr']:>8.2%}{v['mdd']:>9.1%}{extra}")
print('─' * 116)
for lb, md in MODES:
    if md.startswith('wait'):
        v = res[lb]
        print(f'  {lb}：10 年间共 {v["n_wait"]:.0f} 笔奖金进入等待，解冻 {v["n_trig"]:.0f} 次，'
              f'平均每笔等待 {v["wait_mo"]/max(1,v["n_wait"]):.1f} 个月')

# 换算到真实金额的展示 + 分年度
print('\n【分年度累计收益率】')
keys = ['① 奖金到手即投', '③ 固定分 6 期', '⑤ 温度 A 1/3/6/12', '⑧ 等≤55 才投']
years = sorted({r['d'][:4] for r in M})
print(f"{'年份':<8}" + ''.join(f'{k[:9]:>14}' for k in keys))
for y in years:
    line = f'{y:<8}'
    for k in keys:
        s = [x for x in res[k]['series'] if x[0][:4] == y]
        line += f'{s[-1][1]/s[-1][2]-1:>14.1%}' if s else f'{"—":>14}'
    print(line)

print('\n【2022 熊市最低点】')
for k in keys:
    v = res[k]
    y22 = [s for s in v['series'] if s[0][:4] == '2022']
    lo = min(y22, key=lambda s: s[1] / s[2])
    print(f'  {k:<22} {lo[1]/lo[2]-1:>8.1%}（{lo[0]}）')

# 无脑基准（所有钱不分期，含奖金一次投）：就是 ① 的月投不变
b_all = res['① 奖金到手即投']
print(f'\n【口径说明】① = 4,500/月 + 奖金到手当月即投 → 实际就是「全额无脑定投」基准')
