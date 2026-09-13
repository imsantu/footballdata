/* ==========================================================================
   平局页 · H5 移动端适配层

   设计原则：**不复制数据逻辑**。
   draws-big5.js / draws-champ.js 里的 render() 已经把全部模块渲染进 DOM，
   本文件只做四件事：
     1) 挂载 h5-shell（AppBar / 底部 3 tab / 吸顶筛选）
     2) 把「联赛胶囊 + 赛季胶囊」两行替换成两个原生下拉（含五大/次级 optgroup 分组），
        并直接驱动页面原有状态（curLeague / curView / currentSeason / setWin）
     3) 把 hover 气泡改成轻点触发（data-tap 已内置在渲染层，这里补 tap 事件）
     4) 用 QZL_LANDSCAPE 给宽表加「横屏全屏」按钮

   页面脚本不变：仍然由 draws-*.js 负责 render()，本文件只在其后接管交互。
   ========================================================================== */
(function () {
  'use strict';

  // 只有手机端才启用；PC 端本文件直接返回，零副作用
  var IS_MB = (function () {
    try {
      if (window.matchMedia) return !window.matchMedia('(min-width:820px)').matches;
    } catch (e) {}
    return (window.innerWidth || 1024) < 820;
  })();
  if (!IS_MB) return;
  if (!window.QZL_SHELL) return;

  var CFG = window.DRAWS_MB_CFG || {};        // 页面注入：{ title, groups, crossLabel }
  var READY = false;

  // 数据层：两个平局页的数据文件是 `const DATA = {...}`（顶层 const，
  // 是全局词法绑定但不是 window 属性），所以只能用 typeof 探测后按名取用。
  function D() {
    try { return (typeof DATA !== 'undefined') ? DATA : null; } catch (e) { return null; }
  }

  function lgList() { var d = D(); return (d && d.leagues) || []; }

  // 联赛下拉：按五大 / 次级分组。本页数据里的联赛即为该页的全部联赛，
  // 分组标签由页面配置指定（平局·五大页只有「五大联赛」；若未来并入次级再扩）。
  function buildLeagueFilter() {
    var cfg = CFG.leagueGroups;
    if (cfg && cfg.length) {
      return {
        type: 'select', id: 'h5Lg', label: '联赛', value: startLeague(),
        groups: cfg.map(function (g) {
          return {
            label: g.label,
            options: g.options.map(function (o) { return { v: o.code, t: o.cn }; })
          };
        })
      };
    }
    return {
      type: 'select', id: 'h5Lg', label: '联赛', value: startLeague(),
      options: lgList().map(function (l) { return { v: l.code, t: l.cn }; })
    };
  }

  function startLeague() {
    var d = D();
    if (!d || !d.leagues || !d.leagues.length) return '';
    return (window.__h5CurLeague || d.leagues[0].code);
  }

  // 赛季下拉：总览 + 各赛季（与桌面 tab 同集合）
  function buildSeasonFilter() {
    var d = D();
    var opts = [{ v: '__overview__', t: '赛季总览' }];
    if (d && d.seasonOrder) {
      var win = window.__h5Win || 5;
      var seq = d.seasonOrder.filter(function (k) { return k === '2026-27' || indexInWin(k, win) >= 0; });
      seq.forEach(function (k) {
        var lg = (d.leagues || []).find(function (l) { return l.code === startLeague(); });
        var s = lg && lg.seasons ? lg.seasons[k] : null;
        opts.push({ v: k, t: shortSeason(k) + (s ? '（' + s.totalDraws + '场）' : '') });
      });
    }
    return { type: 'select', id: 'h5Sn', label: '赛季', value: window.__h5CurView || '__overview__', options: opts };
  }

  function indexInWin(k, win) {
    var d = D();
    if (!d || !d.seasonOrder) return -1;
    return d.seasonOrder.filter(function (x) { return x !== '2026-27'; }).slice(0, win).indexOf(k);
  }

  function shortSeason(s) {
    var m = /^(\d{4})-(\d{2})$/.exec(s || '');
    return m ? m[1] + '-' + (m[1].slice(0, 2) + m[2]) : s;
  }

  function tabKey() {
    var f = (location.pathname.split('/').pop() || '');
    return /goals/.test(f) ? 'goals' : 'draws';
  }

  function mountShell() {
    if (READY) return;
    READY = true;
    document.documentElement.setAttribute('data-h5', 'on');
    window.QZL_SHELL.mount({
      page: CFG.title || '平局统计',
      tab: tabKey(),
      filters: [
        buildLeagueFilter(),
        buildSeasonFilter(),
        {
          type: 'segment', id: 'h5Win', label: '赛季范围', value: window.__h5Win || 5,
          options: [{ v: 5, t: '近五季' }, { v: 3, t: '近三季' }]
        }
      ],
      onChange: function (id, v) {
        if (id === 'h5Lg') {
          window.__h5CurLeague = v;
          if (typeof setLeague === 'function') setLeague(v);
        } else if (id === 'h5Sn') {
          window.__h5CurView = v;
          if (typeof setView === 'function') setView(v);
        } else if (id === 'h5Win') {
          window.__h5Win = +v;
          if (typeof setWin === 'function') setWin(+v);
          // 赛季下拉的选项集随窗口变化，重建一次
          rebuildSeasonFilter();
        }
      }
    });
  }

  function rebuildSeasonFilter() {
    var sel = document.getElementById('h5Sn');
    if (!sel) return;
    var f = buildSeasonFilter();
    var keep = sel.value;
    sel.innerHTML = '';
    (f.options || []).forEach(function (o) {
      var op = document.createElement('option');
      op.value = o.v;
      op.textContent = o.t;
      sel.appendChild(op);
    });
    // 窗口收窄后原选中的赛季可能已不在列表里 → 落到总览
    if (!Array.prototype.some.call(sel.options, function (o) { return o.value === keep; })) {
      sel.value = '__overview__';
      window.__h5CurView = '__overview__';
      if (typeof setView === 'function') setView('__overview__');
    } else {
      sel.value = keep;
    }
    var lb = document.getElementById('h5lb-h5Sn');
    if (lb && sel.selectedIndex >= 0) lb.textContent = sel.options[sel.selectedIndex].text;
  }

  /* ---------- hover → 轻点 ---------- */
  function bindTapTips() {
    document.addEventListener('click', function (e) {
      var el = e.target;
      while (el && el !== document) {
        if (el.getAttribute && el.getAttribute('data-tap')) {
          var html = el.getAttribute('data-tap');
          if (html) window.QZL_SHELL.tip(el, html);
          return;
        }
        // 兼容渲染层直接用 title 的单元格
        if (el.getAttribute && el.getAttribute('data-tip')) {
          window.QZL_SHELL.tip(el, el.getAttribute('data-tip'));
          return;
        }
        el = el.parentNode;
      }
    }, false);
  }

  // 把渲染层写进 title 的提示搬到 data-tip，避免手机上点一下弹系统提示
  function harvestTitles() {
    var cells = document.querySelectorAll('#overview [title], #topTable [title], #teamTable [title], #seq23 [title], #trend [title]');
    for (var i = 0; i < cells.length; i++) {
      var t = cells[i];
      var v = t.getAttribute('title');
      if (v) { t.setAttribute('data-tip', v); t.removeAttribute('title'); }
    }
  }

  /* ---------- 宽表 → 加横屏入口 ---------- */
  function attachLandscape() {
    if (!window.QZL_LANDSCAPE) return;
    window.QZL_LANDSCAPE.init({
      panels: ['overview', 'trend', 'teamWrap', 'topWrap', 'cmpWrap', 'big5Wrap', 'form5Strips', 'findings', 'statGrid']
    });
  }

  /* ---------- 竖屏宽表裁剪标记 ---------- */
  function markClip() {
    var wraps = document.querySelectorAll('.tw-wrap');
    for (var i = 0; i < wraps.length; i++) {
      var w = wraps[i];
      // 宽表内容明显超过容器宽度时才加渐隐
      var inner = w.querySelector('.tw');
      if (inner && inner.scrollWidth > inner.clientWidth + 4) w.classList.add('h5-clip');
      else w.classList.remove('h5-clip');
    }
  }

  /* ---------- 长说明折叠：把占据大量竖屏空间的说明收进「口径」入口 ---------- */
  function foldNotes() {
    // 1) 段标题里的 .note-flag：抽成一个「口径」小按钮，点开才显示
    var titles = document.querySelectorAll('.section-title');
    for (var i = 0; i < titles.length; i++) {
      var t = titles[i];
      var flag = t.querySelector('.note-flag');
      if (!flag || t.querySelector('.h5-note-tog')) continue;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'h5-note-tog';
      btn.setAttribute('aria-expanded', 'false');
      btn.innerHTML = '口径 <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>';
      (function (host, b) {
        b.addEventListener('click', function (e) {
          e.stopPropagation();
          var open = host.classList.toggle('h5-note-open');
          b.setAttribute('aria-expanded', open ? 'true' : 'false');
          b.firstChild.nodeValue = open ? '收起 ' : '口径 ';
        });
      })(t, btn);
      // 插到标题文本之后（note-flag 之前）
      flag.parentNode.insertBefore(btn, flag);
    }

    // 2) 正文里的 .note / .ov-note：默认收 3 行，点一下展开
    var notes = document.querySelectorAll('.note, .ov-note');
    for (var j = 0; j < notes.length; j++) {
      var n = notes[j];
      if (n.getAttribute('data-h5-fold')) continue;
      n.setAttribute('data-h5-fold', '1');
      if (n.scrollHeight <= 72) continue;      // 本来就很短，不需要折叠
      n.setAttribute('role', 'button');
      n.addEventListener('click', function () {
        this.classList.toggle('h5-note-open');
      });
    }
  }

  function afterRender() {
    harvestTitles();
    markClip();
    attachLandscape();
    foldNotes();
    syncFilterLabels();
  }

  function syncFilterLabels() {
    if (!window.QZL_SHELL) return;
    if (typeof curLeague !== 'undefined') window.__h5CurLeague = curLeague;
    if (typeof curView !== 'undefined') window.__h5CurView = curView;
    if (typeof SEASON_WIN !== 'undefined') window.__h5Win = SEASON_WIN;
    window.QZL_SHELL.setFilter('h5Lg', window.__h5CurLeague);
    window.QZL_SHELL.setFilter('h5Sn', window.__h5CurView);
    window.QZL_SHELL.setFilter('h5Win', window.__h5Win);
  }

  /* ---------- 入口 ---------- */
  function boot() {
    mountShell();
    bindTapTips();
    afterRender();
    // 页面渲染是同步调用 render()，包装一次以便每次渲染后同步交互层
    if (typeof window.render === 'function' && !window.__h5Wrapped) {
      window.__h5Wrapped = true;
      var _r = window.render;
      window.render = function () {
        _r.apply(this, arguments);
        afterRender();
      };
    }
    // 渲染后异步内容（图表 SVG / 表格）再补一次
    [0, 120, 400, 1000].forEach(function (t) { setTimeout(afterRender, t); });
    window.addEventListener('resize', function () { setTimeout(afterRender, 150); });
  }

  if (document.readyState === 'complete' || document.readyState === 'interactive') setTimeout(boot, 0);
  else document.addEventListener('DOMContentLoaded', boot);
  window.addEventListener('load', function () { setTimeout(boot, 80); });
})();
