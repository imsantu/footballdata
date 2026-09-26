/**
 * 把本地全量数据写入微信云开发数据库（服务端权限，幂等 upsert）
 * ------------------------------------------------------------------
 * 定位：这是「数据同步链路」的最后一环。PC 端每日跑完抓取/分析后调用它，
 *       云数据库即被刷新 —— 小程序端所有用户（含新用户）读的是同一份云端数据，
 *       不需要任何人手动导入。
 *
 * 前置（一次性准备）：
 *   1) 安装依赖：  cd weapp && npm i @cloudbase/node-sdk
 *   2) 准备密钥：  腾讯云控制台 → 访问管理 → API 密钥管理 → 拿 SecretId / SecretKey
 *                 云开发控制台 → 环境 ID
 *   3) 写配置：    weapp/.env.local（已 gitignore，切勿提交）
 *        TCB_ENV=cloud1-xxxxxxxx
 *        TENCENTCLOUD_SECRET_ID=xxx
 *        TENCENTCLOUD_SECRET_KEY=yyy
 *      （也可以直接用环境变量传入，launchd / CI 推荐环境变量）
 *
 * 用法：
 *   node tools/seed_cloud.js                      # 全量同步 6 个集合
 *   node tools/seed_cloud.js --only=meta,draw_seasons   # 只同步指定集合（日常增量）
 *   node tools/seed_cloud.js --dry-run            # 只打印将写入什么，不落库
 *
 * 说明：
 *   - 按 _id 用 set() 幂等写入，重复执行不会产生重复文档，只会覆盖更新。
 *   - 客户端集合权限保持「所有用户可读，仅创建者可读写」即可：
 *     客户端只读，写操作全部走这里的**服务端密钥**，密钥不进小程序包。
 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const https = require('https');

// 本脚本随 football-data-site（web 仓库）走 CI：集合 jsonl 在同目录 cloud-import/
const WEAPP = __dirname;
const CLOUD_DIR = path.join(WEAPP, 'cloud-import');
// ⚠️ 硬编码白名单：export_data.js 里新增集合后，必须同步加到这里，否则不会写进云数据库
// （--only= 参数也会校验此表）。fixture_seasons = 2026-27 各联赛全季赛程（含未开赛）。
const ALL = ['meta', 'draw_seasons', 'draw_cross', 'draw_compare', 'goal_seasons', 'fixture_seasons'];

// ---- 参数 ----
const argv = process.argv.slice(2);
const isDry = argv.includes('--dry-run');
const onlyArg = (argv.find((a) => a.startsWith('--only=')) || '').replace('--only=', '');
const targets = onlyArg ? onlyArg.split(',').map((s) => s.trim()).filter(Boolean) : ALL;
const bad = targets.filter((t) => !ALL.includes(t));
if (bad.length) {
  console.error('未知集合：' + bad.join(', ') + '（可选：' + ALL.join(', ') + '）');
  process.exit(1);
}

// ---- GHA 注解：把结果写进 GitHub 的 check-run annotation ----
// 为什么不用普通日志：本仓库是**公开**仓库，Actions 的「日志」需要 admin 权限才能下载
// （匿名请求 403 Must have admin rights），但 **annotation 匿名可读**。把「跳过/成功/失败原因」
// 打成注解后，本机用一条 curl 就能监控云端写库状态，不必登录 GitHub 翻日志。
// 注意：注解正文必须是单行，换行会被 GitHub 截断 → 统一替换成 ' ⏎ '。
function annotate(level, title, msg) {
  const one = String(msg == null ? '' : msg).replace(/\r?\n/g, ' ⏎ ').slice(0, 900);
  console.log(`::${level} title=${title}::${one}`);
}

// ---- 密钥：环境变量优先，其次 weapp/.env.local ----
function loadEnvFile() {
  const f = path.join(WEAPP, '.env.local');
  if (!fs.existsSync(f)) return;
  fs.readFileSync(f, 'utf8').split('\n').forEach((line) => {
    const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
    if (!m || line.trim().startsWith('#')) return;
    const v = m[2].replace(/^["']|["']$/g, '');
    if (!process.env[m[1]]) process.env[m[1]] = v;
  });
}
loadEnvFile();

// ⚠️ 一律 trim：GitHub secret 输入框粘贴时极易带上尾随空格/换行，肉眼看不出来，
//    但腾讯云那边就是「找不到这个环境」。这是 INVALID_ENV 最隐蔽的成因之一。
const ENV = (process.env.TCB_ENV || process.env.WEAPP_CLOUD_ENV || '').trim();
const SECRET_ID = (process.env.TENCENTCLOUD_SECRET_ID || '').trim();
const SECRET_KEY = (process.env.TENCENTCLOUD_SECRET_KEY || '').trim();

// ---- 错误分类：环境级 / 密钥级（配合下方预检，快速失败） ----
function errText(e) {
  return ((e && e.code) || '') + ' ' + ((e && e.message) || '') + ' ' + ((e && e.errMsg) || '');
}
const isEnvErr = (e) => /INVALID_ENV|Env Not Exists/i.test(errText(e));
const isAuthErr = (e) => /AuthFailure|Signature|Credential|Unauthorize/i.test(errText(e));

// Env Not Exists 的两种常见成因（2026-09-25 实况：6 集合全部 INVALID_ENV）：
// ① TCB_ENV 值不对；② 密钥不是「小程序绑定腾讯云账号」的密钥 —— 微信云开发环境
//    属于小程序对应的腾讯云账号，拿别的账号（哪怕是自己的另一个腾讯云账号）的
//    密钥访问，API 层面就报 Env Not Exists，而不是权限错误。
// ⚠️ 常见误会：GitHub secrets 的编辑框永远显示空白（不回显是设计如此），
//    不代表值被清除了 —— 每次运行用的都是保存的值，报错恰恰证明有值且值不对。
// 注：这里不再回显 TCB_ENV 原文（会被 GitHub 打码成 ***，反而看不出问题），改用「长度+指纹」，
// 两次运行一比就知道值有没有变过。
const ENV_FAIL_HELP =
  '腾讯云在「密钥所属账号」下找不到环境（' + envFingerprint() + '）。请检查：' +
  '① GitHub 仓库 Settings → Secrets and variables → Actions 里 TCB_ENV 的值是否为完整环境 ID（粘贴时别带空格/换行）；' +
  '② SecretId/SecretKey 是否来自小程序绑定主体的腾讯云账号（用该主体的微信扫码登录 console.cloud.tencent.com → 访问管理 → API 密钥管理），' +
  '其他账号的密钥会报 Env Not Exists；CAM 子用户还需授权 QcloudTCBFullAccess。' +
  '③ 若指纹与上次成功运行一致 → 配置没变，属腾讯云侧间歇性故障（见下方重试记录）。';

// ---- 诊断：列出「这把密钥所属账号」下全部云开发环境（TC3 签名直调 tcb 云 API，无新依赖）----
// Env Not Exists 只看报错分不清是①还是②。把该账号可见的环境列出来，一次运行即可定位：
// 列表为空 → 密钥账号不对；列表非空但没有目标环境 → 同样是账号不对；有 → TCB_ENV 抄它的写法。
function tcbApi(action, payload) {
  const host = 'tcb.tencentcloudapi.com';
  const service = 'tcb';
  const version = '2018-06-08';
  const ts = Math.floor(Date.now() / 1000);
  const date = new Date(ts * 1000).toISOString().slice(0, 10);      // UTC 日期（签名用）
  const body = JSON.stringify(payload || {});
  const sha = (s) => crypto.createHash('sha256').update(s).digest('hex');
  const canonical =
    'POST\n/\n\n' +
    'content-type:application/json; charset=utf-8\nhost:' + host + '\n' +
    'x-tc-action:' + action.toLowerCase() + '\n\n' +
    'content-type;host;x-tc-action\n' + sha(body);
  const toSign =
    'TC3-HMAC-SHA256\n' + ts + '\n' + date + '/' + service + '/tc3_request\n' + sha(canonical);
  const hmac = (k, d) => crypto.createHmac('sha256', k).update(d).digest();
  const sig = hmac(hmac(hmac('TC3' + SECRET_KEY, date), service), 'tc3_request').toString('hex');
  return new Promise((resolve, reject) => {
    const req = https.request({
      host, method: 'POST', path: '/',
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'X-TC-Action': action, 'X-TC-Version': version, 'X-TC-Timestamp': ts,
        Authorization: 'TC3-HMAC-SHA256 Credential=' + SECRET_ID + '/' + date + '/' + service +
          '/tc3_request, SignedHeaders=content-type;host;x-tc-action, Signature=' + sig
      }
    }, (res) => {
      let buf = '';
      res.on('data', (c) => (buf += c));
      res.on('end', () => {
        try {
          const j = JSON.parse(buf);
          if (j.Response && j.Response.Error) {
            reject(new Error(j.Response.Error.Code + ' ' + j.Response.Error.Message));
          } else resolve(j.Response);
        } catch (e) { reject(new Error('响应解析失败：' + buf.slice(0, 160))); }
      });
    });
    req.on('error', reject);
    req.setTimeout(10000, () => req.destroy(new Error('请求超时')));
    req.write(body);
    req.end();
  });
}

// 环境 ID 的「指纹」：长度 + sha256 前 8 位。
// 为什么需要：secret 的真实值在 GitHub 日志里会被打码成 ***，看不出两次运行用的是不是同一个值。
// 有了指纹就能直接比对：指纹一致却一成一败 → 不是配置变了，是腾讯云侧状态变了
// （环境停服/被释放/欠费隔离）；指纹不一致 → 说明 secret 的值确实被换过。
function envFingerprint() {
  if (!ENV) return '（空）';
  return '长度 ' + ENV.length + ' · 指纹 ' + crypto.createHash('sha256').update(ENV).digest('hex').slice(0, 8);
}

async function diagnoseEnvAccount() {
  try {
    // ⚠️ Action 名必须是 DescribeEnvs。曾写成 DescribeEnvironments → 腾讯云返回
    //    InvalidAction（Action 校验在鉴权之前，用假密钥即可探测出来）。
    const r = await tcbApi('DescribeEnvs', { Limit: 20 });
    const list = (r.EnvList || []).map((e) => e.EnvId + (e.Alias ? '（' + e.Alias + '）' : ''));
    if (!list.length) {
      return '诊断：这把 SecretId/SecretKey 所属的腾讯云账号下【一个云开发环境都没有】→ 密钥不是小程序绑定主体的账号。' +
        '用小程序主体的微信扫码登录 console.cloud.tencent.com 重新建 API 密钥。';
    }
    return '诊断：这把密钥可见的环境有【' + list.join('、') + '】。' +
      '若其中没有小程序的环境，说明密钥账号不对；若有，就把 TCB_ENV 改成上面列出的环境 ID 原文。';
  } catch (e) {
    return '诊断未能列出环境（' + ((e && e.message) || e) + '）——若含 AuthFailure 字样，说明密钥本身无效或不是腾讯云账号的密钥。';
  }
}

// 问腾讯云「这把密钥能看见哪些环境」，挑出与目标环境匹配的那个并返回它的 EnvId **原文**。
// 用途：TCB_ENV 若因大小写、别名、粘贴残留空格/不可见字符而对不上，这里能自动纠正成服务端认的写法。
// 找不到匹配返回 ''：账号下只有一个环境时就认它，多个且都不匹配则不敢乱猜（交给 diagnoseEnvAccount 说明）。
async function resolveRealEnvId() {
  try {
    const r = await tcbApi('DescribeEnvs', { Limit: 20 });
    const list = r.EnvList || [];
    if (!list.length) return '';
    const norm = (s) => String(s || '').trim().toLowerCase();
    const hit = list.find((e) => norm(e.EnvId) === norm(ENV))
      || list.find((e) => norm(e.Alias) === norm(ENV));
    if (hit) return hit.EnvId;
    return list.length === 1 ? list[0].EnvId : '';
  } catch (e) {
    return '';
  }
}

function readDocs(name) {
  const jsonl = path.join(CLOUD_DIR, name + '.jsonl');
  const json = path.join(CLOUD_DIR, 'json-backup', name + '.json');
  if (fs.existsSync(jsonl)) {
    return fs.readFileSync(jsonl, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
  }
  if (fs.existsSync(json)) return JSON.parse(fs.readFileSync(json, 'utf8'));
  throw new Error('找不到数据文件：' + jsonl + ' 或 ' + json + '（先跑 node tools/export_data.js）');
}

async function main() {
  // 预演模式不需要密钥
  if (isDry) {
    console.log('[预演] 不写入云端，仅检查本地数据文件：');
    targets.forEach((n) => console.log('  ' + n + ': ' + readDocs(n).length + ' 条'));
    return;
  }
  if (!ENV || !SECRET_ID || !SECRET_KEY) {
    // 注意：这里是正常分支而非错误 —— CI 未配密钥时也要保持绿灯，只跳过写库。
    console.log(
      '⏭️  未配置云环境密钥，跳过写库（已完成「生成 + 导出」体检）。\n' +
      '    配好 TCB_ENV / TENCENTCLOUD_SECRET_ID / TENCENTCLOUD_SECRET_KEY 后，下次运行即自动写入。'
    );
    // 打 notice 而非 error：这不是失败。但要让「跳过」在注解里可见 ——
    // 否则「跳过（绿灯）」与「真写成功（绿灯）」在结论上完全一样，无法区分。
    annotate('notice', '写库已跳过', '未配置云环境密钥（TCB_ENV / SECRET_ID / SECRET_KEY 有缺失），本次未写云数据库。');
    process.exit(0);
  }

  let tcb;
  try {
    tcb = require('@cloudbase/node-sdk');
  } catch (e) {
    console.error('缺少依赖 @cloudbase/node-sdk，请先执行：cd weapp && npm i @cloudbase/node-sdk');
    annotate('error', '写库失败', '缺少依赖 @cloudbase/node-sdk（CI 里检查「安装云开发服务端 SDK」那一步）');
    process.exit(1);
  }

  // SDK 在 init() 时用密钥换取访问凭证；那一次换取如果抖动/拿到错误上下文，
  // 这个实例之后的所有请求都会一路报 INVALID_ENV，表现和「环境真的不存在」一模一样。
  // 所以重试必须**重建实例**，光重发请求没用。
  // 实测依据（2026-09-26）：23:46 手动跑 6 个集合全败，18 分钟后 00:04 同一份配置全成 —— 只能是可自愈的抖动。
  let activeEnv = ENV;
  const initApp = (envId) => tcb.init({ secretId: SECRET_ID, secretKey: SECRET_KEY, env: envId }).database();
  let db = initApp(activeEnv);
  // 先打指纹：不管后面成功/失败/超时，日志里都能看到这次用的是哪个 TCB_ENV（真实值会被 GitHub 打码）
  console.log('→ 本次写库目标环境：' + envFingerprint());

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const probe = () => db.collection('meta').limit(1).get();
  const BACKOFF = [0, 3000, 8000, 15000];   // 抖动型故障基本 1~2 次内自愈，最多等 ~26s

  // 一轮预检 = 依次退避重试，每次都重建 SDK 实例。返回 '' 通过，否则返回错误说明。
  async function probeRound(tag) {
    for (let i = 0; i < BACKOFF.length; i++) {
      if (BACKOFF[i]) await sleep(BACKOFF[i]);
      try {
        await probe();
        console.log(`✅ 预检通过（${tag}第 ${i + 1} 次）：密钥可访问环境 ${envFingerprint()}`);
        return '';
      } catch (e) {
        if (isEnvErr(e)) {
          console.log(`   预检第 ${i + 1} 次失败：${errText(e)} → 重建 SDK 实例重试`);
          db = initApp(activeEnv);
          continue;
        }
        if (isAuthErr(e)) {
          return '密钥无效或被拒（' + errText(e) + '）。请检查 SecretId/SecretKey 是否正确、是否已停用。';
        }
        // 其他错误（如集合暂时不存在）说明「密钥 + 环境」配对没问题，放行走正常写库流程
        console.log('ℹ️ 预检读 meta 未通过但非环境/密钥问题（' + errText(e) + '），继续写库。');
        return '';
      }
    }
    return 'ENV_NOT_EXISTS';
  }

  let probeErr = await probeRound('首轮');
  let corrected = false;
  if (probeErr === 'ENV_NOT_EXISTS') {
    // 退避重试都没过 → 问腾讯云这把密钥到底能看见哪些环境，拿到真实 EnvId 原文后自动纠正
    // （能修掉大小写/别名/粘贴残留不可见字符这类「看着一样其实不一样」的问题）。
    const fixed = await resolveRealEnvId();
    if (fixed && fixed !== activeEnv) {
      console.log(`   ↻ 按腾讯云返回的真实环境 ID 纠正：${activeEnv} → ${fixed}`);
      activeEnv = fixed;
      db = initApp(activeEnv);
      probeErr = await probeRound('纠正后');
      corrected = true;
    }
  }
  if (probeErr) {
    const head = probeErr === 'ENV_NOT_EXISTS' ? ENV_FAIL_HELP : probeErr;
    const diag = '本次使用的 TCB_ENV：' + envFingerprint() + '（已尝试自动纠正：' + (corrected ? '是，仍失败' : '否') + '）。' +
      '把它和上一次成功运行的指纹对比：一致 → 配置没变，属腾讯云侧间歇性故障；不一致 → secret 值被换过。' +
      ' ' + (await diagnoseEnvAccount());
    console.error('❌ 预检失败：' + head);
    console.error('   ' + diag);
    annotate('error', '写库失败（预检）', head + ' ' + diag);
    process.exit(1);
  }

  const t0 = Date.now();
  const report = [];
  const failed = [];

  // 单个集合的批量写入。抽成函数是为了让「环境级错误」能重建实例后**整体重跑一次** ——
  // 抖动时半路断在某一批上，只重发那几行很容易留下残缺数据，整体重跑靠 doc().set() 幂等无副作用。
  async function writeDocs(name, docs) {
    const BATCH = 20;
    let done = 0;
    let curId = '';
    try {
      for (let i = 0; i < docs.length; i += BATCH) {
        const slice = docs.slice(i, i + BATCH);
        await Promise.all(slice.map((d) => {
          const { _id, ...rest } = d;
          curId = _id;
          return db.collection(name).doc(_id).set(rest);
        }));
        done += slice.length;
        process.stdout.write(`   ${done}/${docs.length}\r`);
      }
      return { ok: true, done, curId, e: null };
    } catch (e) {
      return { ok: false, done, curId, e };
    }
  }

  for (const name of targets) {
    // 集合不存在会让整次写库失败（2026-09-24 的 fixture_seasons 即此因）——
    // 写入前先尝试建集合；已存在时 createCollection 报错，直接忽略。
    try {
      await db.createCollection(name);
      console.log('   + 新建集合 ' + name);
    } catch (e) { /* 已存在 → 忽略，继续写入 */ }

    let docs;
    try {
      docs = readDocs(name);
    } catch (e) {
      // 本地 jsonl 缺失也要走注解：否则整脚本会以「未处理异常」告终，注解里啥也看不到。
      const m = (e && e.message) || String(e);
      console.error(`   ❌ ${name} 读取本地数据失败：` + m);
      annotate('error', '写库失败', `集合 ${name} 读取本地数据失败：${m}`);
      failed.push(name);
      continue;
    }
    console.log(`→ ${name}（${docs.length} 条）`);
    let r = await writeDocs(name, docs);
    if (!r.ok && isEnvErr(r.e)) {
      // 抖动型 INVALID_ENV：重建 SDK 实例 + 退避后整体重跑一次，仍失败才中止
      await sleep(6000);
      db = initApp(activeEnv);
      console.log(`   ↻ ${name} 遇环境级错误，已重建实例，重试…`);
      r = await writeDocs(name, docs);
    }
    if (r.ok) {
      console.log(`   ✅ ${name} 写入完成（${docs.length} 条）          `);
      report.push(name + '=' + docs.length);
    } else {
      // 按集合隔离失败：一个集合失败不拖垮其他集合，最后统一报非 0 退出
      const e = r.e;
      const detail = `集合 ${name} 写至第 ${r.done + 1} 条（_id=${r.curId}）失败：` + ((e && e.message) || e)
        + (e && e.code ? ` · code=${e.code}` : '')
        + (e && e.errMsg ? ` · errMsg=${e.errMsg}` : '')
        + (e && e.requestId ? ` · requestId=${e.requestId}` : '');
      console.error(`   ❌ ${detail}`);
      // 环境级错误（Env Not Exists 等）对所有集合都必然失败，继续循环只会刷屏 —— 立即中止
      if (isEnvErr(e)) {
        console.error('   重试后仍为环境级错误，中止后续所有集合。' + ENV_FAIL_HELP);
        annotate('error', '写库失败（环境不可用）', ENV_FAIL_HELP);
        process.exit(1);
      }
      annotate('error', '写库失败', detail);
      failed.push(name);
    }
  }

  if (failed.length) {
    console.error('\n部分集合写入失败：' + failed.join(', ') + '（其余集合已正常写入）');
    annotate('error', '写库汇总',
      `失败集合：${failed.join(', ')} · 成功集合：${report.join(', ') || '无'}`);
    process.exit(1);
  }

  console.log('\n同步完成：' + report.join(' / ') + '  用时 ' + ((Date.now() - t0) / 1000).toFixed(1) + 's');
  console.log('小程序端：下次冷启动（或下拉刷新）即读到新数据；新用户无需任何操作。');
  // 成功也打一条注解：与「跳过」区分开，且能一眼看出每个集合写了多少条。
  annotate('notice', '写库完成', report.join(' / ') + '  用时 ' + ((Date.now() - t0) / 1000).toFixed(1) + 's');
}

main().catch((e) => {
  const msg = (e && e.message) || String(e);
  console.error('同步失败：', msg);
  // 诊断信息：CI 日志里能直接看出是「密钥/环境没配好」还是「写库本身报错」，
  // 不必再靠猜（密钥只打印前缀，不泄露完整值）。
  if (e && e.code) console.error('  错误码：', e.code);
  if (e && e.errMsg) console.error('  errMsg：', e.errMsg);
  if (e && e.requestId) console.error('  requestId：', e.requestId);
  const diag = 'TCB_ENV=' + (ENV || '(未设置)')
    + ' · SECRET_ID=' + (SECRET_ID ? '已设置(' + String(SECRET_ID).slice(0, 8) + '…)' : '(未设置)')
    + ' · SECRET_KEY=' + (SECRET_KEY ? '已设置' : '(未设置)');
  console.error('  环境诊断：' + diag);
  // 关键：把诊断塞进注解 —— 这是本机唯一能读到云端失败原因的通道。
  annotate('error', '写库异常',
    `${msg} · code=${(e && e.code) || '-'} · errMsg=${(e && e.errMsg) || '-'}`
    + ` · requestId=${(e && e.requestId) || '-'} · ${diag}`);
  process.exit(1);
});
