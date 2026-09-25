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

const ENV = process.env.TCB_ENV || process.env.WEAPP_CLOUD_ENV;
const SECRET_ID = process.env.TENCENTCLOUD_SECRET_ID;
const SECRET_KEY = process.env.TENCENTCLOUD_SECRET_KEY;

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

  const app = tcb.init({ secretId: SECRET_ID, secretKey: SECRET_KEY, env: ENV });
  const db = app.database();
  const t0 = Date.now();
  const report = [];
  const failed = [];

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
      console.log(`   ✅ ${name} 写入完成（${docs.length} 条）          `);
      report.push(name + '=' + docs.length);
    } catch (e) {
      // 按集合隔离失败：一个集合失败不拖垮其他集合，最后统一报非 0 退出
      const detail = `集合 ${name} 写至第 ${done + 1} 条（_id=${curId}）失败：` + ((e && e.message) || e)
        + (e && e.code ? ` · code=${e.code}` : '')
        + (e && e.errMsg ? ` · errMsg=${e.errMsg}` : '')
        + (e && e.requestId ? ` · requestId=${e.requestId}` : '');
      console.error(`   ❌ ${detail}`);
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
