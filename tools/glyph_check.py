# -*- coding: utf-8 -*-
"""检查符号在微软雅黑里是否渲染成豆腐块。"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont

f = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 60)
CANDS = ["✓", "√", "✔", "→", "▶", "●", "·", "「", "」", "×", "✕", "▸", "—", "✋", "🐟", "⬤", "▪"]

for ch in CANDS:
    im = Image.new("L", (120, 120), 0)
    ImageDraw.Draw(im).text((14, 14), ch, font=f, fill=255)
    a = np.asarray(im)
    ys, xs = np.nonzero(a > 60)
    if len(ys) == 0:
        print("%-4s 空白/无字形" % ch)
        continue
    w = xs.max() - xs.min() + 1
    h = ys.max() - ys.min() + 1
    ratio = (a > 60).sum() / max(1, w * h)
    # 豆腐块：接近正方形、填充率低、边界对齐
    tofu = (0.8 < w / max(1, h) < 1.25) and ratio < 0.22 and w > 40
    print("%-4s w=%-3d h=%-3d 填充=%.2f  %s" % (ch, w, h, ratio, "❌豆腐块" if tofu else "✅正常"))
