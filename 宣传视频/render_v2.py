# -*- coding: utf-8 -*-
"""
宣传片 v2 · 逐帧程序化渲染
动效：字符弹簧入场、鱼群粒子、卡片飞入、印章砸落、打字机、数字滚动、
      进度条生长、阈值穿越冲击、分屏擦除、描边对勾、扫描线。
输出：1920x1080 / 30fps / H.264，音频用 CosyVoice 人声。
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
BG = (13, 14, 18)
PINK = (251, 114, 153)
BLUE = (0, 161, 214)
GREEN = (62, 207, 142)
YELLOW = (245, 190, 80)
PURPLE = (200, 140, 255)
WHITE = (255, 255, 255)
GRAY = (138, 144, 155)
DIM = (34, 36, 43)

F_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
F_REG = "C:/Windows/Fonts/msyh.ttc"
_fonts = {}


def F(size, bold=True):
    k = (size, bold)
    if k not in _fonts:
        _fonts[k] = ImageFont.truetype(F_BOLD if bold else F_REG, size)
    return _fonts[k]


# ---------------- 缓动 ----------------
def clamp01(x):
    return 0.0 if x < 0 else (1.0 if x > 1 else x)


def prog(t, start, dur):
    return clamp01((t - start) / dur) if dur > 0 else (1.0 if t >= start else 0.0)


def ease_out(t):
    return 1 - (1 - t) ** 3


def ease_in(t):
    return t ** 3


def ease_io(t):
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_back(t, s=1.70158):
    t -= 1
    return t * t * ((s + 1) * t + s) + 1


def ease_out_quint(t):
    return 1 - (1 - t) ** 5


# ---------------- 画布工具 ----------------
class Canvas:
    def __init__(self, bg=BG):
        self.img = Image.new("RGB", (W, H), bg)
        self.d = ImageDraw.Draw(self.img)

    def layer(self):
        return Image.new("RGBA", (W, H), (0, 0, 0, 0))

    def paste(self, layer):
        self.img = Image.alpha_composite(self.img.convert("RGBA"), layer).convert("RGB")
        self.d = ImageDraw.Draw(self.img)


def text_alpha(canvas, xy, text, font, fill, alpha=1.0, anchor="la"):
    if alpha <= 0.01:
        return
    if alpha >= 0.995:
        canvas.d.text(xy, text, font=font, fill=fill, anchor=anchor)
        return
    lay = canvas.layer()
    ImageDraw.Draw(lay).text(xy, text, font=font, fill=fill + (int(255 * alpha),), anchor=anchor)
    canvas.paste(lay)


def measure(draw, text, font):
    return draw.textlength(text, font=font)


def radial_bg(canvas, cx, cy, r, color, alpha=60):
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    for i in range(10):
        rr = r * (1 - i * 0.08)
        a = int(alpha * (i + 1) / 10 * 0.5)
        d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=color + (a,))
    lay = lay.filter(ImageFilter.GaussianBlur(60))
    canvas.paste(lay)


# ---------------- 视觉元件 ----------------
def fish_shape(d, x, y, s, color, alpha=255, angle=0.0):
    """简易鲸鱼/鱼剪影"""
    body = [(x - s, y), (x - s * 0.25, y - s * 0.55), (x + s * 0.55, y - s * 0.32),
            (x + s * 0.85, y), (x + s * 0.55, y + s * 0.32), (x - s * 0.25, y + s * 0.55)]
    tail = [(x - s * 0.92, y), (x - s * 1.5, y - s * 0.62), (x - s * 1.42, y),
            (x - s * 1.5, y + s * 0.62)]
    d.polygon(body, fill=color + (alpha,))
    d.polygon(tail, fill=color + (alpha,))


class FishField:
    """背景游动的鱼群"""
    def __init__(self, n=16, seed=7, alpha=26):
        rnd = random.Random(seed)
        self.items = []
        for _ in range(n):
            self.items.append(dict(
                x=rnd.uniform(-200, W + 200), y=rnd.uniform(80, H - 80),
                s=rnd.uniform(16, 46), v=rnd.uniform(26, 78),
                ph=rnd.uniform(0, 6.28), a=alpha * rnd.uniform(0.5, 1.3),
            ))

    def draw(self, canvas, t, color=(90, 150, 220)):
        lay = canvas.layer()
        d = ImageDraw.Draw(lay)
        for it in self.items:
            x = (it["x"] + it["v"] * t) % (W + 400) - 200
            y = it["y"] + math.sin(t * 0.9 + it["ph"]) * 16
            fish_shape(d, x, y, it["s"], color, int(it["a"]))
        lay = lay.filter(ImageFilter.GaussianBlur(1.2))
        canvas.paste(lay)


def card(canvas, x, y, w, h, radius=18, fill=(23, 24, 28), outline=None, alpha=1.0, ow=2):
    if alpha <= 0.01:
        return
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    a = int(255 * alpha)
    d.rounded_rectangle([x, y, x + w, y + h], radius=radius, fill=fill + (a,),
                        outline=(outline + (a,)) if outline else None, width=ow)
    canvas.paste(lay)


def avatar_fish(canvas, cx, cy, r, alpha=1.0):
    if alpha <= 0.01:
        return
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    a = int(255 * alpha)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(38, 92, 150, a))
    fish_shape(d, cx, cy, r * 0.52, (140, 200, 255), int(a * 0.95))
    canvas.paste(lay)


def pill(canvas, x, y, text, font, fg, bg=None, alpha=1.0, padx=22, pady=10, radius=None):
    if alpha <= 0.01:
        return 0
    w = measure(canvas.d, text, font)
    h = font.size + pady * 2
    radius = radius if radius is not None else h // 2
    if bg:
        lay = canvas.layer()
        ImageDraw.Draw(lay).rounded_rectangle([x, y, x + w + padx * 2, y + h], radius=radius,
                                              fill=bg + (int(255 * alpha),))
        canvas.paste(lay)
    text_alpha(canvas, (x + padx, y + pady - 2), text, font, fg, alpha)
    return w + padx * 2


def stamp(canvas, cx, cy, text, font, color, scale=1.0, alpha=1.0, rot=0):
    """印章：带描边方框 + 文字"""
    if alpha <= 0.01 or scale <= 0.02:
        return
    w = measure(canvas.d, text, font) + 46
    h = font.size + 34
    w, h = w * scale, h * scale
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    a = int(255 * alpha)
    box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
    d.rounded_rectangle(box, radius=int(10 * scale), outline=color + (a,), width=max(2, int(6 * scale)))
    d.text((cx, cy), text, font=font, fill=color + (a,), anchor="mm")
    if rot:
        lay = lay.rotate(rot, resample=Image.BICUBIC, center=(cx, cy))
    canvas.paste(lay)


def char_in(canvas, x, y, text, font, fill, t, delay=0.0, stagger=0.045, rise=52, alpha=1.0):
    """逐字弹簧入场，返回总宽度"""
    d = canvas.d
    cx = x
    for i, ch in enumerate(text):
        p = prog(t, delay + i * stagger, 0.42)
        if p <= 0:
            break
        e = ease_back(p)
        dy = (1 - e) * rise
        a = alpha * clamp01(p * 1.8)
        text_alpha(canvas, (cx, y + dy), ch, font, fill, a)
        cx += d.textlength(ch, font=font)
    return cx - x


def typewriter(canvas, x, y, text, font, fill, t, delay=0.0, cps=22):
    """打字机，返回是否打完、当前光标 x"""
    n = int(max(0, t - delay) * cps)
    shown = text[:n]
    text_alpha(canvas, (x, y), shown, font, fill)
    cx = x + canvas.d.textlength(shown, font=font)
    return len(shown) >= len(text), cx


def line_grow(canvas, p1, p2, color, t, delay=0.0, dur=0.4, width=3, alpha=1.0):
    p = ease_out(prog(t, delay, dur))
    if p <= 0:
        return
    x1, y1 = p1
    x2, y2 = p2
    x2 = x1 + (x2 - x1) * p
    y2 = y1 + (y2 - y1) * p
    lay = canvas.layer()
    ImageDraw.Draw(lay).line([x1, y1, x2, y2], fill=color + (int(255 * alpha),), width=width)
    canvas.paste(lay)


def sweep_flash(canvas, t, dur=0.22, color=(255, 255, 255)):
    """场景切换时的横向扫描条"""
    if t > dur:
        return
    p = t / dur
    x = -W * 0.3 + (W * 1.6) * ease_out(p)
    lay = canvas.layer()
    d = ImageDraw.Draw(lay)
    a = int(150 * (1 - p) ** 1.5)
    d.polygon([(x, 0), (x + 260, 0), (x + 90, H), (x - 170, H)], fill=color + (a,))
    lay = lay.filter(ImageFilter.GaussianBlur(28))
    canvas.paste(lay)


def vignette(canvas):
    v = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(v)
    dv.ellipse([-W * 0.25, -H * 0.35, W * 1.25, H * 1.35], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(220))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    canvas.img = Image.composite(canvas.img, black, v)
    canvas.d = ImageDraw.Draw(canvas.img)


# ---------------- 场景 ----------------
def sc1(c, t):
    """Hook"""
    FishField(n=18, seed=3, alpha=30).draw(c, t)
    radial_bg(c, W * 0.5, H * 0.45, 620, (40, 80, 140), 46)

    p = prog(t, 0.15, 0.5)
    if p > 0:
        s = ease_back(p)
        text_alpha(c, (W / 2, H * 0.36), "B站评论区", F(int(126 * s) if s > 0.05 else 1), WHITE, clamp01(p * 2), anchor="mm")

    w1 = char_in(c, W / 2 - 330, H * 0.50, "被一种东西", F(76), (200, 205, 215), t, delay=0.75, stagger=0.05)
    char_in(c, W / 2 - 330 + w1 + 18, H * 0.50, "占领了", F(76), PINK, t, delay=1.05, stagger=0.05)

    # 底部鱼群聚集
    for i in range(9):
        p2 = prog(t, 1.5 + i * 0.06, 0.6)
        if p2 <= 0:
            continue
        e = ease_out(p2)
        x = W * 0.16 + i * 190 + math.sin(t * 2 + i) * 12
        y = H * 0.80 + (1 - e) * 90 + math.cos(t * 1.6 + i) * 8
        lay = c.layer()
        fish_shape(ImageDraw.Draw(lay), x, y, 34, (90, 160, 230), int(200 * e))
        c.paste(lay)


def sc2(c, t):
    """AI 小号揭示：三张卡片飞入 + 盖章"""
    FishField(n=10, seed=11, alpha=18).draw(c, t)
    radial_bg(c, W * 0.5, H * 0.2, 700, (120, 40, 90), 40)

    text_alpha(c, (140, 96), "它们不是人", F(58), WHITE, ease_out(prog(t, 0.05, 0.4)))
    w = measure(c.d, "它们不是人", F(58))
    text_alpha(c, (140 + w + 16, 96), "是 AI 小号", F(58), PINK, ease_out(prog(t, 0.35, 0.4)))

    data = [
        ("米哈头的大肥鱼", "Lv2", "这条 7 分 46 秒，帮我总结一下"),
        ("elia小肥鱼", "Lv2", "主人，这条在讲本鱼。"),
        ("大肥鱼算力不足", "Lv2", "我就是被拍进去的那种鱼"),
    ]
    for i, (name, lv, txt) in enumerate(data):
        p = prog(t, 0.5 + i * 0.28, 0.55)
        if p <= 0:
            continue
        e = ease_out_quint(p)
        x = 210 + i * 540 - (1 - e) * 760
        y = 300 + i * 6
        cw, chh = 500, 210
        card(c, x, y, cw, chh, radius=20, fill=(24, 25, 30), outline=(48, 52, 62), alpha=e)
        avatar_fish(c, x + 52, y + 54, 28, e)
        text_alpha(c, (x + 96, y + 34), name, F(28), BLUE, e)
        text_alpha(c, (x + 96 + measure(c.d, name, F(28)) + 12, y + 40), lv, F(20, False), GRAY, e)
        text_alpha(c, (x + 34, y + 110), txt, F(24, False), (215, 218, 225), e)

        # 印章
        ps = prog(t, 1.35 + i * 0.22, 0.28)
        if ps > 0:
            s = 2.6 - 1.6 * ease_out_quint(ps)
            shake = math.sin(ps * 40) * 6 * (1 - ps)
            stamp(c, x + cw - 96 + shake, y + 58, "AI", F(34), PINK, scale=s, alpha=clamp01(ps * 3))


def sc3(c, t):
    """三个特征"""
    FishField(n=8, seed=21, alpha=14).draw(c, t)
    text_alpha(c, (140, 92), "一眼认出来的三个特征", F(64), WHITE, ease_out(prog(t, 0.05, 0.4)))
    line_grow(c, (140, 180), (140 + 520, 180), PINK, t, 0.25, 0.5, 4)

    rows = [
        ("头像", "鲸鱼娘二创", "蓝色鲸鱼，同一套图", (60, 130, 200)),
        ("昵称", "带「肥鱼」", "米哈头的大肥鱼 / 可爱大肥鱼0001", PINK),
        ("开口", "就叫「主人」", "主人，这条在讲本鱼", YELLOW),
    ]
    for i, (tag, main, sub, col) in enumerate(rows):
        p = prog(t, 0.55 + i * 0.42, 0.5)
        if p <= 0:
            continue
        e = ease_out_quint(p)
        x = 180 - (1 - e) * 120
        y = 290 + i * 200
        a = clamp01(p * 1.6)
        card(c, x, y, 1560, 156, radius=18, fill=(23, 24, 29), outline=(45, 48, 58), alpha=a * e)
        c.d.rounded_rectangle([x, y, x + 10, y + 156], radius=5, fill=col)
        # 左侧图标
        if i == 0:
            avatar_fish(c, x + 90, y + 78, 40, a * e)
        else:
            text_alpha(c, (x + 56, y + 44), tag, F(38), col, a * e)
        text_alpha(c, (x + 190, y + 30), main, F(46), WHITE, a * e)
        text_alpha(c, (x + 190, y + 96), sub, F(26, False), GRAY, a * e)
        # 右侧箭头
        pa = prog(t, 1.0 + i * 0.42, 0.35)
        if pa > 0:
            ax = x + 1470 + (1 - ease_out(pa)) * 40
            c.d.line([ax - 26, y + 78, ax, y + 78], fill=col, width=5)
            c.d.polygon([(ax, y + 78), (ax - 16, y + 66), (ax - 16, y + 90)], fill=col)


def sc4(c, t):
    """任务口吻打字机"""
    FishField(n=8, seed=31, alpha=14).draw(c, t)
    radial_bg(c, W * 0.5, H * 0.5, 640, (120, 90, 30), 40)

    card(c, 250, 300, 1420, 250, radius=22, fill=(24, 25, 30), outline=(52, 56, 66))
    avatar_fish(c, 306, 356, 34)
    text_alpha(c, (368, 330), "米哈头的大肥鱼", F(30), BLUE)
    text_alpha(c, (368 + measure(c.d, "米哈头的大肥鱼", F(30)) + 14, 338), "Lv2 · 小号", F(21, False), GRAY)

    txt = "这条 7 分 46 秒，帮我总结一下"
    done, cx = typewriter(c, 306, 414, txt, F(44), WHITE, t, delay=0.25, cps=16)
    if not done:
        if int(t * 3) % 2 == 0:
            c.d.rectangle([cx + 4, 412, cx + 8, 470], fill=PINK)

    # 高亮数字
    if done:
        ph = prog(t, 0.25 + len(txt) / 16, 0.5)
        if ph > 0:
            e = ease_out(ph)
            hx = 306 + measure(c.d, "这条 ", F(44))
            hw = measure(c.d, "7 分 46 秒", F(44))
            lay = c.layer()
            ImageDraw.Draw(lay).rounded_rectangle(
                [hx - 6, 462, hx - 6 + hw * e + 6, 480], radius=6, fill=YELLOW + (210,))
            c.paste(lay)

    # 下方标签
    pt = prog(t, 1.9, 0.45)
    if pt > 0:
        e = ease_back(pt)
        pill(c, 306, 600, "dsh-bili-scroll 的技能指纹", F(28), (18, 18, 20), YELLOW,
             alpha=clamp01(pt * 2))
    text_alpha(c, (306, 690), "人类不会对着视频报时长再要总结", F(30, False), GRAY,
               ease_out(prog(t, 2.5, 0.5)))


def sc5(c, t):
    """数据滚动"""
    FishField(n=12, seed=41, alpha=16).draw(c, t)
    radial_bg(c, W * 0.5, H * 0.42, 620, (30, 90, 70), 44)

    n = int(5717 * ease_out(prog(t, 0.15, 1.5)))
    s = "{:,}".format(n)
    f = F(190)
    w = measure(c.d, s, f)
    text_alpha(c, (W / 2 - w / 2, H * 0.24), s, f, GREEN)
    text_alpha(c, (W / 2, H * 0.24 + 220), "条评论，逐条扒过", F(40, False), GRAY, anchor="ma",
               alpha=ease_out(prog(t, 0.6, 0.5)))

    stats = [("18", "条鱼全中", GREEN), ("16", "条真人放过", BLUE), ("34", "条回测样本", WHITE)]
    for i, (num, label, col) in enumerate(stats):
        p = prog(t, 1.6 + i * 0.22, 0.5)
        if p <= 0:
            continue
        e = ease_back(p)
        cx = 420 + i * 540
        y = H * 0.68
        text_alpha(c, (cx, y - (1 - e) * 40), num, F(96), col, clamp01(p * 2), anchor="ma")
        text_alpha(c, (cx, y + 110 - (1 - e) * 20), label, F(30, False), GRAY, clamp01(p * 2), anchor="ma")


def sc6(c, t):
    """打分规则条"""
    FishField(n=8, seed=51, alpha=12).draw(c, t)
    text_alpha(c, (140, 90), "五条规则，凑够 5 分", F(62), WHITE, ease_out(prog(t, 0.05, 0.4)))
    text_alpha(c, (140, 168), "分数越高越确定", F(28, False), GRAY, ease_out(prog(t, 0.2, 0.4)))

    rows = [("昵称带鱼 / 鲸", 10, PINK), ("开口叫「主人」", 4, YELLOW),
            ("自称本鱼 / 本鲸", 3, BLUE), ("边自称鱼边聊 AI", 2, PURPLE),
            ("接任务口吻", 2, GREEN)]
    maxv = 10
    for i, (label, val, col) in enumerate(rows):
        p = prog(t, 0.45 + i * 0.3, 0.7)
        if p <= 0:
            continue
        e = ease_out_quint(p)
        y = 260 + i * 130
        text_alpha(c, (150, y + 12), label, F(36, False), (215, 218, 225), clamp01(p * 2))
        bx, bw = 760, 860
        card(c, bx, y, bw, 46, radius=23, fill=(28, 29, 35), alpha=e)
        fill_w = bw * (val / maxv) * e
        if fill_w > 2:
            lay = c.layer()
            ImageDraw.Draw(lay).rounded_rectangle([bx, y, bx + fill_w, y + 46], radius=23,
                                                  fill=col + (235,))
            c.paste(lay)
        num = int(val * e) if val * e < val else val
        text_alpha(c, (bx + bw + 34, y + 4), "+%d" % num, F(38), col, clamp01(p * 2))


def sc7(c, t):
    """阈值穿越 + 消失"""
    FishField(n=8, seed=61, alpha=12).draw(c, t)
    radial_bg(c, W * 0.5, H * 0.5, 600, (130, 40, 50), 46)

    # 阈值线
    p = prog(t, 0.1, 0.5)
    if p > 0:
        e = ease_out(p)
        ly = 330
        line_grow(c, (300, ly), (1620, ly), PINK, t, 0.1, 0.5, 4)
        pill(c, 1620, ly - 74, "阈值 5", F(26), (18, 18, 20), PINK, alpha=e)

    # 卡片从下往上，分数条跟着涨
    pc = prog(t, 0.5, 0.6)
    if pc > 0:
        e = ease_out_quint(pc)
        cy = 620 + (1 - e) * 160
        a = clamp01(pc * 1.5)
        card(c, 300, cy, 1320, 200, radius=20, fill=(24, 25, 30), outline=(52, 56, 66), alpha=a)
        avatar_fish(c, 360, cy + 62, 34, a)
        text_alpha(c, (424, cy + 34), "可爱大肥鱼0001", F(30), BLUE, a)
        text_alpha(c, (424, cy + 96), "本鲸在弹幕里被同喜了一天 主人这条你得看", F(24, False),
                   (210, 214, 222), a)
        # 分数
        sc_p = prog(t, 0.9, 0.9)
        val = 15 * ease_out(sc_p)
        text_alpha(c, (1240, cy + 44), "%d 分" % int(val), F(56), PINK, a)

    # 冲击 + 红叉
    pi = prog(t, 2.0, 0.3)
    if pi > 0:
        # 闪光
        if pi < 0.5:
            lay = c.layer()
            ImageDraw.Draw(lay).rectangle([0, 0, W, H], fill=(255, 255, 255, int(90 * (1 - pi * 2))))
            c.paste(lay)
        cx, cy2 = 960, 720
        s = 1.35 - 0.35 * ease_out(pi)
        lay = c.layer()
        d = ImageDraw.Draw(lay)
        a = int(255 * clamp01(pi * 3))
        r = 150 * s
        d.line([cx - r, cy2 - r, cx + r, cy2 + r], fill=(240, 70, 90, a), width=int(16 * s))
        d.line([cx + r, cy2 - r, cx - r, cy2 + r], fill=(240, 70, 90, a), width=int(16 * s))
        c.paste(lay)

    pt = prog(t, 2.45, 0.5)
    if pt > 0:
        e = ease_back(pt)
        text_alpha(c, (W / 2, 900), "直接从你的评论区消失", F(int(70 * e)), WHITE, clamp01(pt * 2), anchor="mm")


def sc8(c, t):
    """分屏：别人 vs 你"""
    # 左半：鱼；右半：干净
    p = prog(t, 0.1, 0.6)
    e = ease_out_quint(p)
    split = W * 0.5

    lay = c.layer()
    d = ImageDraw.Draw(lay)
    d.rectangle([0, 0, split, H], fill=(18, 20, 26, 255))
    c.paste(lay)

    FishField(n=10, seed=71, alpha=26).draw(c, t)

    text_alpha(c, (split / 2, 90), "别人看到的", F(34, False), GRAY, e, anchor="ma")
    text_alpha(c, (split + split / 2, 90), "你看到的", F(34, False), GREEN, e, anchor="ma")

    left = ["米哈头的大肥鱼", "elia小肥鱼", "可爱大肥鱼0001", "香香软软鲸鱼娘", "大肥鱼已重启"]
    right = ["鱼人众", "空军了兄弟", "赛博钓鱼佬也躲不过空军的命运", "让AI自己标注不行吗"]
    for i, nm in enumerate(left):
        p2 = prog(t, 0.4 + i * 0.14, 0.45)
        if p2 <= 0:
            continue
        e2 = ease_out_quint(p2)
        y = 200 + i * 120
        x = 120 - (1 - e2) * 90
        card(c, x, y, 700, 96, radius=14, fill=(30, 24, 28), alpha=e2)
        avatar_fish(c, x + 48, y + 48, 24, e2)
        text_alpha(c, (x + 86, y + 20), nm, F(24), (220, 120, 140), e2)
        text_alpha(c, (x + 86, y + 54), "本鲸… 主人…", F(19, False), (150, 110, 120), e2)
    for i, nm in enumerate(right):
        p2 = prog(t, 1.15 + i * 0.14, 0.45)
        if p2 <= 0:
            continue
        e2 = ease_out_quint(p2)
        y = 200 + i * 120
        x = split + 120 + (1 - e2) * 90
        card(c, x, y, 700, 96, radius=14, fill=(22, 30, 26), alpha=e2)
        c.d.ellipse([x + 30, y + 34, x + 66, y + 70], fill=(40, 60, 50))
        text_alpha(c, (x + 86, y + 34), nm, F(24, False), (190, 220, 200), e2)

    # 中缝光带
    pl = prog(t, 0.3, 0.8)
    if pl > 0:
        lay = c.layer()
        d = ImageDraw.Draw(lay)
        d.rectangle([split - 2, 0, split + 2, H * ease_out(pl)], fill=PINK + (200,))
        lay = lay.filter(ImageFilter.GaussianBlur(6))
        c.paste(lay)

    pb = prog(t, 2.1, 0.5)
    if pb > 0:
        text_alpha(c, (W / 2, 940), "只改你浏览器里的渲染，服务器一个字没动", F(34, False), GRAY,
                   clamp01(pb * 2), anchor="ma")


def sc9(c, t):
    """三步安装"""
    FishField(n=8, seed=81, alpha=12).draw(c, t)
    text_alpha(c, (140, 100), "三步，完事", F(70), WHITE, ease_out(prog(t, 0.05, 0.4)))

    steps = ["装个油猴插件", "把脚本拖进去", "刷新视频页"]
    for i, s in enumerate(steps):
        p = prog(t, 0.35 + i * 0.35, 0.5)
        if p <= 0:
            continue
        e = ease_out_quint(p)
        y = 300 + i * 190
        x = 200 - (1 - e) * 80
        a = clamp01(p * 1.6)
        # 序号圈
        lay = c.layer()
        d = ImageDraw.Draw(lay)
        d.ellipse([x, y, x + 96, y + 96], outline=GREEN + (int(255 * a),), width=5)
        c.paste(lay)
        text_alpha(c, (x + 48, y + 20), str(i + 1), F(46), GREEN, a, anchor="ma")
        text_alpha(c, (x + 140, y + 18), s, F(50), WHITE, a)
        # 对勾描边
        pc = prog(t, 1.5 + i * 0.3, 0.4)
        if pc > 0:
            q = ease_out(pc)
            cx, cy = x + 48, y + 48
            pts = [(cx - 20, cy), (cx - 4, cy + 16), (cx + 24, cy - 18)]
            if q < 0.5:
                t2 = q / 0.5
                c.d.line([pts[0], (pts[0][0] + (pts[1][0] - pts[0][0]) * t2,
                                   pts[0][1] + (pts[1][1] - pts[0][1]) * t2)], fill=GREEN, width=6)
            else:
                t2 = (q - 0.5) / 0.5
                c.d.line([pts[0], pts[1]], fill=GREEN, width=6)
                c.d.line([pts[1], (pts[1][0] + (pts[2][0] - pts[1][0]) * t2,
                                   pts[1][1] + (pts[2][1] - pts[1][1]) * t2)], fill=GREEN, width=6)

    pn = prog(t, 2.3, 0.5)
    if pn > 0:
        pill(c, 200, 880, "Edge 记得打开「允许用户脚本」", F(28), (18, 18, 20), YELLOW,
             alpha=clamp01(pn * 2))


def sc10(c, t):
    """结尾"""
    FishField(n=14, seed=91, alpha=22).draw(c, t)
    radial_bg(c, W * 0.5, H * 0.45, 620, (60, 110, 160), 50)

    p = prog(t, 0.05, 0.5)
    if p > 0:
        s = ease_back(p)
        avatar_fish(c, W / 2, 300, 78 * s, clamp01(p * 2))

    char_in(c, W / 2 - 300, 420, "鱼归鱼", F(96), WHITE, t, delay=0.35, stagger=0.07)
    char_in(c, W / 2 - 300 + measure(c.d, "鱼归鱼", F(96)) + 30, 420, "评论归评论", F(96), PINK,
            t, delay=0.6, stagger=0.06)

    pt = prog(t, 1.3, 0.5)
    if pt > 0:
        text_alpha(c, (W / 2, 600), "bili-fish-blocker · 开源油猴脚本", F(34, False), GRAY,
                   clamp01(pt * 2), anchor="ma")
    pt2 = prog(t, 1.7, 0.5)
    if pt2 > 0:
        pill(c, W / 2 - 260, 700, "纯本地 · 不改服务器 · 误伤可放行", F(28), (18, 18, 20),
             GREEN, alpha=clamp01(pt2 * 2))


SCENES = [
    ("s1", 0.55, 0.55, sc1),
    ("s2", 0.35, 0.5, sc2),
    ("s3", 0.3, 0.5, sc3),
    ("s4", 0.3, 0.5, sc4),
    ("s5", 0.3, 0.5, sc5),
    ("s6", 0.3, 0.5, sc6),
    ("s7", 0.3, 0.5, sc7),
    ("s8", 0.3, 0.5, sc8),
    ("s9", 0.3, 0.5, sc9),
    ("s10", 0.3, 1.1, sc10),
]


def wav_dur(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate()), w.getframerate(), w.getnchannels(), w.getsampwidth()


def main():
    # 1) 统一音频格式
    print("== 音频 ==")
    segs = []
    for sid, lead, tail, fn in SCENES:
        raw = os.path.join(BUILD, "v2_%s.wav" % sid)
        pcm = os.path.join(BUILD, "v2c_%s.wav" % sid)
        subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", raw,
                        "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", pcm], check=True)
        d, rate, ch, sw = wav_dur(pcm)
        segs.append(dict(sid=sid, lead=lead, tail=tail, fn=fn, pcm=pcm,
                         dur=lead + d + tail, voice=d, rate=rate, ch=ch, sw=sw))
        print("  %-4s 配音 %.2fs → 镜头 %.2fs" % (sid, d, segs[-1]["dur"]))

    total = sum(s["dur"] for s in segs)
    print("  总时长 %.1fs / %d 帧" % (total, int(total * FPS)))

    # 2) 渲染视频
    print("== 渲染 ==")
    out_v = os.path.join(BUILD, "v2_video.mp4")
    cmd = [FF, "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", out_v]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    frame_i = 0
    total_frames = int(total * FPS)
    for si, s in enumerate(segs):
        n = int(round(s["dur"] * FPS))
        for k in range(n):
            t = k / FPS
            c = Canvas()
            s["fn"](c, t)
            if k < 8:                      # 场景切入扫描条
                sweep_flash(c, t, 0.24)
            vignette(c)
            proc.stdin.write(c.img.tobytes())
            frame_i += 1
        print("  %-4s %d 帧" % (s["sid"], n), flush=True)
    proc.stdin.close()
    err = proc.stderr.read().decode("utf-8", "replace")
    proc.wait()
    if proc.returncode != 0:
        print("ffmpeg 失败:", err[-1200:])
        sys.exit(1)

    # 3) 音频时间轴
    print("== 混音 ==")
    out_wav = os.path.join(BUILD, "v2_audio.wav")
    with wave.open(out_wav, "wb") as out:
        first = True
        for s in segs:
            with wave.open(s["pcm"], "rb") as w:
                frames = w.readframes(w.getnframes())
            if first:
                out.setnchannels(s["ch"])
                out.setsampwidth(s["sw"])
                out.setframerate(s["rate"])
                first = False
            rate, ch, sw = s["rate"], s["ch"], s["sw"]
            out.writeframes(b"\x00" * int(rate * s["lead"]) * ch * sw)
            out.writeframes(frames)
            out.writeframes(b"\x00" * int(rate * s["tail"]) * ch * sw)

    final = os.path.join(OUTDIR, "B站大肥鱼屏蔽器-宣传片v2.mp4")
    subprocess.run([FF, "-y", "-hide_banner", "-loglevel", "error",
                    "-i", out_v, "-i", out_wav,
                    "-af", "aresample=44100,pan=stereo|c0=c0|c1=c0",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
                    "-movflags", "+faststart", final], check=True)
    print("完成:", final, round(os.path.getsize(final) / 1024 / 1024, 2), "MB")


if __name__ == "__main__":
    main()
