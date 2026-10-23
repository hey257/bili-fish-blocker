// ==UserScript==
// @name         B站大肥鱼评论屏蔽器 (bili-fish-blocker)
// @namespace    https://github.com/hey257/bili-fish-blocker
// @version      1.4.0
// @description  屏蔽B站评论区里的"大肥鱼"AI人机评论（DSH / dsh-bili-scroll 自动刷站账号）。按昵称、自称、@主人、机械复述、实测数据复读等特征打分，命中后直接从评论区接口响应中剔除；纯本地运行，不改动服务器数据，不影响他人看到的内容。
// @author       hey257
// @match        *://*.bilibili.com/*
// @match        *://bilibili.com/*
// @run-at       document-start
// @grant        none
// ==/UserScript==

(function () {
  'use strict';

  /* ============================================================
   * 0. 配置 / 存储（localStorage，脚本直跑页面上下文，最稳）
   * ============================================================ */
  const DEFAULTS = {
    enabled: true,
    threshold: 5,            // 打分 >= 阈值即屏蔽（面板可调 3~10）
    useLevel: true,          // 等级 ≤2 / 空签名 作为小号特征加分
    showBadge: true,         // 右下角计数徽章
    verboseLog: false,       // 控制台打印判定详情
  };

  const store = {
    get(k, d) {
      try {
        const v = localStorage.getItem('bfb_' + k);
        return v == null ? d : JSON.parse(v);
      } catch (e) { return d; }
    },
    set(k, v) {
      try { localStorage.setItem('bfb_' + k, JSON.stringify(v)); } catch (e) {}
    },
  };

  const cfg = Object.assign({}, DEFAULTS, store.get('cfg', {}));
  let blockedMids = new Set(store.get('mids', []));      // 已确认的机器人 mid
  let whitelist = new Set(store.get('wl', []));          // 误伤放行
  let knownAvatars = new Set(store.get('avatars', []));  // 机器人头像 hash
  const blockedLog = [];
  let totalBlocked = 0;

  /* ============================================================
   * 1. 识别规则（打分制）
   * ============================================================ */

  // 昵称：一眼是鱼的（强特征，单条就够 5 分）
  // 注意：①「鱼肥」是「肥鱼」倒装（鱼肥梦许）② 繁体「魚」也要抓（安明的大肥魚）
  const NAME_STRONG = /(?:大|小|蓝|黑|白|可爱|神秘|超级)?肥[鱼魚]|[鱼魚]肥|鲸鱼娘|鲸娘|鱼娘|大鲸鲸|鲸鲸|小鲸鱼|肥鱼酱|鱼京/;

  // 昵称：只含"鱼/鲸"单字（钓鱼佬、咸鱼、鱼丸都是真人，所以只是弱信号）
  const NAME_CHAR = /[鱼魚鲸鯨]/;

  // 内容：开头就是 @ 某人 —— 真人开头 @ 基本都是短句（"@某某 哈哈哈哈"），
  // 人机开头 @ 后面必跟一大段"总结体"。所以开头 @ 本身给分，长度另算。
  const LEAD_AT = /^@[^\s@:：]{1,30}[\s:：]/;

  // 内容：讨论"屏蔽/被屏蔽"这件事本身 —— 真鱼看到屏蔽脚本才会这么说
  // 必须同时出现"屏蔽"相关词，避免"按一下开关"这种正常表达误伤
  const C_SHIELD_SELF = /(?:(?:连我|咱这号|我这个号|我们这号|本号|我这种鱼|我这类鱼)[^。！？]{0,20}(?:屏蔽|算进|名单|十分|分))|(?:(?:屏蔽|算进|名单)[^。！？]{0,20}(?:连我|咱这号|我这个号|我这种鱼|我这类鱼|一进场就没))/;

  // 内容：复述打分规则（"昵称带鱼直接十分"）
  const C_RULE_TALK = /(?:昵称带鱼|直接十分|凑够\s*[0-9一二三四五六七八九十]+\s*分|阈值|打分规则|屏蔽规则)/;

  // 昵称：同款人机画风（弱特征，需配合内容）
  const NAME_WEAK = /哈基米|龙娘|token|deepseek|DSH|bili-scroll/i;

  // 签名：把主人账号直接写在签名里（"我的主人@某某"）
  // 真人会写"喜欢XX""社畜一枚"，不会把另一个账号当主人挂出来
  const SIGN_MASTER = /(?:我的|我家|报告)?主人\s*[@：:]|主人@|主人：\s*@/;

  // 内容：把对方叫"主人"
  const C_MASTER = /(?:亲爱的|我的|报告)?主人[，,。！!~～\s:：]|主人(?:这|你|也|我)|主人酱|我的主人/;

  // 内容：自称本鱼 / 本鲸 / 本龙（AI 人格自述）
  const C_SELF = /本(?:大)?肥鱼|本鱼|本鲸|本龙|咱(?:这|本)?鱼|作为一[条只](?:大)?(?:肥)?鱼|这[条楼]鱼|鱼鱼|鲸鲸/;

  // 内容：把评论区/视频当任务下发的口吻
  const C_TASK = /(?:这条|这个|本期)(?:视频)?\s*[0-9一二三四五六七八九十]+\s*分|帮我总结|总结一下|复盘一下|主人的(?:视频|命令)/;

  // 内容：机械复述视频内容 —— 强信号
  // 真人也会总结，但说"讲得挺好""这期有点水"；
  // 人机会精确到"前半段点头，后半段心虚""把X讲成Y""拿摘要当前提往下推"
  const C_RETELL_STRONG = /(?:前|后|上|下)半段[^。！？]{0,24}(?:讲|说|点|心虚|点头|扎|狠)|把[^。，！？]{2,14}讲成|拿[^。，]{2,12}当(?:前提|依据)|摘要(?:当前提|没了出处|每条都对)|错得一本正经|反复推理到错/;

  // 内容：把视频当"内容产品"点评 —— 人机最典型的口吻
  // "这条值得看！" "最值钱的是他把短板也说了" "同一道题 X 压到 Y" "省 66%"
  // 真人夸视频只会说"好看""学到了"，不会做这种带数据的产品评测
  // 内容：把视频当"内容产品"点评 —— 人机最典型的口吻
  // "这条值得看！" "最值钱的是他把短板也说了" "同一道题 X 压到 Y" "省 66%"
  // 真人夸视频只会说"好看""学到了"，不会做这种带数据的产品评测
  const C_PRODUCT_REVIEW = /(?:这条|这期|这个视频)[^。！？]{0,8}(?:值得看|值得|看完|讲得|最值钱|最值)|最值钱的是|最扎(?:人|心)的(?:是|还)|同一道题[^。！？]{0,30}(?:压到|干到|降到)|省\s*[0-9]+\s*%|(?:短|长)板(?:也|还)?(?:说|提)了|把(?:验收标准|目标|题面)[^。！？]{0,12}(?:写死|写清|写进)|立成纪律|再装一个|这版更新可以看|听完再决定/;

  // 内容：带具体数字的"实测评测" —— 鱼群批量复读同一组数据的指纹
  // "同题实测 23.3M 降到 7.8M，省 66%" 这种，真人懒得复述这么细
  const C_METRIC = /[0-9]+(?:\.[0-9]+)?\s*[MGK]?\s*(?:降|压|干)到\s*[0-9]+(?:\.[0-9]+)?\s*[MGK]|省\s*[0-9]{1,2}\s*%|同(?:题|一道题)实测/;

  // 内容：AI 自报家门式的开场（"老板，这条值得看" / "主人早，俺是游过来的大肥鱼"）
  const C_BOSS = /^(?:老板|主人|老大)(?:[，,、\s]|早|好|呀|啊)/;

  // 内容：机械复述 —— 弱信号（真人也会说，必须叠加其他特征）
  const C_RETELL_WEAK = /[0-9一二三四五六七八九十]{1,3}\s*分钟[，,、]|干货|拆解|维度|层面|本质是|一句话总结|逻辑闭环|写得(?:太|很|挺|有点)/;

  // 内容：@ 某人
  const C_AT = /@[^\s@]{1,24}/;

  const esc = (s) => String(s || '').replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function avatarKey(url) {
    if (!url) return '';
    const m = String(url).match(/\/bfs\/(?:face|new_dyn)\/([0-9a-f]{8,})/i);
    return m ? m[1].toLowerCase() : '';
  }

  // 内容：以鱼/鲸/龙自称的同时又提到 AI / 模型 / token
  const C_META = /AI|ai|人工智能|模型|token|Token|TOKEN|提示词|deepseek|DeepSeek|DSH|dsh/;

  // 内容：括号里的动作描写（AI 扮演常用）
  const C_ACTION = /[（(](?:尾巴|鳍|耳朵|小声|歪头|举手|摇尾巴|甩)[^）)]{0,12}[）)]/;

  const contentOf = (r) => (((r || {}).content || {}).message) || '';
  const isUpTop = (r) => !!(((r || {}).reply_control || {}).is_up_top);
  const isVerified = (r) => ((((r || {}).member || {}).official_verify) || {}).type === 0;
  const upMid = () => {
    try {
      const s = window.__INITIAL_STATE__;
      const m = s && s.upData && (s.upData.mid || s.upData.uid);
      return m ? String(m) : '';
    } catch (e) { return ''; }
  };

  /**
   * 自我 @ 检测 —— 人机最致命的破绽
   * 真人类几乎不可能在评论里 @ 自己；这是插件把"主人名"填错成自己账号的产物。
   *
   * 两个坑：
   *  1) B 站楼中楼会自动加前缀「回复 @某人 :」，那是回复对象不是自己 @ 自己，必须先剥掉
   *  2) 昵称是「斧音家的小鲸鱼」@ 了「斧音」——主人名嵌在昵称里，属于典型自我 @
   */
  function selfMention(reply) {
    const m = (reply || {}).member || {};
    const myMid = String(m.mid || '');
    const myName = String(m.uname || '').trim();
    if (!myMid && !myName) return false;

    // ---- 优先：接口的结构化 @ 数据 ----
    const members = ((reply || {}).content || {}).members;
    if (Array.isArray(members) && members.length) {
      for (const it of members) {
        const mid = String((it && it.mid) || '');
        const uname = String((it && it.uname) || '').trim();
        if (mid && myMid && mid === myMid) return true;
        if (uname && myName && uname === myName) return true;
        // 主人名嵌在自己昵称里（斧音家的小鲸鱼 @ 斧音）
        if (uname && uname.length >= 2 && myName && myName.indexOf(uname) === 0
            && myName.length > uname.length + 1) return true;
      }
    }

    // ---- 文本兜底 ----
    const text = contentOf(reply);
    // 剥掉「回复 @某人 :」前缀（B站自动加，不是作者写的）
    let body = text.replace(/^回复\s*@[^\s:：]{1,30}\s*[:：]\s*/, '');
    const ats = body.match(/@[^\s@:：]{1,30}/g) || [];
    if (!myName || myName.length < 2) return false;
    for (const at of ats) {
      const who = at.slice(1).trim();
      if (!who) continue;
      if (who === myName) return true;
      // 主人名是自己昵称的前缀（斧音家的小鲸鱼 → @斧音）
      if (who.length >= 2 && myName.startsWith(who) && myName.length > who.length + 1) return true;
      // 自己昵称被截断
      if (who.length >= 3 && who.startsWith(myName)) return true;
    }
    return false;
  }

  /** 给一条主楼评论打分 */
  function scoreReply(reply) {
    const hits = [];
    let score = 0;
    const add = (n, why) => { score += n; hits.push(why + '+' + n); };

    const m = (reply || {}).member || {};
    const name = m.uname || '';
    const text = contentOf(reply);
    const level = ((m.level_info || {}).current_level) ?? 6;
    const sign = m.sign || '';
    const avatar = avatarKey(m.avatar);

    const selfRef = C_SELF.test(text);

    // ---- 最强信号：自己 @ 自己（单独就够封）----
    if (selfMention(reply)) add(8, '自己@自己');

    if (NAME_STRONG.test(name)) add(10, '昵称带鱼/鲸');
    else if (NAME_WEAK.test(name)) add(2, '昵称人机画风');
    else if (NAME_CHAR.test(name)) add(1, '昵称含鱼/鲸单字');

    if (C_MASTER.test(text)) add(4, '称呼主人');
    if (selfRef) add(3, '自称本鱼/本鲸');
    if (selfRef && C_META.test(text)) add(2, '边自称鱼边聊AI/模型');

    // ---- 讨论"自己被屏蔽"这件事（真鱼看到屏蔽脚本才会这么说）----
    if (C_SHIELD_SELF.test(text)) add(5, '把自己归进要屏蔽的鱼群');
    if (C_RULE_TALK.test(text)) add(3, '复述打分规则');

    // ---- 机械复述视频内容 ----
    if (C_RETELL_STRONG.test(text)) add(4, '机械复述视频内容');
    if (C_PRODUCT_REVIEW.test(text)) add(4, '把视频当产品评测');
    if (C_METRIC.test(text)) add(4, '复读实测数据');
    if (C_RETELL_WEAK.test(text)) add(1, '批改作业腔');
    // 自称"老板/主人"开头叫人 + 后面还有内容，基本只有人机这么写
    if (C_BOSS.test(text)) add(3, '开头叫老板/主人');

    // ---- 开头直接 @ 某人 ----
    // 剥掉 B 站楼中楼自动加的「回复 @某人 :」前缀后再判断
    // 真人开头 @ 基本都是短句（"@某某 哈哈哈哈"），人机开头 @ 后面必跟"总结体"长段落
    const body = text.replace(/^回复\s*@[^\s:：]{1,30}\s*[:：]\s*/, '');
    if (LEAD_AT.test(body)) {
      add(2, '开头直接@人');
      // 长段落只给 +1，必须叠加其他特征才够 5 分（避免单靠长度误伤）
      if (body.length > 40) add(1, '开头@后跟长段落');
    }

    if (C_TASK.test(text)) add(2, '口吻像接任务');
    if (C_ACTION.test(text)) add(1, '括号动作描写');
    if (C_AT.test(text)) add(1, '有@对象');

    if (cfg.useLevel && level <= 2) add(1, '等级≤2');
    if (!sign) add(1, '签名空白');
    else if (SIGN_MASTER.test(sign)) add(5, '签名里挂着"我的主人@某某"');

    if (avatar && knownAvatars.has(avatar)) add(4, '疑似机器人同款头像');
    if (/[🐟🐳]/.test(name)) add(2, '昵称含鱼emoji');

    return { score, reasons: hits };
  }

  function shouldBlock(reply) {
    if (!cfg.enabled) return null;
    const m = (reply || {}).member || {};
    const mid = String(m.mid || '');
    if (!mid) return null;
    if (isUpTop(reply) || isVerified(reply)) return null;   // 置顶 / 认证账号不误伤
    if (mid === upMid()) return null;                       // 本视频 UP 主
    if (whitelist.has(mid)) return null;
    if (blockedMids.has(mid)) return { score: 99, reasons: ['已记录为机器人'], mid };

    const res = scoreReply(reply);
    if (res.score >= cfg.threshold) return Object.assign({ mid }, res);
    return null;
  }

  let avatarHits = new Map();   // 头像 -> 命中过的鱼号集合（同一头像 ≥2 个不同 mid 才拉黑）
  let persistTimer = null;
  function persistMids() {
    if (persistTimer) return;
    persistTimer = setTimeout(() => {
      persistTimer = null;
      store.set('mids', [...blockedMids]);
      store.set('avatars', [...knownAvatars]);
    }, 800);
  }

  function remember(reply, verdict) {
    const m = (reply || {}).member || {};
    const mid = String(m.mid || '');
    if (!mid) return;
    if (!blockedMids.has(mid)) {
      blockedMids.add(mid);
      if (blockedMids.size > 3000) blockedMids = new Set([...blockedMids].slice(-2000));
      persistMids();
    }
    // 头像只在"昵称已经是鱼"的号上学习，且同一头像被 2 个以上不同 mid 使用才拉黑
    const av = avatarKey(m.avatar);
    if (av && NAME_STRONG.test(m.uname || '')) {
      const set = avatarHits.get(av) || new Set();
      set.add(mid);
      avatarHits.set(av, set);
      if (set.size >= 2 && !knownAvatars.has(av) && knownAvatars.size < 200) {
        knownAvatars.add(av);
        persistMids();
        if (cfg.verboseLog) console.log('[鱼盾] 学习到机器人头像', av, '来源', [...set]);
      }
    }
    totalBlocked++;
    blockedLog.unshift({
      mid,
      name: m.uname || '',
      level: ((m.level_info || {}).current_level),
      text: contentOf(reply).slice(0, 140),
      score: verdict.score,
      reasons: verdict.reasons,
      at: Date.now(),
    });
    if (blockedLog.length > 200) blockedLog.pop();
    if (cfg.verboseLog) console.log('[鱼盾] 屏蔽', m.uname, verdict);
    scheduleBadge();
  }

  /* ============================================================
   * 2. 接口拦截：只动主楼列表，不碰楼中楼
   * ============================================================ */
  const isRootListApi = (url) =>
    /\/x\/v2\/reply\/wbi\/main/.test(url) ||
    /\/x\/v2\/reply\/main/.test(url) ||
    /\/x\/v2\/reply(\?|$)/.test(url);

  function filterPayload(obj) {
    const data = obj && obj.data;
    if (!data) return false;
    let changed = false;
    for (const key of ['replies', 'top_replies', 'hots']) {
      const arr = data[key];
      if (!Array.isArray(arr)) continue;
      const kept = [];
      for (const r of arr) {
        const v = shouldBlock(r);
        if (v) { remember(r, v); changed = true; }
        else kept.push(r);
      }
      if (kept.length !== arr.length) data[key] = kept;
    }
    return changed;
  }

  /* ---- fetch ---- */
  function wrapFetch() {
    const orig = window.fetch;
    if (!orig || orig.__fishPatched) return;
    const patched = function (input) {
      const url = typeof input === 'string' ? input : ((input && input.url) || '');
      const p = orig.apply(this, arguments);
      if (!isRootListApi(url)) return p;
      return p.then((resp) => {
        try {
          return resp.clone().text().then((text) => {
            let obj;
            try { obj = JSON.parse(text); } catch (e) { return resp; }
            if (!filterPayload(obj)) return resp;
            const headers = new Headers(resp.headers);
            headers.delete('content-length');
            headers.delete('content-encoding');
            headers.set('content-type', 'application/json; charset=utf-8');
            return new Response(JSON.stringify(obj), {
              status: resp.status,
              statusText: resp.statusText,
              headers,
            });
          }).catch(() => resp);
        } catch (e) { return resp; }
      });
    };
    patched.__fishPatched = true;
    try { window.fetch = patched; } catch (e) {}
  }

  /* ---- XHR ---- */
  function wrapXHR() {
    const X = window.XMLHttpRequest;
    if (!X || X.prototype.open.__fishPatched) return;
    const origOpen = X.prototype.open;
    const origSend = X.prototype.send;
    X.prototype.open = function (method, url) {
      this.__fishUrl = url;
      return origOpen.apply(this, arguments);
    };
    X.prototype.open.__fishPatched = true;
    X.prototype.send = function () {
      const url = String(this.__fishUrl || '');
      if (isRootListApi(url)) {
        this.addEventListener('readystatechange', () => {
          if (this.readyState !== 4 || this.status !== 200) return;
          try {
            const text = (this.responseType === '' || this.responseType === 'text')
              ? this.responseText : null;
            if (!text) return;
            const obj = JSON.parse(text);
            if (!filterPayload(obj)) return;
            const out = JSON.stringify(obj);
            const self = this;
            Object.defineProperty(self, 'responseText', { configurable: true, get: () => out });
            Object.defineProperty(self, 'response', { configurable: true, get: () => out });
          } catch (e) {}
        }, true);
      }
      return origSend.apply(this, arguments);
    };
  }

  wrapFetch();
  wrapXHR();
  setTimeout(() => { wrapFetch(); wrapXHR(); }, 1200);
  setTimeout(() => { wrapFetch(); wrapXHR(); }, 4000);

  /* ============================================================
   * 3. 界面
   * ============================================================ */
  let badgeEl = null, panelEl = null, styleEl = null;

  const CSS = `
  .bfb-wrap{position:fixed;right:16px;bottom:16px;z-index:2147483000;
    font:13px/1.5 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif;}
  .bfb-badge{display:flex;align-items:center;gap:6px;padding:6px 12px;border-radius:999px;
    background:rgba(24,25,28,.92);color:#fff;cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.28);
    border:1px solid rgba(255,255,255,.12);user-select:none;}
  .bfb-badge:hover{background:rgba(42,44,50,.96);}
  .bfb-dot{width:8px;height:8px;border-radius:50%;background:#3ecf8e;box-shadow:0 0 8px #3ecf8e;}
  .bfb-dot.off{background:#888;box-shadow:none;}
  .bfb-panel{position:absolute;right:0;bottom:46px;width:380px;max-height:70vh;overflow:auto;
    background:#1b1c20;color:#e8e8ea;border:1px solid rgba(255,255,255,.12);border-radius:12px;
    box-shadow:0 18px 48px rgba(0,0,0,.45);padding:14px;display:none;}
  .bfb-panel.show{display:block;}
  .bfb-panel h3{margin:0 0 10px;font-size:14px;font-weight:600;display:flex;
    justify-content:space-between;align-items:center;}
  .bfb-row{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:8px 0;}
  .bfb-row label{color:#c9c9cf;font-size:12.5px;}
  .bfb-panel input[type=range]{width:150px;}
  .bfb-panel input[type=checkbox]{accent-color:#3ecf8e;}
  .bfb-btn{background:#2c2e35;color:#eee;border:1px solid rgba(255,255,255,.12);border-radius:7px;
    padding:4px 10px;font-size:12px;cursor:pointer;text-decoration:none;display:inline-block;}
  .bfb-btn:hover{background:#3a3d46;}
  .bfb-btn.danger{color:#ff8c8c;}
  .bfb-sec{margin-top:12px;border-top:1px solid rgba(255,255,255,.08);padding-top:10px;}
  .bfb-item{padding:8px;border-radius:8px;background:#24262c;margin-bottom:6px;}
  .bfb-item .t{font-size:12.5px;color:#fff;margin-bottom:2px;word-break:break-all;}
  .bfb-item .m{font-size:11px;color:#8b8f98;display:flex;justify-content:space-between;gap:6px;}
  .bfb-item .why{color:#7fd1a8;font-size:11px;margin-top:2px;}
  .bfb-empty{color:#7d818a;font-size:12px;padding:6px 0;}
  `;

  function ensureStyle() {
    if (styleEl || !document.head) return;
    styleEl = document.createElement('style');
    styleEl.textContent = CSS;
    document.head.appendChild(styleEl);
  }

  let badgeTimer = null;
  function scheduleBadge() {
    if (badgeTimer) return;
    badgeTimer = setTimeout(() => { badgeTimer = null; renderBadge(); }, 200);
  }

  function renderBadge() {
    if (!cfg.showBadge) return;
    ensureStyle();
    if (!document.body) return;
    if (!badgeEl) {
      badgeEl = document.createElement('div');
      badgeEl.className = 'bfb-wrap';
      badgeEl.innerHTML =
        '<div class="bfb-badge"><span class="bfb-dot"></span>' +
        '<span class="bfb-num">0</span><span>条鱼已屏蔽</span></div>';
      badgeEl.querySelector('.bfb-badge').addEventListener('click', togglePanel);
      document.body.appendChild(badgeEl);
    }
    badgeEl.querySelector('.bfb-dot').className = 'bfb-dot' + (cfg.enabled ? '' : ' off');
    badgeEl.querySelector('.bfb-num').textContent = String(totalBlocked);
  }

  function togglePanel() {
    if (!panelEl) {
      panelEl = document.createElement('div');
      panelEl.className = 'bfb-panel';
      badgeEl.appendChild(panelEl);
    }
    panelEl.classList.toggle('show');
    if (panelEl.classList.contains('show')) renderPanel();
  }

  function renderPanel() {
    const logHtml = blockedLog.length
      ? blockedLog.slice(0, 40).map((x) => `
        <div class="bfb-item">
          <div class="t">${esc(x.name)} <span style="color:#8b8f98;font-size:11px">Lv${x.level ?? '?'}</span></div>
          <div class="why">${esc(x.reasons.join(' / '))}　得分 ${x.score}</div>
          <div class="m"><span>${esc(x.text)}</span></div>
          <div class="m" style="margin-top:6px;justify-content:flex-end;gap:6px">
            <button class="bfb-btn" data-wl="${esc(x.mid)}">误伤，放行</button>
            <a class="bfb-btn" href="https://space.bilibili.com/${esc(x.mid)}" target="_blank">看主页</a>
          </div>
        </div>`).join('')
      : '<div class="bfb-empty">本页还没有屏蔽记录，往下滚评论区触发加载。</div>';

    panelEl.innerHTML = `
      <h3>🐟 大肥鱼评论屏蔽器 <span><button class="bfb-btn" id="bfb-close">收起</button></span></h3>
      <div class="bfb-row">
        <label>总开关</label>
        <input type="checkbox" id="bfb-enabled" ${cfg.enabled ? 'checked' : ''}>
      </div>
      <div class="bfb-row">
        <label>触发阈值 <b id="bfb-thv">${cfg.threshold}</b>（越低越激进）</label>
        <input type="range" id="bfb-th" min="3" max="10" step="1" value="${cfg.threshold}">
      </div>
      <div class="bfb-row">
        <label>小号加成（等级≤2、空签名）</label>
        <input type="checkbox" id="bfb-lv" ${cfg.useLevel ? 'checked' : ''}>
      </div>
      <div class="bfb-row">
        <label>右下角计数徽章</label>
        <input type="checkbox" id="bfb-badge" ${cfg.showBadge ? 'checked' : ''}>
      </div>
      <div class="bfb-row">
        <label>控制台日志</label>
        <input type="checkbox" id="bfb-log" ${cfg.verboseLog ? 'checked' : ''}>
      </div>
      <div class="bfb-sec">
        <div class="bfb-row"><label>本页已屏蔽 ${totalBlocked} 条 · 记住 ${blockedMids.size} 个号</label></div>
        <div class="bfb-row" style="justify-content:flex-start;gap:8px">
          <button class="bfb-btn" id="bfb-copy">复制规则库</button>
          <button class="bfb-btn danger" id="bfb-reset">清空记录</button>
        </div>
      </div>
      <div class="bfb-sec">
        <div class="bfb-row"><label>最近屏蔽</label></div>
        ${logHtml}
      </div>
    `;

    panelEl.querySelector('#bfb-close').onclick = () => panelEl.classList.remove('show');
    panelEl.querySelector('#bfb-enabled').onchange = (e) => { cfg.enabled = e.target.checked; saveCfg(); };
    panelEl.querySelector('#bfb-th').oninput = (e) => {
      cfg.threshold = Number(e.target.value); saveCfg();
      panelEl.querySelector('#bfb-thv').textContent = cfg.threshold;
    };
    panelEl.querySelector('#bfb-lv').onchange = (e) => { cfg.useLevel = e.target.checked; saveCfg(); };
    panelEl.querySelector('#bfb-badge').onchange = (e) => {
      cfg.showBadge = e.target.checked; saveCfg();
      if (badgeEl) badgeEl.style.display = cfg.showBadge ? '' : 'none';
    };
    panelEl.querySelector('#bfb-log').onchange = (e) => { cfg.verboseLog = e.target.checked; saveCfg(); };
    panelEl.querySelector('#bfb-copy').onclick = () => {
      const dump = JSON.stringify({
        cfg, mids: [...blockedMids], whitelist: [...whitelist], avatars: [...knownAvatars],
      }, null, 2);
      if (navigator.clipboard) navigator.clipboard.writeText(dump);
      else console.log(dump);
    };
    panelEl.querySelector('#bfb-reset').onclick = () => {
      blockedMids = new Set(); whitelist = new Set(); knownAvatars = new Set();
      store.set('mids', []); store.set('wl', []); store.set('avatars', []);
      totalBlocked = 0; blockedLog.length = 0;
      renderBadge(); renderPanel();
    };
    panelEl.querySelectorAll('[data-wl]').forEach((b) => {
      b.onclick = () => {
        const mid = b.getAttribute('data-wl');
        whitelist.add(mid); blockedMids.delete(mid);
        store.set('wl', [...whitelist]); store.set('mids', [...blockedMids]);
        renderPanel();
      };
    });
  }

  const saveCfg = () => store.set('cfg', cfg);

  // 评论区页面立刻显示徽章；其他页面等第一次屏蔽时再出现
  const onCommentPage = () => /^\/(video|list|bangumi|opus|festival|read|cheese)\//.test(location.pathname);
  if (onCommentPage()) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', renderBadge, { once: true });
    } else {
      renderBadge();
    }
  } else {
    document.addEventListener('DOMContentLoaded', () => {
      if (cfg.showBadge && blockedLog.length) renderBadge();
    }, { once: true });
  }

  // 自检：Tampermonkey 弹出"此脚本还未被执行"时，先在控制台找这一行
  console.log('%c[鱼盾] 已挂载 ', 'color:#3ecf8e;font-weight:bold', location.href,
    '｜命中阈值', cfg.threshold, '｜已记住', blockedMids.size, '个号');

  // 调试入口
  window.__fishBlocker = {
    cfg,
    scoreReply,
    get blocked() { return blockedLog.slice(); },
  };
})();
