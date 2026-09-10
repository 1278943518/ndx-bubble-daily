# -*- coding: utf-8 -*-
"""纯 Python 生成「泡沫温度计」图标 PNG（无第三方依赖，带 3x3 超采样抗锯齿）

图形 = 页面里的仪表盘：四色分区半圆弧 + 白色指针 + 转轴
输出: apple-touch-icon.png(180) / icon-192.png / icon-512.png / favicon.png(64)
"""
import math, os, struct, zlib

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bubble_app")

BG     = (0x11, 0x18, 0x27)
WHITE  = (0xFF, 0xFF, 0xFF)
GREEN  = (0x05, 0x96, 0x69)
AMBER  = (0xCA, 0x8A, 0x04)
ORANGE = (0xD9, 0x77, 0x06)
RED    = (0xDC, 0x26, 0x26)

CX, CY, R, SW = 256.0, 344.0, 170.0, 68.0      # 圆心 / 半径 / 线宽
RO = R + SW / 2.0                               # 外缘 204
RI = R - SW / 2.0                               # 内缘 136
NX, NY = 332.67, 262.35                         # 指针端点（对应取值 74）
NW = 24.0                                       # 指针线宽
PIV, PIV_IN = 30.0, 14.0
SS = 3                                          # 超采样倍数


def zone(v):
    if v < 45:  return GREEN
    if v < 55:  return AMBER
    if v < 70:  return ORANGE
    return RED


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    ex, ey = x1 + t * dx, y1 + t * dy
    return math.hypot(px - ex, py - ey)


def sample(x, y):
    """返回该点颜色（设计坐标系 512x512）；转轴画在指针之上"""
    dx, dy = x - CX, y - CY
    d = math.hypot(dx, dy)
    # 转轴（最上层）
    if d <= PIV_IN:
        return BG
    if d <= PIV:
        return WHITE
    # 指针（含圆头）
    if seg_dist(x, y, CX, CY, NX, NY) <= NW / 2.0:
        return WHITE
    # 圆弧：只取上半圆 0~180 度
    if RI <= d <= RO and dy <= 0.0:
        a = math.degrees(math.atan2(-dy, dx))     # 0(右) ~ 180(左)
        return zone((180.0 - a) / 1.8)
    return BG


def render(size):
    n = size * SS
    scale = 512.0 / n
    rows = []
    for j in range(size):
        row = bytearray()
        for i in range(size):
            r = g = b = 0
            for sy in range(SS):
                for sx in range(SS):
                    x = (i * SS + sx + 0.5) * scale
                    y = (j * SS + sy + 0.5) * scale
                    c = sample(x, y)
                    r += c[0]; g += c[1]; b += c[2]
            k = SS * SS
            row += bytes((r // k, g // k, b // k))
        rows.append(bytes(row))
    return rows


def write_png(path, size, rows):
    raw = b"".join(b"\x00" + r for r in rows)

    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    open(path, "wb").write(png)
    return len(png)


TARGETS = [("apple-touch-icon.png", 180), ("icon-192.png", 192),
           ("icon-512.png", 512), ("favicon.png", 64)]
for name, size in TARGETS:
    p = os.path.join(OUT, name)
    n = write_png(p, size, render(size))
    print(f"  {name:22s} {size}x{size}  {n/1024:.1f} KB")
print("done")
