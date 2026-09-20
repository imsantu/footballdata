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
var CACHE = 'fds-shell-v9';

// 数据文件判定（meta.js / 按联赛+赛季拆出的 chunk 等；这些每天随数据源更新，
// 必须用 stale-while-revalidate，否则 cache-first 会一直命中旧数据，页面“数据不变”。
// 注：单体 *-data.js 已废弃不再产出，不再纳入此正则。）
var DATA_RE = /(^|\/)meta\.js$|(^|\/)assets\/js\/data\//;
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
