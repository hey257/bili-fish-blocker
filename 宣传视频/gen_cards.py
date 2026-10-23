# -*- coding: utf-8 -*-
"""生成宣传视频用的卡片图（1920x1080，可直接拖进剪映）。"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "卡片")
os.makedirs(OUT, exist_ok=True)

W, H = 1920, 1080
BG = (15, 16, 19)
CARD = (23, 24, 28)
WHITE = (255, 255, 255)
GRAY = (154, 160, 170)
PINK = (251, 114, 153)
BLUE = (0, 161, 214)
GREEN = (62, 207, 142)

F_BOLD = "C:/Windows/Fonts/msyhbd.ttc"
F_REG = "C:/Windows/Fonts/msyh.ttc"


def font(size, bold=True):
    return ImageFont.truetype(F_BOLD if bold else F_REG, size)


def wrap(draw, text, f, max_w):
    lines, cur = [], ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if draw.textlength(cur + ch, font=f) > max_w and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    return lines


def text_block(draw, text, f, x, y, max_w, lh, fill=WHITE, center=False):
    for line in wrap(draw, text, f, max_w):
        w = draw.textlength(line, font=f)
        draw.text((x + (max_w - w) / 2 if center else x, y), line, font=f, fill=fill)
        y += lh
    return y


def bg(draw, accent=PINK):
    draw.rectangle([0, 0, W, H], fill=BG)
    for i in range(6):
        r = 420 - i * 60
        draw.ellipse([W - 260 - r, -r + 120, W - 260 + r, r + 120], outline=(28, 29, 34), width=2)
    draw.rectangle([0, H - 8, W, H], fill=accent)


def pill(draw, x, y, text, f, fill, fg=WHITE):
    w = draw.textlength(text, font=f)
    draw.rounded_rectangle([x, y, x + w + 44, y + 56], radius=28, fill=fill)
    draw.text((x + 22, y + 8), text, font=f, fill=fg)
    return x + w + 44


def save(img, name):
    p = os.path.join(OUT, name)
    img.save(p)
    print("saved", p)


def card_cover():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    bg(d)
    pill(d, 110, 150, "油猴脚本 · 纯本地 · 不联网", font(28), (255, 255, 255, 0) if False else (35, 130, 90))
    y = 260
    y = text_block(d, "B站评论区里的大肥鱼", font(104), 110, y, 1500, 130)
    y = text_block(d, "一键屏蔽", font(104), 110, y + 6, 1500, 130, PINK)
    y = text_block(d, "DSH 自动刷站刷出来的 AI 人机评论，按昵称/自称/@主人/头像打分，命中即消失",
                   font(40, False), 110, y + 30, 1450, 62, GRAY)
    # 右下角示意：鱼被打叉
    cx, cy = 1560, 700
    d.ellipse([cx - 170, cy - 170, cx + 170, cy + 170], outline=(250, 114, 153), width=6)
    d.line([cx - 130, cy - 130, cx + 130, cy + 130], fill=PINK, width=14)
    d.line([cx + 130, cy - 130, cx - 130, cy + 130], fill=PINK, width=14)
    save(img, "01-封面.png")


def card_problem():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    bg(d, BLUE)
    text_block(d, "你是不是也刷到过这种评论？", font(72), 110, 100, 1700, 100)
    samples = [
        ("米哈头的大肥鱼", "这条 7 分 46 秒，帮我总结一下", 300),
        ("elia小肥鱼", "主人，这条在讲本鱼。拍得挺准——尾巴确实没藏好。", 490),
        ("主人大人的小女仆", "老大，这视频骂的就是本鲸这类在评论区闹灾的鱼……", 700),
    ]
    for name, txt, y in samples:
        d.rounded_rectangle([110, y, 1810, y + 150], radius=22, fill=CARD)
        d.ellipse([140, y + 34, 218, y + 112], fill=(40, 42, 50))
        d.text((258, y + 22), name, font=font(34), fill=BLUE)
        text_block(d, txt, font(34, False), 258, y + 74, 1480, 46, WHITE)
    save(img, "02-问题.png")


def card_rules():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    bg(d, GREEN)
    text_block(d, "5 秒认出人机鱼", font(84), 110, 90, 1700, 110)
    rules = [
        ("昵称", "大肥鱼 / 小肥鱼 / 鲸鱼娘 / XXの大肥鱼", PINK),
        ("自称", "本鱼、本鲸、本龙、这楼鱼", BLUE),
        ("说话对象", "「主人，……」「主人这条你得看」", GREEN),
        ("口吻", "「这条 7 分 46 秒，帮我总结一下」", (245, 190, 80)),
        ("硬信号", "自称是鱼，同时还在聊 AI / 模型 / token", (200, 140, 255)),
    ]
    y = 260
    for tag, desc, color in rules:
        d.rounded_rectangle([110, y, 1810, y + 118], radius=20, fill=CARD)
        d.rounded_rectangle([110, y, 118, y + 118], radius=0, fill=color)
        d.text((160, y + 34), tag, font=font(36), fill=color)
        d.text((420, y + 34), desc, font=font(36, False), fill=WHITE)
        y += 145
    save(img, "03-特征.png")


def card_compare():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    bg(d, PINK)
    text_block(d, "开脚本前 / 开脚本后", font(72), 110, 90, 1700, 100)
    # 左
    d.rounded_rectangle([110, 260, 920, 900], radius=24, fill=CARD)
    d.text((160, 300), "开启前", font=font(48), fill=GRAY)
    names_before = ["米哈头的大肥鱼", "可爱大肥鱼0001", "香香软软鲸鱼娘", "大肥鱼已重启", "银白龙娘GPT"]
    y = 400
    for n in names_before:
        d.text((160, y), "· " + n, font=font(34, False), fill=(200, 80, 90))
        y += 86
    # 右
    d.rounded_rectangle([1000, 260, 1810, 900], radius=24, fill=CARD)
    d.text((1050, 300), "开启后", font=font(48), fill=GRAY)
    names_after = ["鱼人众", "空军了兄弟", "赛博钓鱼佬也躲不过空军的命运", "笑死，这已经是养鱼场了", "让AI自己标注不行吗"]
    y = 400
    for n in names_after:
        d.text((1050, y), "· " + n, font=font(32, False), fill=GREEN)
        y += 86
    save(img, "04-对比.png")


def card_howto():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    bg(d, BLUE)
    text_block(d, "三步装好", font(84), 110, 90, 1700, 110)
    steps = [
        ("1", "装 Tampermonkey 扩展"),
        ("2", "把 .user.js 拖进浏览器，点安装"),
        ("3", "刷新视频页，右下角亮起小圆点"),
    ]
    y = 290
    for num, desc in steps:
        d.ellipse([120, y + 10, 200, y + 90], fill=BLUE)
        d.text((145, y + 22), num, font=font(44), fill=(15, 16, 19))
        d.text((250, y + 20), desc, font=font(44, False), fill=WHITE)
        y += 150
    d.rounded_rectangle([110, 800, 1810, 960], radius=22, fill=CARD)
    d.text((160, 830), "Edge 记得打开：扩展详情 → 允许用户脚本", font=font(36, False), fill=(245, 190, 80))
    d.text((160, 890), "不想装油猴？F12 → Sources → Snippets 直接跑", font=font(34, False), fill=GRAY)
    save(img, "05-安装.png")


def card_end():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    bg(d, PINK)
    text_block(d, "脚本在简介 / 置顶评论", font(76), 110, 200, 1700, 100)
    text_block(d, "bili-fish-blocker.user.js", font(56, False), 110, 380, 1700, 78, PINK)
    text_block(d, "· 纯本地运行，不改服务器数据、不影响别人\n· 误伤一键放行，规则阈值自己调\n· 开源，随意改关键词",
               font(38, False), 110, 540, 1500, 68, GRAY)
    text_block(d, "鱼归鱼，评论归评论。", font(64), 110, 830, 1700, 90, WHITE)
    save(img, "06-结尾.png")


if __name__ == "__main__":
    card_cover()
    card_problem()
    card_rules()
    card_compare()
    card_howto()
    card_end()
