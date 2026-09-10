# -*- coding: utf-8 -*-
"""v11: 长历史证据驱动的两个未测策略
A. 价格动量定投 (AAII: momentum DCA 赢57%, value DCA 仅赢42%)
   —— 注意: 与我们的"温度"不同, 动量是纯价格信号(过去12月收益)
B. 存量减仓 (69年回测: CAPE>=40减仓30%每年最多1次 → Sharpe 0.53→0.58, MDD -56.8%→-48.2%)
   —— 用 温度>=90 对应极端估值阈值
"""
import csv, datetime as dt, itertools
src = open('bt_grid2.py', encoding='utf-8').read().split('SEGS =')[0]
exec(src)
ALL = [r for r in csv.DictReader(open('bubble_out/scores_monthly.csv', encoding='utf-8'))
       if '2016-03-01' <= r['date'] < '2026-09-01']
CASH_M = 0.02 / 12
N = len(ALL)
ndx = [float(r['ndx']) for r in ALL]
T = [float(r['total']) for r in ALL]
D = [r['date'] for r in ALL]
B = naive(ALL)
print('主口径 2016-03 起 %d 月 | 无脑: 收益 %.1f%%  XIRR %.2f%%  MDD %.1f%%'
      % (N, B['ret'] * 100, B['xirr'] * 100, B['mdd'] * 100))
print()

# ---------- A. 价格动量定投 ----------
mom12 = [None] * N
for i in range(12, N):
    mom12[i] = ndx[i] / ndx[i - 12] - 1

def run_mom(up, dn, warm=12, core=1000.0):
    shares = 0.0; pool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
    for i in range(N):
        m = 1.0 if mom12[i] is None else (up if mom12[i] > 0 else dn)
        pool = pool * (1 + CASH_M) + core
        buy = min(pool, core * m)
        if i == N - 1: buy = pool
        pool -= buy
        tot += core; shares += buy / ndx[i]
        val = shares * ndx[i] + pool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * ndx[-1] + pool
    return dict(ret=final / tot - 1, mdd=mdd, pool=pool)

print('=== A. 价格动量定投 (AAII 称 momentum DCA 赢 57%) ===')
print('%-30s%9s%9s%9s' % ('规则(动量>0 / 动量<0)', '超额', 'MDD', '期末池'))
for up, dn in [(1.5, 0.5), (1.3, 0.7), (1.2, 0.8), (2.0, 0.5), (1.5, 0.0), (1.0, 1.5), (0.5, 1.5)]:
    v = run_mom(up, dn)
    tag = '动量定投' if up > dn else '价值定投(反向)'
    print('%-30s%+8.1fpp%9.1f%%%9.0f' % ('%.1f / %.1f  [%s]' % (up, dn, tag),
                                        (v['ret'] - B['ret']) * 100, v['mdd'] * 100, v['pool']))
print('%-30s%9s%9.1f%%%9s' % ('  无脑(基准)', '—', B['mdd'] * 100, '—'))

print()
print('=== A2. 用温度代替动量做同一测试 (对照: 温度高/低 vs 动量高/低) ===')
for up, dn in [(1.5, 0.5), (1.3, 0.7)]:
    shares = 0.0; pool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
    for i in range(N):
        m = up if T[i] >= 64.68 else dn          # 用均分做分界
        pool = pool * (1 + CASH_M) + 1000.0
        buy = min(pool, 1000.0 * m)
        if i == N - 1: buy = pool
        pool -= buy; tot += 1000.0; shares += buy / ndx[i]
        val = shares * ndx[i] + pool
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    r = (shares * ndx[-1] + pool) / tot - 1
    print('  温度>=均分投%.1f / <均分投%.1f: 超额 %+.1fpp  MDD %.1f%%' %
          (up, dn, (r - B['ret']) * 100, mdd * 100))
print('  温度>=均分投0.5 / <均分投1.5 (低温加码=我们一直在做的):')
shares = 0.0; pool = 0.0; tot = 0.0; peak = 0.0; mdd = 0.0
for i in range(N):
    m = 0.5 if T[i] >= 64.68 else 1.5
    pool = pool * (1 + CASH_M) + 1000.0
    buy = min(pool, 1000.0 * m)
    if i == N - 1: buy = pool
    pool -= buy; tot += 1000.0; shares += buy / ndx[i]
    val = shares * ndx[i] + pool
    peak = max(peak, val)
    if val / peak - 1 < mdd: mdd = val / peak - 1
r = (shares * ndx[-1] + pool) / tot - 1
print('     超额 %+.1fpp  MDD %.1f%%' % ((r - B['ret']) * 100, mdd * 100))

# ---------- B. 存量减仓 ----------
print()
print('=== B. 存量减仓 (69年: 极端估值+低频+小比例, 唯一 Sharpe 提升的卖出规则) ===')
def run_stock(init_shares_value, hi_temp, cut, cool_months, rejoin_temp, rejoin_months,
              core=1000.0, bonus=None):
    """init_shares_value: 期初存量市值; hi_temp: 减仓温度阈值; cut: 减仓比例
       cool_months: 冷却期(月); rejoin_temp: 补回温度阈值; rejoin_months: 分几个月补回"""
    price0 = ndx[0]
    shares = init_shares_value / price0
    cash = 0.0; tot = init_shares_value; peak = init_shares_value; mdd = 0.0
    last_cut = -999; rejoin_left = 0; rejoin_amt = 0.0; n_cut = 0
    for i in range(N):
        px = ndx[i]; t = T[i]
        val_before = shares * px
        # 减仓
        if t >= hi_temp and (i - last_cut) >= cool_months and rejoin_left == 0:
            amt = val_before * cut
            if shares > 0:
                shares -= amt / px
                cash += amt
                last_cut = i; n_cut += 1
        # 补回
        if rejoin_left > 0:
            put = rejoin_amt / rejoin_months
            cash -= put; shares += put / px; rejoin_left -= 1
            if rejoin_left == 0: rejoin_amt = 0.0
        elif cash > 1 and t < rejoin_temp:
            rejoin_left = rejoin_months; rejoin_amt = cash
        # 定投
        cash_pit = 0.0
        if bonus and D[i][5:7] in bonus:
            cash_pit += bonus[D[i][5:7]]; tot += bonus[D[i][5:7]]
        shares += (core + cash_pit) / px
        tot += core
        cash *= (1 + CASH_M)
        val = shares * px + cash
        peak = max(peak, val)
        if val / peak - 1 < mdd: mdd = val / peak - 1
    final = shares * ndx[-1] + cash
    return dict(ret=final / tot - 1, mdd=mdd, ncut=n_cut, cash=cash, final=final, tot=tot)

INIT = 300000.0
print('场景: 期初存量 30 万 + 每月定投 1000（不含奖金），2016-03 起')
print('%-42s%9s%9s%9s%7s' % ('规则', '收益率', 'vs持有', 'MDD', '减仓次'))
res_b = []
for nm, hi, cut, cool, rj_t, rj_m in [
        ('① 纯持有(基准)', 999, 0, 12, 0, 12),
        ('② 温度>=90 减30%, 冷却12月, <85分12月补回', 90, 0.30, 12, 85, 12),
        ('③ 温度>=90 减20%, 冷却12月, <85分12月补回', 90, 0.20, 12, 85, 12),
        ('④ 温度>=85 减30%, 冷却12月, <80分12月补回', 85, 0.30, 12, 80, 12),
        ('⑤ 温度>=90 减30%, 冷却24月, <85分6月补回', 90, 0.30, 24, 85, 6),
        ('⑥ 温度>=90 减50%, 冷却12月, <85分12月补回', 90, 0.50, 12, 85, 12),
        ('⑦ 温度>=95 减30%, 冷却12月(几乎不触发)', 95, 0.30, 12, 85, 12),
]:
    v = run_stock(INIT, hi, cut, cool, rj_t, rj_m)
    res_b.append((nm, v))
    print('%-42s%9.1f%%%+9.1fpp%9.1f%%%7d' % (nm, v['ret'] * 100,
          (v['ret'] - res_b[0][1]['ret']) * 100 if res_b else 0, v['mdd'] * 100, v['ncut']))
print('   注: 收益率含期初 30 万存量, 故数值低于纯流量口径')

print()
print('=== B2. 若不含存量(纯定投流量), 减仓无效对照 ===')
print('  纯流量场景无存量可减, 此规则自动失效 → 再次印证"分层"必要性')
