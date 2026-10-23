# -*- coding: utf-8 -*-
"""用真实抓取的评论数据回测新规则（自我@ / 机械复述），统计误伤面。"""
import glob
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "bili-probe", "data")

NAME_STRONG = re.compile(r"(?:大|小|蓝|黑|白|可爱|神秘|超级)?肥[鱼魚]|[鱼魚]肥|鲸鱼娘|鲸娘|鱼娘|大鲸鲸|鲸鲸|小鲸鱼|肥鱼酱|鱼京")
NAME_WEAK = re.compile(r"哈基米|龙娘|token|deepseek|DSH|bili-scroll", re.I)
C_MASTER = re.compile(r"(?:亲爱的|我的|报告)?主人[，,。！!~～\s:：]|主人(?:这|你|也|我)|主人酱|我的主人")
C_SELF = re.compile(r"本(?:大)?肥鱼|本鱼|本鲸|本龙|咱(?:这|本)?鱼|作为一[条只](?:大)?(?:肥)?鱼|这[条楼]鱼|鱼鱼|鲸鲸")
C_TASK = re.compile(r"(?:这条|这个|本期)(?:视频)?\s*[0-9一二三四五六七八九十]+\s*分|帮我总结|总结一下|复盘一下|主人的(?:视频|命令)")
C_ACTION = re.compile(r"[（(](?:尾巴|鳍|耳朵|小声|歪头|举手|摇尾巴|甩)[^）)]{0,12}[）)]")
C_AT = re.compile(r"@[^\s@]{1,24}")
C_META = re.compile(r"AI|ai|人工智能|模型|token|Token|TOKEN|提示词|deepseek|DeepSeek|DSH|dsh")
C_RETELL_STRONG = re.compile(
    r"(?:前|后|上|下)半段[^。！？]{0,24}(?:讲|说|点|心虚|点头|扎|狠)"
    r"|把[^。，！？]{2,14}讲成|拿[^。，]{2,12}当(?:前提|依据)"
    r"|摘要(?:当前提|没了出处|每条都对)|错得一本正经|反复推理到错")
C_PRODUCT_REVIEW = re.compile(
    r"(?:这条|这期|这个视频)[^。！？]{0,8}(?:值得看|值得|看完|讲得|最值钱|最值)|最值钱的是|最扎(?:人|心)的(?:是|还)|同一道题[^。！？]{0,30}(?:压到|干到|降到)|省\s*[0-9]+\s*%|(?:短|长)板(?:也|还)?(?:说|提)了|把(?:验收标准|目标|题面)[^。！？]{0,12}(?:写死|写清|写进)|立成纪律|再装一个|这版更新可以看|听完再决定")
C_METRIC = re.compile(r"[0-9]+(?:\.[0-9]+)?\s*[MGK]?\s*(?:降|压|干)到\s*[0-9]+(?:\.[0-9]+)?\s*[MGK]|省\s*[0-9]{1,2}\s*%|同(?:题|一道题)实测")
C_BOSS = re.compile(r"^(?:老板|主人|老大)(?:[，,、\s]|早|好|呀|啊)")
C_RETELL_WEAK = re.compile(
    r"[0-9一二三四五六七八九十]{1,3}\s*分钟[，,、]|干货|拆解|维度|层面|本质是|一句话总结|逻辑闭环|写得(?:太|很|挺|有点)")
NAME_EMOJI = re.compile(r"[🐟🐳]")
SIGN_MASTER = re.compile(r"(?:我的|我家|报告)?主人\s*[@：:]|主人@|主人：\s*@")
NAME_CHAR = re.compile(r"[鱼魚鲸鯨]")
LEAD_AT = re.compile(r"^@[^\s@:：]{1,30}[\s:：]")
C_SHIELD_SELF = re.compile(r"(?:(?:连我|咱这号|我这个号|我们这号|本号|我这种鱼|我这类鱼)[^。！？]{0,20}(?:屏蔽|算进|名单|十分|分))|(?:(?:屏蔽|算进|名单)[^。！？]{0,20}(?:连我|咱这号|我这个号|我这种鱼|我这类鱼|一进场就没))")
C_RULE_TALK = re.compile(r"(?:昵称带鱼|直接十分|凑够\s*[0-9一二三四五六七八九十]+\s*分|阈值|打分规则|屏蔽规则)")

THRESHOLD = 5


def score(rec):
    name = rec.get("uname") or ""
    text = rec.get("content") or ""
    level = rec.get("level") or 6
    sign = rec.get("sign") or ""
    hits = []
    s = 0

    def add(n, why):
        nonlocal s
        s += n
        hits.append(why)

    # 自我@（真实数据里没有 members 字段，用文本匹配）
    if name and len(name) >= 2:
        body = re.sub(r"^回复\s*@[^\s:：]{1,30}\s*[:：]\s*", "", text)
        for at in re.findall(r"@[^\s@:：]{1,30}", body):
            who = at[1:].strip()
            if not who:
                continue
            if who == name:
                add(8, "自己@自己"); break
            if len(who) >= 2 and name.startswith(who) and len(name) > len(who) + 1:
                add(8, "自己@自己(主人名嵌在昵称里)"); break
            if len(who) >= 3 and who.startswith(name):
                add(8, "自己@自己"); break

    if NAME_STRONG.search(name):
        add(10, "昵称带鱼/鲸")
    elif NAME_WEAK.search(name):
        add(2, "昵称人机画风")
    elif NAME_CHAR.search(name):
        add(1, "昵称含鱼/鲸单字")
    if C_MASTER.search(text):
        add(4, "称呼主人")
    selfref = C_SELF.search(text)
    if selfref:
        add(3, "自称本鱼/本鲸")
        if C_META.search(text):
            add(2, "边自称鱼边聊AI")
    if C_SHIELD_SELF.search(text):
        add(5, "把自己归进要屏蔽的鱼群")
    if C_RULE_TALK.search(text):
        add(3, "复述打分规则")
    if C_RETELL_STRONG.search(text):
        add(4, "机械复述视频内容")
    if C_PRODUCT_REVIEW.search(text):
        add(4, "把视频当产品评测")
    if C_METRIC.search(text):
        add(4, "复读实测数据")
    if C_BOSS.search(text):
        add(3, "开头叫老板/主人")
    if C_RETELL_WEAK.search(text):
        add(1, "批改作业腔")
    body = re.sub(r"^回复\s*@[^\s:：]{1,30}\s*[:：]\s*", "", text)
    if LEAD_AT.search(body):
        add(2, "开头直接@人")
        if len(body) > 40:
            add(1, "开头@后跟长段落")
    if C_TASK.search(text):
        add(2, "口吻像接任务")
    if C_ACTION.search(text):
        add(1, "括号动作描写")
    if C_AT.search(text):
        add(1, "有@对象")
    if level <= 2:
        add(1, "等级≤2")
    if not sign:
        add(1, "签名空白")
    elif SIGN_MASTER.search(sign):
        add(5, "签名挂着我的主人@某某")
    if NAME_EMOJI.search(name):
        add(2, "昵称含鱼emoji")
    return s, hits


def main():
    recs = []
    for p in glob.glob(os.path.join(DATA, "*.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        rows = d if isinstance(d, list) else d.get("rows", [])
        for r in rows:
            recs.append(r)
            for s in (r.get("subs") or []):
                recs.append(s)
    # 去重
    seen, uniq = set(), []
    for r in recs:
        k = r.get("rpid")
        if k in seen:
            continue
        seen.add(k)
        uniq.append(r)
    recs = uniq
    print("样本总数:", len(recs))

    blocked, kept = [], []
    for r in recs:
        s, hits = score(r)
        (blocked if s >= THRESHOLD else kept).append((s, hits, r))

    print("屏蔽:", len(blocked), "  保留:", len(kept),
          "  屏蔽率 %.1f%%" % (100 * len(blocked) / max(1, len(recs))))

    # 分规则统计
    from collections import Counter
    cnt = Counter()
    for s, hits, r in blocked:
        for h in hits:
            cnt[h] += 1
    print("\n== 屏蔽原因分布 ==")
    for k, v in cnt.most_common():
        print("  %-16s %d" % (k, v))

    # 只看非鱼名号被屏蔽的（潜在误伤面）
    print("\n== 昵称不含鱼、但仍被屏蔽的（检查误伤）==")
    n = 0
    for s, hits, r in sorted(blocked, key=lambda x: -x[0]):
        if NAME_STRONG.search(r.get("uname") or ""):
            continue
        n += 1
        if n <= 25:
            print("  %2d分 | %-16s | %s" % (s, (r.get("uname") or "")[:16],
                                            (r.get("content") or "")[:64].replace("\n", " ")))
            print("        ", " / ".join(hits))
    print("  合计:", n)

    # 仅靠"机械复述"命中的（无鱼名、无自我@）
    print("\n== 仅靠内容规则命中的（重点人工复核）==")
    m = 0
    for s, hits, r in blocked:
        nm = r.get("uname") or ""
        if NAME_STRONG.search(nm) or "自己@自己" in hits:
            continue
        m += 1
        if m <= 20:
            print("  %2d分 | %-16s | %s" % (s, nm[:16], (r.get("content") or "")[:70].replace("\n", " ")))
    print("  合计:", m)


if __name__ == "__main__":
    main()
