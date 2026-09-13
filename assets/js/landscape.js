/* ==========================================================================
   横屏全屏模块（公共）
   从 goals-app.js 抽出，供进球数页与两个平局页共用。

   设计要点：
   · **点按钮触发**（不做旋转自动检测）——按钮插在每个宽表面板前面
   · 打开方式：cloneNode 克隆该面板 → 塞进 .land-stage（rotate(90deg) 旋转 90°、
     宽高互换 100vh/100vw）→ 尝试 requestFullscreen()
   · 三种退出：点按钮 / 按 Esc / 点遮罩
   · 手机上「旋转手机」会让浏览器自己重排，与我们的 CSS 旋转叠加会错乱，
     所以只用按钮触发；提示条里也写清楚「点 ✕ 退出」。

   用法：
     window.QZL_LANDSCAPE.init({ panels: ['overview','teams','trend','seq23'] });
   或自动模式（不传 panels，自动扫描挂载点里非空的面板）。
   ========================================================================== */
(function () {
  'use strict';

  var ICON = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
    'stroke-linecap="round" stroke-linejoin="round" style="width:15px;height:15px">' +
    '<path d="M21 9V5a2 2 0 0 0-2-2h-4M3 15v4a2 2 0 0 0 2 2h4M21 15v4a2 2 0 0 1-2 2h-4M3 9V5a2 2 0 0 1 2-2h4"/></svg>';

  // 默认候选面板（按页面存在与否自动筛选）
  var DEFAULT_PANELS = ['overview', 'teams', 'trend', 'seq23', 'top', 'cmp', 'form5'];

  // 横屏入口做成「次级按钮」而非实心主按钮：App 里这类辅助操作不该抢主视觉。
  // 退出按钮同样去饱和度，用中性深色而不是橙红渐变。
  var CSS = ''
    + '.land-overlay{position:fixed;inset:0;z-index:9999;background:var(--bg,#f4f6fa);overflow:auto;-webkit-overflow-scrolling:touch;}'
    + '.land-stage{position:absolute;top:50%;left:50%;width:100vh;height:100vw;transform:translate(-50%,-50%) rotate(90deg);transform-origin:center;overflow:auto;}'
    + '.land-stage>.land-clone{width:100%;}'
    + '.land-exit{position:fixed;top:calc(env(safe-area-inset-top,0px) + 14px);right:14px;z-index:10001;display:inline-flex;align-items:center;gap:6px;min-height:44px;padding:0 18px;border:0;border-radius:22px;background:rgba(255,255,255,.92);color:#0e131a;font-size:15px;font-weight:500;cursor:pointer;box-shadow:0 2px 10px rgba(16,20,28,.14);font-family:inherit;backdrop-filter:saturate(180%) blur(12px);-webkit-backdrop-filter:saturate(180%) blur(12px);appearance:none;-webkit-appearance:none;}'
    + '.land-exit:active{transform:scale(.96);background:rgba(255,255,255,1);}'
    + '.land-hint{position:fixed;left:0;right:0;bottom:18px;z-index:10001;text-align:center;color:var(--text-muted,#7c8899);font-size:12px;pointer-events:none;}'
    + '.land-btn{appearance:none;-webkit-appearance:none;display:inline-flex;align-items:center;justify-content:center;gap:4px;height:28px;padding:0 10px;border:0;border-radius:14px;background:#eef2f8;color:#5a6675;font-size:12px;font-weight:500;cursor:pointer;font-family:inherit;line-height:1;white-space:nowrap;flex:0 0 auto;-webkit-tap-highlight-color:transparent;}'
    + '.land-btn:active{background:#e2e8f2;}'
    + '.land-btn.on{background:#e8eef7;color:#2f7bdc;}'
    + '.land-btn svg{width:13px;height:13px;opacity:.8;}'
    /* 内联在标题行右侧的排版 */
    + '.section-title.h5-has-land{display:flex;align-items:flex-start;gap:8px;}'
    + '.section-title.h5-has-land>.note-flag{flex:1 1 100%;}'
    + '.land-btn-inline{margin-left:auto;order:-1;align-self:flex-start;}'
    + '.section-title.h5-has-land>.land-btn-inline{margin-left:auto;}';

  var overlay = null, stage = null, openPanelId = null, panelList = DEFAULT_PANELS;

  function injectStyle() {
    if (document.getElementById('landscapeStyle')) return;
    var st = document.createElement('style');
    st.id = 'landscapeStyle';
    st.textContent = CSS;
    (document.head || document.documentElement).appendChild(st);
  }

  function ensureOverlay() {
    if (overlay) return;
    overlay = document.createElement('div');
    overlay.className = 'land-overlay';
    overlay.id = 'landOverlay';
    overlay.style.display = 'none';

    var scrim = document.createElement('div');
    scrim.className = 'land-scrim';
    scrim.style.position = 'absolute';
    scrim.style.inset = '0';

    stage = document.createElement('div');
    stage.className = 'land-stage';

    var exitBtn = document.createElement('button');
    exitBtn.type = 'button';
    exitBtn.className = 'land-exit';
    exitBtn.textContent = '✕ 退出横屏';

    var hintEl = document.createElement('div');
    hintEl.className = 'land-hint';
    hintEl.textContent = '横屏阅读更佳 · 可拖动查看 · 点 ✕ 或按 Esc 退出';

    overlay.appendChild(scrim);
    overlay.appendChild(stage);
    overlay.appendChild(exitBtn);
    overlay.appendChild(hintEl);
    document.body.appendChild(overlay);

    exitBtn.addEventListener('click', close);
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay || e.target === scrim) close();
    });
  }

  function setBtn(pid, on) {
    var b = document.getElementById('landBtn-' + pid);
    if (!b) return;
    b.classList.toggle('on', !!on);
    b.innerHTML = on ? '✕ 退出横屏' : (ICON + ' 横屏全屏');
  }

  function open(panel) {
    ensureOverlay();
    if (openPanelId) close();
    openPanelId = panel.id;
    var clone = panel.cloneNode(true);
    clone.className = (clone.className || '') + ' land-clone';
    clone.removeAttribute('id');
    // 克隆体里的 id 会与原件重复，去掉以免 getElementById 抢到副本
    var ids = clone.querySelectorAll('[id]');
    for (var i = 0; i < ids.length; i++) ids[i].removeAttribute('id');
    stage.innerHTML = '';
    stage.appendChild(clone);
    overlay.style.display = 'block';
    document.body.classList.add('land-open');
    setBtn(openPanelId, true);
    if (overlay.requestFullscreen) { try { overlay.requestFullscreen(); } catch (e) {} }
  }

  function close() {
    if (!openPanelId) return;
    var pid = openPanelId;
    openPanelId = null;
    if (stage) stage.innerHTML = '';
    if (overlay) overlay.style.display = 'none';
    document.body.classList.remove('land-open');
    if (document.fullscreenElement && document.exitFullscreen) { try { document.exitFullscreen(); } catch (e) {} }
    setBtn(pid, false);
  }

  function makeBtn(pid) {
    var id = 'landBtn-' + pid, b = document.getElementById(id);
    if (b) return b;
    b = document.createElement('button');
    b.type = 'button';
    b.id = id;
    b.className = 'land-btn';
    b.innerHTML = ICON + ' 横屏全屏';
    b.addEventListener('click', function () {
      var p = document.getElementById(pid);
      if (!p) return;
      if (openPanelId === pid) close(); else open(p);
    });
    return b;
  }

  function isHidden(el) {
    if (el.offsetWidth || el.offsetHeight || el.getClientRects().length) return false;
    // 自身有尺寸即视为可见；否则再往上看有没有祖先被 display:none 掉
    return true;
  }

  function activePanels() {
    var out = [];
    for (var i = 0; i < panelList.length; i++) {
      var el = document.getElementById(panelList[i]);
      // 必须有内容，且当前确实可见 —— 否则会给隐藏视图（如未激活的 viewOverview）
      // 也插一个按钮，出现「屏幕外还有按钮」的情况。
      if (el && el.innerHTML.trim() !== '' && !isHidden(el)) out.push(panelList[i]);
    }
    return out;
  }

  // 把按钮挂到面板「前面最近的 section-title」里（标题行右侧），
  // 而不是单独占一行插在面板与标题之间 —— 后者会把标题挤下去、观感很散。
  // 往回最多找 2 个兄弟节点（面板与标题之间可能隔着 chart-card 等），
  // 都找不到就退回插在面板前面。
  function findTitleHost(p) {
    var s = p.previousElementSibling, hops = 0;
    while (s && hops < 3) {
      if (s.classList && s.classList.contains('section-title')) return s;
      if (s.id && /^(findings|topWrap|cmpWrap|big5Wrap|overview|teams|trend|seq23)/.test(s.id)) return null;
      s = s.previousElementSibling; hops++;
    }
    return null;
  }

  function mountBtn(pid, p) {
    var btn = makeBtn(pid);
    var host = findTitleHost(p);
    if (host) {
      host.classList.add('h5-has-land');
      btn.classList.add('land-btn-inline');
      host.appendChild(btn);
      return;
    }
    p.parentNode.insertBefore(btn, p);
  }

  function attach() {
    var active = activePanels();
    // 先清掉页面上所有残留按钮，再从零按 active 集合重建。
    // 之所以不用 id 去重：面板内容被 innerHTML 重写时按钮可能一起被移除，
    // 而某些渲染路径会保留按钮却丢掉 id，导致重复插入（曾出现两个「横屏全屏」）。
    var all = document.querySelectorAll('.land-btn');
    for (var k = 0; k < all.length; k++) all[k].parentNode.removeChild(all[k]);
    var titles = document.querySelectorAll('.section-title.h5-has-land');
    for (var t = 0; t < titles.length; t++) titles[t].classList.remove('h5-has-land');
    for (var j = 0; j < active.length; j++) {
      var p = document.getElementById(active[j]);
      if (!p || !p.parentNode) continue;
      mountBtn(active[j], p);
    }
  }

  function init(opts) {
    opts = opts || {};
    if (opts.panels && opts.panels.length) panelList = opts.panels;
    injectStyle();
    if (!window.__landscapeBound) {
      window.__landscapeBound = true;
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && openPanelId) close();
      });
      document.addEventListener('fullscreenchange', function () {
        if (!document.fullscreenElement && openPanelId) close();
      });
    }
    attach();
    // 页面每次重渲染后，面板集合可能变化 → 用 MutationObserver 轻量跟随
    if (window.MutationObserver && !window.__landscapeObserved && opts.watch !== false) {
      window.__landscapeObserved = true;
      var pend = false;
      try {
        new MutationObserver(function () {
          if (pend) return;
          pend = true;
          setTimeout(function () { pend = false; attach(); }, 120);
        }).observe(document.body, { childList: true, subtree: true });
      } catch (e) {}
    }
  }

  window.QZL_LANDSCAPE = { init: init, attach: attach, open: open, close: close, isOpen: function () { return !!openPanelId; } };
})();
