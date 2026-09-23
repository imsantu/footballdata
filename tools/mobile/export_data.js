/**
 * 数据导出：原型数据(android-prototype-epl-data.js) → 微信云开发集合 JSON + 本地离线 mock
 * ------------------------------------------------------------------
 * 用法：node tools/export_data.js
 * 产出：
 *   cloud-import/<name>.jsonl              （控制台手动导入用，JSON Lines 格式）
 *   cloud-import/json-backup/<name>.json   （数组格式备份，便于人工查看/校验）
 *   cloudfunctions/football/data/<name>.json （可选一键导入云函数用）
 *   miniprogram/utils/mock-data.js         （1 联赛 1 赛季精简样本，无云环境也能跑 UI）
 * 注意：数据文件不要写入 miniprogram/ 目录（约 2.7MB 会撑爆主包 2MB 限制）。
 *
 * 集合设计
 *   meta         单文档 _id:'global'  —— 联赛列表 / 赛季顺序 / 进球档定义
 *   draw_seasons 每联赛每赛季一文档    —— 平局：总览 / 比分分布 / 各轮 / 球队
 *   draw_cross   每联赛一文档          —— 跨赛季汇总（近 N 季）
 *   draw_compare 每口径一文档(big5/champ/compare3) —— 五大联赛横评
 *   goal_seasons 每联赛每赛季一文档    —— 进球数：总览 / 球队（b 对象转数组规避字段名坑）
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

// 本脚本随 football-data-site（web 仓库）走 CI：源文件由同目录 gen_app_data.js 生成在 .build/，
// 集合 jsonl 写到本目录 cloud-import/（seed_cloud.js 读取），mock / 云函数数据等中间产物落到 .build/（已 gitignore）。
const SRC = path.join(__dirname, '.build', 'android-prototype-epl-data.js');
const OUT_CLOUD = path.join(__dirname, 'cloud-import');               // jsonl（控制台导入）+ json 备份
const OUT_MOCK = path.join(__dirname, '.build', 'mock-data.js');

// ---- 1. 载入原型数据 ----
const sb = { window: {} };
vm.createContext(sb);
vm.runInContext(fs.readFileSync(SRC, 'utf8'), sb);
const A = sb.window.APP;

const seasonOrder = A.seasonOrder;
const buckets = A.goals.buckets;          // [0,1,2,3,4,5,6,"7+"]
const labels = A.goals.labels;
const cats = A.cats;                       // ["0-0","1-1","2-2","其他"]
const leagues = A.leagues;                 // [{code,cn,name}]
const drawCodes = leagues.map(l => l.code).filter(c => A[c] && A[c].seasons);
const goalCodes = Object.keys(A.goals.leagues);

console.log('seasonOrder =', seasonOrder.join(', '));
console.log('draw leagues =', drawCodes.join(', '));
console.log('goal leagues =', goalCodes.join(', '));
const LATEST = seasonOrder[0]; // 季序为「最新在前」，默认赛季即 seasonOrder[0]，mock 与之对齐
console.log('LATEST =', LATEST);

fs.mkdirSync(OUT_CLOUD, { recursive: true });

// 同时把数据打包进云函数（cloudfunctions/football/data/），
// 供其 importData 动作离线写入云数据库——这样无需进控制台手动导入，App 内一键完成。
const OUT_FN_DATA = path.join(__dirname, '.build', 'fn-data');
fs.mkdirSync(OUT_FN_DATA, { recursive: true });

// 微信云开发控制台导入只接受 JSON Lines（每行一个对象），不接受外层数组。
// 因此每个集合同时产出：<name>.json（数组，便于人工查看/校验）与 <name>.jsonl（导入用）。
function writeColl(name, arr) {
  const json = path.join(OUT_CLOUD, 'json-backup', name + '.json');
  const jsonl = path.join(OUT_CLOUD, name + '.jsonl');
  fs.mkdirSync(path.join(OUT_CLOUD, 'json-backup'), { recursive: true });
  fs.writeFileSync(json, JSON.stringify(arr, null, 0));
  fs.writeFileSync(jsonl, arr.map((o) => JSON.stringify(o)).join('\n') + (arr.length ? '\n' : ''));
  // 云函数内 importData 直接 require 这些数组文件（云端以自身身份写入，无需控制台）
  fs.writeFileSync(path.join(OUT_FN_DATA, name + '.json'), JSON.stringify(arr));
  console.log(`  ${name}: ${arr.length} 条 -> cloud-import/.jsonl + json 备份 + 云函数 data`);
}

// ---- 2. meta ----
// dataVersion / updatedAt：数据版本戳。客户端启动时比对本地缓存的版本号，
// 变了就清掉内存缓存重新拉取 —— 这样 PC 端每天自动同步后，老用户无需清缓存也能看到新数据。
function stamp() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + p(d.getHours()) + p(d.getMinutes());
}
// 运维面板白名单：同步脚本读环境变量 DEV_OPENIDS（逗号分隔），写进云端 meta。
// 放云端而不是写死在小程序包里 → 改白名单不用重新发版；且「我的」页只对命中的账号渲染运维区。
// 同时存明文与哈希两份：明文便于排查，哈希避免 openid 直接躺在可被读到的文档里。
function fnv1a(s) {
  let h = 2166136261;
  const str = String(s || '');
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}
const devOpenids = (process.env.DEV_OPENIDS || '')
  .split(',').map((s) => s.trim()).filter(Boolean);

const meta = {
  _id: 'global', seasonOrder, leagues, buckets, labels, cats,
  dataVersion: stamp(),
  updatedAt: new Date().toISOString(),
  devOpenids,
  devOpenidHashes: devOpenids.map(fnv1a)
};
if (devOpenids.length) console.log('  运维白名单 openid：' + devOpenids.length + ' 个');
writeColl('meta', [meta]);

// ---- 3. draw_seasons ----
const drawSeasons = [];
for (const code of drawCodes) {
  const lg = A[code];
  for (const sk of Object.keys(lg.seasons)) {
    const s = lg.seasons[sk];
    drawSeasons.push({
      _id: `${code}_${sk}`,
      league: code,
      season: sk,
      totalMatches: s.totalMatches,
      totalDraws: s.totalDraws,
      drawRate: s.drawRate,
      nteams: s.nteams,
      perRoundCount: s.perRoundCount,
      rounds: s.rounds,
      roundMax: s.roundMax,
      moveFinal: s.moveFinal,
      note: s.note,
      overall: s.overall,
      perRound: s.perRound,
      teams: s.teams
    });
  }
}
writeColl('draw_seasons', drawSeasons);
console.log('draw_seasons docs =', drawSeasons.length);

// ---- 4. draw_cross（每联赛两个文档：<code>_5 近五季 / <code>_3 近三季）----
const drawCross = [];
for (const code of drawCodes) {
  [['5', A[code].cross], ['3', A[code].cross3]].forEach(([win, c]) => {
    if (!c) return;
    drawCross.push({
      _id: `${code}_${win}`, league: code, win: Number(win),
      seasonSeq: c.seasonSeq, meta: c.meta, teams: c.teams
    });
  });
}
writeColl('draw_cross', drawCross);
console.log('draw_cross docs =', drawCross.length);

// ---- 5. draw_compare（4 个口径：big5/champ × 近五季/近三季）----
const drawCompare = [];
const scopes = [
  ['big5', '5', A.compare],
  ['big5', '3', A.compare3],
  ['champ', '5', A.champ && A.champ.compare],
  ['champ', '3', A.champ && A.champ.compare3]
];
for (const [scope, win, obj] of scopes) {
  if (!obj) continue;
  drawCompare.push({
    _id: `${scope}_${win}`, scope, win: Number(win),
    seasonSeq: obj.seasonSeq, rows: obj.rows
  });
}
writeColl('draw_compare', drawCompare);
console.log('draw_compare docs =', drawCompare.length);

// ---- 6. goal_seasons（b 对象 → 数组）----
const goalSeasons = [];
for (const code of goalCodes) {
  const sc = A.goals.leagues[code].scopes;
  for (const sk of Object.keys(sc)) {
    const s = sc[sk];
    const teams = (s.teams || []).map(t => ({
      ...t,
      b: buckets.map(bk => t.b[String(bk)] || 0) // 与 buckets 对齐的数组
    }));
    goalSeasons.push({
      _id: `${code}_${sk}`,
      league: code,
      season: sk,
      totalMatches: s.totalMatches,
      expected: s.expected,
      teamCount: s.teamCount,
      inProgress: s.inProgress,
      avgGoals: s.avgGoals,
      note: s.note,
      buckets: s.buckets || buckets,
      teams
    });
  }
}
writeColl('goal_seasons', goalSeasons);
console.log('goal_seasons docs =', goalSeasons.length);

// ---- 7. 本地离线 mock：en 最新赛季（平局 + 进球）+ cross + compare ----
const mock = {
  meta,
  drawSeason: drawSeasons.find(d => d._id === `en_${LATEST}`),
  goalSeason: goalSeasons.find(d => d._id === `en_${LATEST}`),
  drawCross: drawCross.find(d => d._id === 'en_5'),
  drawCross3: drawCross.find(d => d._id === 'en_3'),
  drawCompare: {
    big5_5: drawCompare.find(d => d._id === 'big5_5'),
    big5_3: drawCompare.find(d => d._id === 'big5_3'),
    champ_5: drawCompare.find(d => d._id === 'champ_5'),
    champ_3: drawCompare.find(d => d._id === 'champ_3')
  }
};
const mockText =
  '/** 自动生成（tools/export_data.js）：1 联赛 1 赛季离线样本，仅供无云环境时预览 UI。\n' +
  ' * 正式数据请导入 cloud-import/*.jsonl 到云数据库，并在 config/index.js 填 CLOUD_ENV。 */\n' +
  'module.exports = ' + JSON.stringify(mock, null, 2) + ';\n';
fs.writeFileSync(OUT_MOCK, mockText);
console.log('mock written ->', OUT_MOCK, '(', (mockText.length / 1024).toFixed(0), 'KB )');
console.log('DONE');
