# -*- coding: utf-8 -*-
"""用 CosyVoice 生成的人声配音重新合成宣传片（复用已渲染的卡片与字幕帧）。"""
import os, subprocess, sys, wave

BASE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(BASE, "build")
FRAMES = os.path.join(BUILD, "frames")
OUTDIR = os.path.join(BASE, "成品")
FF = r"C:\Users\17797\py310-embed\lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
FPS = 30

SCENES = [
    dict(id="01", lead=0.45, tail=0.7),
    dict(id="02", lead=0.35, tail=0.55),
    dict(id="03", lead=0.35, tail=0.55),
    dict(id="04", lead=0.35, tail=0.55),
    dict(id="05", lead=0.35, tail=0.55),
    dict(id="06", lead=0.35, tail=1.0),
]


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if p.returncode != 0:
        print("CMD FAILED:", " ".join(cmd)[:200])
        print(p.stderr[-600:])
        sys.exit(1)


def wav_info(path):
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate()), w.getframerate(), w.getnchannels(), w.getsampwidth()


def build_clip(frame, dur, out):
    vf = ("scale=2200:-1,"
          "zoompan=z='min(1+0.00045*on,1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          ":d=1:s=1920x1080:fps=%d," % FPS +
          "fade=t=in:st=0:d=0.45,fade=t=out:st=%.2f:d=0.45,format=yuv420p" % max(0.1, dur - 0.45))
    run([FF, "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-framerate", str(FPS), "-i", frame, "-t", "%.3f" % dur,
         "-vf", vf, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-r", str(FPS), "-pix_fmt", "yuv420p", out])


def main():
    total = 0.0
    clips = []
    listfile = os.path.join(BUILD, "clips_cosy.txt")
    with open(listfile, "w", encoding="utf-8") as f:
        for sc in SCENES:
            raw = os.path.join(BUILD, "cosy_%s.wav" % sc["id"])
            wav = os.path.join(BUILD, "c16_%s.wav" % sc["id"])
            run([FF, "-y", "-hide_banner", "-loglevel", "error", "-i", raw,
                 "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", wav])
            dur, rate, ch, sw = wav_info(wav)
            sc.update(voice_dur=dur, dur=sc["lead"] + dur + sc["tail"], wav=wav)
            total += sc["dur"]
            print("  %s 配音 %.2fs → 镜头 %.2fs" % (sc["id"], dur, sc["dur"]))
            frame = os.path.join(FRAMES, "frame_%s.png" % sc["id"])
            clip = os.path.join(BUILD, "clipc_%s.mp4" % sc["id"])
            build_clip(frame, sc["dur"], clip)
            clips.append(clip)
            f.write("file '%s'\n" % clip.replace("\\", "/"))
    print("总时长 %.1fs" % total)

    video = os.path.join(BUILD, "video_cosy.mp4")
    run([FF, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", listfile, "-c", "copy", video])

    outwav = os.path.join(BUILD, "audio_cosy.wav")
    with wave.open(outwav, "wb") as out:
        first = True
        for sc in SCENES:
            with wave.open(sc["wav"], "rb") as w:
                params = w.getparams()
                frames = w.readframes(w.getnframes())
            if first:
                out.setnchannels(params.nchannels)
                out.setsampwidth(params.sampwidth)
                out.setframerate(params.framerate)
                first = False
            rate, ch, sw = params.framerate, params.nchannels, params.sampwidth
            out.writeframes(b"\x00" * int(rate * sc["lead"]) * ch * sw)
            out.writeframes(frames)
            out.writeframes(b"\x00" * int(rate * sc["tail"]) * ch * sw)

    final = os.path.join(OUTDIR, "B站大肥鱼屏蔽器-宣传片-人声版.mp4")
    run([FF, "-y", "-hide_banner", "-loglevel", "error",
         "-i", video, "-i", outwav,
         "-af", "aresample=44100,pan=stereo|c0=c0|c1=c0",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-shortest",
         "-movflags", "+faststart", final])
    print("完成:", final, round(os.path.getsize(final) / 1024 / 1024, 2), "MB")


if __name__ == "__main__":
    main()
