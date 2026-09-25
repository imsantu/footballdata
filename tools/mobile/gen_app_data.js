#!/usr/bin/env node
/**
 * 移动端原型数据生成器
 * ------------------------------------------------------------------
 * 从 PC 站 (../football-data-site) 的 draws-big5 数据集抽取「五大联赛」
 * 全部赛季 + 跨季聚合，生成移动端可直接 window.APP 使用的单文件数据。
 *
 * 用法：node tools/gen_app_data.js
 * 产出：android-prototype-epl-data.js（window.APP）
 *       assets/crests/*.png（按实际用到的球队同步队徽）
 *
 * 说明：产出的是「裁剪版」——只保留移动端界面真正消费的字段，
 *       去掉 formCounts / deduct / pct 等冗余项，体积约为全量的 45%。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const HERE = __dirname;
// 本脚本现在随 football-data-site（web 仓库）一起走 CI：默认站点目录 = 本仓库根
// （tools/mobile/ 的上两级）。CI 也可显式用 FD_SITE_DIR 指向任意站点目录。
function resolveSite() {
  if (process.env.FD_SITE_DIR) return path.resolve(process.env.FD_SITE_DIR);
  const webRoot = path.resolve(HERE, '..', '..'); // tools/mobile -> football-data-site
  if (fs.existsSync(path.join(webRoot, 'assets/js/data/draws-big5', 'shell.js'))) return webRoot;
  // 回退：本地从移动仓库运行时，站点在移动仓库的上上层
  const alt = path.resolve(HERE, '..', '..', '..', 'football-data-site');
  if (fs.existsSync(path.join(alt, 'assets/js/data/draws-big5', 'shell.js'))) return alt;
  return webRoot;
}
const SITE = resolveSite();
const DATA_DIR = path.join(SITE, 'assets/js/data/draws-big5');
const CHAMP_DIR = path.join(SITE, 'assets/js/data/draws-champ');
const GOALS_DIR = path.join(SITE, 'assets/js/data/goals');
const CREST_SRC = path.join(SITE, 'assets/img/crests');
// 中间产物统一放 .build/（已 gitignore），云同步不依赖队徽 PNG，重定向避免污染仓库
const CREST_DST = path.join(HERE, '.build', 'crests');
const OUT = path.join(HERE, '.build', 'android-prototype-epl-data.js');

const LEAGUES = ['en', 'es', 'de', 'it', 'fr'];
const SEASONS = ['2021-22', '2022-23', '2023-24', '2024-25', '2025-26', '2026-27'];

/* ---------- 1. 加载 PC 站数据到内存 ---------- */
const sandbox = { window: {} };
vm.createContext(sandbox);
const run = (f) => vm.runInContext(fs.readFileSync(f, 'utf8'), sandbox, { filename: f });

// shell 需要 window.DATA.leagues 已存在才会挂载
sandbox.window.DATA = { leagues: LEAGUES.map((c) => ({ code: c, seasons: {} })) };
run(path.join(DATA_DIR, 'shell.js'));
for (const lg of LEAGUES) {
  for (const s of SEASONS) {
    const f = path.join(DATA_DIR, lg, s + '.js');
    if (fs.existsSync(f)) run(f);
    else console.warn('  ! 缺失赛季数据:', lg, s);
  }
}
run(path.join(DATA_DIR, 'cross.js'));

const D = sandbox.window.DATA;

/* ---------- 2. 裁剪 ---------- */
const pickTeam = (t) => ({
  name: t.name, cn: t.cn, rank: t.rank, pts: t.pts,
  draws: t.draws, d00: t.d00, d11: t.d11, d22: t.d22, dother: t.dother,
  streak: t.streak, gap: t.gap, every: t.every === undefined ? null : t.every,
  formSeq: t.formSeq, formMatches: t.formMatches,
  formDetail: t.formDetail || [],
  promo: !!t.promo, releg: !!t.releg,
  upTop: !!t.upTop, demoted: !!t.demoted,
  // 队名红/绿（与 web 版 draws.js 的 CFG.promotion=true 分支一致）：fromTop=从上一级降入（降班马，标红）；
  // promo=从下一级升入（升班马，标绿）。仅次级联赛可能出现 fromTop，顶级联赛恒为 false。
  // 升降 icon（升/降/adm）由 upTop / releg / demoted 三个字段决定，且只在赛季已结束
  // （season.moveFinal === true）时渲染 —— 进行中的赛季下季名单未定，一律不标。
  fromTop: !!t.fromTop,
});
const pickSeason = (s) => ({
  season: s.season, totalMatches: s.totalMatches, totalDraws: s.totalDraws,
  drawRate: s.drawRate, nteams: s.nteams, perRoundCount: s.perRoundCount,
  rounds: s.rounds, roundMax: s.roundMax, moveFinal: s.moveFinal, note: s.note || '',
  overall: (s.overall || []).map((c) => ({ score: c.score, n: c.n })),
  perRound: (s.perRound || []).map((r) => ({
    round: r.round, n: r.n,
    draws: (r.draws || []).map((d) => ({ h: d.h, a: d.a, hs: d.hs, as: d.as })),
  })),
  teams: (s.teams || []).map(pickTeam),
});
const pickCrossTeam = (t) => ({
  name: t.name, cn: t.cn, seasons: t.seasons, per: t.per, matches: t.matches,
  total: t.total, avgSeason: t.avgSeason, rate: t.rate, every: t.every,
  min: t.min, max: t.max, range: t.range, sd: t.sd,
  maxStreak: t.maxStreak, streakSeason: t.streakSeason,
  gap: t.gap, gapSeason: t.gapSeason,
  d00: t.d00, d11: t.d11, d22: t.d22, dother: t.dother, rank: t.rank,
});
const pickCross = (c) => (!c ? null : {
  seasonSeq: c.seasonSeq, meta: c.meta,
  teams: (c.teams || []).map(pickCrossTeam),
});

/* ---------- 3. 组装 APP ---------- */
const APP = {
  leagues: [],   // 在加载次级联赛后交错填充（big5 与 次级 交替）
  seasonOrder: D.seasonOrder,
  cats: D.cats,
  compare: D.compare,
  compare3: D.compare3,
};

/* ---------- 3a. 次级联赛（英冠/西乙/德乙/意乙/法乙）----------
 * 完整加载逐季数据 + 跨季聚合（cross/cross3），以 en2/es2/de2/it2/fr2 存入 APP，
 * 让次级联赛也能像五大联赛一样进入 L1 并拥有 统计/明细/榜单/汇总 全套页面。
 */
function loadChamp() {
  const c = { window: {} };
  vm.createContext(c);
  vm.runInContext(fs.readFileSync(path.join(CHAMP_DIR, 'shell.js'), 'utf8'), c, { filename: 'champ/shell.js' });
  for (const lg of LEAGUES) {
    for (const s of SEASONS) {
      const f = path.join(CHAMP_DIR, lg, s + '.js');
      if (fs.existsSync(f)) vm.runInContext(fs.readFileSync(f, 'utf8'), c, { filename: f });
    }
  }
  vm.runInContext(fs.readFileSync(path.join(CHAMP_DIR, 'cross.js'), 'utf8'), c, { filename: 'champ/cross.js' });
  const CD = c.window.DATA;
  const order = (rows) => LEAGUES.map((code) => rows.find((r) => r.code === code)).filter(Boolean);
  // 横评行 code 加 '2' 后缀（en2/es2…），与 LG_LOGO/LG_COLOR/LG_CN 的次级键保持一致
  const order2 = (rows) => order(rows).map((r) => Object.assign({}, r, { code: r.code + '2' }));
  const out = {
    leagues: CD.leagues.map((l) => ({ code: l.code + '2', cn: l.cn, name: l.name || '', tier: 'champ' })),
    compare: { seasonSeq: CD.compare.seasonSeq, rows: order2(CD.compare.rows) },
    compare3: { seasonSeq: CD.compare3.seasonSeq, rows: order2(CD.compare3.rows) },
    crestByTeam: CD.crestByTeam || {},
  };
  for (const l of CD.leagues) {
    const seasons = {};
    for (const k of SEASONS) {
      const s = l.seasons && l.seasons[k];
      if (!s || !s.teams) continue;
      seasons[k] = pickSeason(s);
    }
    out[l.code + '2'] = { seasons, cross: pickCross(l.cross), cross3: pickCross(l.cross3) };
  }
  return out;
}
const CHAMP = loadChamp();
APP.champ = { leagues: CHAMP.leagues, compare: CHAMP.compare, compare3: CHAMP.compare3 };
['en2', 'es2', 'de2', 'it2', 'fr2'].forEach((code) => { APP[code] = CHAMP[code]; });

/* ---------- 2b. 进球数数据集（goals）---------- */
// 与平局数据同构：leagues[].scopes[<赛季>]，但无跨季聚合（PC 站亦无）。
// seq23Matches 压成 "轮|日期|主客|对手|比分" 短串，体积约为对象形式的 1/3。
const packMatch = (m) => [m.round, m.date, m.ha, m.opponent, m.score].join('|');
// 注意：源数据的 team.total 口径不稳定（完赛赛季＝已赛场次，进行中赛季＝进球数），一律弃用。
// 已赛场次取 b 各档之和；进/失球从 seq23Matches 还原（score 口径＝主客视角：主队进球-客队进球）。
const pickGoalTeam = (t) => {
  const played = Object.values(t.b || {}).reduce((a, c) => a + c, 0);
  let gf = 0, ga = 0;
  for (const m of (t.seq23Matches || [])) {
    const sp = String((m && m.score) || '').split('-');
    if (sp.length !== 2) continue;
    const a = +sp[0] || 0, b = +sp[1] || 0;
    if (m.ha === 'A') { gf += b; ga += a; } else { gf += a; ga += b; }
  }
  return {
    name: t.name, cn: t.cn, rank: t.rank, pts: t.pts,
    b: t.b, played, gf, ga,
    gap2: t.gap2, gap3: t.gap3, gap23: t.gap23,
    seq23: t.seq23 || [],
    n2: t.count2, n3: t.count3, s2: t.streak2, s3: t.streak3,
    m23: (t.seq23Matches || []).map(packMatch),
  };
};
const pickScope = (s) => ({
  totalMatches: s.totalMatches, expected: s.expected, teamCount: s.teamCount,
  inProgress: !!s.inProgress, avgGoals: s.avgGoals, note: s.note || '',
  buckets: s.buckets || {},
  teams: (s.teams || []).map(pickGoalTeam),
});
function loadGoals() {
  const gs = { buckets: [], labels: [], leagues: {} };
  const g = { window: { DATA: { leagues: LEAGUES.map((c) => ({ code: c, scopes: {} })) } } };
  vm.createContext(g);
  const runG = (f) => vm.runInContext(fs.readFileSync(f, 'utf8'), g, { filename: f });
  runG(path.join(GOALS_DIR, 'shell.js'));
  for (const lg of LEAGUES) {
    for (const s of SEASONS) {
      const f = path.join(GOALS_DIR, lg, s + '.js');
      if (fs.existsSync(f)) runG(f);
      else console.warn('  ! 缺失进球数据:', lg, s);
    }
  }
  const GD = g.window.DATA;
  gs.buckets = GD.buckets; gs.labels = GD.labels;
  gs._crests = GD.crests || {};
  for (const l of GD.leagues) {
    const scopes = {};
    for (const k of SEASONS) {
      const s = l.scopes && l.scopes[k];
      if (!s || !s.teams) continue;
      scopes[k] = pickScope(s);
    }
    gs.leagues[l.code] = { cn: l.cn, scopes };
  }
  return gs;
}
APP.goals = loadGoals();

/* ---------- 2c. 赛程表（fixtures）---------- */
// 各联赛 2026-27 全季赛程（含未开赛场次与开球时间），源 = titan007，与赛果同一份文件
// （该文件本就是全季赛程，赛果只取已完赛部分）。结构与 PC 站 assets/js/data/fixtures/ 一致。
//   matches = [[round, kickoff, home, away, state, score], ...]
//   state: 'FT' 已完赛（score 形如 '3-0'，主客视角） | 'SCH' 未开赛（score 为空串）
//   kickoff: 'YYYY-MM-DD HH:MM'（北京时间）；home/away: 规范英文队名（与 draws/goals 同一套）
const FIX_DIR = path.join(SITE, 'assets/js/data/fixtures');
function loadFixtures() {
  const out = { schema: null, seasonOrder: [], meta: null, leagues: [], seasons: {} };
  const f = { window: {} };
  vm.createContext(f);
  const runF = (p) => vm.runInContext(fs.readFileSync(p, 'utf8'), f, { filename: p });
  const shell = path.join(FIX_DIR, 'shell.js');
  if (!fs.existsSync(shell)) { console.warn('  ! 缺赛程数据:', shell); return out; }
  runF(shell);
  const FD = f.window.DATA;
  out.schema = FD.schema; out.seasonOrder = FD.seasonOrder; out.meta = FD.meta;
  out.leagues = FD.leagues.map((l) => ({ code: l.code, cn: l.cn, name: l.name, en: l.en, tier: l.tier }));
  for (const l of FD.leagues) {
    const p = path.join(FIX_DIR, l.code, '2026-27.js');
    if (!fs.existsSync(p)) { console.warn('  ! 缺失赛程:', l.code); continue; }
    runF(p);
    const s = l.seasons && l.seasons['2026-27'];
    if (s) out.seasons[l.code] = s;
  }
  return out;
}
APP.fixtures = loadFixtures();

// 队徽：英文名 -> slug（与 assets/crests/<slug>.png 对应）
const crestByName = {};
for (const [name, uri] of Object.entries(D.crestByTeam || {})) {
  const m = /\/crests\/(.+)\.png$/.exec(uri);
  if (m) crestByName[name] = m[1];
}
// 进球数数据集的队徽（现与 draws 共用 assets/img/crests/；旧数据可能仍是 goals-crests，
// 故正则同时接受两种目录，避免历史 chunk 解析不到 slug）
for (const [name, uri] of Object.entries(APP.goals._crests || {})) {
  const m = /\/(?:goals-)?crests\/(.+)\.png$/.exec(uri);
  if (m && !crestByName[name]) crestByName[name] = m[1];
}
// 次级联赛队徽（英冠/西乙/德乙/意乙/法乙），与五大联赛同 slug 体系
for (const [name, uri] of Object.entries(CHAMP.crestByTeam || {})) {
  const m = /\/crests\/(.+)\.png$/.exec(uri);
  if (m && !crestByName[name]) crestByName[name] = m[1];
}

/* ---------- 3b. L1 联赛顺序：五大联赛 优先排在前面，次级联赛随后（不再穿插） ---------- */
const big5Leagues = D.leagues.map((l) => ({ code: l.code, cn: l.cn, name: l.name || '' }));
const champLeagues = CHAMP.leagues.map((l) => ({ code: l.code, cn: l.cn, name: l.name || '' }));
APP.leagues = [...big5Leagues, ...champLeagues];

for (const l of D.leagues) {
  const seasons = {};
  for (const k of SEASONS) {
    const s = l.seasons && l.seasons[k];
    if (!s || !s.teams) continue;         // 数据缺失的赛季直接跳过
    seasons[k] = pickSeason(s);
    s.teams.forEach((t) => {              // 补齐该队队徽 slug
      if (!crestByName[t.name] && t.cn) crestByName[t.name] = null;
    });
  }
  APP[l.code] = {
    seasons,
    cross: pickCross(l.cross),
    cross3: pickCross(l.cross3),
  };
}
APP.crestByName = crestByName;
delete APP.goals._crests;

/* ---------- 4. 同步队徽 PNG ---------- */
fs.mkdirSync(CREST_DST, { recursive: true });
let copied = 0, missing = [];
for (const slug of new Set(Object.values(crestByName).filter(Boolean))) {
  const src = path.join(CREST_SRC, slug + '.png');
  const dst = path.join(CREST_DST, slug + '.png');
  if (!fs.existsSync(dst) && fs.existsSync(src)) { fs.copyFileSync(src, dst); copied++; }
  else if (!fs.existsSync(dst)) missing.push(slug);
}

/* ---------- 5. 写出 ---------- */
const stamp = new Date().toISOString().slice(0, 10);
const banner = `/* 移动端原型数据 · 自动生成，请勿手改
 * 源：PC 站 football-data-site/assets/js/data/draws-big5
 * 生成：${stamp} · 联赛：${LEAGUES.join('/')} · 季节：${SEASONS.join(' ')}
 * 用法：window.APP[联赛code].seasons[赛季] / .cross / .cross3
 */
`;
fs.writeFileSync(OUT, banner + 'window.APP=' + JSON.stringify(APP) + ';\n');

const kb = (fs.statSync(OUT).size / 1024).toFixed(0);
console.log(`✓ 已生成 ${path.basename(OUT)} (${kb} KB)`);
for (const l of D.leagues) {
  const n = Object.keys(APP[l.code].seasons).length;
  const cur = APP[l.code].seasons['2026-27'];
  console.log(`  ${l.cn}(${l.code}): ${n} 季 · 本季 ${cur ? cur.totalMatches + '场/' + cur.totalDraws + '平/' + cur.teams.length + '队' : '—'}` +
    ` · cross ${APP[l.code].cross ? APP[l.code].cross.teams.length + '队' : '无'}`);
}
console.log(`  次级联赛对照：${APP.champ.leagues.map((l) => l.cn).join('/')} · 近五季 ${APP.champ.compare.rows.length} 行 / 近三季 ${APP.champ.compare3.rows.length} 行`);
console.log(`  队徽：新增 ${copied} 个，缺失 ${missing.length} 个${missing.length ? ' -> ' + missing.slice(0, 8).join(',') : ''}`);
for (const code of LEAGUES) {
  const g = APP.goals.leagues[code];
  const n = g ? Object.keys(g.scopes).length : 0;
  const cur = g && g.scopes['2026-27'];
  console.log(`  ${g ? g.cn : code} 进球：${n} 季 · 本季 ${cur ? cur.totalMatches + '场/场均' + cur.avgGoals + '球/' + cur.teams.length + '队' : '—'}`);
}
const FX = APP.fixtures.seasons;
const fxCodes = Object.keys(FX);
if (fxCodes.length) {
  const tt = fxCodes.reduce((a, c) => a + FX[c].total, 0);
  const pf = fxCodes.reduce((a, c) => a + FX[c].played, 0);
  console.log(`  赛程：${fxCodes.length} 个联赛 · ${tt} 场（已完赛 ${pf} / 未开赛 ${tt - pf}）` +
    ` · 数据版本 ${(APP.fixtures.meta || {}).generated || '—'}`);
} else {
  console.warn('  ! 赛程数据为空，请先执行 generator/build_fixtures.py');
}
