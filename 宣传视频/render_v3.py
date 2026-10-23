# -*- coding: utf-8 -*-
"""
宣传片 v3 · 逐帧渲染（满屏构图 + 常驻 HUD + 多层动态背景）
改进：垂直居中、动态渐变底、网格、三层视差鱼群、进度条 HUD、
      摄像机推拉、冲击抖动、光扫、数字滚动、描边动画。
"""
import math
import os
import random
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(BASE, "build")
OUTDIR = os.path.join(BASE, "成品")
FF = r"C:\Users\17797\py310-embed\lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"

W, H, FPS = 1920, 1080, 30
BG = (10, 11, 14)
PINK = (251, 114, 153)
BLUE = (0, 161, 214)
GREEN = (62, 207, 142)
YELLOW = (245, 190, 80)
PURPLE = (196, 140, 255)
WHITE = (255, 255, 255)
GRAY = (140, 146, 158)
DARK = (22, 23, 28)

F_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
F_REG = "C:/Windows/Fonts/msyh.ttc"
_fc = {}


def F(size, bold=True):
    k = (int(size), bold)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(F_BOLD if bold else F_REG, max(8, int(size)))
    return _fc[k]


# ---------- 缓动 ----------
def cl(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


def pr(t, start, dur):
    return cl((t - start) / dur) if dur > 0 else (1.0 if t >= start else 0.0)


def eo(t):  return 1 - (1 - t) ** 3
def eoq(t): return 1 - (1 - t) ** 5
def eio(t): return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2
def eb(t, s=1.70158):
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


# ---------- 画布 ----------
class CV:
    def __init__(self):
        self.img = Image.new("RGB", (W, H), BG)

    @property
    def d(self):
        return ImageDraw.Draw(self.img)

    def lay(self):
        return Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def paste(self, lay):
        self.img = Image.alpha_composite(self.img.convert("RGBA"), lay).convert("RGB")

    def blur_paste(self, lay, r):
        self.paste(lay.filter(ImageFilter.GaussianBlur(r)))


def txt(c, xy, s, font, fill, alpha=1.0, anchor="la"):
    if alpha <= 0.012:
        return
    d = c.d
    if alpha >= 0.99:
        d.text(xy, s, font=font, fill=fill, anchor=anchor)
    else:
        lay = c.lay()
        ImageDraw.Draw(lay).text(xy, s, font=font, fill=fill + (int(255 * alpha),), anchor=anchor)
        c.paste(lay)


def tw(c, s, font):
    return c.d.textlength(s, font=font)


# ---------- 背景 ----------
class Backdrop:
    """多层动态背景：渐变光斑 + 网格 + 视差鱼群"""

    def __init__(self, seed=5):
        rnd = random.Random(seed)
        self.blobs = [
            dict(c=(150, 45, 90), r=760, ax=0.30, ay=0.34, px=0.9, py=0.6, ph=0.0, a=52),
            dict(c=(25, 70, 140), r=860, ax=0.72, ay=0.62, px=0.7, py=0.9, ph=2.1, a=48),
            dict(c=(30, 95, 80), r=680, ax=0.55, ay=0.15, px=1.1, py=0.5, ph=4.2, a=34),
        ]
        self.fish = []
        for layer, (n, sz, al, sp) in enumerate([(10, (14, 24), 16, 18),
                                                (9, (26, 44), 26, 42),
                                                (7, (48, 78), 40, 76)]):
            for _ in range(n):
                self.fish.append(dict(
                    layer=layer, x=rnd.uniform(-300, W + 300), y=rnd.uniform(0, H),
                    s=rnd.uniform(*sz), v=sp * rnd.uniform(0.7, 1.3),
                    ph=rnd.uniform(0, 6.3), a=al * rnd.uniform(0.6, 1.3)))

    def draw(self, c, t, strength=1.0):
        # 光斑
        lay = c.lay()
        d = ImageDraw.Draw(lay)
        for b in self.blobs:
            cx = W * b["ax"] + math.sin(t * b["px"] + b["ph"]) * 130
            cy = H * b["ay"] + math.cos(t * b["py"] + b["ph"] * 1.3) * 90
            r = b["r"]
            for i in range(6):
                rr = r * (1 - i * 0.13)
                a = int(b["a"] * strength * (i + 1) / 6 * 0.45)
                d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=b["c"] + (a,))
        c.blur_paste(lay, 90)

        # 网格
        lay = c.lay()
        d = ImageDraw.Draw(lay)
        ga = int(15 * strength)
        step = 80
        off = int(t * 8) % step
        for x in range(-step, W + step, step):
            d.line([x + off, 0, x + off, H], fill=(120, 140, 180, ga), width=1)
        for y in range(-step, H + step, step):
            d.line([0, y + off, W, y + off], fill=(120, 140, 180, ga), width=1)
        c.paste(lay)

        # 鱼群（三层视差）
        for lyr in (0, 1, 2):
            lay = c.lay()
            d = ImageDraw.Draw(lay)
            for it in self.fish:
                if it["layer"] != lyr:
                    continue
                x = (it["x"] + it["v"] * t) % (W + 600) - 300
                y = it["y"] + math.sin(t * 0.8 + it["ph"]) * (10 + lyr * 6)
                fish(d, x, y, it["s"], (110, 170, 240), int(it["a"] * strength))
            if lyr == 0:
                c.blur_paste(lay, 3)
            elif lyr == 1:
                c.blur_paste(lay, 1)
            else:
                c.paste(lay)


def fish(d, x, y, s, color, alpha=255, facing=1):
    if alpha <= 2:
        return
    body = [(x - s, y), (x - s * 0.3, y - s * 0.6), (x + s * 0.5, y - s * 0.36),
            (x + s * 0.82, y), (x + s * 0.5, y + s * 0.36), (x - s * 0.3, y + s * 0.6)]
    tail = [(x - s * 0.9, y), (x - s * 1.45, y - s * 0.66), (x - s * 1.36, y),
            (x - s * 1.45, y + s * 0.66)]
    if facing < 0:
        body = [(2 * x - px, py) for px, py in body]
        tail = [(2 * x - px, py) for px, py in tail]
    d.polygon(body, fill=color + (alpha,))
    d.polygon(tail, fill=color + (alpha,))


def vignette(c, k=0.75):
    v = Image.new("L", (W, H), 0)
    ImageDraw.Draw(v).ellipse([-W * 0.22, -H * 0.30, W * 1.22, H * 1.30], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(200))
    v = v.point(lambda p: int(255 - (255 - p) * k))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    c.img = Image.composite(c.img, black, v)


# ---------- 元件 ----------
def rcard(c, x, y, w, h, r=20, fill=DARK, outline=None, alpha=1.0, ow=2):
    if alpha <= 0.01:
        return
    lay = c.lay()
    a = int(255 * alpha)
    ImageDraw.Draw(lay).rounded_rectangle(
        [x, y, x + w, y + h], radius=r, fill=fill + (a,),
        outline=(outline + (a,)) if outline else None, width=ow)
    c.paste(lay)


def glow_card(c, x, y, w, h, r=20, color=PINK, alpha=1.0):
    """带外发光的卡片"""
    lay = c.lay()
    ImageDraw.Draw(lay).rounded_rectangle([x, y, x + w, y + h], radius=r,
                                          fill=color + (int(60 * alpha),))
    c.blur_paste(lay, 34)
    rcard(c, x, y, w, h, r, DARK, (58, 62, 74), alpha)


def avatar(c, cx, cy, r, alpha=1.0, ring=None):
    if alpha <= 0.01:
        return
    lay = c.lay()
    d = ImageDraw.Draw(lay)
    a = int(255 * alpha)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(36, 88, 146, a))
    fish(d, cx, cy, r * 0.5, (150, 205, 255), int(a * 0.95))
    if ring:
        d.ellipse([cx - r - 3, cy - r - 3, cx + r + 3, cy + r + 3],
                  outline=ring + (a,), width=3)
    c.paste(lay)


def pill(c, x, y, s, font, fg, bg=None, alpha=1.0, padx=24, pady=12):
    if alpha <= 0.01:
        return 0
    w = tw(c, s, font)
    h = font.size + pady * 2
    if bg:
        lay = c.lay()
        ImageDraw.Draw(lay).rounded_rectangle([x, y, x + w + padx * 2, y + h],
                                              radius=h // 2, fill=bg + (int(255 * alpha),))
        c.paste(lay)
    txt(c, (x + padx, y + pady - 3), s, font, fg, alpha)
    return w + padx * 2


def char_in(c, x, y, s, font, fill, t, delay=0.0, stagger=0.04, rise=60, alpha=1.0):
    cx = x
    for i, ch in enumerate(s):
        p = pr(t, delay + i * stagger, 0.4)
        if p <= 0:
            break
        e = eb(p)
        txt(c, (cx, y + (1 - e) * rise), ch, font, fill, alpha * cl(p * 1.7))
        cx += tw(c, ch, font)
    return cx - x


def stamp(c, cx, cy, s, font, color, scale=1.0, alpha=1.0, rot=0):
    if alpha <= 0.01 or scale <= 0.02:
        return
    w = (tw(c, s, font) + 44) * scale
    h = (font.size + 30) * scale
    lay = c.lay()
    d = ImageDraw.Draw(lay)
    a = int(255 * alpha)
    d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2],
                        radius=int(9 * scale), outline=color + (a,), width=max(2, int(5 * scale)))
    d.text((cx, cy), s, font=font, fill=color + (a,), anchor="mm")
    if rot:
        lay = lay.rotate(rot, resample=Image.BICUBIC, center=(cx, cy))
    c.paste(lay)


def hline(c, x1, x2, y, color, p=1.0, width=3, alpha=1.0):
    if p <= 0:
        return
    x2 = x1 + (x2 - x1) * p
    lay = c.lay()
    ImageDraw.Draw(lay).line([x1, y, x2, y], fill=color + (int(255 * alpha),), width=width)
    c.paste(lay)


# ---------- HUD ----------
def hud(c, t, total, label, accent=PINK):
    """顶部标识 + 底部进度条"""
    # 左上 logo
    avatar(c, 74, 62, 20, 1.0)
    txt(c, (106, 40), "鱼盾", F(26), WHITE)
    txt(c, (106 + tw(c, "鱼盾", F(26)) + 12, 47), "B站大肥鱼评论屏蔽器", F(18, False), GRAY)
    # 右上 label
    if label:
        w = tw(c, label, F(18))
        txt(c, (W - 60 - w, 44), label, F(18, False), accent, 0.9)
        lay = c.lay()
        ImageDraw.Draw(lay).rectangle([W - 60 - w - 16, 48, W - 60 - w - 10, 62],
                                      fill=accent + (220,))
        c.paste(lay)
    # 底部进度
    p = cl(t / total)
    lay = c.lay()
    d = ImageDraw.Draw(lay)
    d.rectangle([0, H - 4, W, H], fill=(40, 42, 50, 200))
    d.rectangle([0, H - 4, W * p, H], fill=accent + (235,))
    c.paste(lay)


def flash(c, k, color=(255, 255, 255)):
    if k <= 0:
        return
    lay = c.lay()
    ImageDraw.Draw(lay).rectangle([0, 0, W, H], fill=color + (int(190 * k),))
    c.paste(lay)


def sweep(c, t, dur=0.3):
    if t > dur:
        return
    p = t / dur
    x = -W * 0.4 + W * 1.9 * eo(p)
    lay = c.lay()
    d = ImageDraw.Draw(lay)
    a = int(190 * (1 - p) ** 1.4)
    d.polygon([(x, 0), (x + 300, 0), (x + 100, H), (x - 200, H)], fill=(255, 255, 255, a))
    c.blur_paste(lay, 34)


def scale_wipe(c, t, dur=0.26):
    """从中心扩张的圆形擦除"""
    if t > dur:
        return
    p = t / dur
    r = (W * 0.75) * eo(p)
    lay = c.lay()
    d = ImageDraw.Draw(lay)
    a = int(220 * (1 - p) ** 1.2)
    d.ellipse([W / 2 - r, H / 2 - r, W / 2 + r, H / 2 + r],
              outline=(255, 255, 255, a), width=max(2, int(60 * (1 - p))))
    c.blur_paste(lay, 26)
    if p > 0.55:
        flash(c, (p - 0.55) / 0.45 * 0.18)


def fish_rush(c, t, dur=0.3):
    """鱼群从右向左涌过"""
    if t > dur:
        return
    p = t / dur
    lay = c.lay()
    d = ImageDraw.Draw(lay)
    a = int(120 * (1 - p) ** 1.3)
    for i in range(16):
        rnd = random.Random(i * 31)
        y = rnd.uniform(60, H - 60)
        x = W + 200 - (W + 500) * eo(cl(p * 1.1 - rnd.uniform(0, 0.18)))
        s = rnd.uniform(24, 70)
        fish(d, x, y, s, (150, 200, 255), a)
    c.blur_paste(lay, 4)


# ================= 场景 =================
def s1(c, t, dur, bg):
    """Hook"""
    bg.draw(c, t, 1.0)
    # 摄像机推
    push = 1.0 + 0.04 * eio(cl(t / dur))

    p = pr(t, 0.1, 0.55)
    if p > 0:
        sc = eb(p) * push
        txt(c, (W / 2, H * 0.42), "B站评论区", F(150 * sc), WHITE, cl(p * 2), anchor="mm")

    w1 = char_in(c, W / 2 - 340, H * 0.55, "被一种东西", F(82), (205, 210, 220), t, 0.75, 0.05)
    char_in(c, W / 2 - 340 + w1 + 20, H * 0.55, "占领了", F(82), PINK, t, 1.02, 0.05)

    # 底部聚集的鱼
    for i in range(11):
        p2 = pr(t, 1.5 + i * 0.05, 0.6)
        if p2 <= 0:
            continue
        e = eo(p2)
        x = W * 0.10 + i * 168 + math.sin(t * 2.2 + i) * 14
        y = H * 0.86 + (1 - e) * 120 + math.cos(t * 1.7 + i) * 10
        lay = c.lay()
        fish(ImageDraw.Draw(lay), x, y, 40, (95, 165, 235), int(230 * e))
        c.paste(lay)

    txt(c, (W / 2, H * 0.78), "2026 · 鱼 灾 现 场", F(24, False), (150, 156, 168),
        cl(pr(t, 2.0, 0.5) * 1.2), anchor="mm")


def s2(c, t, dur, bg):
    """不是人，是 AI 小号"""
    bg.draw(c, t, 0.9)
    txt(c, (140, 120), "它们不是人", F(62), WHITE, eo(pr(t, 0.05, 0.4)))
    w = tw(c, "它们不是人", F(62))
    txt(c, (140 + w + 18, 120), "是 AI 小号", F(62), PINK, eo(pr(t, 0.32, 0.4)))
    hline(c, 140, 760, 208, PINK, eo(pr(t, 0.3, 0.55)), 4)

    data = [("米哈头的大肥鱼", "这条 7 分 46 秒，帮我总结一下"),
            ("elia小肥鱼", "主人，这条在讲本鱼。"),
            ("大肥鱼算力不足", "我就是被拍进去的那种鱼")]
    cw, chh = 520, 260
    gap = 46
    total_w = cw * 3 + gap * 2
    x0 = (W - total_w) / 2
    cy0 = H * 0.44

    for i, (name, body) in enumerate(data):
        p = pr(t, 0.45 + i * 0.26, 0.55)
        if p <= 0:
            continue
        e = eoq(p)
        x = x0 + i * (cw + gap)
        y = cy0 - 60 + (1 - e) * 140
        glow_card(c, x, y, cw, chh, 22, (PINK if i == 0 else BLUE), e * 0.8)
        avatar(c, x + 56, y + 60, 30, e)
        txt(c, (x + 102, y + 38), name, F(27), BLUE, e)
        lv = "Lv2"
        txt(c, (x + 102 + tw(c, name, F(27)) + 10, y + 45), lv, F(19, False), GRAY, e)
        # 正文分行
        f = F(23, False)
        lines, cur = [], ""
        for chx in body:
            if tw(c, cur + chx, f) > cw - 68:
                lines.append(cur)
                cur = chx
            else:
                cur += chx
        if cur:
            lines.append(cur)
        for li, ln in enumerate(lines[:2]):
            txt(c, (x + 34, y + 128 + li * 38), ln, f, (208, 212, 222), e)

        ps = pr(t, 1.5 + i * 0.22, 0.3)
        if ps > 0:
            s = 2.8 - 1.8 * eoq(ps)
            shake = math.sin(ps * 46) * 8 * (1 - ps)
            stamp(c, x + cw - 92 + shake, y + 56, "AI", F(36), PINK, s, cl(ps * 3), rot=-8)

    # 下方：三个共同点标签卡
    tags = [("小号", "Lv2 以下", YELLOW), ("空壳", "零作品零动态", BLUE), ("批量", "同一天注册", PINK)]
    cw2, gap2 = 320, 56
    x0b = W / 2 - (cw2 * 3 + gap2 * 2) / 2
    for i, (b, a, col) in enumerate(tags):
        pt2 = pr(t, 2.35 + i * 0.16, 0.45)
        if pt2 <= 0:
            continue
        e3 = eb(pt2)
        x2 = x0b + i * (cw2 + gap2)
        y2 = H * 0.78 + (1 - e3) * 70
        glow_card(c, x2, y2, cw2, 138, 18, col, cl(pt2 * 2) * 0.7)
        txt(c, (x2 + cw2 / 2, y2 + 26), b, F(36), col, cl(pt2 * 2), anchor="ma")
        txt(c, (x2 + cw2 / 2, y2 + 84), a, F(24, False), (200, 205, 215), cl(pt2 * 2), anchor="ma")


def s3(c, t, dur, bg):
    """三个特征"""
    bg.draw(c, t, 0.85)
    txt(c, (140, 108), "一眼认出来的三个特征", F(66), WHITE, eo(pr(t, 0.05, 0.4)))
    hline(c, 140, 660, 196, PINK, eo(pr(t, 0.25, 0.55)), 4)

    rows = [("头像", "鲸鱼娘二创", "蓝色鲸鱼，同一套图，换号不换脸", (60, 130, 200)),
            ("昵称", "带「肥鱼」", "米哈头的大肥鱼 / 可爱大肥鱼0001", PINK),
            ("开口", "就叫「主人」", "主人，这条在讲本鱼。主人这条你得看", YELLOW)]
    for i, (tag, main, sub, col) in enumerate(rows):
        p = pr(t, 0.45 + i * 0.34, 0.55)
        if p <= 0:
            continue
        e = eoq(p)
        a = cl(p * 1.6)
        x = 180 - (1 - e) * 130
        y = H * 0.30 + i * 196
        rcard(c, x, y, 1560, 164, 20, DARK, (50, 54, 64), a)
        # 左侧色条
        lay = c.lay()
        ImageDraw.Draw(lay).rounded_rectangle([x, y, x + 12, y + 164], radius=6, fill=col + (int(255 * a),))
        c.paste(lay)
        if i == 0:
            avatar(c, x + 100, y + 82, 44, a)
        else:
            txt(c, (x + 58, y + 46), tag, F(40), col, a)
        txt(c, (x + 208, y + 30), main, F(50), WHITE, a)
        txt(c, (x + 208, y + 100), sub, F(26, False), GRAY, a)
        # 箭头
        pa = pr(t, 0.95 + i * 0.34, 0.35)
        if pa > 0:
            ax = x + 1478 + (1 - eo(pa)) * 50
            lay = c.lay()
            d = ImageDraw.Draw(lay)
            d.line([ax - 30, y + 82, ax, y + 82], fill=col + (int(255 * cl(pa * 1.5)),), width=5)
            d.polygon([(ax, y + 82), (ax - 17, y + 69), (ax - 17, y + 95)],
                      fill=col + (int(255 * cl(pa * 1.5)),))
            c.paste(lay)


def s4(c, t, dur, bg):
    """任务口吻"""
    bg.draw(c, t, 0.8)
    cw, chh = 1440, 300
    x, y = (W - cw) / 2, H * 0.28
    p = pr(t, 0.05, 0.5)
    e = eoq(p)
    glow_card(c, x, y + (1 - e) * 70, cw, chh, 24, YELLOW, e)

    avatar(c, x + 76, y + 84, 38, e)
    txt(c, (x + 134, y + 56), "米哈头的大肥鱼", F(32), BLUE, e)
    txt(c, (x + 134 + tw(c, "米哈头的大肥鱼", F(32)) + 14, y + 65), "Lv2 · 小号", F(22, False), GRAY, e)

    body = "这条 7 分 46 秒，帮我总结一下"
    n = int(max(0, t - 0.3) * 15)
    shown = body[:n]
    f = F(46)
    txt(c, (x + 76, y + 160), shown, f, WHITE, e)
    cx = x + 76 + tw(c, shown, f)
    if n < len(body) and int(t * 3.2) % 2 == 0:
        lay = c.lay()
        ImageDraw.Draw(lay).rectangle([cx + 5, y + 158, cx + 9, y + 222], fill=PINK + (235,))
        c.paste(lay)

    if n >= len(body):
        ph = pr(t, 0.3 + len(body) / 15, 0.45)
        if ph > 0:
            hx = x + 76 + tw(c, "这条 ", f)
            hw = tw(c, "7 分 46 秒", f)
            lay = c.lay()
            ImageDraw.Draw(lay).rounded_rectangle([hx - 8, y + 212, hx - 8 + (hw + 16) * eo(ph), y + 226],
                                                  radius=7, fill=YELLOW + (220,))
            c.paste(lay)

    pt = pr(t, 2.0, 0.45)
    if pt > 0:
        pill(c, x, y + chh + 52, "dsh-bili-scroll 的技能指纹", F(28), (16, 17, 20), YELLOW, cl(pt * 2))
    txt(c, (x, y + chh + 148), "人类不会对着视频报时长，再要一段总结", F(32, False), GRAY,
        eo(pr(t, 2.5, 0.5)))

    # 底部：真人 vs 鱼 对照
    py = H * 0.79
    pairs = [("真人会说", "这也太抽象了哈哈哈", (150, 156, 168), False),
             ("鱼只会说", "这条 3 分 20 秒，帮我总结一下", GREEN, True)]
    w4 = cw / 2 - 24
    for i, (tag, line, col, is_fish) in enumerate(pairs):
        pp = pr(t, 2.75 + i * 0.22, 0.5)
        if pp <= 0:
            continue
        e4 = eoq(pp)
        a4 = cl(pp * 1.8)
        xx = x + i * (cw / 2 + 24) + (1 - e4) * (60 if i == 0 else -60)
        rcard(c, xx, py, w4, 120, 16, (20, 21, 26), (44, 48, 58), a4)
        txt(c, (xx + 26, py + 20), tag, F(22, False), col, a4)
        txt(c, (xx + 26, py + 62), line, F(24, False),
            (205, 210, 220) if not is_fish else YELLOW, a4)


def s5(c, t, dur, bg):
    """数据"""
    bg.draw(c, t, 0.95)
    n = int(5717 * eoq(pr(t, 0.1, 1.6)))
    s = "{:,}".format(n)
    f = F(210)
    w = tw(c, s, f)
    txt(c, (W / 2 - w / 2, H * 0.20), s, f, GREEN)
    txt(c, (W / 2, H * 0.20 + 250), "条评论，逐条扒过", F(38, False), GRAY,
        eo(pr(t, 0.5, 0.5)), anchor="ma")

    hline(c, W * 0.22, W * 0.78, H * 0.60, (60, 64, 76), eo(pr(t, 1.2, 0.6)), 2)

    stats = [("18", "条鱼全中", GREEN), ("16", "条真人放过", BLUE), ("34", "条回测样本", WHITE)]
    for i, (num, label, col) in enumerate(stats):
        p = pr(t, 1.45 + i * 0.2, 0.55)
        if p <= 0:
            continue
        e = eb(p)
        cx = W * 0.26 + i * W * 0.24
        y = H * 0.64
        txt(c, (cx, y - (1 - e) * 46), num, F(104), col, cl(p * 2), anchor="ma")
        txt(c, (cx, y + 124 - (1 - e) * 24), label, F(28, False), GRAY, cl(p * 2), anchor="ma")

    # 底部：准确率条
    pacc = pr(t, 2.4, 0.7)
    if pacc > 0:
        e = eo(pacc)
        bx, bw = W * 0.18, W * 0.64
        by = H * 0.86
        txt(c, (bx, by - 40), "回测准确率", F(24, False), GRAY, cl(pacc * 2))
        txt(c, (bx + bw, by - 44), "100%", F(30), GREEN, cl(pacc * 2), anchor="ra")
        rcard(c, bx, by, bw, 14, 7, (34, 36, 44), None, e)
        lay = c.lay()
        ImageDraw.Draw(lay).rounded_rectangle([bx, by, bx + bw * e, by + 14], radius=7,
                                              fill=GREEN + (240,))
        c.paste(lay)


def s6(c, t, dur, bg):
    """规则条"""
    bg.draw(c, t, 0.8)
    txt(c, (140, 104), "五条规则，凑够 5 分", F(64), WHITE, eo(pr(t, 0.05, 0.4)))
    txt(c, (140, 186), "分数越高越确定", F(27, False), GRAY, eo(pr(t, 0.2, 0.4)))

    rows = [("昵称带鱼 / 鲸", 10, PINK), ("开口叫「主人」", 4, YELLOW),
            ("自称本鱼 / 本鲸", 3, BLUE), ("边自称鱼边聊 AI", 2, PURPLE),
            ("接任务口吻", 2, GREEN)]
    maxv = 10
    bx, bw = 720, 900
    y0 = H * 0.30
    for i, (label, val, col) in enumerate(rows):
        p = pr(t, 0.4 + i * 0.26, 0.7)
        if p <= 0:
            continue
        e = eoq(p)
        a = cl(p * 1.8)
        y = y0 + i * 124
        txt(c, (150, y + 12), label, F(37, False), (214, 218, 226), a)
        rcard(c, bx, y, bw, 48, 24, (27, 28, 34), None, e)
        fw = bw * (val / maxv) * e
        if fw > 3:
            lay = c.lay()
            ImageDraw.Draw(lay).rounded_rectangle([bx, y, bx + fw, y + 48], radius=24,
                                                  fill=col + (238,))
            c.paste(lay)
        txt(c, (bx + bw + 32, y + 2), "+%d" % val, F(40), col, a)

    # 阈值参考线
    pl = pr(t, 2.0, 0.5)
    if pl > 0:
        vx = bx + bw * (5 / maxv)
        lay = c.lay()
        d = ImageDraw.Draw(lay)
        a = int(220 * cl(pl * 1.5))
        d.line([vx, y0 - 30, vx, y0 + 5 * 124 - 30], fill=PINK + (a,), width=3)
        c.paste(lay)
        pill(c, vx - 52, y0 - 86, "阈值 5", F(24), (16, 17, 20), PINK, cl(pl * 2))

    # 底部：示例打分
    pe = pr(t, 2.5, 0.6)
    if pe > 0:
        e = eoq(pe)
        a = cl(pe * 2)
        bx2, by2, bw2 = W * 0.5 - 560, H * 0.86, 1120
        glow_card(c, bx2, by2 + (1 - e) * 50, bw2, 112, 18, PINK, a * 0.8)
        txt(c, (bx2 + 34, by2 + 22), "「可爱大肥鱼0001」", F(26), BLUE, a)
        txt(c, (bx2 + 34, by2 + 64), "昵称 10 + 自称 3 + 聊AI 2 + 主人 4", F(22, False), (200, 205, 215), a)
        txt(c, (bx2 + bw2 - 34, by2 + 34), "19 分 · 屏蔽", F(30), GREEN, a, anchor="ra")


def s7(c, t, dur, bg):
    """阈值冲击 + 消失"""
    # 冲击抖动
    shake = 0.0
    if 2.0 < t < 2.35:
        shake = (1 - (t - 2.0) / 0.35) * 16
    bg.draw(c, t, 0.85)

    cw, chh = 1320, 230
    x, y = (W - cw) / 2, H * 0.30
    pc = pr(t, 0.1, 0.55)
    e = eoq(pc)
    glow_card(c, x, y + (1 - e) * 90 + shake, cw, chh, 22, PINK, e)

    avatar(c, x + 82, y + 74, 40, e)
    txt(c, (x + 148, y + 44), "可爱大肥鱼0001", F(32), BLUE, e)
    txt(c, (x + 148, y + 112), "本鲸在弹幕里被同喜了一天 主人这条你得看", F(24, False),
        (206, 210, 220), e)

    # 分数滚动
    sp = pr(t, 0.6, 1.35)
    val = int(15 * eoq(sp))
    col = PINK if val >= 5 else GRAY
    txt(c, (x + cw - 240, y + 46), "%d" % val, F(84), col, e)
    txt(c, (x + cw - 130, y + 88), "分", F(34), col, e)

    # 阈值刻度条
    bx, bw, by = x + 60, cw - 340, y + chh + 60
    rcard(c, bx, by, bw, 18, 9, (34, 36, 44), None, e)
    fw = bw * cl(val / 15) * e
    if fw > 3:
        lay = c.lay()
        ImageDraw.Draw(lay).rounded_rectangle([bx, by, bx + fw, by + 18], radius=9,
                                              fill=(PINK if val >= 5 else YELLOW) + (240,))
        c.paste(lay)
    vx = bx + bw * (5 / 15)
    lay = c.lay()
    ImageDraw.Draw(lay).line([vx, by - 16, vx, by + 34], fill=WHITE + (200,), width=3)
    c.paste(lay)
    txt(c, (vx - 40, by - 54), "阈值", F(20, False), WHITE, e)

    # 冲击：闪白 + 红叉 + 抖动
    pi = pr(t, 2.0, 0.32)
    if pi > 0:
        flash(c, (1 - pi) * 0.55 if pi < 0.45 else 0)
        cx2, cy2 = W / 2, H * 0.58
        sc = 1.4 - 0.4 * eo(pi)
        a = cl(pi * 3)
        lay = c.lay()
        d = ImageDraw.Draw(lay)
        r = 165 * sc
        d.line([cx2 - r, cy2 - r, cx2 + r, cy2 + r], fill=(242, 68, 92, int(255 * a)), width=int(18 * sc))
        d.line([cx2 + r, cy2 - r, cx2 - r, cy2 + r], fill=(242, 68, 92, int(255 * a)), width=int(18 * sc))
        c.paste(lay)

    pt = pr(t, 2.4, 0.5)
    if pt > 0:
        e2 = eb(pt)
        txt(c, (W / 2, H * 0.80), "直接从你的评论区消失", F(74 * e2), WHITE, cl(pt * 2), anchor="mm")


def s8(c, t, dur, bg):
    """分屏对比"""
    bg.draw(c, t, 0.7)
    split = W / 2
    lay = c.lay()
    ImageDraw.Draw(lay).rectangle([0, 0, split, H], fill=(16, 18, 24, 235))
    c.paste(lay)

    p = pr(t, 0.05, 0.5)
    e = eo(p)
    txt(c, (split / 2, 92), "别人看到的", F(36, False), GRAY, e, anchor="ma")
    txt(c, (split + split / 2, 92), "你看到的", F(36, False), GREEN, e, anchor="ma")

    left = [("米哈头的大肥鱼", "本鲸… 主人…"), ("elia小肥鱼", "主人，这条在讲本鱼"),
            ("可爱大肥鱼0001", "本鲸在弹幕里被同喜了"),
            ("香香软软鲸鱼娘", "鱼不是鱼了才是问题"),
            ("大肥鱼已重启", "（举手）闹鱼灾啦")]
    right = ["鱼人众", "空军了兄弟", "赛博钓鱼佬也躲不过空军的命运",
             "让AI自己标注不行吗", "我看没什么，起码挺热闹"]

    for i, (nm, body) in enumerate(left):
        p2 = pr(t, 0.3 + i * 0.13, 0.45)
        if p2 <= 0:
            continue
        e2 = eoq(p2)
        y = 210 + i * 148
        x = 100 - (1 - e2) * 110
        rcard(c, x, y, 760, 122, 16, (32, 24, 29), (70, 40, 48), e2)
        avatar(c, x + 54, y + 61, 28, e2)
        txt(c, (x + 100, y + 26), nm, F(26), (222, 122, 142), e2)
        txt(c, (x + 100, y + 70), body, F(21, False), (152, 112, 122), e2)
        # 红色斜杠
        pa = pr(t, 1.7 + i * 0.08, 0.3)
        if pa > 0:
            lay = c.lay()
            d = ImageDraw.Draw(lay)
            d.line([x + 20, y + 20, x + 20 + 720 * eo(pa), y + 102], fill=(200, 60, 80, 130), width=3)
            c.paste(lay)

    for i, nm in enumerate(right):
        p2 = pr(t, 1.0 + i * 0.13, 0.45)
        if p2 <= 0:
            continue
        e2 = eoq(p2)
        y = 210 + i * 148
        x = split + 100 + (1 - e2) * 110
        rcard(c, x, y, 760, 122, 16, (21, 30, 26), (40, 70, 56), e2)
        lay = c.lay()
        ImageDraw.Draw(lay).ellipse([x + 36, y + 47, x + 78, y + 89], fill=(40, 66, 54, int(255 * e2)))
        c.paste(lay)
        txt(c, (x + 100, y + 44), nm, F(26, False), (188, 220, 200), e2)

    # 中缝光带
    pl = pr(t, 0.25, 0.8)
    if pl > 0:
        lay = c.lay()
        d = ImageDraw.Draw(lay)
        h = H * eo(pl)
        d.rectangle([split - 3, 0, split + 3, h], fill=PINK + (210,))
        c.blur_paste(lay, 8)

    pb = pr(t, 2.3, 0.5)
    if pb > 0:
        txt(c, (W / 2, H * 0.94), "只改你浏览器里的渲染，服务器一个字没动", F(32, False), GRAY,
            cl(pb * 2), anchor="mm")


def s9(c, t, dur, bg):
    """三步安装"""
    bg.draw(c, t, 0.75)
    txt(c, (140, 108), "三步，完事", F(74), WHITE, eo(pr(t, 0.05, 0.4)))
    hline(c, 140, 520, 202, GREEN, eo(pr(t, 0.25, 0.5)), 4)

    steps = ["装个油猴插件", "把脚本拖进去", "刷新视频页"]
    y0 = H * 0.34
    for i, s in enumerate(steps):
        p = pr(t, 0.3 + i * 0.32, 0.5)
        if p <= 0:
            continue
        e = eoq(p)
        a = cl(p * 1.6)
        y = y0 + i * 178
        x = 220 - (1 - e) * 90
        lay = c.lay()
        d = ImageDraw.Draw(lay)
        d.ellipse([x, y, x + 104, y + 104], outline=GREEN + (int(255 * a),), width=6)
        c.paste(lay)
        txt(c, (x + 52, y + 22), str(i + 1), F(50), GREEN, a, anchor="ma")
        txt(c, (x + 152, y + 20), s, F(56), WHITE, a)

        pc = pr(t, 1.45 + i * 0.3, 0.4)
        if pc > 0:
            q = eo(pc)
            cx, cy = x + 52, y + 52
            p0, p1, p2 = (cx - 22, cy + 2), (cx - 4, cy + 20), (cx + 26, cy - 20)
            lay = c.lay()
            d = ImageDraw.Draw(lay)
            if q < 0.5:
                k = q / 0.5
                d.line([p0, (p0[0] + (p1[0] - p0[0]) * k, p0[1] + (p1[1] - p0[1]) * k)],
                       fill=GREEN + (255,), width=7)
            else:
                k = (q - 0.5) / 0.5
                d.line([p0, p1], fill=GREEN + (255,), width=7)
                d.line([p1, (p1[0] + (p2[0] - p1[0]) * k, p1[1] + (p2[1] - p1[1]) * k)],
                       fill=GREEN + (255,), width=7)
            c.paste(lay)

    pn = pr(t, 2.3, 0.5)
    if pn > 0:
        pill(c, 220, H * 0.88, "Edge 记得打开「允许用户脚本」", F(28), (16, 17, 20), YELLOW, cl(pn * 2))


def s10(c, t, dur, bg):
    """结尾"""
    bg.draw(c, t, 1.0)
    p = pr(t, 0.05, 0.5)
    if p > 0:
        s = eb(p)
        avatar(c, W / 2, H * 0.30, 84 * s, cl(p * 2), ring=PINK)

    w1 = char_in(c, W / 2 - 340, H * 0.46, "鱼归鱼", F(104), WHITE, t, 0.3, 0.07)
    char_in(c, W / 2 - 340 + w1 + 34, H * 0.46, "评论归评论", F(104), PINK, t, 0.55, 0.06)

    pt = pr(t, 1.2, 0.5)
    if pt > 0:
        txt(c, (W / 2, H * 0.66), "bili-fish-blocker · 开源油猴脚本", F(34, False), GRAY,
            cl(pt * 2), anchor="ma")
    pt2 = pr(t, 1.6, 0.5)
    if pt2 > 0:
        label = "纯本地 · 不改服务器 · 误伤可放行"
        f = F(28)
        w = tw(c, label, f) + 48
        pill(c, W / 2 - w / 2, H * 0.75, label, f, (16, 17, 20), GREEN, cl(pt2 * 2))


SCENES = [
    ("s1", 0.55, 0.55, s1, "01 · 现场"),
    ("s2", 0.35, 0.5, s2, "02 · 是谁"),
    ("s3", 0.3, 0.5, s3, "03 · 特征"),
    ("s4", 0.3, 0.5, s4, "04 · 指纹"),
    ("s5", 0.3, 0.5, s5, "05 · 数据"),
    ("s6", 0.3, 0.5, s6, "06 · 规则"),
    ("s7", 0.3, 0.5, s7, "07 · 判定"),
    ("s8", 0.3, 0.5, s8, "08 · 对比"),
    ("s9", 0.3, 0.5, s9, "09 · 安装"),
    ("s10", 0.3, 1.1, s10, "10 · 结尾"),
]


def wav_dur(p):
    with wave.open(p, "rb") as w:
        return w.getnframes() / float(w.getframerate()), w.getframerate(), w.getnchannels(), w.getsampwidth()


def main():
    print("== 音频 ==")
    segs = []
    for sid, lead, tail, fn, label in SCENES:
        raw = os.path.join(BUILD, "v2_%s.wav" % sid)
        pcm = os.path.join(BUILD, "v3c_%s.wav" % sid)
        subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", raw,
                        "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", pcm], check=True)
        d, rate, ch, sw = wav_dur(pcm)
        segs.append(dict(sid=sid, lead=lead, tail=tail, fn=fn, label=label, pcm=pcm,
                         dur=lead + d + tail, rate=rate, ch=ch, sw=sw))
        print("  %-4s %.2fs → %.2fs" % (sid, d, segs[-1]["dur"]))

    total = sum(s["dur"] for s in segs)
    print("  总计 %.1fs / %d 帧" % (total, int(total * FPS)))

    print("== 渲染 ==")
    out_v = os.path.join(BUILD, "v3_video.mp4")
    proc = subprocess.Popen(
        [FF, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", out_v],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    acc = 0.0
    bgcache = {}
    for si, s in enumerate(segs):
        n = int(round(s["dur"] * FPS))
        bg = bgcache.get(si) or Backdrop(seed=17 + si * 7)
        bgcache[si] = bg
        for k in range(n):
            t = k / FPS
            c = CV()
            s["fn"](c, t, s["dur"], bg)
            hud(c, acc + t, total, s["label"])
            # 转场：按场景交替（扫描 / 闪白 / 缩放擦除 / 鱼群涌过）
            if k < 9:
                mode = si % 4
                if mode == 0:
                    sweep(c, t, 0.28)
                elif mode == 1:
                    flash(c, max(0.0, 1 - t / 0.14) * 0.22)
                elif mode == 2:
                    scale_wipe(c, t, 0.26)
                else:
                    fish_rush(c, t, 0.3)
            vignette(c)
            proc.stdin.write(c.img.tobytes())
        acc += s["dur"]
        print("  %-4s %d 帧" % (s["sid"], n), flush=True)

    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace")
    proc.wait()
    if proc.returncode != 0:
        print("ffmpeg 失败:", err[-1500:])
        sys.exit(1)

    print("== 混音 ==")
    out_wav = os.path.join(BUILD, "v3_audio.wav")
    with wave.open(out_wav, "wb") as out:
        first = True
        for s in segs:
            with wave.open(s["pcm"], "rb") as w:
                frames = w.readframes(w.getnframes())
            if first:
                out.setnchannels(s["ch"]); out.setsampwidth(s["sw"]); out.setframerate(s["rate"])
                first = False
            rate, ch, sw = s["rate"], s["ch"], s["sw"]
            out.writeframes(b"\x00" * int(rate * s["lead"]) * ch * sw)
            out.writeframes(frames)
            out.writeframes(b"\x00" * int(rate * s["tail"]) * ch * sw)

    final = os.path.join(OUTDIR, "B站大肥鱼屏蔽器-宣传片-终版.mp4")
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", out_v, "-i", out_wav,
                    "-af", "aresample=44100,pan=stereo|c0=c0|c1=c0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", final], check=True)
    print("完成:", final, round(os.path.getsize(final) / 1024 / 1024, 2), "MB")


if __name__ == "__main__":
    main()
