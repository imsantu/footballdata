/* ==========================================================================
   sw.js — 足球数据中心 Service Worker（站点根目录，与 index.html 同级）

   作用：让「换网络 / 二次打开」也能秒开，并在离线时仍可浏览已看过的页面。

   缓存策略：
     1) 数据文件（按联赛+赛季拆出的 chunk / meta.js）：stale-while-revalidate
        —— 先秒回本地缓存（换网/二次打开立即出数），后台静默拉取最新写入缓存，
           下次访问即是最新。数据每天由自动化推送一次，单日内最多“晚到一次”，
           页脚已显示数据日期，可放心。
     2) 其它同源静态资源（HTML / CSS / 逻辑 JS / 字体 / 图片）：cache-first
        —— 外壳近乎秒开；改动后请把下方 CACHE 版本号 +1 强制刷新。
     3) 页面导航（HTML）：cache-first，离线时回退到已缓存的站点首页。

   ⚠️ 改了本文件之后，务必把 CACHE 版本号 +1，否则浏览器不会拉取新版 SW 逻辑。
   ========================================================================== */
'use strict';

// 站点根（处理 GitHub Pages 子路径 /footballdata/）：
//   sw.js 自身位于 /footballdata/sw.js，去掉文件名即得根。
var ROOT = (self.location.pathname || '/').replace(/\/sw\.js$/, '').replace(/\/+$/, '');

// 外壳缓存版本：任何外壳文件（site.js / css / 页面 HTML / 逻辑 JS）改动后 +1
// v5：数据 chunk 进一步拆为 assets/js/data/<group>/<league>/<season>.js，弱网下单次只取一个联赛；
//     Cache Storage 持久保留已成功加载的 chunk，切换时优先复用本地缓存；同时弱网失败不再强行渲染。
// v4：次级联赛 logo 改独立文件名（en2/es2/...，与五大联赛的 en/es/... 区分）+ 推上线清除单体大文件，
//     旧 v3 缓存里 PNG 文件名错了 + 站点可能仍带已删除的单体，+1 强制浏览器重新拉取。
// v3：DATA_RE 纳入按季拆出的 chunk 目录 assets/js/data/（shell.js / <season>.js / cross.js），
//     旧 v2 缓存把这些 chunk 误判为 cache-first，导致每日数据更新永远进不了浏览器、"切联赛/赛季数据不变"。
//     +1 强制浏览器重新拉取新版 SW 逻辑。
// v2：goals-pc.js / goals-mb.js 去掉 升 icon 的 !isNewSeason 限制（2026-27 升班马也标升），
//     旧 v1 缓存里是带限制的旧版，必须换新版本号强制浏览器重新拉取。
// v11：修正「各队 2 球 / 3 球走势分布」色块悬停框的比分口径 —— seq23Matches.score 是
//      「主客视角」(主队进球-客队进球)，客场时把对手排到前面后比分不能再翻一次，否则读出来
//      本队进球数正好相反（2 球色块看着像 1 球）。涉及 goals-pc.js / goals-champ.js（逻辑 JS），
//      旧缓存是错版，必须 +1 强制浏览器重新拉取。
// v10：次级联赛进球数页上线（pages/goals-champ.html + goals-champ.js + data/goals-champ/）。
// v15：meta.js 从 stale-while-revalidate 改为 **network-first**。它原先归在 DATA_RE 里，
//      导致页脚「本页更新时间」永远「晚一次访问」——先返回旧缓存、后台才更新。用户在不同时间
//      访问不同页面，就会看到不同日期（如平局页比进球数页旧一天），看起来像「没更新」。
//      meta.js 只有几十字节，每次拉取成本可忽略，故改为有网必取最新。
// v16：四个页面的 HTML 不再写死当季 chunk 路径（原先各有一行 `data/<group>/en/2026-27.js`，
//      赛季一换就要改 4 个文件，漏一个默认联赛就空白）。改由逻辑 JS 按 shell.js 的
//      seasonOrder[0] 在启动时预取；同时删除了完全重复的 assets/img/goals-crests/ 目录
//      （队徽统一到 assets/img/crests/）。页面 HTML 与逻辑 JS 都属外壳 → +1 强制换新。
// v17：4 个逻辑 JS 不再写死赛季字面量（原 '2026-27' 共 57 处：进行中的赛季一换就要人工
//      对齐 4 个文件，漏一处不报错、只静默出错）。改为从已加载的 shell.js 推导
//      （draws 用 seasonOrder[0]；goals 用 leagues[0].order[0]）；Python 侧同步收敛到
//      generator/season.py 一处。逻辑 JS 属外壳 → +1 强制换新。
// v18：修复「展开比分明细」按钮在单季视图下点了没反应（renderTop() 依赖的 cross 分块
//      8 秒后才预取，此前 CR() 为 undefined → 抛错并连带跳过 renderTeams()）。
// v19：平局页的两份逻辑 JS 与两份 CSS 合并为共用文件（draws.js / draws.css）——
//      差异下沉为页面声明的 window.DRAWS_CFG 与 :root{--namecol-*}。此前改一处忘另一处
//      是「改不完整」的主要来源。旧文件名（draws-big5.js / draws-champ.js /
//      draws-big5.css / draws-champ.css）已删除 → 旧缓存里的条目必须换新，+1。
// v20：进球数页的两份逻辑 JS 合并为 goals.js（差异走页面声明的 window.GOALS_CFG），
//      样式 goals-pc.css 改名 goals.css（它本来就是两页共用，名字里的 pc 是历史遗留）。
//      旧文件名 goals-pc.js / goals-champ.js / goals-pc.css 已删除 → +1。
var CACHE = 'fds-shell-v21';
// shell-hash: ecae2d362057fc364295e784514fb2a7e62aa55a91bdffd471d7742c4a9642dd（由 tools/bump_sw.py 维护：外壳文件合并 sha256；改了外壳它就把 CACHE +1）

// meta.js 单独判定：体积仅几十字节，是页脚「本页更新时间」的唯一来源，必须 network-first。
var META_RE = /(^|\/)meta\.js$/;
// 数据文件判定（按联赛+赛季拆出的 chunk；这些每天随数据源更新且体积大，
// 用 stale-while-revalidate 保证弱网/二次打开秒出，最多「晚到一次」是划算的）。
// 注：单体 *-data.js 已废弃不再产出，不再纳入此正则。
var DATA_RE = /(^|\/)assets\/js\/data\//;
// 静态资源判定（外壳 / 资源）
var SHELL_RE = /\.(?:html|css|js|mjs|woff2?|ttf|eot|png|jpe?g|gif|webp|svg|ico|json)$/;

self.addEventListener('install', function () {
  // 跳过等待，新版本立即激活
  self.skipWaiting();
});

self.addEventListener('activate', function (event) {
  event.waitUntil((function () {
    return caches.keys().then(function (keys) {
      return Promise.all(keys.map(function (k) {
        return k !== CACHE ? caches.delete(k) : null;
      }));
    }).then(function () {
      return self.clients.claim();
    });
  })());
});

function sameOrigin(url) {
  try { return new URL(url).origin === self.location.origin; } catch (e) { return false; }
}

self.addEventListener('fetch', function (event) {
  var req = event.request;
  if (req.method !== 'GET') return;
  var url;
  try { url = new URL(req.url); } catch (e) { return; }
  if (!sameOrigin(url)) return;

  // ---- meta.js：network-first（页脚时间必须新鲜，体积可忽略）----
  if (META_RE.test(url.pathname)) {
    event.respondWith((function () {
      return caches.open(CACHE).then(function (cache) {
        return fetch(req, { cache: 'no-cache' }).then(function (res) {
          if (res && res.ok) cache.put(req, res.clone());
          return res;
        }).catch(function () {
          // 离线：回退缓存；连缓存都没有就给一个安全空值，避免页脚报错
          return cache.match(req).then(function (c) {
            return c || new Response('window.SITE_META=null;', {
              headers: { 'Content-Type': 'application/javascript; charset=utf-8' }
            });
          });
        });
      });
    })());
    return;
  }

  // ---- 数据文件：stale-while-revalidate ----
  if (DATA_RE.test(url.pathname)) {
    event.respondWith((function () {
      return caches.open(CACHE).then(function (cache) {
        return cache.match(req).then(function (cached) {
          var network = fetch(req, { cache: 'no-cache' }).then(function (res) {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          }).catch(function () { return cached; });
          return cached || network;
        });
      });
    })());
    return;
  }

  // ---- 页面导航：cache-first，离线回退首页 ----
  if (req.mode === 'navigate') {
    event.respondWith((function () {
      return caches.open(CACHE).then(function (cache) {
        return fetch(req).then(function (res) {
          if (res && res.ok) cache.put(req, res.clone());
          return res;
        }).catch(function () {
          return cache.match(req)
            .then(function (c) { return c; })
            .then(function (c) { return c || cache.match(ROOT + '/index.html'); })
            .then(function (c) { return c || cache.match(ROOT + '/'); })
            .then(function (c) {
              return c || new Response('当前离线，且该页面未被缓存过。', {
                status: 503,
                headers: { 'Content-Type': 'text/plain; charset=utf-8' }
              });
            });
        });
      });
    })());
    return;
  }

  // ---- 其它静态资源：cache-first ----
  if (SHELL_RE.test(url.pathname)) {
    event.respondWith((function () {
      return caches.open(CACHE).then(function (cache) {
        return cache.match(req).then(function (cached) {
          if (cached) return cached;
          return fetch(req).then(function (res) {
            if (res && res.ok) cache.put(req, res.clone());
            return res;
          }).catch(function () { return cached || new Response('', { status: 504 }); });
        });
      });
    })());
    return;
  }
});
