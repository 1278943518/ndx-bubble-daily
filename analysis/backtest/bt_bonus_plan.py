# -*- coding: utf-8 -*-
"""v10 最终方案: 核心定投永不减 + 奖金低温加投
结论驱动:
 ① 定投流量绝不减少 (Faber -64.3pp / 减投 +0.7pp 且不稳健)
 ② 加码资金必须来自增量(奖金), 不能靠减投攒钱(会踏空)
 ③ 低温区确有 edge (未来12M +15.6% / 24M +37.4% / 36M +55.8%)
口径: 核心每月固定 + 每年两笔奖金; 对比"奖金即投" vs "奖金等低温投"
"""
import csv, datetime as dt, itertools
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2016-03-01' <= r['date'] < '2026-09-01']
CASH_M = 0.02 / 12
BONUS = {'02': 20000.0, '09': 10000.0}   # 2月2万 + 下半年1万
CORE = 1000.0

def run(rows, lo=999, wait_cap=0, core=CORE):
    """lo: 温度低于该值才投奖金; wait_cap: 最长等待月数(0=不限)"""
    shares = 0.0; wpool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
    waited = 0; wmax = 0; n_bonus = 0
    for i, r in enumerate(rows):
        d = r['date']; ndx = float(r['ndx']); t = float(r['total'])
        wpool *= (1 + CASH_M)
        m = d[5:7]
        if m in BONUS:
            wpool += BONUS[m]; tot += BONUS[m]; waited = 0; n_bonus += 1
        buy = core                                  # 核心: 无条件, 永不减
        tot += core
        if wpool > 1 and (t < lo or (wait_cap and waited >= wait_cap)):
            buy += wpool; wpool = 0.0; waited = 0
        else:
            waited += 1; wmax = max(wmax, waited)
        shares += buy / ndx
        val = shares * ndx + wpool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + wpool
    return dict(ret=final / tot - 1, mdd=mdd, pool=wpool, wmax=wmax, xirr=None)

def run_x(rows, lo=999, wait_cap=0, core=CORE):
    shares = 0.0; wpool = 0.0; tot = 0.0; flows = []
    for i, r in enumerate(rows):
        d = dt.date.fromisoformat(r['date'][:10]); ndx = float(r['ndx']); t = float(r['total'])
        wpool *= (1 + CASH_M)
        cash_in = 0.0
        if r['date'][5:7] in BONUS:
            wpool += BONUS[r['date'][5:7]]; cash_in += BONUS[r['date'][5:7]]
        buy = core
        if wpool > 1 and (t < lo or (wait_cap and waited_months.get(i, 0) >= wait_cap)):
            buy += wpool; wpool = 0.0
        shares += buy / ndx
        flows.append((d, -(core + cash_in)))
    flows.append((dt.date.fromisoformat(rows[-1]['date'][:10]), shares * float(rows[-1]['ndx']) + wpool))
    return xirr(flows)

# 简单版(不跟踪 waited 跨月, 用 wait_cap 时按月数)
def run2(rows, lo=999, wait_cap=0, core=CORE):
    shares = 0.0; wpool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
    waited = 0; wmax = 0
    for i, r in enumerate(rows):
        ndx = float(r['ndx']); t = float(r['total'])
        wpool *= (1 + CASH_M)
        if r['date'][5:7] in BONUS:
            wpool += BONUS[r['date'][5:7]]; tot += BONUS[r['date'][5:7]]; waited = 0
        buy = core; tot += core
        if wpool > 1:
            if t < lo or (wait_cap and waited >= wait_cap):
                buy += wpool; wpool = 0.0; waited = 0
            else:
                waited += 1; wmax = max(wmax, waited)
        shares += buy / ndx
        val = shares * ndx + wpool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * float(rows[-1]['ndx']) + wpool
    return dict(ret=final / tot - 1, mdd=mdd, pool=wpool, wmax=wmax)

BASE = run2(ALL)          # 奖金即投
print('主口径 2016-03 起 %d 个月 | 核心 1000/月 + 奖金 2月2万/9月1万' % len(ALL))
print('基准(奖金即投): 收益 %.1f%%  MDD %.1f%%  期末奖金池 %.0f' %
      (BASE['ret'] * 100, BASE['mdd'] * 100, BASE['pool']))
print()
print('=== 奖金"等低温再投"扫描 (vs 奖金即投, pp) ===')
print('%-30s%9s%9s%9s%9s' % ('规则', '超额', 'MDD', '最长等待', '期末滞留'))
grid = []
for lo, cap in itertools.product([40, 45, 50, 55, 60, 65], [0, 6, 12, 24]):
    v = run2(ALL, lo, cap)
    grid.append(((v['ret'] - BASE['ret']) * 100, lo, cap, v))
grid.sort(reverse=True)
for d, lo, cap, v in grid[:12]:
    print('%-30s%+8.1fpp%9.1f%%%7d月%11.0f' %
          ('温度<%d 投, 最长等%d月' % (lo, cap) if cap else '温度<%d 投, 不限等待' % lo,
           d, v['mdd'] * 100, v['wmax'], v['pool']))
print('%-30s%9s%9.1f%%%7s%11.0f' % ('  奖金即投(基准)', '—', BASE['mdd'] * 100, '—', BASE['pool']))

print()
print('=== 反向对照: 奖金"等高温才投"(应显著跑输) ===')
for lo in [70, 75]:
    v = run2(ALL, lo, 0)
    print('  温度>=%d 才投: %+.1fpp' % (lo, (v['ret'] - BASE['ret']) * 100))

print()
print('=== Top3 稳健性: 滚动5年 + 前后半段 ===')
wins = []
i = 0
while i + 60 <= len(ALL):
    wins.append(ALL[i:i + 60]); i += 3
H1 = [r for r in ALL if r['date'] < '2021-01-01']
H2 = [r for r in ALL if r['date'] >= '2021-01-01']
for d, lo, cap, v in grid[:3]:
    ds = []
    for w in wins:
        b = run2(w)['ret']; ds.append((run2(w, lo, cap)['ret'] - b) * 100)
    o1 = (run2(H1, lo, cap)['ret'] - run2(H1)['ret']) * 100
    o2 = (run2(H2, lo, cap)['ret'] - run2(H2)['ret']) * 100
    print('  温度<%d/cap%d: 滚动%+.1f 正窗口%d/%d  前半%+.1f 后半%+.1f' %
          (lo, cap, sum(ds) / len(ds), sum(1 for x in ds if x > 0), len(ds), o1, o2))

print()
print('=== 关键: 若整段都没等到低温, 奖金会躺多久? ===')
for lo in [45, 50, 55]:
    wait = 0; mx = 0
    for r in ALL:
        if r['date'][5:7] in BONUS: wait = 0
        if float(r['total']) < lo: wait = 0
        else: wait += 1; mx = max(mx, wait)
    print('  温度<%d: 历史最长等待 %d 个月' % (lo, mx))
