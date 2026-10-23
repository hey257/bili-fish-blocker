# -*- coding: utf-8 -*-
"""宣传片 v2 配音：文案更短、节奏更快，用本地 CosyVoice3 + 你的音色。"""
import os, sys, time

CV_DIR = r"C:\Users\17797\WorkBuddy\2026-10-07-16-15-16\tts-setup\CosyVoice"
MODEL = os.path.join(CV_DIR, "pretrained_models", "Fun-CosyVoice3-0.5B")
PROMPT = r"C:\Users\17797\WorkBuddy\2026-10-07-16-15-16\tts-setup\my_voice_16k.wav"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build")
os.makedirs(OUT, exist_ok=True)

INSTRUCT = ("You are a helpful assistant. 请用标准普通话，语气轻快、像在跟朋友吐槽，语速偏快，"
            "重点词稍微加重。<|endofprompt|>")

LINES = [
    ("s1", "B站评论区，被一种东西占领了。"),
    ("s2", "它们不是人，是插件自动刷出来的 AI 小号。"),
    ("s3", "鲸鱼娘头像，名字带肥鱼，开口就叫主人。"),
    ("s4", "还会说，这条七分四十六秒，帮我总结一下。"),
    ("s5", "我扒了五千多条评论，把特征做成了打分规则。"),
    ("s6", "昵称带鱼十分，叫主人四分，自称本鲸三分。"),
    ("s7", "凑够五分，直接从你的评论区消失。"),
    ("s8", "只在你本地生效，不改服务器，也不影响别人。"),
    ("s9", "装个油猴，拖进去，刷新，完事。"),
    ("s10", "鱼归鱼，评论归评论。"),
]


def main():
    os.chdir(CV_DIR)
    sys.path.insert(0, CV_DIR)
    sys.path.append(os.path.join(CV_DIR, "third_party", "Matcha-TTS"))
    import torch
    import torchaudio
    from cosyvoice.cli.cosyvoice import AutoModel

    t0 = time.time()
    print("加载模型…")
    cv = AutoModel(model_dir=MODEL)
    print("就绪 %.1fs" % (time.time() - t0))

    for sid, text in LINES:
        chunks = [o["tts_speech"] for o in cv.inference_instruct2(text, INSTRUCT, PROMPT, stream=False)]
        speech = torch.cat(chunks, dim=1)
        path = os.path.join(OUT, "v2_%s.wav" % sid)
        torchaudio.save(path, speech, cv.sample_rate)
        print("  %s  %.2fs" % (sid, speech.shape[1] / cv.sample_rate))


if __name__ == "__main__":
    main()
