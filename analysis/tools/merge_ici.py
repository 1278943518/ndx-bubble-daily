# -*- coding: utf-8 -*-
"""拼接 ICI monthly flows 全史：多版本 union（后版本优先，含修订）"""
import csv, glob

FILES = [
    # (commit版本, 优先级低→高)
    'ici_m_850cc70605af.csv',    # 2014-05: 2007-01 ~ 2014-03
    'ici_m_ec9b7c64baca.csv',    # 2015-02: 2007-01 ~ 2014-12
    'ici_m_9170d09956ae.csv',    # 2024-12: 2007-01 ~ 2024-10
    'ici_m_2450d47abec8.csv',    # 2025-02: 2007-01 ~ 2024-11
    'ici_m_d44a5d836b1f.csv',    # 2025-07: 2007-01 ~ 2024-11 (同2450)
    'ici_m_3dc02b8e4c23.csv',    # 2026-08: 2020-01 ~ 2026-05
]
cols = None
data = {}
for f in FILES:
    with open(f, encoding='utf-8') as fh:
        rows = list(csv.DictReader(fh))
    if not rows: continue
    if cols is None: cols = list(rows[0].keys())
    for r in rows:
        d = r['Date'].strip()
        if not d: continue
        # 后读文件覆盖先读（更接近最新版本 = 更权威）
        data[d] = [float(r[c]) if r[c] not in ('', None) else None for c in cols[1:]]

# 追加 equitycharts monthly 的 2024-01 ~ 2026-07（仅取 2026-06/07 新段，其余已被覆盖）
import urllib.request, json
try:
    d = json.loads(urllib.request.urlopen(
        urllib.request.Request('https://equitycharts.tech/api/fund-flows/combined',
                               headers={'User-Agent': 'Mozilla/5.0'}), timeout=30).read())
    # monthly 字段: date, equityTotal...但那是 combined（含ETF），与 mutual fund 口径不同！
    # 检查是否有 mutual-fund-only 的 monthly 端点…… 先打标记
    print('注意: equitycharts monthly 为 combined 口径(含ETF), 暂不并入 mutual fund 序列')
except Exception as e:
    print('equitycharts fetch err', e)

dates = sorted(data.keys())
out = []
for d in dates:
    out.append([d] + [('' if v is None else repr(v)) for v in data[d]])
with open('bubble_data/ici_flows_monthly.csv', 'w', encoding='utf-8', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(cols)
    w.writerows(out)

print(f'列: {cols}')
print(f'拼接完成: {len(out)} 个月, {dates[0]} ~ {dates[-1]}')
# 检查缺口
import datetime as dt
dd = [dt.date.fromisoformat(x) for x in dates]
gaps = []
for i in range(1, len(dd)):
    m = (dd[i].year - dd[i-1].year) * 12 + dd[i].month - dd[i-1].month
    if m != 1: gaps.append((dd[i-1].isoformat(), dd[i].isoformat(), m))
print('缺口:', gaps if gaps else '无')

# 简单看几个关键点值（Total Equity 列 = cols[1]）
eq = {d: data[d][0] for d in dates}
for y in ['2007-01-31', '2008-12-31', '2015-12-31', '2020-03-31', '2021-03-31', '2022-12-31', '2024-12-31', '2026-05-31']:
    if y in eq: print(f'  {y}: Total Equity = {eq[y]:,.0f} (百万$)')
