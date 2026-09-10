# -*- coding: utf-8 -*-
"""v12: 多资产趋势轮动 (长历史唯一"提收益+砍回撤"的方案)
与单资产择时的本质区别: 不空仓, 而是切换到另一个趋势向上的资产 → 规避踏空
资产池: 纳指100(进攻) + 投资级公司债 LQD(防御)  数据 2010 起, 主口径 2016-03 起
"""
import csv, datetime as dt
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
MON = list(csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8')))
px = {}
for r in csv.DictReader(open('bubble_data/lqd_month.csv', encoding='utf-8')):
    k = list(r.keys())
    dk = [c for c in k if 'date' in c.lower()] or [k[0]]
    ck = [c for c in k if 'close' in c.lower()] or [k[1]]
    px[r[dk[0]]] = float(r[ck[0]])
ALL = [r for r in MON if '2016-03-01' <= r['date'] < '2026-09-01' and r['date'] in px]
N = len(ALL)
ndx = [float(r['ndx']) for r in ALL]
lqd = [px[r['date']] for r in ALL]
D = [r['date'] for r in ALL]
print('主口径 %d 个月 (%s → %s)' % (N, D[0], D[-1]))
print('纳指 %.0f → %.0f (%+.0f%%)   公司债 %.2f → %.2f (%+.0f%%)'
      % (ndx[0], ndx[-1], (ndx[-1] / ndx[0] - 1) * 100, lqd[0], lqd[-1], (lqd[-1] / lqd[0] - 1) * 100))
print()

def sma(a, w=10):
    o = [None] * len(a)
    for i in range(w - 1, len(a)):
        o[i] = sum(a[i - w + 1:i + 1]) / w
    return o
S_N = sma(ndx, 10); S_L = sma(lqd, 10)
INIT = 300000.0

def run(mode, core=1000.0):
    """mode: hold_ndx / hold_5050 / rotate(趋势轮动) / rotate_ndx_only(单资产择时)"""
    sh_n = 0.0; sh_l = 0.0; cash = 0.0; tot = INIT
    # 期初按 mode 建仓
    if mode == 'hold_ndx': sh_n = INIT / ndx[0]
    elif mode == 'hold_5050': sh_n = INIT / 2 / ndx[0]; sh_l = INIT / 2 / lqd[0]
    elif mode in ('rotate', 'rotate_ndx_only'): sh_n = INIT / ndx[0]
    peak = INIT; mdd = 0.0; sw = 0
    for i in range(N):
        pn, pl = ndx[i], lqd[i]
        if mode == 'rotate':
            in_n = S_N[i] is None or pn >= S_N[i]
            in_l = S_L[i] is None or pl >= S_L[i]
            target_n = INIT if False else None
            v = sh_n * pn + sh_l * pl + cash
            want_n = 0.5 if in_n else 0.0
            want_l = 0.5 if in_l else 0.0
            s = want_n + want_l
            if s == 0: want_l = 1.0; s = 1.0
            tn = v * want_n / s; tl = v * want_l / s
            if abs(sh_n * pn - tn) > v * 0.02 or abs(sh_l * pl - tl) > v * 0.02:
                sw += 1
            sh_n = tn / pn; sh_l = tl / pl; cash = 0.0
        elif mode == 'rotate_ndx_only':
            in_n = S_N[i] is None or pn >= S_N[i]
            v = sh_n * pn + sh_l * pl + cash
            if in_n and sh_n * pn < v * 0.5:
                sh_n = v / pn; sh_l = 0.0; cash = 0.0; sw += 1
            elif (not in_n) and sh_n * pn > v * 0.5:
                cash = v; sh_n = 0.0; sh_l = 0.0; sw += 1
            cash *= (1 + 0.02 / 12)
        sh_n += core / pn * (0.5 if mode == 'hold_5050' else 1.0)
        if mode == 'hold_5050': sh_l += core / pl * 0.5
        tot += core
        v = sh_n * pn + sh_l * pl + cash
        peak = max(peak, v)
        if v / peak - 1 < mdd: mdd = v / peak - 1
    final = sh_n * ndx[-1] + sh_l * lqd[-1] + cash
    return dict(ret=final / tot - 1, mdd=mdd, sw=sw, final=final)

print('=== 存量 30 万 + 每月定投 1000，2016-03 起 ===')
print('%-34s%10s%10s%9s%8s' % ('策略', '收益率', 'vs全纳指', 'MDD', '切换次'))
base = None
res = []
for nm, md in [('① 全仓纳指（单资产持有）', 'hold_ndx'),
               ('② 纳指/公司债 50/50 固定', 'hold_5050'),
               ('③ 双资产趋势轮动（不空仓）', 'rotate'),
               ('④ 纳指单资产择时（跌破持现金）', 'rotate_ndx_only')]:
    v = run(md)
    if base is None: base = v['ret']
    res.append((nm, v))
    print('%-34s%10.1f%%%+9.1fpp%9.1f%%%8d' % (nm, v['ret'] * 100, (v['ret'] - base) * 100,
                                               v['mdd'] * 100, v['sw']))
print()
print('=== 关键: 轮动 vs 单资产择时 的差异 ===')
r3 = [x for x in res if x[0].startswith('③')][0][1]
r4 = [x for x in res if x[0].startswith('④')][0][1]
print('  单资产择时(跌破→现金): 收益 %.1f%%  MDD %.1f%%' % (r4['ret'] * 100, r4['mdd'] * 100))
print('  多资产轮动(跌破→换债): 收益 %.1f%%  MDD %.1f%%' % (r3['ret'] * 100, r3['mdd'] * 100))
print('  差额 %+.1fpp  → 轮动%s' % ((r3['ret'] - r4['ret']) * 100,
      '胜出（不空仓是关键）' if r3['ret'] > r4['ret'] else '未胜出'))
print()
print('=== 纳指跌破均线的月份, 公司债表现如何（轮动是否真有替代资产）===')
cnt = 0; win = 0
for i in range(10, N):
    if S_N[i] and ndx[i] < S_N[i] and i + 12 < N:
        cnt += 1
        if lqd[i + 12] / lqd[i] > ndx[i + 12] / ndx[i]: win += 1
if cnt:
    print('  纳指跌破均线后 12 个月, 公司债跑赢纳指的比例: %d/%d (%.0f%%)' % (win, cnt, win / cnt * 100))
