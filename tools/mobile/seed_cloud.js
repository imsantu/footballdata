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
 *   node tools/seed_cloud.js                      # 全量同步 5 个集合
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
const ALL = ['meta', 'draw_seasons', 'draw_cross', 'draw_compare', 'goal_seasons'];

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
    console.error(
      '缺少云环境配置。请在 weapp/.env.local 写入（或设置环境变量）：\n' +
      '  TCB_ENV=<云开发环境ID>\n  TENCENTCLOUD_SECRET_ID=<SecretId>\n  TENCENTCLOUD_SECRET_KEY=<SecretKey>'
    );
    process.exit(1);
  }

  let tcb;
  try {
    tcb = require('@cloudbase/node-sdk');
  } catch (e) {
    console.error('缺少依赖 @cloudbase/node-sdk，请先执行：cd weapp && npm i @cloudbase/node-sdk');
    process.exit(1);
  }

  const app = tcb.init({ secretId: SECRET_ID, secretKey: SECRET_KEY, env: ENV });
  const db = app.database();
  const t0 = Date.now();
  const report = [];

  for (const name of targets) {
    const docs = readDocs(name);
    console.log(`→ ${name}（${docs.length} 条）`);
    const BATCH = 20;
    let done = 0;
    for (let i = 0; i < docs.length; i += BATCH) {
      const slice = docs.slice(i, i + BATCH);
      await Promise.all(slice.map((d) => {
        const { _id, ...rest } = d;
        return db.collection(name).doc(_id).set(rest);
      }));
      done += slice.length;
      process.stdout.write(`   ${done}/${docs.length}\r`);
    }
    console.log(`   ✅ ${name} 写入完成（${docs.length} 条）          `);
    report.push(name + '=' + docs.length);
  }

  console.log('\n同步完成：' + report.join(' / ') + '  用时 ' + ((Date.now() - t0) / 1000).toFixed(1) + 's');
  console.log('小程序端：下次冷启动（或下拉刷新）即读到新数据；新用户无需任何操作。');
}

main().catch((e) => {
  console.error('同步失败：', (e && e.message) || e);
  process.exit(1);
});
