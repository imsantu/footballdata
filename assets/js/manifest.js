/* ══════════════════════════════════════════════════════════════════════════
   站点清单 · 页面身份的唯一声明处（P2-②）
   ──────────────────────────────────────────────────────────────────────────
   以前「加一个页面」要改 3~4 处：site.js 顶部的 SITE_NAV（页头下拉 + 首页卡片）、
   新页面 HTML 里内联的 window.DRAWS_CFG / window.GOALS_CFG（数据目录、横向对照
   的文案与徽标、升降级语义）、以及页面自己的脚本引用。同一件事写两遍，就会
   出现「改了导航忘了改 CFG」这类不一致。

   现在全站只有一张表：下面的 TOPICS + PAGES。

   ★ 加一个新页面（例：五大联赛 · 伤停）只需三步：
       1) 在 PAGES 里加一条记录（id 用页面名，如 'injuries-big5'）
       2) 把该 id 加进 TOPICS 对应主题的 pages 数组
       3) 页面 HTML 放进 pages/、数据与脚本放进 assets/js/
      —— 页头下拉、首页卡片、页面身份（CFG）全部自动同步，不用再改 site.js。

   字段说明（PAGES 的每条记录）：
     topic     所属统计主题（TOPICS 里的 id）—— 决定页头「统计主题」下拉与首页卡片分组
     js        驱动本页的实现脚本：'draws' → 挂 window.DRAWS_CFG；'goals' → window.GOALS_CFG
     group     **数据目录名**，即 assets/js/data/<group>/。注意 goals-big5 用的是 'goals'，
               与页面 id 不同名，所以必须显式写、不能用 id 顶替
     label     页面**全名**（= CFG.label）：面包屑、走势图标题、横向对照 Tab 都用它
     navLabel  页头「联赛层级」下拉与首页卡片上的**短名**；省略时等于 label
               （例：draws-champ 全名「五大次级联赛」，下拉里只写「次级联赛」）
     file      pages/ 下的文件名。导航靠它定位「当前页」，必须与实际文件名完全一致
     ready     false = 灰态「敬请期待」，导航与首页卡片都不可点
     promotion 升降级语义：true = 次级联赛（upTop / releg / demoted / fromTop，且队名着色）；
               false = 五大联赛（promo / releg）。**必须是布尔值**
     badge     横向对照 Tab 里的联赛徽标（内联 SVG 字符串），draws / goals 两侧共用
     desc      首页卡片的描述文案

   ⚠️ 本文件必须**同步**加载（不能加 defer），且排在 site.js 与页面逻辑脚本之前：
        <script src="assets/js/manifest.js"></script>
        <script src="assets/js/site.js"></script>
      site.js 用它生成页头下拉与首页卡片；draws.js / goals.js 用它拿到页面身份。
      少写这一行会立刻抛错，而不是静默渲染成另一个联赛的样式。
   ══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  // 横向对照 Tab 的联赛徽标（原样搬运自各页面内联 CFG 与 goals.js，逐字节保持不变）
  var BADGE_UEFA = '<svg class="uefa-logo" viewBox="0 0 30 18" aria-label="UEFA"><rect x="0" y="0" width="30" height="18" rx="3" fill="#0a1f44"/><text x="15" y="12.5" font-family="Arial,Helvetica,sans-serif" font-size="9" font-weight="800" fill="#fff" text-anchor="middle" letter-spacing="0.5">UEFA</text></svg>';
  var BADGE_2ND = '<svg class="uefa-logo" viewBox="0 0 30 18" aria-label="次级联赛"><rect x="0" y="0" width="30" height="18" rx="3" fill="#0a1f44"/><text x="15" y="12.5" font-family="Arial,Helvetica,sans-serif" font-size="9" font-weight="800" fill="#fff" text-anchor="middle" letter-spacing="0.5">2ND</text></svg>';

  // ── 统计主题：页头「统计主题」下拉 + 首页卡片分组 ──
  var TOPICS = [
    { id: 'draws', label: '平局统计',   pages: ['draws-big5', 'draws-champ'] },
    { id: 'goals', label: '进球数统计', pages: ['goals-big5', 'goals-champ'] }
  ];

  // ── 页面身份：唯一真相源 ──
  var PAGES = {
    'draws-big5': {
      topic: 'draws', js: 'draws', group: 'draws-big5',
      label: '五大联赛', file: 'draws-big5.html', ready: true,
      promotion: false, badge: BADGE_UEFA,
      desc: '英超 / 西甲 / 德甲 / 意甲 / 法甲 · 平局率、比分分布、各轮走势与各队平局'
    },
    'draws-champ': {
      topic: 'draws', js: 'draws', group: 'draws-champ',
      label: '五大次级联赛', navLabel: '次级联赛', file: 'draws-champ.html', ready: true,
      promotion: true, badge: BADGE_2ND,
      desc: '英冠 / 西乙 / 德乙 / 法乙 / 意乙 · 平局率、比分分布、各轮走势与各队平局'
    },
    'goals-big5': {
      topic: 'goals', js: 'goals', group: 'goals',
      label: '五大联赛', file: 'goals-big5.html', ready: true,
      promotion: false, badge: BADGE_UEFA,
      desc: '英超 / 西甲 / 德甲 / 意甲 / 法甲 · 单场总进球数分布、球队进球榜、赛季走势'
    },
    'goals-champ': {
      topic: 'goals', js: 'goals', group: 'goals-champ',
      label: '五大次级联赛', navLabel: '次级联赛', file: 'goals-champ.html', ready: true,
      promotion: true, badge: BADGE_2ND,
      desc: '英冠 / 西乙 / 德乙 / 法乙 / 意乙 · 单场总进球数分布、球队进球榜、赛季走势'
    }
  };

  // 无法确定当前页时（首页 / 占位页）默认落在「平局统计」
  var DEFAULT_TOPIC_ID = 'draws';

  function has(o, k) { return Object.prototype.hasOwnProperty.call(o, k); }

  /* ---- 派生站点导航：site.js 的页头下拉与首页卡片共用（形状与原 SITE_NAV 完全一致） ---- */
  function nav() {
    return TOPICS.map(function (tp) {
      return {
        id: tp.id,
        label: tp.label,
        items: (tp.pages || []).map(function (pid) {
          if (!has(PAGES, pid)) {
            throw new Error('manifest.js：TOPICS 里引用了未声明的页面 id「' + pid + '」');
          }
          var p = PAGES[pid];
          return {
            id: pid,
            label: p.navLabel || p.label,
            file: p.file,
            ready: p.ready !== false,
            desc: p.desc
          };
        })
      };
    });
  }

  /* ---- 当前页面 id：靠文件名判断（与 site.js 的定位方式一致，pages/ 下的相对路径无关） ---- */
  function pageId() {
    var cur = (location.pathname.split('/').pop() || '').toLowerCase();
    for (var id in PAGES) {
      if (has(PAGES, id) && String(PAGES[id].file).toLowerCase() === cur) return id;
    }
    return null;
  }

  /* ---- 按 id 取页面身份（调试 / 未来复用） ---- */
  function cfg(id) {
    if (!has(PAGES, id)) {
      throw new Error('manifest.js：未知页面 id「' + id + '」（可用：' + Object.keys(PAGES).join('、') + '）');
    }
    return PAGES[id];
  }

  window.FD_MANIFEST = {
    version: 1,
    defaultTopic: DEFAULT_TOPIC_ID,
    topics: TOPICS,
    pages: PAGES
  };
  window.FD_NAV = nav;
  window.FD_CFG = cfg;
  window.FD_PAGE_ID = pageId;

  /* ---- 按当前页面自动挂上页面身份：页面 HTML 里不再需要内联 DRAWS_CFG / GOALS_CFG ---- */
  var pid = pageId();
  if (pid) {
    var p = PAGES[pid];
    if (p.js === 'draws') window.DRAWS_CFG = p;
    else if (p.js === 'goals') window.GOALS_CFG = p;
  }
})();
