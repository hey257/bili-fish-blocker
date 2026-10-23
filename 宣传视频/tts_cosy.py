# -*- coding: utf-8 -*-
"""用本地 Fun-CosyVoice3-0.5B，以「我的声音」为音色，为宣传片逐句配音。"""
import os
import sys
import time

CV_DIR = r"C:\Users\17797\WorkBuddy\2026-10-07-16-15-16\tts-setup\CosyVoice"
MODEL = os.path.join(CV_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")
PROMPT = r"C:\Users\17797\WorkBuddy\2026-10-07-16-15-16\tts-setup\my_voice_16k.wav"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build")
os.makedirs(OUT, exist_ok=True)

INSTRUCT = "You are a helpful assistant. 请用标准普通话，语气自然、像在跟朋友安利，语速稍快。<|endofprompt|>"

LINES = [
    ("01", "B站评论区里的大肥鱼，最近是不是越来越多了？"),
    ("02", "它们全是被那个自动刷站插件刷出来的 AI 小号：鲸鱼娘头像、名字带肥鱼、张口就叫主人，还动不动帮你总结视频。"),
    ("03", "我用真评论回测了一套识别规则：昵称、自称、艾特主人、接任务口吻，再加上「边自称鱼边聊 AI」这条硬信号，凑够五分就屏蔽。"),
    ("04", "装之前，一屏全是鱼；装上之后，一屏全是真人。它只在你自己的浏览器里生效，不改服务器数据，也不影响别人看到的内容。"),
    ("05", "装个油猴插件，把脚本拖进浏览器，刷新视频页就够了。浏览器扩展设置里记得打开「允许用户脚本」。"),
    ("06", "脚本开源，误伤一键放行，阈值自己调。鱼归鱼，评论归评论。"),
]


def main():
    os.chdir(CV_DIR)
    sys.path.insert(0, CV_DIR)
    sys.path.append(os.path.join(CV_DIR, "third_party", "Matcha-TTS"))
    from cosyvoice.cli.cosyvoice import AutoModel
    import torchaudio

    t0 = time.time()
    print("加载模型…", MODEL)
    cv = AutoModel(model_dir=MODEL)
    print("模型就绪，用时 %.1fs" % (time.time() - t0))

    for sid, text in LINES:
        t1 = time.time()
        chunks = []
        for _, out in enumerate(cv.inference_instruct2(text, INSTRUCT, PROMPT, stream=False)):
            chunks.append(out["tts_speech"])
        import torch
        speech = torch.cat(chunks, dim=1)
        path = os.path.join(OUT, "cosy_%s.wav" % sid)
        torchaudio.save(path, speech, cv.sample_rate)
        dur = speech.shape[1] / cv.sample_rate
        print("  %s  %.2fs  合成耗时 %.1fs  → %s" % (sid, dur, time.time() - t1, os.path.basename(path)))


if __name__ == "__main__":
    main()
