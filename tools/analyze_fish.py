# -*- coding: utf-8 -*-
"""批量搜索鱼号，验证两个假设：
1) mid 号段集中 = 同一批注册
2) 头像复用
"""
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/155.0.0.0 Safari/537.36")
H = {"User-Agent": UA, "Referer": "https://www.bilibili.com/",
     "Accept": "application/json", "Accept-Language": "zh-CN,zh;q=0.9"}

KEYWORDS = ["大肥鱼", "小肥鱼", "鲸鱼娘", "肥鱼", "鲸娘", "蓝肥鱼", "大鲸鲸",
            "肥鱼酱", "鲸鱼", "deepseek", "dsh", "哈基米", "龙娘"]


def get(url, params=None, cookie=""):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    h = dict(H)
    if cookie:
        h["Cookie"] = cookie
    req = urllib.request.Request(url, headers=h)
    return json.loads(urllib.request.urlopen(req, timeout=25).read().decode("utf-8"))


def akey(u):
    if not u:
        return ""
    m = re.search(r"/bfs/(?:face|new_dyn)/([0-9a-f]{8,})", u, re.I)
    return m.group(1).lower() if m else ""


def main():
    spi = get("https://api.bilibili.com/x/frontend/finger/spi")["data"]
    ck = "buvid3=%s; buvid4=%s; b_nut=%d" % (spi["b_3"], spi["b_4"], int(time.time()))

    users = {}
    for kw in KEYWORDS:
        for pn in (1, 2):
            try:
                d = get("https://api.bilibili.com/x/web-interface/wbi/search/type",
                        {"search_type": "bili_user", "keyword": kw, "page": pn}, ck)
            except Exception as e:
                print("err", kw, pn, e)
                continue
            if d.get("code") != 0:
                print("code", d.get("code"), kw)
                continue
            for u in ((d.get("data") or {}).get("result") or []):
                mid = str(u.get("mid") or "")
                if not mid:
                    continue
                users[mid] = dict(mid=mid, uname=u.get("uname") or "",
                                  level=u.get("level"), fans=u.get("fans"),
                                  face=u.get("upic") or "", kw=kw,
                                  sign=u.get("usign") or "")
            time.sleep(1.2)
        print("  %-10s 累计 %d" % (kw, len(users)))

    # 只看像鱼的
    FISH = re.compile(r"(?:大|小|蓝|黑|白|可爱|神秘|超级)?肥鱼|鲸鱼娘|鲸娘|鱼娘|大鲸鲸|鲸鲸|小鲸鱼|肥鱼酱|鱼京")
    fish = [u for u in users.values() if FISH.search(u["uname"])]
    print("\n搜到用户 %d，其中昵称像鱼 %d" % (len(users), len(fish)))

    print("\n=== mid 号段分布（按前 7 位）===")
    seg = Counter()
    for u in fish:
        seg[u["mid"][:7]] += 1
    for s, c in seg.most_common(12):
        print("  %-8s %d 个" % (s, c))

    print("\n=== 像鱼号的明细（按 mid 排序）===")
    for u in sorted(fish, key=lambda x: int(x["mid"])):
        print("  %-18s %-2s 粉%-6s %-16s %s" % (
            u["mid"], u["level"], u["fans"], u["uname"][:16], akey(u["face"])[:16]))

    print("\n=== 头像复用 ===")
    av = defaultdict(list)
    for u in users.values():
        k = akey(u["face"])
        if k:
            av[k].append(u)
    multi = [(k, v) for k, v in av.items() if len(v) >= 2]
    multi.sort(key=lambda x: -len(x[1]))
    for k, v in multi[:15]:
        print("  %s  %d 个号: %s" % (k[:16], len(v), [x["uname"][:12] for x in v[:5]]))
    print("  多号共用头像组数:", len(multi))

    out = {"users": list(users.values()), "fish": fish}
    with open("fish_users.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("\nsaved fish_users.json")


if __name__ == "__main__":
    main()
