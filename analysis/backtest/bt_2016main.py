# -*- coding: utf-8 -*-
"""主口径回测 v5: 2016-03 起 (8/8腿, 唯一完全可比)
用户确认: 主口径 2016-03 起; 2000-2015 缺腿区间直接弃用
"""
import csv, datetime as dt, itertools
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2016-03-01' <= r['date'] < '2026-09-01']
CASH_M = 0.02 / 12

def mk(hi, hm, lo, lm):
    def cf(t):
        if t >= hi: return hm
        if t < lo: return lm
        return 1.0
    return cf

B = naive(ALL)
print('=== 主口径: 2016-03 起 ===')
print('样本 %d 个月 (%s → %s)' % (len(ALL), ALL[0]['date'], ALL[-1]['date']))
print('纳指 %.0f → %.0f (%+.0f%%)' % (float(ALL[0]['ndx']), float(ALL[-1]['ndx']),
      (float(ALL[-1]['ndx']) / float(ALL[0]['ndx']) - 1) * 100))
print('无脑基准: 收益 %.1f%%  XIRR %.2f%%  MDD %.1f%%' % (B['ret'] * 100, B['xirr'] * 100, B['mdd'] * 100))
print()

print('=== 参数网格 (口径A 预算恒定) 按超额排序 ===')
print('%-22s%9s%9s%9s%9s%9s' % ('参数 hi/hm/lo/lm', '收益率', 'vs无脑', 'XIRR', 'MDD', '期末池'))
grid = []
for hi, hm, lo, lm in itertools.product([80, 85, 90], [0.0, 0.2, 0.5, 1.0], [40, 45, 50], [2, 3, 4]):
    cf = mk(hi, hm, lo, lm)
    v = run(ALL, cf)
    grid.append(((v['ret'] - B['ret']) * 100, hi, hm, lo, lm, v))
grid.sort(reverse=True)
for d, hi, hm, lo, lm, v in grid[:12]:
    print('%-22s%9.1f%%%+8.1fpp%9.2f%%%9.1f%%%9.0f'
          % ('%d/%.1f/%d/%.1f' % (hi, hm, lo, lm), v['ret'] * 100, d, v['xirr'] * 100, v['mdd'] * 100, v['pool']))
print('%-22s%9.1f%%%8s%9.2f%%%9.1f%%%9s' % ('① 无脑', B['ret'] * 100, '—', B['xirr'] * 100, B['mdd'] * 100, '—'))

print()
print('=== 稳健性 1: 滚动 5 年窗口 (60月, 步长3月) 超额是否稳定 ===')
best = grid[0]
cands = [('用户指定 90/0.2/45/3.0', mk(90, 0.2, 45, 3.0)),
         ('网格最优 %d/%.1f/%d/%.1f' % (best[1], best[2], best[3], best[4]), mk(best[1], best[2], best[3], best[4])),
         ('85/0.2/45/3.0', mk(85, 0.2, 45, 3.0))]
wins = []
i = 0
while i + 60 <= len(ALL):
    wins.append(ALL[i:i + 60]); i += 3
print('窗口数 %d (%s ~ %s)' % (len(wins), wins[0][0]['date'], wins[-1][-1]['date']))
for nm, cf in cands:
    ds = []
    for w in wins:
        b = naive(w)['ret']; ds.append((run(w, cf)['ret'] - b) * 100)
    pos = sum(1 for x in ds if x > 0)
    print('  %-24s 均值%+.1fpp  中位%+.1fpp  最差%+.1fpp  最好%+.1fpp  正窗口 %d/%d'
          % (nm, sum(ds) / len(ds), sorted(ds)[len(ds) // 2], min(ds), max(ds), pos, len(ds)))

print()
print('=== 稳健性 2: 剔除 2022-2023 那轮低温加码后 ===')
for nm, cf in cands:
    shares = 0.0; pool = 0.0; tot = 0.0
    for r in ALL:
        ndx = float(r['ndx']); t = float(r['total'])
        m = cf(t)
        if r['date'] >= '2022-06-01' and m > 1: m = 1.0
        pool = pool * (1 + CASH_M) + 1000.0
        buy = min(pool, 1000.0 * m); pool -= buy; tot += 1000.0
        shares += buy / ndx
    full = (run(ALL, cf)['ret'] - B['ret']) * 100
    noc = ((shares * float(ALL[-1]['ndx']) + pool) / tot - 1 - B['ret']) * 100
    print('  %-24s 完整%+.1fpp → 剔除后%+.1fpp (该轮贡献 %+.1fpp)' % (nm, full, noc, full - noc))

print()
print('=== 稳健性 3: 前半/后半 (2016-2021 / 2021-2026) ===')
H = [('前半 2016-03~2020-12', '2016-03-01', '2021-01-01'), ('后半 2021-01~2026-08', '2021-01-01', '2026-09-01')]
for nm, cf in cands:
    out = []
    for _, d0, d1 in H:
        w = [r for r in ALL if d0 <= r['date'] < d1]
        b = naive(w)['ret']; out.append((run(w, cf)['ret'] - b) * 100)
    print('  %-24s 前半%+.1fpp  后半%+.1fpp  %s' % (nm, out[0], out[1],
          '✓同号' if out[0] * out[1] > 0 else '✗不一致'))

print()
print('=== 口径B 真倍数 (外部追加, 比 XIRR) ===')
print('%-22s%9s%9s%9s' % ('参数', 'XIRR', 'vs无脑', 'MDD'))
for hi, hm, lo, lm in [(90, 0.2, 45, 3.0), (85, 0.0, 45, 4.0), (85, 0.2, 45, 2.0)]:
    cf = mk(hi, hm, lo, lm)
    shares = 0.0; tot = 0.0; flows = []; peak = 0.0; mdd = 0.0; pool = 0.0
    for r in ALL:
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx']); t = float(r['total'])
        buy = 1000.0 * cf(t)
        tot += buy; shares += buy / ndx; flows.append((d, -buy))
        val = shares * ndx
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(ALL[-1]['ndx'])
    flows.append((dt.date.fromisoformat(ALL[-1]['date'][:10]), final))
    x = xirr(flows)
    print('%-22s%9.2f%%%+8.1fpp%9.1f%%' % ('%d/%.1f/%d/%.1f' % (hi, hm, lo, lm), x * 100, (x - B['xirr']) * 100, mdd * 100))
print('%-22s%9.2f%%%8s%9.1f%%' % ('① 无脑', B['xirr'] * 100, '—', B['mdd'] * 100))
