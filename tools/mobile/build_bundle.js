#!/usr/bin/env node
/**
 * 打包小程序数据包：把 export_data.js 产出的 6 个集合合并成**一个** JSON 文件，
 * 落到站点目录 assets/js/data/mobile/app-data.json，随站点一起发布到 GitHub Pages。
 *
 * 为什么改成这个链路（2026-09-26）：
 *   原先是「GitHub Actions 用腾讯云密钥直连写云开发数据库」，但同一份密钥会
 *   间歇性报 `[100003] Env Not Exists`（实测相隔 18 分钟、同一份配置一败一成），
 *   无法根治。现在拆成两段：
 *     web 仓库（本脚本）——只负责算好数据并发布成一个静态 JSON（这部分一直稳定）；
 *     小程序云函数 syncDaily——每天下载这个 JSON，用**环境内置身份**写进云数据库。
 *   统计计算仍只做一次（在 web 侧），两端数据逐字段一致；云函数不需要任何密钥，
 *   也就不会再出现 Env Not Exists。
 *
 * 用法：node tools/mobile/build_bundle.js      （须先跑 export_data.js 产出 .build/fn-data）
 * 输出：assets/js/data/mobile/app-data.json
 */
const fs = require('fs');
const path = require('path');

const HERE = __dirname;
const FN_DATA = path.join(HERE, '.build', 'fn-data');
const COLLS = ['meta', 'draw_seasons', 'draw_cross', 'draw_compare', 'goal_seasons', 'fixture_seasons'];

function resolveSite() {
  if (process.env.FD_SITE_DIR) return path.resolve(process.env.FD_SITE_DIR);
  return path.resolve(HERE, '..', '..');   // tools/mobile -> 仓库根
}
const SITE = resolveSite();
const OUT_DIR = path.join(SITE, 'assets', 'js', 'data', 'mobile');
const OUT = path.join(OUT_DIR, 'app-data.json');

const colls = {};
let total = 0;
for (const c of COLLS) {
  const f = path.join(FN_DATA, c + '.json');
  if (!fs.existsSync(f)) {
    console.error('❌ 缺少 ' + f + ' —— 请先跑 `node export_data.js`（它会产出 .build/fn-data/*.json）');
    process.exit(1);
  }
  const arr = JSON.parse(fs.readFileSync(f, 'utf8'));
  if (!Array.isArray(arr)) {
    console.error('❌ ' + f + ' 不是数组，导出可能有误');
    process.exit(1);
  }
  colls[c] = arr;
  total += arr.length;
  console.log('  ' + c.padEnd(16) + arr.length + ' 条');
}

const metaDoc = (colls.meta && colls.meta[0]) || {};
// dataVersion 沿用 meta 里那个（客户端靠它判断要不要刷新缓存），放在外层方便云函数先比对、没变就直接跳过写库
const bundle = {
  dataVersion: metaDoc.dataVersion || '',
  generatedAt: metaDoc.updatedAt || new Date().toISOString(),
  colls
};

fs.mkdirSync(OUT_DIR, { recursive: true });
// 不缩进：省体积（每天都要往仓库里提交一份）
fs.writeFileSync(OUT, JSON.stringify(bundle));

const kb = (fs.statSync(OUT).size / 1024).toFixed(0);
console.log('\n✅ 数据包已生成：' + path.relative(SITE, OUT) + '（' + kb + ' KB，共 ' + total + ' 条文档）');
console.log('   dataVersion = ' + bundle.dataVersion);
console.log('   云函数下载地址：' + (process.env.SITE_BASE_URL || 'https://imsantu.github.io/footballdata') +
  '/assets/js/data/mobile/app-data.json');
