# -*- coding: utf-8 -*-
"""用 ffmpeg + Windows SAPI 把卡片图 + 旁白合成宣传视频。"""
import json, os, subprocess, wave, sys
from PIL import Image, ImageDraw, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
CARDS = os.path.join(BASE, "卡片")
BUILD = os.path.join(BASE, "build")
OUTDIR = os.path.join(BASE, "成品")
FRAMES = os.path.join(BUILD, "frames")
for d in (BUILD, OUTDIR, FRAMES):
    os.makedirs(d, exist_ok=True)

FF = r"C:\Users\17797\py310-embed\lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
FPS = 30

SCENES = [
    dict(id="01", card="01-封面.png", lead=0.5, tail=0.8,
         caption="B站评论区里的大肥鱼，越来越多了",
         voice="B站评论区里的大肥鱼，最近是不是越来越多了？"),
    dict(id="02", card="02-问题.png", lead=0.4, tail=0.6,
         caption="它们全是插件自动刷站刷出来的 AI 小号",
         voice="它们全是被 DSH 插件自动刷站刷出来的 AI 小号：鲸鱼娘头像、名字带肥鱼、张口就叫主人，还动不动帮你总结视频。"),
    dict(id="03", card="03-特征.png", lead=0.4, tail=0.6,
         caption="五条特征，认出人机鱼",
         voice="我用真评论回测了一套识别规则：昵称、自称、艾特主人、接任务口吻，再加上「边自称鱼边聊 AI」这条硬信号，凑够五分就屏蔽。"),
    dict(id="04", card="04-对比.png", lead=0.4, tail=0.6,
         caption="只在你本地生效，不改服务器数据",
         voice="装之前，一屏全是鱼；装上之后，一屏全是真人。它只在你自己的浏览器里生效，不改服务器数据，也不影响别人看到的内容。"),
    dict(id="05", card="05-安装.png", lead=0.4, tail=0.6,
         caption="三步装好，刷新即用",
         voice="装个 Tampermonkey，把脚本拖进浏览器，刷新视频页就够了。Edge 记得打开「允许用户脚本」。"),
    dict(id="06", card="06-结尾.png", lead=0.4, tail=1.2,
         caption="鱼归鱼，评论归评论",
         voice="脚本开源，误伤一键放行，阈值自己调。鱼归鱼，评论归评论。"),
]


def run(cmd, ok=True):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0 and ok:
        print("CMD FAILED:", " ".join(cmd)[:300])
        print(p.stderr[-800:])
        sys.exit(1)
    return p


def tts(script_path):
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path])


def make_tts_script():
    lines = ["Add-Type -AssemblyName System.Speech",
             "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
             "$s.SelectVoice('Microsoft Huihui Desktop')",
             "$s.Rate = 1", "$s.Volume = 100"]
    for sc in SCENES:
        wav = os.path.join(BUILD, "voice_%s.wav" % sc["id"]).replace("'", "''")
        txt = sc["voice"].replace("'", "''")
        lines += ["$s.SetOutputToWaveFile('%s')" % wav,
                  "$s.Speak('%s')" % txt,
                  "$s.SetOutputToNull()"]
    lines.append("$s.Dispose()")
    p = os.path.join(BUILD, "tts.ps1")
    with open(p, "w", encoding="utf-8-sig") as f:
        f.write("\n".join(lines))
    return p


def wav_duration(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate()), w.getframerate(), w.getnchannels(), w.getsampwidth()


def caption_frame(card, caption, out):
    img = Image.open(os.path.join(CARDS, card)).convert("RGB")
    W, H = img.size
    bar_h = 118
    overlay = Image.new("RGBA", (W, bar_h), (0, 0, 0, 150))
    img.paste(Image.alpha_composite(img.crop((0, H - bar_h, W, H)).convert("RGBA"), overlay).convert("RGB"),
              (0, H - bar_h))
    d = ImageDraw.Draw(img)
    f = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 54)
    tw = d.textlength(caption, font=f)
    d.text(((W - tw) / 2, H - bar_h + 30), caption, font=f, fill=(255, 255, 255))
    img.save(out)


def build_clip(frame, dur, out):
    vf = (
        "scale=2200:-1,"
        "zoompan=z='min(1+0.00045*on,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        ":d=1:s=1920x1080:fps=%d," % FPS +
        "fade=t=in:st=0:d=0.45,fade=t=out:st=%.2f:d=0.45,format=yuv420p" % max(0.1, dur - 0.45)
    )
    run([FF, "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-framerate", str(FPS), "-i", frame, "-t", "%.3f" % dur,
         "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-r", str(FPS), "-pix_fmt", "yuv420p", out])


def main():
    global SCENES
    print("== 1/5 配音 ==")
    tts(make_tts_script())

    print("== 2/5 计算时长 ==")
    clips, total = [], 0.0
    for sc in SCENES:
        wav = os.path.join(BUILD, "voice_%s.wav" % sc["id"])
        dur, rate, ch, sw = wav_duration(wav)
        sc["voice_dur"] = dur
        sc["dur"] = sc["lead"] + dur + sc["tail"]
        total += sc["dur"]
        print("  %s  配音 %.2fs  镜头 %.2fs  %s" % (sc["id"], dur, sc["dur"], sc["voice"][:18]))
    print("  总时长 %.1fs" % total)

    print("== 3/5 生成带字幕的画面 ==")
    for sc in SCENES:
        frame = os.path.join(FRAMES, "frame_%s.png" % sc["id"])
        caption_frame(sc["card"], sc["caption"], frame)
        sc["frame"] = frame
        print("  ", os.path.basename(frame))

    print("== 4/5 渲染镜头并拼接 ==")
    listfile = os.path.join(BUILD, "clips.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for sc in SCENES:
            clip = os.path.join(BUILD, "clip_%s.mp4" % sc["id"])
            build_clip(sc["frame"], sc["dur"], clip)
            clips.append(clip)
            f.write("file '%s'\n" % clip.replace("\\", "/"))
            print("  ", os.path.basename(clip))
    video = os.path.join(BUILD, "video.mp4")
    run([FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listfile, "-c", "copy", video])
    print("  video.mp4 完成")

    print("== 5/5 混音 ==")
    # 用 wave 模块按镜头时间轴拼音频：前置静音 + 配音 + 后置静音
    outwav = os.path.join(BUILD, "audio.wav")
    with wave.open(outwav, "wb") as out:
        first = True
        for sc in SCENES:
            wav_path = os.path.join(BUILD, "voice_%s.wav" % sc["id"])
            with wave.open(wav_path, "rb") as w:
                params = w.getparams()
                frames = w.readframes(w.getnframes())
            if first:
                out.setnchannels(params.nchannels)
                out.setsampwidth(params.sampwidth)
                out.setframerate(params.framerate)
                silence = b"\x00" * int(params.sampwidth * params.nchannels)
                first = False
            rate, ch, sw = params.framerate, params.nchannels, params.sampwidth
            out.writeframes(b"\x00" * int(rate * sc["lead"]) * ch * sw)
            out.writeframes(frames)
            out.writeframes(b"\x00" * int(rate * sc["tail"]) * ch * sw)

    final = os.path.join(OUTDIR, "B站大肥鱼屏蔽器-宣传.mp4")
    run([FF, "-y", "-hide_banner", "-loglevel", "error",
         "-i", video, "-i", outwav,
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
         "-movflags", "+faststart", final])
    print("\n完成:", final, round(os.path.getsize(final) / 1024 / 1024, 2), "MB")


if __name__ == "__main__":
    main()
