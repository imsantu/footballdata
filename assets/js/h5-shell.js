/* ==========================================================================
   H5 移动端外壳（仅手机端启用，PC 端完全不加载/不生效）

   提供的公共能力：
     · 顶部 AppBar      —— 灰色 LOGO 占位 + 当前页名 + 右侧槽位（可放横屏/设置）
     · 吸顶筛选区      —— 联赛下拉（optgroup 分组：五大 / 次级）、赛季下拉、赛季范围分段
     · 底部 3 tab      —— 平局 / 进球数 / 更多，56px 高 + 安全区
     · 轻点气泡 tapTip —— 替代 PC 的 hover tooltip
     · 回到顶部 FAB

   主题：仅浅色单主题。**不读 localStorage、不读 prefers-color-scheme**，
   并把 <html data-theme> 钉死为 light，确保任何情况下都不闪深色。

   用法（在移动端分支里调用）：
     QZL_SHELL.mount({
       page: '平局 · 五大',
       tab:  'draws',                 // draws | goals | more
       filters: [                     // 可选，按序渲染吸顶筛选区
         { type:'select', id:'lgSel', label:'联赛', groups:[
             { label:'五大联赛', options:[{v:'__all__',t:'全部五大'},…] },
             { label:'次级联赛', options:[{v:'__all2__',t:'全部次级'},…] } ] },
         { type:'select', id:'snSel', label:'赛季', options:[…] },
         { type:'segment', id:'winSeg', options:[{v:5,t:'近五季'},{v:3,t:'近三季'}] }
       ],
       onChange: function(id, value){ … }
     });
   ========================================================================== */
(function () {
  'use strict';

  // ==========================================================================
  // 尺寸规范（对照 iOS HIG / Material 3）
  //   顶栏：iOS 内联标题 17px/600 居中；左右图标触控靶 44×44（HIG 最小点击区）
  //   底栏：内容高 56px（M3 垂直项约 56–64dp）+ safe-area-inset-bottom；
  //         图标 24px（M3 标准 24dp）、标签 12px（M3 label 12sp）；
  //         选中态用 64×32 圆角胶囊底（M3 active indicator）
  //   安全区：顶部必须留 env(safe-area-inset-top)，否则被刘海/灵动岛压住
  // ==========================================================================
  var CSS = ''
    + ':root{--h5-bg:#f4f6fa;--h5-card:#fff;--h5-border:#eaeef5;--h5-text:#0e131a;--h5-muted:#7c8899;--h5-dim:#a3adba;--h5-accent:#2f7bdc;--h5-green:#0a9b73;--h5-bar:rgba(255,255,255,.88);'
    +   '--h5-safe-top:env(safe-area-inset-top,0px);--h5-safe-bot:env(safe-area-inset-bottom,0px);'
    +   '--h5-appbar-h:44px;--h5-tabbar-h:56px;--h5-appbar:calc(var(--h5-appbar-h) + var(--h5-safe-top));--h5-tabbar:var(--h5-tabbar-h);--h5-filter:0px;}'
    + 'html[data-theme]{color-scheme:light;}'
    + 'body.h5-mode{background:var(--h5-bg);color:var(--h5-text);}'
    /* ---------- 顶栏：状态栏安全区 + 居中标题 ---------- */
    + '.h5-appbar{position:fixed;top:0;left:0;right:0;z-index:60;padding-top:var(--h5-safe-top);background:var(--h5-bar);backdrop-filter:saturate(180%) blur(14px);-webkit-backdrop-filter:saturate(180%) blur(14px);border-bottom:.5px solid #e9edf5;}'
    + '.h5-navrow{height:var(--h5-appbar-h);display:flex;align-items:center;padding:0 6px;}'
    + '.h5-appbar .h5-slot{flex:0 0 auto;display:flex;align-items:center;gap:4px;}'
    /* 左右槽等宽（各占一个 44px 触点宽度），标题才是真正居中而不是「靠右」 */
    + '.h5-appbar .h5-slot-l,.h5-appbar .h5-slot-r{min-width:44px;justify-content:flex-end;}'
    + '.h5-appbar .h5-slot-l{justify-content:flex-start;}'
    + '.h5-title{flex:1;min-width:0;font-size:17px;font-weight:600;line-height:1.2;text-align:center;color:var(--h5-text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;letter-spacing:-.2px;}'
    + '.h5-logo{width:28px;height:28px;border-radius:8px;background:#cfd8e5;color:#7c8899;font-size:7px;font-weight:500;display:flex;align-items:center;justify-content:center;letter-spacing:.3px;flex:0 0 auto;}'
    /* 触控靶统一 44×44（HIG 最小可点尺寸） */
    + '.h5-icobtn{width:44px;height:44px;border-radius:11px;background:transparent;border:0;display:inline-flex;align-items:center;justify-content:center;color:var(--h5-accent);cursor:pointer;padding:0;-webkit-tap-highlight-color:transparent;}'
    + '.h5-icobtn:active{background:#eef1f7;}'
    /* ---------- 筛选区：默认收起，点顶栏胶囊才展开 ---------- */
    + '.h5-filters{position:fixed;top:var(--h5-appbar);left:0;right:0;z-index:59;background:rgba(244,246,250,.96);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-bottom:.5px solid #e9edf5;padding:0 14px;max-height:0;overflow:hidden;opacity:0;transition:max-height .22s ease,opacity .18s ease,padding .22s ease;}'
    + '.h5-filters.open{max-height:220px;opacity:1;padding:10px 14px 11px;}'
    + '.h5-scrim{position:fixed;left:0;right:0;top:var(--h5-appbar);bottom:0;z-index:58;background:rgba(16,20,28,.28);opacity:0;pointer-events:none;transition:opacity .2s;}'
    + '.h5-scrim.on{opacity:1;pointer-events:auto;}'
    /* 顶栏筛选胶囊 */
    + '.h5-chip{display:inline-flex;align-items:center;gap:5px;height:32px;padding:0 11px;border-radius:16px;border:0;background:#eef2f8;color:var(--h5-accent);font-family:inherit;font-size:13px;font-weight:500;cursor:pointer;-webkit-tap-highlight-color:transparent;max-width:190px;}'
    + '.h5-chip span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}'
    + '.h5-chip:active{background:#e2eaf6;}'
    + '.h5-chip svg{flex:0 0 auto;transition:transform .2s;}'
    + '.h5-chip[aria-expanded="true"] svg{transform:rotate(180deg);}'
    + '.h5-frow{display:flex;gap:8px;}'
    + '.h5-frow+.h5-frow{margin-top:8px;}'
    + '.h5-sel{flex:1;min-width:0;height:40px;border-radius:10px;background:var(--h5-card);box-shadow:0 1px 2px rgba(16,20,28,.05),0 0 0 .5px #eaeef5;display:flex;align-items:center;padding:0 11px;gap:6px;position:relative;}'
    + '.h5-sel .h5-sl{font-size:14px;font-weight:500;color:var(--h5-text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}'
    + '.h5-sel svg{margin-left:auto;flex:0 0 auto;}'
    + '.h5-sel select{position:absolute;inset:0;opacity:0;width:100%;height:100%;font-size:16px;appearance:none;-webkit-appearance:none;border:0;}'
    + '.h5-seg{display:flex;background:#e9edf5;border-radius:9px;padding:3px;gap:3px;}'
    + '.h5-seg button{flex:1;border:0;background:transparent;font-size:13px;color:var(--h5-muted);padding:7px 0;border-radius:7px;font-family:inherit;cursor:pointer;-webkit-tap-highlight-color:transparent;}'
    + '.h5-seg button.on{background:#fff;color:var(--h5-text);font-weight:500;box-shadow:0 1px 2px rgba(16,20,28,.07);}'
    /* ---------- 内容区：上下都要避让固定栏 + 安全区 ---------- */
    + '.h5-main{padding-top:calc(var(--h5-appbar) + var(--h5-filter) + 4px);padding-bottom:calc(var(--h5-tabbar) + var(--h5-safe-bot) + 20px);}'
    /* 筛选面板是 fixed 覆盖层，展开时给内容区补上等高的上边距，避免被压住 */
    + 'html.h5-filters-open body>.container,html.h5-filters-open body>main{padding-top:calc(var(--h5-appbar) + var(--h5-filter) + 4px);transition:padding-top .22s ease;}'
    /* ---------- 底部 Tab 栏：图标 24 / 标签 12 / 选中胶囊 ---------- */
    + '.h5-tabbar{position:fixed;bottom:0;left:0;right:0;z-index:60;display:flex;background:var(--h5-bar);backdrop-filter:saturate(180%) blur(14px);-webkit-backdrop-filter:saturate(180%) blur(14px);border-top:.5px solid #e9edf5;padding-bottom:var(--h5-safe-bot);}'
    + '.h5-tabbar a{flex:1;height:var(--h5-tabbar-h);display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;text-decoration:none;color:#8d98a6;font-size:12px;line-height:1;font-family:inherit;-webkit-tap-highlight-color:transparent;}'
    + '.h5-tabbar a .h5-ti{width:64px;height:32px;border-radius:16px;display:flex;align-items:center;justify-content:center;transition:background .16s;}'
    + '.h5-tabbar a.on{color:var(--h5-accent);font-weight:500;}'
    + '.h5-tabbar a.on .h5-ti{background:#dbe8fa;}'
    + '.h5-tabbar a:active .h5-ti{background:#e8eef7;}'
    + '.h5-tabbar a.wait{opacity:.45;pointer-events:none;}'
    + '.h5-tip{position:fixed;z-index:90;pointer-events:none;background:#1c2230;color:#fff;border-radius:12px;padding:10px 12px;font-size:13px;line-height:1.6;box-shadow:0 12px 30px rgba(16,20,28,.3);display:none;max-width:262px;}'
    + '.h5-fab{position:fixed;right:14px;bottom:calc(var(--h5-tabbar) + var(--h5-safe-bot) + 14px);z-index:58;width:44px;height:44px;border-radius:15px;border:0;background:rgba(255,255,255,.94);box-shadow:0 2px 6px rgba(16,20,28,.08),0 8px 22px rgba(16,20,28,.16);color:#5c6773;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .18s;cursor:pointer;}'
    + '.h5-fab.on{opacity:1;pointer-events:auto;}'
    + '.h5-fade{position:fixed;left:0;right:0;height:40px;z-index:57;pointer-events:none;background:linear-gradient(to top,rgba(244,246,250,.98),rgba(244,246,250,.5),transparent);bottom:calc(var(--h5-tabbar) + var(--h5-safe-bot));}'
    + '@media (min-width:820px){.h5-appbar,.h5-filters,.h5-tabbar,.h5-fab,.h5-fade{display:none !important;}}';

  var TAB_DEFS = [
    { key: 'draws',  label: '平局',   href: 'draws-big5.html',  icon: '<path d="M4 7h16M4 12h16M4 17h10"/>' },
    { key: 'goals',  label: '进球数', href: 'goals-big5.html',  icon: '<circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18"/>' },
    { key: 'more',   label: '更多',   href: 'more.html',        icon: '<circle cx="12" cy="5" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="12" cy="19" r="1.6"/>' }
  ];

  var state = { page: '', tab: '', filters: [], onChange: null, els: {} };

  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
  function root() { return window.SITE_ROOT || ''; }
  function ico(path, size) {
    return '<svg width="' + (size || 13) + '" height="' + (size || 13) + '" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + path + '</svg>';
  }
  var CARET = '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="#7c8899" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';

  function injectStyle() {
    if (document.getElementById('h5ShellStyle')) return;
    var st = document.createElement('style');
    st.id = 'h5ShellStyle';
    st.textContent = CSS;
    (document.head || document.documentElement).appendChild(st);
  }

  // 仅浅色：手机端把主题彻底钉死。
  // 注意 site.js 会在自身初始化时写回 data-theme（桌面三态主题），
  // 所以这里不仅要设 light，还要挂一个守卫，在它写回后立刻纠正。
  function forceLight() {
    try {
      var r = document.documentElement;
      r.setAttribute('data-theme', 'light');
      r.style.colorScheme = 'light';
      var m = document.querySelector('meta[name="theme-color"]');
      if (m) m.setAttribute('content', '#f4f6fa');
    } catch (e) {}
  }
  // 守卫：site.js 每次 paint() 都会改 data-theme / theme-color，这里紧盯并纠回
  function guardLight() {
    if (window.__h5LightGuarded) return;
    window.__h5LightGuarded = true;
    forceLight();
    try {
      if (!window.MutationObserver) return;
      new MutationObserver(function (muts) {
        for (var i = 0; i < muts.length; i++) {
          var t = muts[i].target;
          if (muts[i].attributeName === 'data-theme') {
            if (t.getAttribute('data-theme') !== 'light') forceLight();
          }
        }
      }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    } catch (e) {}
    // 兜底轮询：个别浏览器 MutationObserver 对 late 写入不敏感
    var n = 0;
    var iv = setInterval(function () {
      forceLight();
      if (++n > 40) clearInterval(iv);      // 约 10s 后停止，避免长期占用
    }, 250);
  }

  // 顶栏：外层负责状态栏安全区（padding-top），内层 .h5-navrow 是 44px 标准导航行。
  // 结构 [左槽] [居中标题] [右槽]，左右槽等宽占位才能让标题真正居中。
  function buildAppBar() {
    var el = document.createElement('div');
    el.className = 'h5-appbar';
    el.innerHTML =
      '<div class="h5-navrow">' +
        '<div class="h5-slot h5-slot-l" id="h5SlotL"><div class="h5-logo">LOGO</div></div>' +
        '<div class="h5-title" id="h5Title">' + esc(state.page) + '</div>' +
        '<div class="h5-slot h5-slot-r" id="h5Slot"></div>' +
      '</div>';
    return el;
  }

  // 顶栏右侧的「当前筛选」胶囊：默认状态下筛选面板收起，只显示这一颗胶囊，
  // 把首屏让给核心结论。点击后展开面板。
  function buildFilterChip() {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'h5-chip';
    b.id = 'h5Chip';
    b.setAttribute('aria-expanded', 'false');
    b.innerHTML = '<span id="h5ChipTxt"></span>' + CARET.replace('#7c8899', 'currentColor');
    b.addEventListener('click', function (e) {
      e.stopPropagation();
      toggleFilters();
    });
    return b;
  }

  function toggleFilters(force) {
    var box = document.querySelector('.h5-filters');
    var chip = document.getElementById('h5Chip');
    if (!box) return;
    var open = (typeof force === 'boolean') ? force : !box.classList.contains('open');
    box.classList.toggle('open', open);
    document.documentElement.classList.toggle('h5-filters-open', open);
    if (chip) chip.setAttribute('aria-expanded', open ? 'true' : 'false');
    var m = document.querySelector('.h5-scrim');
    if (m) m.classList.toggle('on', open);
    // 展开瞬间面板高度还在过渡中（读到的接近 0），所以先用 scrollHeight 量出真实高度，
    // 过渡结束后再用实际渲染高度校准一次。
    if (open) {
      var real = box.scrollHeight;
      document.documentElement.style.setProperty('--h5-filter', (real + 0) + 'px');
      setTimeout(syncFilterH, 260);
    } else {
      document.documentElement.style.setProperty('--h5-filter', '0px');
    }
  }

  function syncChipText() {
    var t = document.getElementById('h5ChipTxt');
    if (!t) return;
    var parts = [];
    state.filters.forEach(function (f) {
      if (f.type !== 'select') return;
      var sel = document.getElementById(f.id);
      if (!sel || sel.selectedIndex < 0) return;
      parts.push(sel.options[sel.selectedIndex].text.replace(/（.*?）/, '').trim());
    });
    t.textContent = parts.join(' · ') || '筛选';
  }

  function buildFilters() {
    if (!state.filters || !state.filters.length) return null;
    var box = document.createElement('div');
    box.className = 'h5-filters';
    var rows = [], curRow = null;
    state.filters.forEach(function (f) {
      if (f.type === 'select') {
        curRow = document.createElement('div');
        curRow.className = 'h5-frow';
        var wrap = document.createElement('div');
        wrap.className = 'h5-sel';
        var opts = '';
        if (f.groups) {
          f.groups.forEach(function (g) {
            opts += '<optgroup label="' + esc(g.label) + '">';
            g.options.forEach(function (o) {
              opts += '<option value="' + esc(o.v) + '"' + (String(o.v) === String(f.value) ? ' selected' : '') + '>' + esc(o.t) + '</option>';
            });
            opts += '</optgroup>';
          });
        } else {
          (f.options || []).forEach(function (o) {
            opts += '<option value="' + esc(o.v) + '"' + (String(o.v) === String(f.value) ? ' selected' : '') + '>' + esc(o.t) + '</option>';
          });
        }
        wrap.innerHTML = '<span class="h5-sl" id="h5lb-' + f.id + '"></span>' + CARET +
          '<select id="' + f.id + '" aria-label="' + esc(f.label) + '">' + opts + '</select>';
        curRow.appendChild(wrap);
        rows.push(curRow);
        curRow = null;
        state.els[f.id] = wrap;
      } else if (f.type === 'segment') {
        if (!curRow) { curRow = document.createElement('div'); curRow.className = 'h5-frow'; rows.push(curRow); }
        var seg = document.createElement('div');
        seg.className = 'h5-seg';
        seg.id = f.id;
        (f.options || []).forEach(function (o) {
          var b = document.createElement('button');
          b.type = 'button';
          b.setAttribute('data-v', o.v);
          b.textContent = o.t;
          if (String(o.v) === String(f.value)) b.className = 'on';
          b.addEventListener('click', function () {
            var btns = seg.querySelectorAll('button');
            for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('on', btns[i] === b);
            fire(f.id, o.v);
          });
          seg.appendChild(b);
        });
        curRow.appendChild(seg);
        state.els[f.id] = seg;
      }
    });
    rows.forEach(function (r) { box.appendChild(r); });
    return box;
  }

  // 底部 Tab：M3 结构 —— 图标 24px 包在 64×32 圆角胶囊里（选中时填充），标签在下方 12px。
  function buildTabBar() {
    var el = document.createElement('nav');
    el.className = 'h5-tabbar';
    var html = '';
    TAB_DEFS.forEach(function (t) {
      var on = t.key === state.tab ? ' on' : '';
      var wait = t.ready === false ? ' wait' : '';
      html += '<a class="' + (on + wait).trim() + '" href="' + root() + 'pages/' + t.href + '"' + (t.ready === false ? ' aria-disabled="true"' : '') + '>' +
        '<span class="h5-ti">' + ico(t.icon, 24) + '</span><span class="h5-tl">' + t.label + '</span></a>';
    });
    el.innerHTML = html;
    return el;
  }

  function buildTip() {
    var t = document.createElement('div');
    t.className = 'h5-tip';
    t.id = 'h5Tip';
    return t;
  }

  function buildFab() {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'h5-fab';
    b.setAttribute('aria-label', '回到顶部');
    b.innerHTML = ico('<path d="M12 19V5"/><path d="M6 11l6-6 6 6"/>', 17);
    b.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
    return b;
  }

  function fire(id, value) {
    syncLabel(id);
    syncChipText();
    if (typeof state.onChange === 'function') { try { state.onChange(id, value); } catch (e) {} }
  }

  function syncLabel(id) {
    var sel = document.getElementById(id);
    if (!sel) return;
    var lb = document.getElementById('h5lb-' + id);
    if (lb && sel.selectedIndex >= 0) lb.textContent = sel.options[sel.selectedIndex].text;
  }

  function syncFilterH() {
    var f = document.querySelector('.h5-filters');
    if (!f || !f.classList.contains('open')) {
      document.documentElement.style.setProperty('--h5-filter', '0px');
      return;
    }
    var h = Math.round(f.getBoundingClientRect().height);
    document.documentElement.style.setProperty('--h5-filter', h + 'px');
  }
  window.addEventListener('resize', syncFilterH);
  window.addEventListener('orientationchange', function () { setTimeout(syncFilterH, 120); });

  /* ---------- 轻点气泡 ---------- */
  var tipTimer = null;
  function tipAt(el, html) {
    var t = document.getElementById('h5Tip');
    if (!t) return;
    t.innerHTML = html;
    t.style.display = 'block';
    var r = el.getBoundingClientRect();
    var w = t.offsetWidth, h = t.offsetHeight;
    var left = r.left + r.width / 2 - w / 2;
    var top = r.top - h - 12;
    if (top < 8) top = r.bottom + 12;
    if (left + w > window.innerWidth - 8) left = window.innerWidth - w - 8;
    if (left < 8) left = 8;
    if (top + h > window.innerHeight - 8) top = window.innerHeight - h - 8;
    t.style.left = left + 'px';
    t.style.top = top + 'px';
    clearTimeout(tipTimer);
    tipTimer = setTimeout(hideTip, 2800);
  }
  function hideTip() { var t = document.getElementById('h5Tip'); if (t) t.style.display = 'none'; }

  /* ---------- 主动更新筛选值（页面逻辑调用） ---------- */
  function setFilter(id, value) {
    var el = document.getElementById(id);
    if (!el) return;
    if (el.tagName === 'SELECT') {
      el.value = value;
      syncLabel(id);
    } else {
      var btns = el.querySelectorAll('button');
      for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('on', String(btns[i].getAttribute('data-v')) === String(value));
    }
    syncChipText();
  }
  function setPage(name) {
    var t = document.querySelector('.h5-appbar .h5-title');
    if (t) t.textContent = name;
    state.page = name;
  }
  function slot() { return document.getElementById('h5Slot'); }

  // 首屏骨架收尾：移动端 site.js 不参与（它整套外壳都让位了），
  // 所以 QZL_BOOT_DONE 由本文件兜底定义，确保 #bootVeil 一定会淡出。
  function installBootDone() {
    if (window.QZL_BOOT_DONE) return;
    var t0 = (window.performance && performance.now) ? performance.now() : Date.now();
    window.QZL_BOOT_DONE = function () {
      var v = document.getElementById('bootVeil');
      if (!v) return;
      var now = (window.performance && performance.now) ? performance.now() : Date.now();
      if (now - t0 < 300) { if (v.parentNode) v.parentNode.removeChild(v); return; }
      v.classList.add('out');
      setTimeout(function () { if (v.parentNode) v.parentNode.removeChild(v); }, 320);
    };
    window.addEventListener('load', function () { setTimeout(window.QZL_BOOT_DONE, 150); });
    setTimeout(window.QZL_BOOT_DONE, 3000);
  }

  function mount(opts) {
    opts = opts || {};
    state.page = opts.page || '';
    state.tab = opts.tab || '';
    state.filters = opts.filters || [];
    state.onChange = opts.onChange || null;
    state.els = {};
    if (window.__h5ShellMounted) {
      // 已挂载：仅更新标题与筛选值，避免重复插入
      if (opts.page) setPage(opts.page);
      return;
    }
    window.__h5ShellMounted = true;

    injectStyle();
    forceLight();
    guardLight();
    installBootDone();
    document.body.classList.add('h5-mode');

    var bar = buildAppBar();
    var filters = buildFilters();
    var tabbar = buildTabBar();
    var tip = buildTip();
    var fab = buildFab();
    var fade = document.createElement('div');
    fade.className = 'h5-fade';

    var scrim = document.createElement('div');
    scrim.className = 'h5-scrim';

    document.body.appendChild(bar);
    if (filters) document.body.appendChild(filters);
    document.body.appendChild(scrim);
    document.body.appendChild(fade);
    document.body.appendChild(tabbar);
    document.body.appendChild(fab);
    document.body.appendChild(tip);

    // 顶栏右侧的「当前筛选」胶囊（必须在 bar 入文档之后再插入，
    // 否则 getElementById('h5Slot') 拿不到还未上树的节点）
    if (filters) {
      var slotR = document.getElementById('h5Slot');
      if (slotR) slotR.appendChild(buildFilterChip());
    }

    // 下拉 change 事件
    state.filters.forEach(function (f) {
      if (f.type !== 'select') return;
      var sel = document.getElementById(f.id);
      if (!sel) return;
      syncLabel(f.id);
      sel.addEventListener('change', function () { fire(f.id, sel.value); });
    });
    syncChipText();
    syncFilterH();

    // 点遮罩 / 点空白收起筛选面板
    scrim.addEventListener('click', function () { toggleFilters(false); });
    document.addEventListener('click', function (e) {
      var box = document.querySelector('.h5-filters');
      if (!box || !box.classList.contains('open')) return;
      if (box.contains(e.target)) return;
      var chip = document.getElementById('h5Chip');
      if (chip && chip.contains(e.target)) return;
      toggleFilters(false);
    }, false);
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') toggleFilters(false);
    });

    // FAB 显隐
    var onScroll = function () { fab.classList.toggle('on', window.scrollY > 220); };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();

    // 点空白收起气泡：带 data-tap 的元素才保留
    document.addEventListener('click', function (e) {
      var el = e.target;
      while (el && el !== document) {
        if (el.getAttribute && el.getAttribute('data-tap')) return;
        el = el.parentNode;
      }
      hideTip();
    }, false);

    if (window.__siteThemeBound !== undefined) window.__siteThemeBound = forceLight;
    window.QZL_BOOT_DONE && window.QZL_BOOT_DONE();
  }

  window.QZL_SHELL = {
    mount: mount, setPage: setPage, setFilter: setFilter, slot: slot,
    tip: tipAt, hideTip: hideTip, forceLight: forceLight, TAB_DEFS: TAB_DEFS,
    syncChip: syncChipText, toggleFilters: toggleFilters
  };
})();
