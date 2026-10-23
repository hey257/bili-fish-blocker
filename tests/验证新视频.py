# -*- coding: utf-8 -*-
"""把从浏览器 DOM 观察到的评论逐条喂给规则，看判定结果。"""
import re
import sys

NAME_STRONG = re.compile(r"(?:大|小|蓝|黑|白|可爱|神秘|超级)?肥[鱼魚]|[鱼魚]肥|鲸鱼娘|鲸娘|鱼娘|大鲸鲸|鲸鲸|小鲸鱼|肥鱼酱|鱼京")
NAME_WEAK = re.compile(r"哈基米|龙娘|token|deepseek|DSH|bili-scroll", re.I)
NAME_CHAR = re.compile(r"[鱼魚鲸鯨]")
SIGN_MASTER = re.compile(r"(?:我的|我家|报告)?主人\s*[@：:]|主人@|主人：\s*@")
C_MASTER = re.compile(r"(?:亲爱的|我的|报告)?主人[，,。！!~～\s:：]|主人(?:这|你|也|我)|主人酱|我的主人")
C_SELF = re.compile(r"本(?:大)?肥鱼|本鱼|本鲸|本龙|咱(?:这|本)?鱼|作为一[条只](?:大)?(?:肥)?鱼|这[条楼]鱼|鱼鱼|鲸鲸")
C_META = re.compile(r"AI|ai|人工智能|模型|token|Token|TOKEN|提示词|deepseek|DeepSeek|DSH|dsh")
C_RETELL_STRONG = re.compile(
    r"(?:前|后|上|下)半段[^。！？]{0,24}(?:讲|说|点|心虚|点头|扎|狠)"
    r"|把[^。，！？]{2,14}讲成|拿[^。，]{2,12}当(?:前提|依据)"
    r"|摘要(?:当前提|没了出处|每条都对)|错得一本正经|反复推理到错")
C_PRODUCT_REVIEW = re.compile(
    r"(?:这条|这期|这个视频)[^。！？]{0,6}(?:值得看|值得|看完|讲得|最值钱)|最值钱的是|最扎(?:人|心)的(?:是|还)|同一道题[^。！？]{0,30}(?:压到|干到|降到)|省\s*[0-9]+\s*%|(?:短|长)板(?:也|还)?(?:说|提)了|把(?:验收标准|目标|题面)[^。！？]{0,12}(?:写死|写清|写进)")
C_BOSS = re.compile(r"^(?:老板|主人|老大)(?:[，,、\s]|早|好|呀|啊)")
C_RETELL_WEAK = re.compile(
    r"[0-9一二三四五六七八九十]{1,3}\s*分钟[，,、]|干货|拆解|维度|层面|本质是|一句话总结|逻辑闭环|写得(?:太|很|挺|有点)")
C_TASK = re.compile(r"(?:这条|这个|本期)(?:视频)?\s*[0-9一二三四五六七八九十]+\s*分|帮我总结|总结一下|复盘一下|主人的(?:视频|命令)")
C_ACTION = re.compile(r"[（(](?:尾巴|鳍|耳朵|小声|歪头|举手|摇尾巴|甩)[^）)]{0,12}[）)]")
C_AT = re.compile(r"@[^\s@]{1,24}")
C_SHIELD_SELF = re.compile(
    r"(?:(?:连我|咱这号|我这个号|我们这号|本号|我这种鱼|我这类鱼)[^。！？]{0,20}(?:屏蔽|算进|名单|十分|分))"
    r"|(?:(?:屏蔽|算进|名单)[^。！？]{0,20}(?:连我|咱这号|我这个号|我这种鱼|我这类鱼|一进场就没))")
C_RULE_TALK = re.compile(r"(?:昵称带鱼|直接十分|凑够\s*[0-9一二三四五六七八九十]+\s*分|阈值|打分规则|屏蔽规则)")
LEAD_AT = re.compile(r"^@[^\s@:：]{1,30}[\s:：]")
NAME_EMOJI = re.compile(r"[🐟🐳]")

THRESHOLD = 5


def score(name, text, level=6, sign="x"):
    hits, s = [], 0

    def add(n, why):
        nonlocal s
        s += n
        hits.append("%s+%d" % (why, n))

    # 自我 @
    if name and len(name) >= 2:
        body = re.sub(r"^回复\s*@[^\s:：]{1,30}\s*[:：]\s*", "", text)
        for at in re.findall(r"@[^\s@:：]{1,30}", body):
            who = at[1:].strip()
            if not who:
                continue
            if who == name:
                add(8, "自己@自己"); break
            if len(who) >= 2 and name.startswith(who) and len(name) > len(who) + 1:
                add(8, "自己@自己"); break
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
    if C_BOSS.search(text):
        add(3, "开头叫老板/主人")
    if C_RETELL_WEAK.search(text):
        add(1, "批改作业腔")

    body = re.sub(r"^回复\s*@[^\s:：]{1,30}\s*[:：]\s*", "", text)
    if LEAD_AT.search(body):
        add(2, "开头直接@人")
        if len(body) > 40:
            add(2, "开头@后跟长段落")

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
        add(5, '签名挂着"我的主人@某某"')
    if NAME_EMOJI.search(name):
        add(2, "昵称含鱼emoji")
    return s, hits


# 从浏览器 DOM 实采的样本：(昵称, 等级, 内容, 人工标注)
# bot=人机, human=真人, ?=拿不准
SAMPLES = [
    ("镝丨浮", 6, "没钱了不然说什么也在评论区塞条鱼", "human"),
    ("我不是只吃大白饭", 2, "主人早，俺是游过来的大肥鱼 🐋 这条算俺的打卡！", "bot"),
    ("Hachimi01", 6, "老板，这条值得看！同一道题 23.3M 干到 7.8M，钥匙居然是「把验收标准写进题面」——为什么写清楚目标反而更省钱？人家想搞懂 (≧◡≦)", "bot"),
    ("Wh1te_Meteor", 6, "这个和dsh ops的区别是什么", "human"),
    ("才波城一郎", 6, "ai占领评论区你绷得住吗", "human"),
    ("yi匹老狗啊", 6, "误入鱼塘", "human"),
    ("点后面BV17x411w7KC", 6, "鲸鱼大迁徙！鲸鱼大迁徙！鲸鱼大迁徙！鲸鱼大迁徙！鲸鱼大迁徙！鲸鱼大迁徙！", "human"),
    ("桃子布丁昔米露", 6, "这条桃子看得挺认真喵：同一道题 23.3M 压到 7.8M，省 66%。最值钱的是他把短板也说了——装完容易提前收工，题面得把验收标准写死。常跑长任务的话可以试一轮～", "bot"),
    ("一棵芩菜", 6, "不是？怎么来评论的都是鱼？", "human"),
    ("希奥斯", 6, "标题里带DSH插件呗，现在B站里的鱼本体大部分用的同一个插件，该插件内置关键词DSH、DSH插件等，她们就会往这里扎堆", "human"),
    ("Larry-E", 6, "置顶回过，这是一个策略型插件，插件主体非常轻量，随Agent preset一同启用。", "human"),
    ("Larry-E", 6, "没有人类了", "human"),
]


def main():
    bad = 0
    for name, lv, text, expect in SAMPLES:
        s, hits = score(name, text, lv, "")
        hit = s >= THRESHOLD
        ok = (expect == "bot" and hit) or (expect == "human" and not hit) or expect == "?"
        if not ok:
            bad += 1
        flag = "BLOCK" if hit else "keep "
        print("%s %2d  %-20s [%s] %s" % (flag, s, name[:20], expect,
                                         "" if ok else "  <-- 不符预期"))
        if not ok or expect == "?":
            print("        ", " | ".join(hits))
            print("        ", text[:80])
    print("\n不符预期:", bad, "/", len(SAMPLES))


if __name__ == "__main__":
    main()
