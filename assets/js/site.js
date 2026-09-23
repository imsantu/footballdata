/* ==========================================================================
   站点外壳：全宽冻结顶栏（bilibili 风三段式）

     行 1   左：品牌（马善政毛笔楷书 + 渐变）
             中：联赛 tab（页面脚本渲染后搬进来）
             右：统计类型 ▾ / 联赛层级 ▾ / 范围 ▾ / 主题按钮
     行 2   二级 tab：赛季年份（居中）

   · 顶栏 position:fixed + 等高占位块，绕开 sticky 包含块坑
   · 主题由外壳唯一持有（qzl_theme），跨页状态一致
   · 「范围」下拉菜单读页面 #winSwitch 按钮（不修改页面 JS），点击反向触发原按钮
   · 「品牌字体」走 assets/font/ma-shan-zheng.woff2（仅含「叕中啦」三字，1.6 KB）

   ★ 以后要加新页面（次级联赛进球数、其他地区联赛…），只改下面的 SITE_NAV：
       1) 在对应主题下面加一条 { id, label, file, ready, desc }
       2) 把页面 HTML 放进 pages/、数据与脚本放进 assets/js/、样式放进 assets/css/
       3) file 名与 pages/ 下的文件名保持一致即可，导航与首页卡片会自动同步
   ========================================================================== */
(function () {
  'use strict';

  // 站点导航与首页卡片共用同一份配置：必须先挂到 window 再做桌面/移动分叉。
  // 否则手机上 4 张入口卡片（#homeCards）会因为 SITE_NAV 未定义而消失，只剩标题。
  //
  // 移动端（<820px）：站点外壳整体让位给 H5 移动外壳（assets/js/h5-shell.js）；
  // 桌面顶栏、三态主题、下拉菜单在手机上都是多余且会打架的东西，直接不建。
  // 页面脚本仍会照常渲染数据，只是顶栏交给移动端自己的 AppBar + 底部 tab。

  var SITE_NAV = [
    {
      id: 'draws',
      label: '平局统计',
      items: [
        { id: 'draws-big5',  label: '五大联赛', file: 'draws-big5.html',  ready: true,
          desc: '英超 / 西甲 / 德甲 / 意甲 / 法甲 · 平局率、比分分布、各轮走势与各队平局' },
        { id: 'draws-champ', label: '次级联赛', file: 'draws-champ.html', ready: true,
          desc: '英冠 / 西乙 / 德乙 / 法乙 / 意乙 · 平局率、比分分布、各轮走势与各队平局' }
      ]
    },
    {
      id: 'goals',
      label: '进球数统计',
      items: [
        { id: 'goals-big5',  label: '五大联赛', file: 'goals-big5.html',  ready: true,
          desc: '英超 / 西甲 / 德甲 / 意甲 / 法甲 · 单场总进球数分布、球队进球榜、赛季走势' },
        { id: 'goals-champ', label: '次级联赛', file: 'goals-champ.html', ready: true,
          desc: '英冠 / 西乙 / 德乙 / 法乙 / 意乙 · 单场总进球数分布、球队进球榜、赛季走势' }
      ]
    }
  ];

  // 无法确定当前页时（首页 / 占位页）默认落在「平局统计」
  var DEFAULT_GROUP_ID = 'draws';

  // 暴露给首页复用（首页直接按这份配置渲染卡片，避免两处维护）
  window.SITE_NAV = SITE_NAV;
  window.SITE_PAGE_URL = function (f) { return (window.SITE_ROOT || '') + 'pages/' + f; };

  // 已统一改为「手机上也强制电脑版」：不再因窄屏提前 return，桌面外壳在任何宽度都会构建。
  // 原来的 H5 移动外壳（h5-shell.js）已移除，窄屏若提前 return 会让页面整体空白。
  try {
    if (window.matchMedia && !window.matchMedia('(min-width:820px)').matches) {
      var r = document.documentElement;
      r.setAttribute('data-theme', 'light');
      r.style.colorScheme = 'light';
      var mt = document.querySelector('meta[name="theme-color"]');
      if (mt) mt.setAttribute('content', '#f4f6fa');
      // 仅设浅色兜底，不再 return —— 继续走下方桌面外壳构建流程。
    }
  } catch (e) {}

  var ROOT = window.SITE_ROOT || '';         // 根目录页为 ''；pages/ 下的页为 '../'
  var NO_SEL = !!window.SITE_NO_SEL;          // 首页：去掉顶部 3 个下拉（统计主题/联赛层级/范围）
  // 品牌 LOGO：圆形红底 + 金色行书「中」（final_logo 素材包，assets/img/logo/png/logo-64x64.png）。
  // 透明底，深色 / 浅色导航栏均适用；文字色由 site.css 的 --brand-grad（红→金）统一控制。
  var BRAND_SVG =
    '<img class="mark" src="' + ROOT + 'assets/img/logo/png/logo-64x64.png" alt="叕中啦" width="22" height="22">';
  var CARET_SVG =
    '<svg class="caret" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" ' +
    'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';

  function pageUrl(f) { return ROOT + 'pages/' + f; }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }

  // ---- 当前页定位：靠文件名判断属于哪个主题 / 哪个层级 ----
  var cur = (location.pathname.split('/').pop() || '').toLowerCase();
  var groupIdx = -1, itemIdx = -1, defIdx = -1;
  for (var i = 0; i < SITE_NAV.length; i++) {
    if (defIdx < 0 && SITE_NAV[i].id === DEFAULT_GROUP_ID) defIdx = i;
    for (var j = 0; j < SITE_NAV[i].items.length; j++) {
      if (SITE_NAV[i].items[j].file.toLowerCase() === cur) { groupIdx = i; itemIdx = j; }
    }
  }
  if (groupIdx < 0) groupIdx = (defIdx >= 0) ? defIdx : 0;
  if (itemIdx < 0) itemIdx = 0;
  var group = SITE_NAV[groupIdx];

  // ---------------- 下拉菜单 ----------------
  function selHtml(kind, options, active) {
    var h = '<div class="sel" data-kind="' + kind + '">';
    h += '<button type="button" class="sel-btn" aria-haspopup="true" aria-expanded="false">' +
           '<span class="lb">' + esc(options[active].label) + '</span>' + CARET_SVG + '</button>';
    h += '<div class="sel-menu">';
    options.forEach(function (o, i) {
      h += '<button type="button" class="sel-item' + (i === active ? ' on' : '') + (o.disabled ? ' wait' : '') +
           '" data-kind="' + kind + '" data-i="' + i + '">' + esc(o.label) +
           (o.disabled ? '<span class="dot"></span>' : '') + '</button>';
    });
    h += '</div></div>';
    return h;
  }
  // 空状态（用于范围下拉：页面脚本还没把 #winSwitch 渲染出来）
  function selEmptyHtml(kind, label) {
    return '<div class="sel" data-kind="' + kind + '" style="display:none">' +
           '<button type="button" class="sel-btn"><span class="lb">' + esc(label) + '</span>' + CARET_SVG + '</button>' +
           '<div class="sel-menu"></div></div>';
  }

  var groupOpts = SITE_NAV.map(function (gp) {
    return { label: gp.label, disabled: !gp.items.some(function (x) { return x.ready; }) };
  });
  var levelOpts = group.items.map(function (it) {
    return { label: it.label, disabled: !it.ready };
  });

  var top = document.createElement('div');
  top.className = 'site-top';
  top.id = 'siteTop';
  top.innerHTML =
    '<div class="site-top-in">' +
      '<div class="site-top-row">' +
        '<a class="site-brand" href="' + ROOT + 'index.html" aria-label="叕中啦 · 足球数据中心">' + BRAND_SVG +
          '<span class="nm">叕中啦</span></a>' +
        '<div class="site-center" id="siteCenter"></div>' +
        '<div class="site-right">' +
          (NO_SEL ? '' :
            selHtml('g', groupOpts, groupIdx) +
            selHtml('l', levelOpts, itemIdx) +
            selEmptyHtml('w', '近五季')     /* 数据页才需要：范围下拉 adopt() 时按 #winSwitch 重写 */
          ) +
          '<button type="button" class="theme-btn" id="siteThemeBtn" aria-label="切换主题">🌗</button>' +
        '</div>' +
      '</div>' +
      '<div class="site-top-sub" id="siteSub"></div>' +
    '</div>';

  var spacer = document.createElement('div');
  spacer.className = 'site-top-spacer';
  spacer.id = 'siteTopSpacer';

  // 外壳直接挂到 body 下（原来的 #siteNav 只是个短小容器，会限制吸顶范围）
  var oldNav = document.getElementById('siteNav');
  if (oldNav && oldNav.parentNode) oldNav.parentNode.removeChild(oldNav);
  document.body.insertBefore(spacer, document.body.firstChild);
  document.body.insertBefore(top, spacer);

  // ---------------- 下拉交互 ----------------
  function closeAll(except) {
    var sels = top.querySelectorAll('.sel');
    for (var i = 0; i < sels.length; i++) {
      if (sels[i] === except) continue;
      sels[i].classList.remove('open');
      var b = sels[i].querySelector('.sel-btn');
      if (b) b.setAttribute('aria-expanded', 'false');
    }
  }
  // 跳页前先给下拉一个「忙」态（箭头转圈），再让出一帧确保它画出来，
  // 免得几 MB 数据脚本下载期间看起来像没响应。
  function goPage(box, url) {
    if (!url) return;
    closeAll();
    if (box) box.classList.add('busy');
    setTimeout(function () { location.href = url; }, 60);
  }

  top.addEventListener('click', function (e) {
    var t = e.target;
    while (t && t !== top) {
      if (t.classList) {
        if (t.classList.contains('sel-btn')) {
          var box = t.parentNode;
          if (box.style.display === 'none') return;     // 空状态下隐藏，不响应
          var willOpen = !box.classList.contains('open');
          closeAll(box);
          box.classList.toggle('open', willOpen);
          t.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
          e.stopPropagation();
          return;
        }
        if (t.classList.contains('sel-item')) {
          var kind = t.getAttribute('data-kind');
          if (kind === 'g') {
            var i = parseInt(t.getAttribute('data-i'), 10);
            if (t.classList.contains('wait')) return;
            if (i === groupIdx) { closeAll(); return; }
            var gp = SITE_NAV[i];
            var def = gp.items.filter(function (x) { return x.ready; })[0] || gp.items[0];
            goPage(box, pageUrl(def.file));
          } else if (kind === 'l') {
            var k = parseInt(t.getAttribute('data-i'), 10);
            if (t.classList.contains('wait')) return;
            var it = group.items[k];
            if (!it || !it.ready) return;
            if (it.file.toLowerCase() === cur) { closeAll(); return; }
            goPage(box, pageUrl(it.file));
          } else if (kind === 'w') {
            // 范围下拉：找到页面对应的 .wbtn，反向触发它的 click（页面逻辑由原按钮接管）
            var win = t.getAttribute('data-win');
            var realBtn = document.querySelector('#winSwitch [data-win="' + win + '"]');
            if (realBtn) { realBtn.click(); }
            closeAll();
          }
          return;
        }
      }
      t = t.parentNode;
    }
  });
  document.addEventListener('click', function (e) {
    var t = e.target;
    while (t && t !== document) {
      if (t.classList && t.classList.contains('sel')) return;
      t = t.parentNode;
    }
    closeAll();
  });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeAll(); });

  // ---------------- 高度同步（fixed 顶栏需要等高占位块） ----------------
  function syncTopH() {
    var el = document.getElementById('siteTop');
    if (!el) return;
    var h = Math.round(el.getBoundingClientRect().height);
    document.documentElement.style.setProperty('--site-top-h', h + 'px');
    document.documentElement.style.setProperty('--navh', h + 'px');
    try { document.documentElement.style.scrollPaddingTop = h + 'px'; } catch (e) {}
    var sp = document.getElementById('siteTopSpacer');
    if (sp) sp.style.height = h + 'px';
  }

  // ---------------- 首屏骨架：内容就绪后淡出 ----------------
  // 数据脚本动辄 3~5MB 且原本是同步 <script>，会阻塞解析/渲染，
  // 于是「深色背景已经画好、内容还没出来」＝ 切页时闪黑。
  // 骨架是 HTML 里静态写死的（不依赖任何脚本/外链），首帧就能画出来顶住空窗。
  var bootT0 = (window.performance && performance.now) ? performance.now() : Date.now();
  var bootGone = false;
  function hideBoot() {
    if (bootGone) return;
    bootGone = true;
    var v = document.getElementById('bootVeil');
    if (!v) return;
    var now = (window.performance && performance.now) ? performance.now() : Date.now();
    // 骨架块是延迟 0.25s 才淡入的：还没露脸就直接摘掉整块遮罩，避免「闪一下骨架」；
    // 已经露脸了就走淡出动画，别硬切。
    if (now - bootT0 < 300) { if (v.parentNode) v.parentNode.removeChild(v); return; }
    v.classList.add('out');
    setTimeout(function () { if (v.parentNode) v.parentNode.removeChild(v); }, 320);
  }
  window.QZL_BOOT_DONE = hideBoot;
  // 兜底：页面脚本万一没回调，load 后或 6s 后也会收掉，绝不会卡住不消失
  window.addEventListener('load', function () { setTimeout(hideBoot, 150); });
  setTimeout(hideBoot, 6000);

  // ---------------- 把页面的联赛 tab / 年份搬进外壳 ----------------
  function moveTo(id, host) {
    var el = document.getElementById(id);
    if (!el || !host || el.parentNode === host) return false;
    host.appendChild(el);
    return true;
  }

  // ---------------- 范围下拉：根据页面 #winSwitch 重建 ----------------
  // 用「按钮个数 + 当前 .on 文案」做签名，内容不变就不重建（避免抖开菜单）
  var winSig = null;
  function buildWinDropdown() {
    var ws = document.getElementById('winSwitch');
    var sel = top.querySelector('.sel[data-kind="w"]');
    if (!sel) return;
    if (!ws) { sel.style.display = 'none'; return; }

    var btns = ws.querySelectorAll('[data-win]');
    if (!btns.length) { sel.style.display = 'none'; return; }

    var sig = btns.length + '|' + Array.from(btns).map(function (b) {
      return b.textContent.trim() + (b.classList.contains('on') ? '*' : '');
    }).join('·');

    var label = sel.querySelector('.sel-btn .lb');
    var menu = sel.querySelector('.sel-menu');
    var activeIdx = 0;

    if (sig === winSig) {
      // 仅同步「当前选中」状态（页面上点了原按钮后，外壳也要更新高亮）
      for (var i2 = 0; i2 < btns.length; i2++) {
        if (btns[i2].classList.contains('on')) { activeIdx = i2; break; }
      }
      Array.from(menu.querySelectorAll('.sel-item')).forEach(function (it, k) {
        it.classList.toggle('on', k === activeIdx);
      });
      if (label) label.textContent = btns[activeIdx].textContent.trim();
      return;
    }
    winSig = sig;

    // 内容变了（页面切到另一组范围）→ 整体重建
    var html = '';
    btns.forEach(function (b, idx) {
      var v = b.getAttribute('data-win');
      var txt = b.textContent.trim();
      if (b.classList.contains('on')) activeIdx = idx;
      html += '<button type="button" class="sel-item" data-kind="w" data-win="' + esc(v) + '">' + esc(txt) + '</button>';
    });
    sel.innerHTML =
      '<button type="button" class="sel-btn" aria-haspopup="true" aria-expanded="false">' +
        '<span class="lb">' + esc(btns[activeIdx].textContent.trim()) + '</span>' + CARET_SVG +
      '</button>' +
      '<div class="sel-menu">' + html + '</div>';
    Array.from(menu.querySelectorAll('.sel-item')).forEach(function (it, k) {
      it.classList.toggle('on', k === activeIdx);
    });
    sel.style.display = '';
  }

  function adopt() {
    var center = document.getElementById('siteCenter');
    var sub = document.getElementById('siteSub');
    var moved = false;

    if (center) moved = moveTo('leagueTabs', center) || moved;
    if (sub) {
      moved = moveTo('seasonTabs', sub) || moved;
      // 二级 tab 由页面脚本动态填充：没有年份时整行隐藏
      var has2nd = sub.querySelector('.season-tabs, .pillrow');
      sub.style.display = has2nd ? '' : 'none';
    }
    // 范围下拉随 #winSwitch 重建
    buildWinDropdown();

    // 原容器被掏空后收掉，避免留下一条空壳
    if (moved) {
      var bars = document.querySelectorAll('.stickynav');
      for (var k = 0; k < bars.length; k++) {
        var bar = bars[k];
        if (!bar.querySelector('#leagueTabs, #seasonTabs')) bar.classList.add('site-moved');
      }
    }

    // 页面脚本一旦就位，就把它自己的主题实现接到外壳上
    if (typeof window.applyMode === 'function' && window.__siteThemeBound !== window.applyMode) {
      window.__siteThemeBound = window.applyMode;
      shellApply(readMode());
      window.toggleTheme = function () { shellToggle(); };
    }
    syncTopH();
  }

  var pend = false;
  function schedAdopt() {
    if (pend) return;
    pend = true;
    setTimeout(function () { pend = false; adopt(); }, 60);
  }

  adopt();
  if (window.MutationObserver) {
    try { new MutationObserver(schedAdopt).observe(document.body, { childList: true, subtree: true }); } catch (e) {}
  }
  [0, 200, 600, 1500, 3000].forEach(function (t) { setTimeout(adopt, t); });
  window.addEventListener('load', function () { adopt(); setTimeout(adopt, 800); });
  window.addEventListener('resize', syncTopH);
  if (window.ResizeObserver) {
    try { new ResizeObserver(syncTopH).observe(top); } catch (e) {}
  }

  // ======================================================================
  // 主题：全站唯一（外壳持有）。
  //   自动 → 浅色 → 深色 → 自动 三态循环；「自动」统一为跟随系统外观
  //   （prefers-color-scheme，不支持时退回本地时间 6:00–18:00 浅色）。
  //   模式同时写进 qzl_theme / fbg_theme 两个历史键，跨页读到的始终是同一个值。
  // ======================================================================
  var THEME_KEY = 'qzl_theme';
  var THEME_MIRROR = ['qzl_theme', 'fbg_theme'];

  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); return true; } catch (e) { return false; } }

  function sysTheme() {
    try {
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) return 'dark';
      if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) return 'light';
    } catch (e) {}
    var h = new Date().getHours();
    return (h >= 6 && h < 18) ? 'light' : 'dark';
  }
  function actualOf(mode) { return mode === 'auto' ? sysTheme() : mode; }
  function paint(t) {
    document.documentElement.setAttribute('data-theme', t);
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute('content', t === 'dark' ? '#0f1117' : '#eef1f6');
  }
  var memMode = null;
  function readMode() {
    var m = lsGet(THEME_KEY);
    if (m === null) m = memMode;
    if (m !== 'auto' && m !== 'light' && m !== 'dark') m = 'auto';
    return m;
  }
  // 主题按钮图标（emoji 单字符，足够 bilibili 风的圆方块感）
  function refreshShellBtn(mode, actual) {
    var b = document.getElementById('siteThemeBtn');
    if (!b) return;
    var ico = '🌗', tip;
    if (mode === 'auto')      { ico = (actual === 'dark' ? '🌒' : '🌖'); tip = '自动 · 跟随系统外观（点击切换）'; }
    else if (mode === 'light') { ico = '☀️'; tip = '固定浅色（点击切换）'; }
    else                      { ico = '🌙'; tip = '固定深色（点击切换）'; }
    b.textContent = ico;
    b.setAttribute('aria-label', tip);
  }
  function shellApply(mode) {
    var actual = actualOf(mode);
    memMode = mode;
    for (var i = 0; i < THEME_MIRROR.length; i++) lsSet(THEME_MIRROR[i], mode);
    if (typeof window.applyMode === 'function') { try { window.applyMode(mode); } catch (e) {} }
    paint(actual);
    refreshShellBtn(mode, actual);
  }
  function shellToggle() {
    var m = readMode();
    shellApply(m === 'auto' ? 'light' : (m === 'light' ? 'dark' : 'auto'));
  }

  window.SITE_THEME = { apply: shellApply, toggle: shellToggle, mode: readMode };
  window.SITE_THEME_READY = function () { adopt(); shellApply(readMode()); window.toggleTheme = function () { shellToggle(); }; };

  var themeBtn = document.getElementById('siteThemeBtn');
  if (themeBtn) themeBtn.addEventListener('click', function () { shellToggle(); });

  try {
    if (window.matchMedia) {
      var mq = window.matchMedia('(prefers-color-scheme: dark)');
      var onSys = function () { if (readMode() === 'auto') shellApply('auto'); };
      if (mq.addEventListener) mq.addEventListener('change', onSys);
      else if (mq.addListener) mq.addListener(onSys);
    }
  } catch (e) {}
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible' && readMode() === 'auto') shellApply('auto');
  });

  // 首屏先落一次主题，避免页面脚本加载前闪白 / 闪黑
  shellApply(readMode());
})();

// ======================================================================
// Service Worker 注册（桌面 / 移动共用；站点根 scope，覆盖所有页面）
// 见根目录 sw.js：数据文件 stale-while-revalidate（换网秒开 + 每日新数据最终生效），
// 外壳 cache-first。改了任何外壳文件（site.js / css / 页面 HTML）后，
// 记得把 sw.js 里的 CACHE 版本号 +1，否则浏览器不会拉取新版 SW 逻辑。
// ⚠️ SW 仅在安全上下文（https 或 localhost）生效；GitHub Pages 为 https，部署后自动启用。
// ======================================================================
(function () {
  'use strict';
  try {
    if (!('serviceWorker' in navigator)) return;
    var proto = location.protocol;
    if (proto !== 'https:' && proto !== 'http:') return;
    if (proto === 'http:' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') return;

    // 计算站点根（处理 GitHub Pages 子路径 /footballdata/）：
    //   /footballdata/pages/goals-big5.html -> /footballdata
    //   /footballdata/                      -> /footballdata
    function siteRoot() {
      var p = location.pathname;
      p = p.replace(/\/pages\/[^/]*$/, '');
      p = p.replace(/\/index\.html$/, '');
      p = p.replace(/\/+$/, '');
      return p || '';
    }
    var root = siteRoot();
    var swUrl = root + '/sw.js';

    // load 后再注册，不阻塞首屏；注册失败也不影响正常浏览。
    window.addEventListener('load', function () {
      navigator.serviceWorker.register(swUrl, { scope: root + '/' }).catch(function (err) {
        if (window.console) console.warn('[SW] 注册失败（不影响浏览）：', err);
      });
    });
  } catch (e) {}
})();

// ── 页脚「本页更新时间」──────────────────────────────────────────────
// 全站统一读站点时间账本 window.SITE_META（assets/js/meta.js 由每次提交/同步刷新），
// 五个页面（首页 + 四个统计页）共用同一份，保证时间永远一致。
// 挂在 DOMContentLoaded 上：defer 的 meta.js 必定已执行完（首页只有这一处兜底填充）。
document.addEventListener('DOMContentLoaded', function () {
  var el = document.getElementById('ftGen');
  if (!el) return;
  var v = (window.SITE_META && window.SITE_META.generated) || '';
  el.textContent = v || '–';
});