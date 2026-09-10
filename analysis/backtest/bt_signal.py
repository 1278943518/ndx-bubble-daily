# -*- coding: utf-8 -*-
"""决定性检验：温度计对纳指未来收益到底有没有预测力？"""
import json, statistics as st

D = json.load(open(r'C:/Users/Leo/WorkBuddy/2026-08-28-18-05-51/bubble_app/data.json', encoding='utf-8'))
M = D['month']
W = D['week']

def bucket_stats(pairs, label):
    """pairs: [(temp, fwd_ret_pct)]"""
    print(f'\n【{label}】样本 {len(pairs)} 个')
    bs = [(0, 40, '≤40'), (40, 55, '40–55'), (55, 65, '55–65'), (65, 75, '65–75'), (75, 85, '75–85'), (85, 999, '≥85')]
    print(f"  {'温度区间':<10}{'样本数':>7}{'未来收益均值':>13}{'中位数':>10}{'为正比例':>10}")
    for lo, hi, lb in bs:
        v = [r for t, r in pairs if lo <= t < hi]
        if not v:
            print(f'  {lb:<10}{0:>7}{"—":>13}'); continue
        print(f'  {lb:<10}{len(v):>7}{st.mean(v):>12.1f}%{st.median(v):>9.1f}%{sum(1 for x in v if x>0)/len(v):>9.0%}')
    # 相关系数
    ts = [p[0] for p in pairs]; rs = [p[1] for p in pairs]
    mt, mr = st.mean(ts), st.mean(rs)
    num = sum((a-mt)*(b-mr) for a, b in pairs)
    den = (sum((a-mt)**2 for a in ts) * sum((b-mr)**2 for b in rs)) ** .5
    print(f'  相关系数 r = {num/den:+.3f}')
    # 斯皮尔曼
    st_t = sorted(range(len(ts)), key=lambda i: ts[i]); st_r = sorted(range(len(rs)), key=lambda i: rs[i])
    rt = {i: k for k, i in enumerate(st_t)}; rr = {i: k for k, i in enumerate(st_r)}
    d2 = sum((rt[i]-rr[i])**2 for i in range(len(ts)))
    n = len(ts)
    print(f'  斯皮尔曼 ρ = {1 - 6*d2/(n*(n*n-1)):+.3f}')

print('=' * 70)
print('月度数据：温度 → 未来 N 个月纳指收益')
print('=' * 70)
for h in (3, 6, 12, 24):
    pairs = []
    for i in range(len(M) - h):
        t = float(M[i]['total'])
        r = (float(M[i+h]['ndx']) / float(M[i]['ndx']) - 1) * 100
        pairs.append((t, r))
    bucket_stats(pairs, f'未来 {h} 个月')

print('\n' + '=' * 70)
print('周度数据：温度 → 未来 N 周纳指收益')
print('=' * 70)
for h in (13, 26, 52):
    pairs = []
    for i in range(len(W) - h):
        t = float(W[i]['total'])
        r = (float(W[i+h]['ndx']) / float(W[i]['ndx']) - 1) * 100
        pairs.append((t, r))
    bucket_stats(pairs, f'未来 {h} 周')

print('\n' + '=' * 70)
print('反方向检验：过去 N 个月涨幅 → 当前温度（温度是不是只是"涨出来的"）')
print('=' * 70)
for h in (6, 12, 24):
    pairs = []
    for i in range(h, len(M)):
        past = (float(M[i]['ndx']) / float(M[i-h]['ndx']) - 1) * 100
        pairs.append((past, float(M[i]['total'])))
    ts = [p[0] for p in pairs]; rs = [p[1] for p in pairs]
    mt, mr = st.mean(ts), st.mean(rs)
    num = sum((a-mt)*(b-mr) for a, b in pairs)
    den = (sum((a-mt)**2 for a in ts) * sum((b-mr)**2 for b in rs)) ** .5
    print(f'  过去 {h:>2} 个月涨幅 vs 当前温度：r = {num/den:+.3f}')

print('\n' + '=' * 70)
print('关键对照：如果完全不看温度，无脑持有的收益是多少')
print('=' * 70)
for h in (12, 24):
    v = [(float(M[i+h]['ndx']) / float(M[i]['ndx']) - 1) * 100 for i in range(len(M) - h)]
    print(f'  任意时点买入持有 {h} 个月：均值 {st.mean(v):.1f}%  中位 {st.median(v):.1f}%  '
          f'为正比例 {sum(1 for x in v if x>0)/len(v):.0%}  最差 {min(v):.1f}%  最好 {max(v):.1f}%')
