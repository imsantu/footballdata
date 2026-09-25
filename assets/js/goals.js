/* ══════════════════════════════════════════════════════════════════════════
   进球数统计页 · 五大联赛 / 五大次级联赛 共用实现
   ──────────────────────────────────────────────────────────────────────────
   这两个页面此前是两份 876 / 883 行、96.7% 逐行相同的文件（goals-pc.js /
   goals-champ.js，现已删除），差异只有 8 处，可归为两类：

   ① 纯身份差异（由页面声明）
        · 数据集目录（assets/js/data/goals/ ↔ goals-champ/）
        · 冠军奖杯 SVG 常量（champ 侧提为常量，pc 侧内联，逐字节相同）
   ② 升降级标记：两套数据集、两套字段来源，但**都直接读权威字段，不做任何推断**
        · 次级联赛（promotion:true）：数据由 generator/build_champ_goals.py 从
          draws-champ 原样搬运，带权威字段 upTop / releg / demoted / fromTop /
          promo + 赛季级 moveFinal，直接读字段，与「平局统计 · 次级联赛」逐字一致。
        · 五大联赛（promotion:false）：字段由 tools/sync_site.py 的 inject_promotion()
          从 draws-big5 原样搬运（promo / releg + 赛季级 moveFinal），同样直接读字段。
          -> 2026-09-26 之前这里是**全站唯一的推断式实现**（「上/下赛季名单差集 +
             积分榜末 N 位」三层退化），实测漏标 14 处（最早赛季没有上赛季可比，
             该季 5 个联赛的升班马全部漏标；fr 2022-23 欧塞尔漏标降级）。已删除。

   页面加载顺序（缺 CFG 会立刻抛错，而不是静默用错一套升降级语义）：
     <script>window.GOALS_CFG = {group:'goals', promotion:false};</script>
     <script defer src="../assets/js/goals.js"></script>
   ══════════════════════════════════════════════════════════════════════════ */
var CFG = window.GOALS_CFG;
if(!CFG || !CFG.group || typeof CFG.promotion !== 'boolean'){
  throw new Error('goals.js：页面必须先声明 window.GOALS_CFG = {group, promotion}（promotion 必须是布尔值）');
}

// 冠军奖杯（与平局统计页同款），仅在本季「最终裁定」的赛季挂在榜首队名旁
const CHAMP_SVG = '<span class="champ"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg></span>';
window.LABELS = window.LABELS || ['0 球','1 球','2 球','3 球','4 球','5 球','6 球','7+ 球'];
window.BUCKETS = window.BUCKETS || window.DATA.buckets;
// 默认选中"数据完整的最新赛季"。新赛季刚开踢时只有几场（如 2026-27 仅首轮），
// 直接落在它上面看到的分布毫无意义，所以自动退到上一个已完赛的赛季（通常是 2025-26）。
// 若某联赛所有赛季都不完整（极端情况），则退回最新一个。
function defaultSeason(lg){
  for(const k of lg.order){
    const sc = lg.scopes[k];
    if(sc.expected > 0 && sc.totalMatches >= sc.expected) return k;
  }
  return lg.order[0];
}
var _url0 = window.FD_URL ? window.FD_URL.read() : {};
function _validGoalLeague(code){ return code === '__all__' || DATA.leagues.some(function(l){ return l.code === code; }); }
let currentLeague = _validGoalLeague(_url0.league) ? _url0.league : DATA.leagues[0].code;
// 默认落在进行中的最新赛季；若 URL 带赛季，则优先恢复可用的深链状态。
/* ---------------- 进行中的赛季（唯一来源：已加载的 shell.js）----------------
   各联赛 order 均为新→旧，[0] 即当季。此前本文件写死了赛季字面量，换季要人工回来
   对齐 4 个逻辑文件（漏一处就静默出错）；改为推导后，换季只需改生成侧一处。 */
var ONGOING_SEASON = ((DATA.leagues[0] || {}).order || [])[0] || '';
/* seq23 走势图只对「当季 + 近五季」绘制（更早的赛季没有逐场 2/3 球明细） */
var SEQ_SEASONS = ((DATA.leagues[0] || {}).order || []).slice(0, 6);
let currentSeason = (function(){
  var lg = currentLeague === '__all__' ? DATA.leagues[0] : leagueOf(currentLeague);
  return _url0.season && lg && (lg.order || []).includes(_url0.season) ? _url0.season : ((lg.order || []).includes(ONGOING_SEASON) ? ONGOING_SEASON : defaultSeason(lg));
})();

/* ---------------- 当季 chunk 提前预取 ----------------
   页面已**不再**写死 `data/<group>/en/<season>.js`：那行会在赛季切换时要求改 4 个 HTML，
   漏掉任何一个页面，它的默认联赛就加载不出数据（且不报错，只是空白）。
   这里在「联赛 + 赛季」一确定就立刻把 renderAfterEnsure() 将要用的 chunk 全部发起请求，
   等执行到文件末尾时它们多半已在飞或已就绪 —— 既不写死赛季，也不比原来慢。
   注：_chunkInflight / _chunkRenderToken 原本声明在文件末尾的懒加载段落，
   必须提前到这里，否则本行调用会读到 undefined。 */
var _chunkInflight = {};
var _chunkRenderToken = 0;
ensureChunks(neededChunks(), function(){});

let teamSort = {key:'rank', dir:1};
let teamGoalsShowAll = false;
function toggleTeamGoals(){ teamGoalsShowAll = !teamGoalsShowAll; renderTeams(); }
// 进球数 / 失球数 / 净胜球数 三列（得失球）折叠状态：进行中的当季默认收起，其余赛季默认显示；用户点「显示得失球」后锁定
let teamTotalsShow = true;
let teamTotalsPinned = null; // null = 跟随赛季默认；true/false = 用户手动设定
function toggleTeamTotals(){ const cur=(teamTotalsPinned===null)?(currentSeason!==ONGOING_SEASON):teamTotalsPinned; teamTotalsPinned=!cur; renderTeams(); }
// 不出预警：从最近一场往前，连续多少轮（场）该队总进球既 ≠2 也 ≠3（即只打出 0/1/4+ 球）
function trailingNot23(seq){ if(!seq||!seq.length) return 0; let n=0; for(let i=seq.length-1;i>=0;i--){ const x=seq[i]; if(x!==2&&x!==3) n++; else break; } return n; }
// 2/3 球走势面板筛选状态：关键词、2 球 / 3 球开关、被隐藏的球队
let seqQuery = '', seqShow2 = true, seqShow3 = true, seqHidden = {};

// 跨赛季统计口径：近五季 / 近三季（与平局页一致，由外壳顶部「范围」下拉菜单驱动）
let SEASON_WIN = (_url0.win === '3' ? 3 : 5);
function syncGoalUrl(replace){
  if(window.FD_URL) window.FD_URL.write({league:currentLeague, season:currentSeason, win:SEASON_WIN}, !!replace);
}
// lg.order 为「新 → 旧」，取最近 N 季；进行中的最新季天然落在最前，始终在窗口内
function winSeasons(lg){ return (lg && lg.order ? lg.order : []).slice(0, SEASON_WIN); }
// 把 currentSeason 规范到当前窗口内 —— 必须在「决定加载哪些 chunk」之前调用。
//
// 背景（2026-09-26 修）：窗口会裁掉旧赛季（只保留最近 SEASON_WIN 季）。若 URL 深链指向
// 窗口外赛季（w=5 时的第 6 季 2021-22），旧代码是在 render() 内部由 buildSeasonTabs()
// 才把 currentSeason 落到 ws[0]，而 renderAfterEnsure() 早已按那个窗口外赛季算完
// neededChunks() 并加载完对应 chunk —— 于是变成「按 2021-22 加载 chunk、却按 2026-27
// 渲染」，而 2026-27 的 chunk 从未被请求（只有 shell stub，scope_stub 剥掉了
// teams/buckets）→ maxBucket 读 sc.buckets 抛 TypeError → render() 中断 → 整页白屏。
// 表现：分享/收藏一个历史赛季链接（第 6 季）打开是白屏。
function normalizeSeason(){
  if(currentLeague==='__all__') return;
  var lg=leagueOf(currentLeague); if(!lg) return;
  var ws=winSeasons(lg);
  if(ws.length && ws.indexOf(currentSeason)<0) currentSeason=ws[0];
}

const THEME_KEY='fbg_theme';
function paintTheme(t){ document.documentElement.setAttribute('data-theme', t); }
// 「自动」全站统一为跟随系统外观；不支持该媒体查询时才退回本地时间 6–18 点
function fixedAuto(){
  try{ if(typeof window.matchMedia==='function') return window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'; }catch(e){}
  const h=new Date().getHours(); return (h>=6 && h<18)?'light':'dark';
}
function sunAuto(){
  return new Promise(function(res, rej){
    try{ const c=sessionStorage.getItem('fbg_sun'); if(c){ const o=JSON.parse(c); if(o.d===new Date().toDateString()){ res(o.t); return; } } }catch(e){}
    const to=setTimeout(function(){ rej(new Error('timeout')); }, 5000);
    function ok(t){ clearTimeout(to); try{ sessionStorage.setItem('fbg_sun', JSON.stringify({d:new Date().toDateString(), t:t})); }catch(e){} res(t); }
    function no(e){ clearTimeout(to); rej(e); }
    fetch('https://ipapi.co/json/').then(function(r){return r.json();}).then(function(g){
      if(typeof g.latitude!=='number' || typeof g.longitude!=='number') throw new Error('no geo');
      return fetch('https://api.sunrise-sunset.org/json?lat='+g.latitude+'&lng='+g.longitude+'&formatted=0');
    }).then(function(r){return r.json();}).then(function(j){
      if(!j.results||!j.results.sunrise||!j.results.sunset) throw new Error('no sun');
      const now=Date.now(), sr=Date.parse(j.results.sunrise), ss=Date.parse(j.results.sunset);
      ok((now>=sr && now<ss)?'light':'dark');
    }).catch(no);
  });
}
function refreshThemeBtn(mode, actual){
  const b=document.getElementById('themeBtn'); if(!b) return;
  if(mode==='auto') b.textContent = (actual==='dark' ? '🌗 自动·深色' : '🌗 自动·浅色');
  else if(mode==='light') b.textContent = '☀️ 浅色';
  else b.textContent = '🌙 深色';
}
function applyMode(mode){
  try{ localStorage.setItem(THEME_KEY, mode); }catch(e){}
  if(mode==='auto'){
    const a=fixedAuto(); paintTheme(a); refreshThemeBtn('auto', a);
    // 已移除联网的日出/日落判定：自动模式全站统一为「跟随系统外观」，
    // 否则同一站点里几个页面会出现明暗不一致（见 assets/js/site.js）。
  } else {
    paintTheme(mode); refreshThemeBtn(mode, mode);
  }
}
function toggleTheme(){
  let cur=null; try{ cur=localStorage.getItem(THEME_KEY); }catch(e){}
  cur = cur || 'auto';
  const nxt = (cur==='auto') ? 'light' : (cur==='light' ? 'dark' : 'auto');
  applyMode(nxt);
}
(function(){
  // 主题的初始化与切换已统一交给站点外壳（assets/js/site.js）：
  // 本页不再自行读 localStorage 决定明暗，避免与外壳按钮 / 其他页面状态不一致。
  // 外壳缺失时（例如单独打开本文件）退回本页默认的「自动」。
  if(window.SITE_THEME_READY) window.SITE_THEME_READY();
  else applyMode('auto');
})();

function toggleTrendMetric(){ trendMetric = (trendMetric==='count' ? 'pct' : 'count'); renderTrendAll(); }

function fmtPct(c, total){ return total ? (c/total*100).toFixed(1)+'%' : '0%'; }
function leagueOf(code){ return DATA.leagues.find(l=>l.code===code); }
function colorFor(s){ let h=0; for(let i=0;i<s.length;i++) h=(h*31+s.charCodeAt(i))%360; return 'hsl('+h+',55%,45%)'; }
function crestHtml(name, cn){
  const uri = DATA.crests[name];
  if(uri) return '<img class="crest" src="'+uri+'" alt="'+cn+'">';
  const ini = /[A-Za-z]/.test(cn) ? cn.slice(0,2).toUpperCase() : cn.slice(0,1);
  return '<span class="crest-fallback" style="background:'+colorFor(name)+'">'+ini+'</span>';
}
function lgCrestHtml(code, cn){
  const lg = leagueOf(code);
  if(lg.logo) return '<img src="'+lg.logo+'" alt="'+cn+'">';
  return '<span class="lg-fallback" style="background:'+colorFor(code)+'">'+cn.slice(0,1)+'</span>';
}

function buildLeagueTabs(){
  const el=document.getElementById('leagueTabs'); el.innerHTML='';
  DATA.leagues.forEach(l=>{
    const b=document.createElement('div');
    b.className='league-tab'+(l.code===currentLeague?' active':'');
    const sc=l.scopes[l.order[0]];
    const badge=sc?sc.avgGoals.toFixed(2):'–';
    const logo=l.logo?('<img src="'+l.logo+'" alt="'+l.cn+'">'):lgCrestHtml(l.code,l.cn);
    b.innerHTML=logo+'<span>'+l.cn+'</span><span class="rt">'+badge+'</span>';
    b.onclick=()=>{ currentLeague=l.code; syncGoalUrl(false); renderAfterEnsure(); };   // 切换联赛：保留当前赛季不变
    el.appendChild(b);
  });
  const all=document.createElement('div');
  all.className='league-tab big5'+('__all__'===currentLeague?' active':'');
  all.innerHTML='<svg class="uefa-logo" viewBox="0 0 30 18" aria-label="UEFA"><rect x="0" y="0" width="30" height="18" rx="3" fill="#0a1f44"/><text x="15" y="12.5" font-family="Arial,Helvetica,sans-serif" font-size="9" font-weight="800" fill="#fff" text-anchor="middle" letter-spacing="0.5">UEFA</text></svg><span>五大联赛</span><span class="rt">对照</span>';
  all.onclick=()=>{ currentLeague='__all__'; syncGoalUrl(false); renderAfterEnsure(); };
  el.appendChild(all);
}
function buildSeasonTabs(){
  const el=document.getElementById('seasonTabs');
  if(currentLeague==='__all__'){ el.innerHTML=''; el.style.display='none'; return; }
  el.style.display='';
  el.innerHTML='';
  const lg=leagueOf(currentLeague);
  // 窗口裁掉旧赛季：只显示最近 N 季，进行中的最新季始终保留
  const ws = winSeasons(lg);
  if(ws.indexOf(currentSeason) < 0) currentSeason = ws[0];
  ws.forEach(k=>{
    const b=document.createElement('div');
    b.className='season-tab'+(k===currentSeason?' active':'');
    b.textContent=dispSeason(k);
    b.onclick=()=>{ currentSeason=k; syncGoalUrl(false); renderAfterEnsure(); };
    el.appendChild(b);
  });
}

/* 赛季范围开关：近五季 ⇄ 近三季（与平局页同一套分段开关交互）。
   页面只负责把按钮渲染进 #winSwitch，外壳顶部「范围」下拉会读取它们并反向触发点击。 */
function buildWinSwitch(){
  const el=document.getElementById('winSwitch');
  if(!el) return;
  const opt=(n,label)=>'<button type="button" class="wbtn'+(SEASON_WIN===n?' on':'')+'" data-win="'+n+
    '">'+label+'</button>';
  el.innerHTML='<span class="wlab"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/></svg>范围</span>'+
    opt(5,'近五季')+opt(3,'近三季');
  el.querySelectorAll('[data-win]').forEach(b=>{ b.onclick=()=>setWin(+b.getAttribute('data-win')); });
}
function setWin(n){
  if(n!==3 && n!==5) return;
  SEASON_WIN=n;
  // 当前赛季若被窗口裁掉，自动落到窗口内最新一季
  if(currentLeague!=='__all__'){
    const ws=winSeasons(leagueOf(currentLeague));
    if(ws.indexOf(currentSeason)<0) currentSeason=ws[0];
  }
  syncGoalUrl(false);
  renderAfterEnsure();
}

function maxBucket(sc){
  // 守卫：sc 可能是 shell 里的 stub（scope_stub 剥掉了 teams/buckets 两个重数组键），
  // 也可能当前季 chunk 尚未加载。此时返回 0 而不是抛错 —— 抛错会中断整个 render()，
  // 页面变成白屏。正常路径下 currentSeason 已由 normalizeSeason() 保证落在窗口内、
  // 且 render() 开头的兜底已确保对应 chunk 已加载，这里只是最后一道防线。
  if(!sc || !sc.buckets) return 0;
  return Math.max(...BUCKETS.map(b=>sc.buckets[b]||0));
}
// 平均每轮出现几场：单轮有 队数/2 场（双循环），故 轮次 = 已赛场次 ÷ (队数/2)。
// 赛季未打完时轮次可能是小数（如西甲 2026-27 只踢了 14 场 ≈ 1.4 轮），用实际值算更贴近真实节奏。
function roundsOf(sc){
  // 必须用 teamCount（完整参赛队数），不能用 teams.length——
  // 后者只含"已踢过球的队"，进行中赛季会偏少，导致轮次被高估
  var n=sc.teamCount || (sc.teams && sc.teams.length) || 0;
  var per=n/2;
  return (per>0 && sc.totalMatches>0) ? (sc.totalMatches/per) : 0;
}
function perRound(sc,c){ var r=roundsOf(sc); return r>0 ? (c/r) : null; }

function renderOverview(){
  const lg=leagueOf(currentLeague); const sc=lg.scopes[currentSeason];
  const total=sc.totalMatches; const maxv=maxBucket(sc);
  const idx=lg.order.indexOf(currentSeason);
  const prevKey = (idx>=0 && idx+1<lg.order.length) ? lg.order[idx+1] : null;
  const prevSc = prevKey ? lg.scopes[prevKey] : null;
  const prevLabel = prevKey ? dispSeason(prevKey) : '';
  // 悬停提示内容构造器：占比环比 / 场/轮环比，与「场均进球」的 ▲▼ 悬停同一套交互
  const deltaHTML=(d,digits,unit)=>{
    const ar=d>0?'↑':(d<0?'↓':'—');
    const cl=d>0?'var(--green)':(d<0?'#e74c3c':'var(--text-muted)');
    return '变化：<span style="color:'+cl+'">'+ar+' '+(d>0?'+':'')+d.toFixed(digits)+unit+'</span>';
  };
  const pctTip=i=>{
    if(!prevSc) return '<b>'+LABELS[i]+'</b><br>无上一赛季数据可比';
    const b=BUCKETS[i], pt=prevSc.totalMatches||0;
    const pv=pt?prevSc.buckets[b]/pt*100:0, cv=total?sc.buckets[b]/total*100:0;
    const d=+(cv-pv).toFixed(1);
    return '<b>'+LABELS[i]+' · 占比环比 '+prevLabel+'</b><br>'
      +'上赛季：<b>'+prevSc.buckets[b]+'</b> 场（'+pv.toFixed(1)+'%）<br>'
      +'本赛季：<b>'+sc.buckets[b]+'</b> 场（'+cv.toFixed(1)+'%）<br>'+deltaHTML(d,1,' 个百分点');
  };
  const prTip=i=>{
    if(!prevSc) return '<b>'+LABELS[i]+'</b><br>无上一赛季数据可比';
    const b=BUCKETS[i];
    const pv=perRound(prevSc,prevSc.buckets[b]), cv=perRound(sc,sc.buckets[b]);
    if(pv===null||cv===null) return '<b>'+LABELS[i]+'</b><br>上一赛季无场次数据';
    const d=+(cv-pv).toFixed(2);
    return '<b>'+LABELS[i]+' · 场/轮环比 '+prevLabel+'</b><br>'
      +'上赛季：<b>'+pv.toFixed(2)+'</b> 场/轮<br>'
      +'本赛季：<b>'+cv.toFixed(2)+'</b> 场/轮<br>'+deltaHTML(d,2,' 场/轮');
  };
  let rows='';
  const fmtPR=v=> (v===null||v===undefined) ? '—' : (v.toFixed(2)+' 场/轮');
  BUCKETS.forEach((b,i)=>{
    const c=sc.buckets[b]; const pct=total?c/total*100:0; const w=maxv?(c/maxv*100):0;
    rows+='<tr><td class="left" style="font-weight:600">'+LABELS[i]+'</td>'
      +'<td class="bignum">'+c+'</td>'
      +'<td><div class="bar-wrap"><div class="bar" style="width:'+w.toFixed(1)+'%"></div>'
      +'<span class="pct cmp-able" data-t="'+i+'">'+pct.toFixed(1)+'%</span>'
      +'<span class="per-round cmp-able" data-t="'+i+'">'+fmtPR(perRound(sc,c))+'</span></div></td></tr>';
  });
  rows+='<tr style="background:var(--card2)"><td class="left" style="font-weight:700;color:var(--text-strong)">合计</td>'
    +'<td class="bignum" style="color:var(--text-strong)">'+total+'</td>'
    +'<td><div class="bar-wrap"><span class="pct" style="color:var(--text-strong)">100.0%</span>'
    +'<span class="per-round" style="color:var(--text-strong)">'+fmtPR(perRound(sc,total))+'</span></div></td></tr>';
  let avgCmp='';
  if(prevKey){
    const prevAvg=lg.scopes[prevKey].avgGoals;
    const d=+(sc.avgGoals-prevAvg).toFixed(2);
    const pp=prevAvg.toFixed(2), cc=sc.avgGoals.toFixed(2), dd=d.toFixed(2);
    if(d>0) avgCmp=' <span class="cmp-up avg-cmp" data-p="'+pp+'" data-c="'+cc+'" data-d="'+dd+'" data-dir="up">▲</span>';
    else if(d<0) avgCmp=' <span class="cmp-down avg-cmp" data-p="'+pp+'" data-c="'+cc+'" data-d="'+Math.abs(d).toFixed(2)+'" data-dir="down">▼</span>';
    else avgCmp=' <span class="cmp-eq avg-cmp" data-p="'+pp+'" data-c="'+cc+'" data-d="0.00" data-dir="eq">—</span>';
  }
  rows+='<tr style="background:var(--row-green-bg)"><td class="left" style="font-weight:700;color:var(--green)">场均进球</td>'
    +'<td class="bignum" style="color:var(--green)">'+sc.avgGoals.toFixed(2)+avgCmp+'</td><td><span class="pct" style="color:var(--green)">球/场</span></td></tr>';
  const flag=sc.note?'<span class="note-flag">'+sc.note+'</span>':'';
  document.getElementById('overview').innerHTML=
    '<div class="section-title">'+lg.cn+' · 总进球分布总览 — '+dispSeason(currentSeason)+flag+'</div>'
    +'<table class="ov-table"><thead><tr><th class="left">总进球</th><th>场次</th><th>占比 · 场/轮</th></tr></thead>'
    +'<tbody>'+rows+'</tbody></table>'
    +'<div class="ov-note">「场/轮」= 平均每轮出现几场。轮次 = 已赛场次 ÷ 每轮场数（每轮场数 = 球队数 ÷ 2）。'
    +'带虚线下划线的<b>占比</b>与<b>场/轮</b>可悬停查看与上一赛季的环比。</div>';
  const at=document.getElementById('avgTip');
  // 占比 / 场/轮 的环比悬停（与场均进球 ▲▼ 同一套 tooltip）
  const bindCmp=(sel,fn)=>{
    document.querySelectorAll('#overview '+sel+'[data-t]').forEach(el=>{
      el.addEventListener('mousemove',e=>{
        at.style.display='block'; at.style.left=(e.clientX+14)+'px'; at.style.top=(e.clientY+14)+'px';
        at.innerHTML=fn(+el.getAttribute('data-t'));
      });
      el.addEventListener('mouseleave',()=>{ at.style.display='none'; });
    });
  };
  bindCmp('.pct', pctTip);
  bindCmp('.per-round', prTip);
  document.querySelectorAll('#overview .avg-cmp').forEach(el=>{
    el.addEventListener('mousemove',e=>{
      at.style.display='block'; at.style.left=(e.clientX+14)+'px'; at.style.top=(e.clientY+14)+'px';
      // 与「占比 / 场·轮」的环比提示保持一致：变化块带颜色（↑绿 / ↓红 / —灰）
      const dir=el.getAttribute('data-dir');
      const abs=+el.getAttribute('data-d');       // data-d 存的是绝对值，按方向还原正负
      const signed = dir==='down' ? -abs : abs;
      at.innerHTML='<b>场均进球 · 环比上一赛季</b><br>上赛季：<b>'+el.getAttribute('data-p')+'</b> 球/场<br>本赛季：<b>'+el.getAttribute('data-c')+'</b> 球/场<br>'+deltaHTML(signed, 2, ' 球/场');
    });
    el.addEventListener('mouseleave',()=>{ at.style.display='none'; });
  });
}

function renderTeams(){
  const lg=leagueOf(currentLeague); const sc=lg.scopes[currentSeason];
  // 进入当季时若停留在历史赛季的「最大同时不出」排序键，复位回默认（该列在当季已移除）
  if(currentSeason===ONGOING_SEASON && teamSort.key==='gap23'){ teamSort={key:'rank',dir:1}; }
  const total=sc.totalMatches;
  // 升降级标记：两套数据集、两套字段来源，但**都直接读权威字段，不做任何推断**。
  //  · 次级联赛（promotion:true）：goals-champ 数据由 generator/build_champ_goals.py 从
  //    draws-champ 原样搬运，带 upTop / releg / demoted / fromTop / promo + 赛季级 moveFinal。
  //  · 五大联赛（promotion:false）：tools/sync_site.py 的 inject_promotion() 从 draws-big5
  //    原样搬运 promo / releg + 赛季级 moveFinal（2026-09-26 起）。
  //    → 此前这里是一套「上/下赛季名单差集 + 积分榜末 N 位」的三层退化推断，是全站唯一的
  //      推断式实现，且实测漏标 14 处：最早赛季（2021-22）没有上赛季可比，该季 5 个联赛的
  //      升班马**全部漏标**（13 处）；fr 2022-23 欧塞尔漏标降级（1 处）。该推断已删除。
  const moveFinal = sc.moveFinal !== false;
  let teams=sc.teams.slice();
  // 每队每轮只踢 1 场，故「已赛场次」= 经历轮次
  const roundsOfT = t => BUCKETS.reduce((s,bb)=>s+(t.b[bb]||0),0);
  const avgKey = (t,n) => { const r=roundsOfT(t); const c=(n===2?t.count2:t.count3); return (c&&r)? r/c : null; };
  // 进球数 / 失球数 / 净胜球数：从 seq23Matches 汇总。
  // 注意 score 的口径是「主客视角」= 主队进球-客队进球（不是球队视角！），
  // 必须按 ha 取自己那一侧，否则所有客场的进失球会整体颠倒。
  const goalsOf = t => {
    const ms = (t && t.seq23Matches) || [];
    let gf=0, ga=0;
    for (const m of ms) {
      const sp = String((m && m.score) || '').split('-');
      if (sp.length !== 2) continue;
      const a = +sp[0] || 0, b = +sp[1] || 0;
      if (m.ha === 'A') { gf += b; ga += a; }   // 客场：自己是后者
      else              { gf += a; ga += b; }   // 主场：自己是前者
    }
    return { gf, ga, gd: gf - ga };
  };
  const k=teamSort.key, dir=teamSort.dir;
  teams.sort((a,b)=>{
    let va,vb;
    if(k==='rank'){ va=a.rank; vb=b.rank; }
    else if(k==='total'){ va=a.total; vb=b.total; }
    else if(k==='gap2'){ va=a.gap2; vb=b.gap2; }
    else if(k==='gap3'){ va=a.gap3; vb=b.gap3; }
    else if(k==='gap23'){ va=a.gap23; vb=b.gap23; }
    else if(k==='warn23'){ va=trailingNot23(a.seq23); vb=trailingNot23(b.seq23); }
    else if(k==='gf'){ va=goalsOf(a).gf; vb=goalsOf(b).gf; }
    else if(k==='ga'){ va=goalsOf(a).ga; vb=goalsOf(b).ga; }
    else if(k==='gd'){ va=goalsOf(a).gd; vb=goalsOf(b).gd; }
    else if(k==='avg2'){ va=avgKey(a,2); vb=avgKey(b,2); }
    else if(k==='avg3'){ va=avgKey(a,3); vb=avgKey(b,3); }
    else if(k==='streak2'){ va=a.streak2; vb=b.streak2; }
    else if(k==='streak3'){ va=a.streak3; vb=b.streak3; }
    else { va=a.b[k]; vb=b.b[k]; }
    if(va==null) va=-1; if(vb==null) vb=-1;
    if(va!==vb) return dir*(va-vb);
    if(b.b['7+']!==a.b['7+']) return b.b['7+']-a.b['7+'];
    return a.rank-b.rank;
  });
  const arr = kk => (teamSort.key===kk ? (teamSort.dir<0?' ▼':' ▲') : '');
  let head='<tr><th class="sortable'+(teamSort.key==='rank'?' sorted':'')+'" data-k="rank">排名'+arr('rank')+'</th>'
    +'<th class="left">球队</th>';
  const hasSeq = sc.teams.some(t=>t.seq23 && t.seq23.length);
  // 「不出预警 / 快要🀄️了」列 + 「显示得失球」按钮：仅当季提供（历史赛季不显示、不收起、不加按钮）
  const showWarn = (currentSeason===ONGOING_SEASON);
  BUCKETS.forEach((b,i)=>{
    // 列太多时默认只保留 2 球 / 3 球两档，其余进球档折叠，点「展开明细」再看
    const hide = (!teamGoalsShowAll && i!==2 && i!==3);
    head+='<th class="sortable'+(String(teamSort.key)===String(b)?' sorted':'')+(hide?'" style="display:none':'')+'" data-k="'+b+'">'+LABELS[i]+arr(b)+'</th>';
  });
  // 进球数 / 失球数 / 净胜球（得失球）三列：仅当季默认收起（点「显示得失球」可展开/收起）；
  // 历史赛季始终展开，且不受 teamTotalsPinned 影响（历史赛季没有「显示得失球」按钮，不能让它们陷于收起态）
  const totalsShown = (currentSeason===ONGOING_SEASON) ? ((teamTotalsPinned===null)?false:teamTotalsPinned) : true;
  const thHide = totalsShown ? '' : ' style="display:none"';
  head+='<th class="sortable total-h'+(teamSort.key==='gf'?' sorted':'')+'" data-k="gf"'+thHide+'>进球数'+arr('gf')+'</th>';
  head+='<th class="sortable total-h'+(teamSort.key==='ga'?' sorted':'')+'" data-k="ga"'+thHide+'>失球数'+arr('ga')+'</th>';
  head+='<th class="sortable total-h'+(teamSort.key==='gd'?' sorted':'')+'" data-k="gd"'+thHide+'>净胜球'+arr('gd')+'</th>';
  if(showWarn){
    head+='<th class="sortable'+(teamSort.key==='warn23'?' sorted':'')+'" data-k="warn23" style="color:#e03131">快要🀄️了'+arr('warn23')+'</th>';
  }
  head+='<th class="sortable'+(teamSort.key==='gap2'?' sorted':'')+'" data-k="gap2">不出2球'+arr('gap2')+'</th>';
  head+='<th class="sortable'+(teamSort.key==='gap3'?' sorted':'')+'" data-k="gap3">不出3球'+arr('gap3')+'</th>';
  if(currentSeason!==ONGOING_SEASON){ head+='<th class="sortable'+(teamSort.key==='gap23'?' sorted':'')+'" data-k="gap23">最大同时不出'+arr('gap23')+'</th>'; }
  if(hasSeq){
    head+='<th class="sortable b2-h'+(teamSort.key==='avg2'?' sorted':'')+'" data-k="avg2">平均出2球'+arr('avg2')+'</th>';
    head+='<th class="sortable b3-h'+(teamSort.key==='avg3'?' sorted':'')+'" data-k="avg3">平均出3球'+arr('avg3')+'</th>';
    head+='<th class="sortable b2-h'+(teamSort.key==='streak2'?' sorted':'')+'" data-k="streak2">连续2球'+arr('streak2')+'</th>';
    head+='<th class="sortable b3-h'+(teamSort.key==='streak3'?' sorted':'')+'" data-k="streak3">连续3球'+arr('streak3')+'</th>';
  }
  head+='</tr>';
  let rows='';
  teams.forEach(t=>{
    const rkCls = (teamSort.key==='rank')?' col-sel':'';
    let mark='', nameHtml=t.cn, champ='';
    if(CFG.promotion){
      // 次级联赛：icon ＝ 本季「最终裁定」的去向（升入顶级 → 升；竞技降级 → 降；
      // 行政降级 → 降（琥珀色））；队名配色 ＝ 上季的来源（从顶级降入 → 红；
      // 从次次级联赛升入 → 绿）。字段与「平局统计 · 次级联赛」同源，绝不可用名单差集推断。
      if(moveFinal){
        if(t.upTop) mark+='<span class="move up">升</span>';
        if(t.releg) mark+='<span class="move down">降</span>';
        if(t.demoted) mark+='<span class="move adm">降</span>';
      }
      const nmCls = t.fromTop ? ' down-clr' : (t.promo ? ' up-clr' : '');
      nameHtml = '<span class="nm'+nmCls+'">'+t.cn+'</span>';
      champ = (t.rank===1 && moveFinal)?CHAMP_SVG:'';
    } else {
      // 五大联赛：直接读 draws-big5 搬来的权威字段（tools/sync_site.py: inject_promotion），
      // 与「平局统计 · 五大联赛」的 draws.js（CFG.promotion=false 分支）逐字一致：
      //   · promo —— 本季升班马（季初从下一级升入）；所有赛季都标，含进行中的当季
      //     （升班马一旦出场即可确认，不存在误判）
      //   · releg —— 本季结束后降出本联赛；仅在赛季已结束（moveFinal）时才标
      //   · 队名不着色：五大联赛没有「上季从顶级降入 / 从次次级升入」这两个来源，
      //     故不加 up-clr / down-clr（与 draws.js 一致，不要"顺手"补上配色）。
      if(t.promo) mark+='<span class="move up">升</span>';
      if(moveFinal && t.releg) mark+='<span class="move down">降</span>';
      champ = (moveFinal && t.rank===1)?CHAMP_SVG:'';
    }
    let cells='<td class="rk'+rkCls+'">'+t.rank+'</td><td class="left name">'+crestHtml(t.name,t.cn)+nameHtml+'<span class="pts-inline">'+t.pts+'</span>'+champ+mark+'</td>';
    BUCKETS.forEach((b,i)=>{
      const c=t.b[b];
      let tdcls=(String(teamSort.key)===String(b))?' col-sel':'';
      if(i===2) tdcls+=' col-2'; if(i===3) tdcls+=' col-3';
      const hide = (!teamGoalsShowAll && i!==2 && i!==3);
      cells+='<td class="'+tdcls.trim()+(hide?'" style="display:none':'')+'">'+c+'</td>';
    });
    // 进球数 / 失球数 / 净胜球数 三列：在数据驱动的循环里就地计算，可折叠
    const g = goalsOf(t);
    const gdCls = g.gd>0 ? ' gd-pos' : (g.gd<0 ? ' gd-neg' : ' gd-zero');
    const gdDisp = (g.gd>0?'+':'') + g.gd;
    const tdHide = totalsShown ? '' : ';display:none';
    cells+='<td class="'+(teamSort.key==='gf'?'col-sel':'')+'" style="text-align:center;font-weight:600'+tdHide+'">'+g.gf+'</td>';
    cells+='<td class="'+(teamSort.key==='ga'?'col-sel':'')+'" style="text-align:center;font-weight:600'+tdHide+'">'+g.ga+'</td>';
    cells+='<td class="'+(teamSort.key==='gd'?'col-sel':'')+gdCls+'" style="text-align:center;font-weight:700'+tdHide+'">'+gdDisp+'</td>';
    if(showWarn){
      // 不出预警（快要🀄️了）：目前连续多少轮（场）总进球既 ≠2 也 ≠3；≥5 标红加粗（无底色）
      const w23 = trailingNot23(t.seq23);
      const wHi = w23>=5 ? ';color:#c92a2a;font-weight:700' : '';
      cells+='<td class="gap-cell'+(teamSort.key==='warn23'?' col-sel':'')+'" style="text-align:center;font-weight:600'+wHi+'">'+w23+'</td>';
    }
    const g2=(t.gap2==null)?'—':t.gap2, g3=(t.gap3==null)?'—':t.gap3, g23=(t.gap23==null)?'—':t.gap23;
    cells+='<td class="gap-cell'+(teamSort.key==='gap2'?' col-sel':'')+'" style="text-align:center;font-weight:600">'+g2+'</td>';
    cells+='<td class="gap-cell'+(teamSort.key==='gap3'?' col-sel':'')+'" style="text-align:center;font-weight:600">'+g3+'</td>';
    if(currentSeason!==ONGOING_SEASON){ cells+='<td class="gap-cell'+(teamSort.key==='gap23'?' col-sel':'')+'" style="text-align:center;font-weight:600">'+g23+'</td>'; }
    if(hasSeq){
      // 注意：单元格顺序必须与表头一致（不出2球 / 不出3球 / 最大同时不出 / 平均出2球 / 平均出3球 / 连续2球 / 连续3球）
      const rnd=roundsOfT(t);
      const a2=(t.count2&&rnd)?(rnd/t.count2).toFixed(1):'—';
      const a3=(t.count3&&rnd)?(rnd/t.count3).toFixed(1):'—';
      cells+='<td class="'+(teamSort.key==='avg2'?'col-sel':'')+'">'+a2+'</td>';
      cells+='<td class="'+(teamSort.key==='avg3'?'col-sel':'')+'">'+a3+'</td>';
      cells+='<td class="'+(teamSort.key==='streak2'?'col-sel':'')+'" style="font-weight:600">'+(t.streak2==null?'—':t.streak2)+'</td>';
      cells+='<td class="'+(teamSort.key==='streak3'?'col-sel':'')+'" style="font-weight:600">'+(t.streak3==null?'—':t.streak3)+'</td>';
    }
    rows+='<tr>'+cells+'</tr>';
  });
  const flag=sc.note?'<span class="note-flag">'+sc.note+'</span>':'';
  // 图例文案（仅次级联赛用）：与「平局统计 · 次级联赛」逐字一致
  const colorTxt = '；<b style="color:#e74c3c">队名标红</b>＝上季从顶级联赛降入'+
                   '；<b style="color:var(--green)">队名标绿</b>＝上季从次次级联赛升入';
  const moveTxt = (moveFinal
    ? '；<span class="move up">升</span> 本季最终升级，下季升入顶级联赛'+
      '；<span class="move down">降</span> 本季竞技降级，下季降出本联赛'+
      (teams.some(t=>t.demoted)?'；<span class="move adm">降</span> 行政降级，非竞技原因':'')
    : '；本季尚在进行、下季升降名单未定，暂不标注升 / 降 icon')+colorTxt;
  document.getElementById('teams').innerHTML=
    '<div class="section-title">'+lg.cn+' · 各球队总进球分布'+flag
    +'<button class="gap-toggle" onclick="toggleTeamGoals()" style="margin-left:10px;padding:4px 12px;border:1px solid var(--border);background:var(--accent);color:#fff;font-size:12.5px;border-radius:8px;cursor:pointer;vertical-align:middle">'+ (teamGoalsShowAll?'隐藏 4–7+ 球列':'显示全部进球数')+'</button>'
    + (showWarn ? '<button class="gap-toggle" onclick="toggleTeamTotals()" style="margin-left:8px;padding:4px 12px;border:1px solid var(--border);background:var(--accent);color:#fff;font-size:12.5px;border-radius:8px;cursor:pointer;vertical-align:middle">'+ (totalsShown?'隐藏得失球':'显示得失球')+'</button>' : '') +'</div>'
    +'<table class="team-table"><thead>'+head+'</thead><tbody>'+rows+'</tbody></table>'
    + (CFG.promotion
       ? '<div class="note">'+(moveFinal?'🏆 当季冠军':'🏆 当前榜首')+moveTxt+'。</div>'
       : '');
  document.querySelectorAll('.team-table th.sortable').forEach(th=>{
    th.onclick=()=>{ const kk=th.getAttribute('data-k');
      if(teamSort.key===kk){ teamSort.dir*=-1; }
      else { teamSort.key=kk; const numeric = (kk!=='rank' && kk!=='name'); teamSort.dir = numeric ? -1 : 1; }
      renderTeams(); };
  });
}

let trendHidden = {}; // bucket index -> true 表示该曲线已隐藏
let trendMetric = 'count'; // 'count' = 场次（默认） | 'pct' = 占比

function fullSeason(s){ const p=String(s).split('-'); return p[0]+'-20'+p[1]; }
function dispSeason(s){ return fullSeason(s); }

function drawTrendChart(lg){
  const seasons=winSeasons(lg).slice().reverse(); // oldest -> newest (within window)
  const COLORS=['#4a9eff','#2ecc71','#ffd43b','#ff5252','#9b59ff','#1ab9c9','#ff9f43','#ff5fa2'];
  const allSeries=BUCKETS.map((b,i)=>{
    const count=seasons.map(s=>{ const sc=lg.scopes[s]; return sc.buckets[b]; });
    const pct=seasons.map(s=>{ const sc=lg.scopes[s]; const tot=sc.totalMatches||1; return sc.buckets[b]/tot*100; });
    return {i:i, color:COLORS[i], count:count, pct:pct};
  });
  const vis=allSeries.filter(s=>!trendHidden[s.i]);
  const valOf = s => trendMetric==='count' ? s.count : s.pct;
  let maxV=0; vis.forEach(s=>valOf(s).forEach(v=>{ if(v>maxV) maxV=v; }));
  let step;
  if(trendMetric==='pct'){ maxV=Math.ceil(maxV/5)*5; if(maxV<5) maxV=5; step=maxV/4; }
  else { maxV=Math.ceil(maxV/10)*10; if(maxV<10) maxV=10; step=maxV/4; }
  const W=880,H=400, ml=52,mr=18,mt=30,mb=54;
  const pw=W-ml-mr, ph=H-mt-mb, n=seasons.length;
  const X=i=> ml + (n===1?pw/2:pw*i/(n-1));
  const Y=v=> mt + ph*(1 - v/maxV);
  const isPct = trendMetric==='pct';
  let svg='<svg class="trend-svg" data-lg="'+lg.code+'" viewBox="0 0 '+W+' '+H+'" width="100%" style="max-width:'+W+'px;display:block">';
  svg+='<rect x="0" y="0" width="'+ml+'" height="'+H+'" fill="transparent" style="cursor:pointer" onclick="toggleTrendMetric()"></rect>';
  for(let g=0; g<=4; g++){
    const val=step*g, y=Y(val);
    svg+='<line x1="'+ml+'" y1="'+y+'" x2="'+(W-mr)+'" y2="'+y+'" style="stroke:var(--axis)" stroke-width="1"/>';
    svg+='<text x="'+(ml-10)+'" y="'+(y+4)+'" style="fill:var(--text-muted)" font-size="11" text-anchor="end">'+val.toFixed(0)+(isPct?'%':'球')+'</text>';
  }
  seasons.forEach((s,i)=>{
    let anchor='middle', lx=X(i);
    if(i===0){ anchor='start'; lx=ml; }
    else if(i===n-1){ anchor='end'; lx=W-mr; }
    svg+='<text x="'+lx+'" y="'+(H-mb+22)+'" style="fill:var(--text-dim)" font-size="12.5" text-anchor="'+anchor+'">'+fullSeason(s)+'</text>';
  });
  svg+='<text x="'+ml+'" y="18" style="fill:var(--text-strong);cursor:pointer" font-size="13" font-weight="600" onclick="toggleTrendMetric()">各总进球数 · '+(isPct?'占比':'场次')+'走势</text>';
  if(vis.length===0){
    svg+='<text x="'+(W/2)+'" y="'+(mt+ph/2)+'" style="fill:var(--text-muted)" font-size="14" text-anchor="middle">（全部曲线已隐藏，点击下方图例色块可恢复显示）</text>';
  } else {
    vis.forEach(s=>{
      const vals=valOf(s);
      const pts=vals.map((v,i)=>X(i)+','+Y(v)).join(' ');
      svg+='<polyline points="'+pts+'" style="stroke:'+s.color+';fill:none" stroke-width="2.6" stroke-linejoin="round" stroke-linecap="round"/>';
      vals.forEach((v,i)=>{
        svg+='<circle class="tp" cx="'+X(i)+'" cy="'+Y(v)+'" r="3.6" fill="'+s.color+'" '
          +'data-l="'+LABELS[s.i]+'" data-s="'+fullSeason(seasons[i])+'" data-c="'+s.count[i]+'" data-p="'+s.pct[i].toFixed(1)+'"/>';
      });
    });
  }
  svg+='</svg>';
  return svg;
}
function drawTrendLegend(){
  const COLORS=['#4a9eff','#2ecc71','#ffd43b','#ff5252','#9b59ff','#1ab9c9','#ff9f43','#ff5fa2'];
  let legend='<div class="legend">';
  BUCKETS.forEach((b,i)=>{ const off=trendHidden[i]?' off':''; legend+='<span class="lg-item'+off+'" data-i="'+i+'"><span class="sw" style="background:'+COLORS[i]+'"></span>'+LABELS[i]+'</span>'; });
  legend+='</div>';
  return legend;
}
let combMetric='count'; var trendSeason=null; var trendLeagueHidden={}; var trendBucketHidden={};
let combLeague='all', combBucket='both';
function renderCombinedChart(){
  var leagues=DATA.leagues;
  var seasons=leagues[0].order.filter(function(s){return s!==ONGOING_SEASON;}).sort().slice(-SEASON_WIN).reverse();
  var COLORS={en:'#e0142b',es:'#ff9f1c',it:'#2ecc71',de:'#4a9eff',fr:'#9b59ff'};
  var NAMES={en:'英超',es:'西甲',it:'意甲',de:'德甲',fr:'法甲'};
  if(!trendSeason || seasons.indexOf(trendSeason)<0) trendSeason=seasons[0];
  var pct= trendMetric==='pct';
  var visBuckets=BUCKETS.filter(function(b){return !trendBucketHidden[b];});
  var visLeagues=leagues.filter(function(lg){return !trendLeagueHidden[lg.code];});
  function cntOf(lg,b){var sc=lg.scopes[trendSeason];return (sc&&sc.buckets&&sc.buckets[b])||0;}
  function valOf(lg,b){var sc=lg.scopes[trendSeason];var n=(sc&&sc.totalMatches)||0;var c=cntOf(lg,b);return pct?(n? c/n*100:0):c;}
  var maxV=0; visLeagues.forEach(function(lg){visBuckets.forEach(function(b){var v=valOf(lg,b);if(v>maxV)maxV=v;});});
  maxV= pct? Math.ceil(maxV/5)*5 : Math.ceil(maxV/10)*10; if(maxV<=0) maxV= pct?5:10;
  var W=880,H=460,ml=54,mr=16,mt=34,mb=92,pw=W-ml-mr,ph=H-mt-mb;
  function Y(v){return mt+ph*(1-v/maxV);}
  var nG=visBuckets.length;
  var gw= nG? pw/nG : pw;
  var svg='<svg class="trend-svg comb-svg" viewBox="0 0 '+W+' '+H+'" width="100%" style="display:block;margin:0 auto" preserveAspectRatio="xMidYMid meet">';
  for(var g=0; g<=5; g++){var gv=maxV*g/5, gy=Y(gv); svg+='<line x1="'+ml+'" y1="'+gy.toFixed(1)+'" x2="'+(W-mr)+'" y2="'+gy.toFixed(1)+'" style="stroke:var(--axis)" stroke-width="1"/><text x="'+(ml-8)+'" y="'+(gy+4).toFixed(1)+'" style="fill:var(--text-muted)" font-size="11" text-anchor="end">'+gv.toFixed(0)+(pct?'%':'')+'</text>';}
  if(nG===0 || visLeagues.length===0){
    svg+='<text x="'+(W/2)+'" y="'+(mt+ph/2)+'" style="fill:var(--text-muted)" font-size="14" text-anchor="middle">（请至少选择一个进球档与联赛）</text>';
  } else {
    visBuckets.forEach(function(b,gi){
      var gx=ml+gw*gi;
      var innerW=gw-16;
      var nL=visLeagues.length;
      var bw=Math.min(36, innerW/nL*0.82);
      var totalW=bw*nL;
      var startX=gx+(gw-totalW)/2;
      visLeagues.forEach(function(lg,j){
        var v=valOf(lg,b); var h=Math.max(0, ph*v/maxV); var x=startX+bw*j; var y=Y(v);
        var c=cntOf(lg,b);
        svg+='<rect class="cb" x="'+x.toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+h.toFixed(1)+'" rx="3" fill="'+COLORS[lg.code]+'" data-code="'+lg.code+'" data-lg="'+NAMES[lg.code]+'" data-b="'+b+'" data-s="'+fullSeason(trendSeason)+'" data-n="'+c+'" data-v="'+v.toFixed(pct?1:0)+'" data-u="'+(pct?'%':'场')+'"><title>'+NAMES[lg.code]+' · '+fullSeason(trendSeason)+' · '+b+'球：'+c+(pct?'（'+v.toFixed(1)+'%）':'场')+'</title></rect>';
      });
      var lx=gx+gw/2;
      svg+='<text x="'+lx.toFixed(1)+'" y="'+(H-mb+22).toFixed(1)+'" style="fill:var(--text-dim)" font-size="12.5" text-anchor="middle">'+LABELS[BUCKETS.indexOf(b)]+'</text>';
    });
  }
  svg+='</svg>';
  var seasonBtns='<div class="comb-seasons">';
  seasons.forEach(function(s){ seasonBtns+='<button type="button" class="comb-season'+(s===trendSeason?' on':'')+'" data-s="'+s+'">'+fullSeason(s)+'</button>'; });
  seasonBtns+='</div>';
  var hint='<div class="note">选择赛季查看五大联赛各进球档分布；下方按钮可隐藏 / 显示进球档与联赛，颜色＝联赛。悬停柱形看精确场次与占比。</div>';
  var bkChips='<div class="comb-ctrl"><span class="comb-ctrl-label">进球档</span>';
  BUCKETS.forEach(function(b){var on=!trendBucketHidden[b]; bkChips+='<button type="button" class="comb-chip'+(on?' on':' off')+'" data-b="'+b+'">'+LABELS[BUCKETS.indexOf(b)]+'</button>';});
  bkChips+='</div>';
  var lgChips='<div class="comb-ctrl"><span class="comb-ctrl-label">联赛</span>';
  leagues.forEach(function(lg){var on=!trendLeagueHidden[lg.code]; var st=on?('background:'+COLORS[lg.code]+';border-color:transparent;color:#fff;'):''; lgChips+='<button type="button" class="comb-chip'+(on?' on':' off')+'" data-lg="'+lg.code+'" style="'+st+'">'+NAMES[lg.code]+'</button>';});
  lgChips+='</div>';
  var metricHtml='<span class="comb-metric"><a class="cm'+(!pct?' on':'')+'" data-m="count">场次</a><i>/</i><a class="cm'+(pct?' on':'')+'" data-m="pct">占比</a></span>';
  var head='<div class="section-title comb-head"><span>五大联赛 · 进球数分布对比</span>'+metricHtml+'</div>';
  var style='<style id="combStyle">'+'.comb-head{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;}.comb-metric{font-size:13.5px;font-weight:700;display:inline-flex;align-items:center;gap:6px;}.comb-metric .cm{color:var(--text-muted);cursor:pointer;text-decoration:none;padding:4px 10px;border-radius:9px;transition:all .15s;}.comb-metric .cm:hover{background:var(--col-sel-bg);}.comb-metric .cm.on{color:#fff;background:var(--accent);}.comb-metric i{color:var(--text-muted);font-style:normal;}.comb-seasons{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 4px;}.comb-season{padding:8px 16px;border-radius:11px;border:1px solid var(--border);background:var(--card);color:var(--text2);font-size:13.5px;font-weight:800;cursor:pointer;transition:all .16s;letter-spacing:.2px;}.comb-season:hover{transform:translateY(-1px);border-color:var(--accent);}.comb-season.on{background:linear-gradient(90deg,#2f7bdc,#4a9eff);color:#fff;border-color:transparent;box-shadow:0 5px 14px rgba(47,123,220,.30);}.comb-ctrl{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:12px 0 2px;}.comb-ctrl-label{font-size:12.5px;color:var(--text-muted);font-weight:700;margin-right:2px;}.comb-chip{padding:6px 13px;border-radius:18px;border:1px solid var(--border);background:var(--card2);color:var(--text2);font-size:13px;font-weight:700;cursor:pointer;transition:all .15s;user-select:none;line-height:1.2;}.comb-chip:hover{transform:translateY(-1px);}.comb-chip.off{opacity:.4;text-decoration:line-through;}.comb-chip.on{color:#fff;border-color:transparent;background:var(--accent);}.comb-svg .cb{cursor:pointer;transition:opacity .12s;}.comb-svg .cb:hover{opacity:.82;}'+'</style>';
  document.getElementById('trend').innerHTML=head+hint+seasonBtns+style+svg+bkChips+lgChips+'<div class="trend-tip" id="combTip"></div>';
  document.querySelectorAll('#trend .comb-season').forEach(function(b){b.onclick=function(){trendSeason=b.getAttribute('data-s'); renderCombinedChart();};});
  document.querySelectorAll('#trend .comb-chip[data-b]').forEach(function(b){b.onclick=function(){var k=b.getAttribute('data-b'); if(trendBucketHidden[k]) delete trendBucketHidden[k]; else trendBucketHidden[k]=true; renderCombinedChart();};});
  document.querySelectorAll('#trend .comb-chip[data-lg]').forEach(function(b){b.onclick=function(){var c=b.getAttribute('data-lg'); if(trendLeagueHidden[c]) delete trendLeagueHidden[c]; else trendLeagueHidden[c]=true; renderCombinedChart();};});
  document.querySelectorAll('#trend .comb-metric .cm').forEach(function(a){a.onclick=function(e){e.preventDefault(); trendMetric=a.getAttribute('data-m'); renderCombinedChart();};});
  var tip=document.getElementById('combTip');
  document.querySelectorAll('#trend .cb').forEach(function(r){
    r.addEventListener('mousemove',function(e){tip.style.display='block'; var cx=e.clientX, cy=e.clientY; if(cx==null&&e.touches&&e.touches[0]){cx=e.touches[0].clientX;cy=e.touches[0].clientY;} tip.style.left=(cx+14)+'px'; tip.style.top=(cy+14)+'px'; tip.innerHTML='<b style="color:'+COLORS[r.getAttribute('data-code')]+'">'+r.getAttribute('data-lg')+'</b> · '+r.getAttribute('data-s')+'<br>'+r.getAttribute('data-b')+'球：<b>'+r.getAttribute('data-n')+'</b> 场'+(pct?'（'+r.getAttribute('data-v')+'%）':'');});
    r.addEventListener('mouseleave',function(){tip.style.display='none';});
  });
}



function playTrendAnim(){
  var pls=document.querySelectorAll('.trend-svg polyline');
  var dots=document.querySelectorAll('.trend-svg circle.tp');
  if(!pls.length) return;
  pls.forEach(function(pl){
    var nat=pl.getAttribute('stroke-dasharray');
    if(nat && nat!=='none'){ pl.style.transition='none'; pl.style.opacity=0; return; }
    var L=pl.getTotalLength(); pl.style.transition='none'; pl.style.strokeDasharray=L; pl.style.strokeDashoffset=L;
  });
  dots.forEach(function(d){ d.style.transition='none'; d.style.opacity=0; });
  var host=document.querySelector('.trend-svg'); if(host) host.getBoundingClientRect();
  pls.forEach(function(pl){
    var nat=pl.getAttribute('stroke-dasharray');
    if(nat && nat!=='none'){ pl.style.transition='opacity .7s ease'; pl.style.opacity=1; return; }
    pl.style.transition='stroke-dashoffset 1.8s ease'; pl.style.strokeDashoffset=0;
  });
  dots.forEach(function(d){ d.style.transition='opacity .7s ease 1.0s'; d.style.opacity=1; });
}

function seqVisibleTeams(sc){
  return sc.teams.slice().sort(function(a,b){return a.rank-b.rank;});
}
function seqStripsHtml(teams){
  var cnMap={}; teams.forEach(function(t){cnMap[t.name]=t.cn;}); var strips='';
  teams.forEach(function(t){
    var hidden=!!seqHidden[t.name];
    var cells='';
    (t.seq23||[]).forEach(function(v,idx){
      var cls=' s0';
      if(v===2&&seqShow2) cls=' s2';
      else if(v===3&&seqShow3) cls=' s3';
      var gm=t.seq23Matches&&t.seq23Matches[idx]||{};
      var oppCn=cnMap[gm.opponent]||gm.opponent;
      cells+='<i class="sq'+cls+' seq-score-cell" data-home="'+(t.cn||t.name)+'" data-away="'+oppCn+'" data-score="'+(gm.score||'')+'" data-date="'+(gm.date||'')+'" data-round="'+(gm.round||(idx+1))+'" data-ha="'+(gm.ha||'H')+'" data-season="'+currentSeason+'"></i>';
    });
    var vis=hidden?' 隐藏':' 显示';
    strips+='<div class="seq-row'+(hidden?' seq-hidden':'')+'">'
      +'<button type="button" class="seq-name seq-team-toggle'+(hidden?'':' on')+'" data-t="'+t.name+'" aria-pressed="'+(!hidden)+'">'
      +crestHtml(t.name,t.cn)+'<span>'+t.cn+'</span><small class="seq-eye">'+vis+'</small></button>'
      +'<div class="seq-strip"'+(hidden?' style="display:none"':'')+'>'+cells+'</div>'
      +'<span class="seq-cnt">2球 '+(t.count2||0)+' · 3球 '+(t.count3||0)+'</span></div>';
  });
  return strips||'<div class="ov-note" style="padding:10px">没有符合筛选条件的球队。</div>';
}
function updateSeqStrips(sc){
  var box=document.getElementById('seqStrips'); if(!box)return;
  var vis=seqVisibleTeams(sc); box.innerHTML=seqStripsHtml(vis);
  var shown=vis.filter(function(t){return !seqHidden[t.name];}).length;
  var cnt=document.getElementById('seqCount'); if(cnt)cnt.textContent='显示 '+shown+' / '+sc.teams.length+' 支球队';
  box.querySelectorAll('.seq-team-toggle').forEach(function(btn){
    btn.onclick=function(){var nm=btn.getAttribute('data-t');
      if(seqHidden[nm]) delete seqHidden[nm]; else seqHidden[nm]=true;
      updateSeqStrips(sc);
    };
  });
  bindSeqScoreTips(box);
}
/* 各队 2 球 / 3 球走势色块悬停：展示该场比分信息，格式对齐平局统计页的悬浮框。
   色块已自带 data-home / data-away / data-score / data-date / data-round / data-ha。
   score 口径为「主客视角」(主队-客队)，故客场时与平局页一致翻转为主队在前。 */
function bindSeqScoreTips(box){
  var tip=document.getElementById('combTip');
  if(!tip){
    // 进球数分布对比图未渲染时 #combTip 尚不存在，这里按需补一个，保证悬浮框始终有容器
    tip=document.createElement('div');
    tip.id='combTip';
    tip.className='trend-tip';
    document.body.appendChild(tip);
  }
  box.querySelectorAll('.seq-score-cell').forEach(function(el){
    el.addEventListener('mousemove', function(e){
      var home=el.getAttribute('data-home')||'', away=el.getAttribute('data-away')||'';
      var sc=el.getAttribute('data-score')||'', dt=el.getAttribute('data-date')||'';
      var rn=el.getAttribute('data-round')||'', ha=el.getAttribute('data-ha')||'H';
      var season=el.getAttribute('data-season')||currentSeason;
      tip.style.display='block';
      var line=home+' <b>'+sc+'</b> '+away;
      var sp=String(sc).split('-');
      // score 是「主客视角」= 主队进球-客队进球。客场时对手才是主队，把对手排到前面后，
      // 比分必须仍是 sp[0]-sp[1]（主队在前），不能再翻一次，否则读出来本队进球数正好相反。
      if(ha==='A' && sp.length===2) line=away+' <b>'+sp[0]+'-'+sp[1]+'</b> '+home;
      var body='<b>第 '+rn+' 轮</b> · '+dt+' · '+(ha==='H'?'主场':'客场');
      if(sc) body+='<br>'+line;
      tip.innerHTML=body;
      var x=e.clientX+14, y=e.clientY+14;
      tip.style.left=x+'px'; tip.style.top=y+'px';
      var r=tip.getBoundingClientRect(), pad=8;
      if(x+r.width>window.innerWidth-pad)  x=Math.max(pad, window.innerWidth-r.width-pad);
      if(y+r.height>window.innerHeight-pad) y=Math.max(pad, window.innerHeight-r.height-pad);
      tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    el.addEventListener('mouseleave', function(){ tip.style.display='none'; });
  });
}
function seqVisibleTeams(sc){
  return sc.teams.slice().sort(function(a,b){return a.rank-b.rank;});
}
function seqStripsHtml(teams){
  var cnMap={}; teams.forEach(function(t){cnMap[t.name]=t.cn;}); var strips='';
  teams.forEach(function(t){
    var hidden=!!seqHidden[t.name];
    var cells='';
    (t.seq23||[]).forEach(function(v,idx){
      var cls=' s0';
      if(v===2&&seqShow2) cls=' s2';
      else if(v===3&&seqShow3) cls=' s3';
      var gm=t.seq23Matches&&t.seq23Matches[idx]||{};
      var oppCn=cnMap[gm.opponent]||gm.opponent;
      cells+='<i class="sq'+cls+' seq-score-cell" data-home="'+(t.cn||t.name)+'" data-away="'+oppCn+'" data-score="'+(gm.score||'')+'" data-date="'+(gm.date||'')+'" data-round="'+(gm.round||(idx+1))+'" data-ha="'+(gm.ha||'H')+'" data-season="'+currentSeason+'"></i>';
    });
    var vis=hidden?' 隐藏':' 显示';
    strips+='<div class="seq-row'+(hidden?' seq-hidden':'')+'">'
      +'<button type="button" class="seq-name seq-team-toggle'+(hidden?'':' on')+'" data-t="'+t.name+'" aria-pressed="'+(!hidden)+'">'
      +crestHtml(t.name,t.cn)+'<span>'+t.cn+'</span><small class="seq-eye">'+vis+'</small></button>'
      +'<div class="seq-strip"'+(hidden?' style="display:none"':'')+'>'+cells+'</div>'
      +'<span class="seq-cnt">2球 '+(t.count2||0)+' · 3球 '+(t.count3||0)+'</span></div>';
  });
  return strips||'<div class="ov-note" style="padding:10px">没有符合筛选条件的球队。</div>';
}
function updateSeqStrips(sc){
  var box=document.getElementById('seqStrips'); if(!box)return;
  var vis=seqVisibleTeams(sc); box.innerHTML=seqStripsHtml(vis);
  var shown=vis.filter(function(t){return !seqHidden[t.name];}).length;
  var cnt=document.getElementById('seqCount'); if(cnt)cnt.textContent='显示 '+shown+' / '+sc.teams.length+' 支球队';
  box.querySelectorAll('.seq-team-toggle').forEach(function(btn){
    btn.onclick=function(){var nm=btn.getAttribute('data-t');
      if(seqHidden[nm]) delete seqHidden[nm]; else seqHidden[nm]=true;
      updateSeqStrips(sc);
    };
  });
  bindSeqScoreTips(box);
}
function renderSeq23(){
  var el=document.getElementById('seq23'); if(!el)return;
  if(currentLeague==='__all__'||SEQ_SEASONS.indexOf(currentSeason)<0){el.innerHTML='';return;}
  var lg=leagueOf(currentLeague),sc=lg.scopes[currentSeason]; if(!sc||!sc.teams.some(function(t){return t.seq23&&t.seq23.length;})){el.innerHTML='';return;}
  seqHidden={};
  el.innerHTML='<div class="section-title">'+lg.cn+' '+fullSeason(currentSeason)+' · 各队 2 球 / 3 球走势分布</div>'
    +'<div class="note">每条色带按时间顺序显示该队逐场总进球：2 球、3 球及其他。量化指标已并入上方球队表，可点表头或排序条排序；直接点击每条色带左侧球队名称，可显示或隐藏该球队。</div>'
    +'<div class="seq-filter"><button type="button" class="seq-tg'+(seqShow2?' on':'')+'" data-b="2">2 球</button><button type="button" class="seq-tg'+(seqShow3?' on':'')+'" data-b="3">3 球</button></div>'
    +'<div class="seq-strips" id="seqStrips"></div>';
  el.querySelectorAll('.seq-tg[data-b]').forEach(function(btn){btn.onclick=function(){var b=btn.getAttribute('data-b');if(b==='2')seqShow2=!seqShow2;else seqShow3=!seqShow3;btn.classList.toggle('on');updateSeqStrips(sc);};});
  updateSeqStrips(sc);
}


// ---------- goals 按季 chunk 懒加载（弱网/离线优先）----------
// 首屏所需 chunk 已由文件顶部提前预取（页面 HTML 不再写死赛季）。
// （_chunkInflight / _chunkRenderToken 已在文件顶部随预取一起声明）
function _dataDir(){ return (window.SITE_ROOT || '') + 'assets/js/data/' + CFG.group + '/'; }
function isChunkLoaded(name){
  var m = /^([^/]+)\/(.+)\.js$/.exec(name);
  var code = m ? m[1] : currentLeague;
  var season = m ? m[2] : name.replace(/\.js$/, '');
  // 按“联赛 + 赛季”校验，弱网下只需请求当前联赛的小 chunk。
  var L = leagueOf(code) || DATA.leagues[0];
  return !!(L && L.scopes && L.scopes[season] && L.scopes[season].teams);
}
function _chunkStatus(message, retry){
  var el = document.getElementById('chunkStatus');
  if(!el){
    el = document.createElement('div');
    el.id = 'chunkStatus';
    el.style.cssText = 'position:fixed;top:10px;left:50%;transform:translateX(-50%);z-index:9999;max-width:calc(100% - 32px);padding:8px 12px;border-radius:8px;background:#fff8e1;color:#7a4e00;box-shadow:0 2px 10px rgba(0,0,0,.12);font:13px/1.4 system-ui,sans-serif;text-align:center;';
    document.body.appendChild(el);
  }
  el.textContent = message || '';
  if(retry){
    var b = document.createElement('button');
    b.type = 'button'; b.textContent = '重试'; b.style.cssText = 'margin-left:8px;padding:2px 8px;cursor:pointer;';
    b.onclick = retry; el.appendChild(b);
  }
  el.style.display = message ? '' : 'none';
}
function _loadChunk(name, done){
  if(isChunkLoaded(name)){ done(true); return; }
  if(_chunkInflight[name]){ _chunkInflight[name].push(done); return; }
  _chunkInflight[name] = [done];
  var sc = document.createElement('script'), ended = false;
  function finish(ok){
    if(ended) return; ended = true; clearTimeout(timer);
    var list = _chunkInflight[name] || []; delete _chunkInflight[name];
    list.forEach(function(cb){ cb(!!ok && isChunkLoaded(name)); });
  }
  var timer = setTimeout(function(){ finish(false); }, 15000);
  sc.src = _dataDir() + name;
  sc.onload = function(){ finish(true); };
  sc.onerror = function(){ finish(false); };
  document.head.appendChild(sc);
}
function ensureChunks(names, done){
  var pending = [], seen = {};
  (names || []).forEach(function(n){ if(!seen[n] && !isChunkLoaded(n)){ seen[n]=1; pending.push(n); } });
  if(!pending.length){ done(true); return; }
  var left = pending.length, ok = true;
  pending.forEach(function(name){ _loadChunk(name, function(got){ ok = ok && got; if(--left === 0) done(ok); }); });
}
function neededChunks(){
  var need = [];
  if(currentLeague === '__all__'){
    DATA.leagues.forEach(function(L){ (L.order || []).forEach(function(k){ need.push(L.code + '/' + k + '.js'); }); });
  } else {
    var lg = (typeof leagueOf === 'function' ? leagueOf(currentLeague) : null) || DATA.leagues[0];
    var order = lg.order || [];
    var idx = order.indexOf(currentSeason);
    if(idx >= 0){
      if(idx-1 >= 0) need.push(currentLeague + '/' + order[idx-1] + '.js');
      if(idx+1 < order.length) need.push(currentLeague + '/' + order[idx+1] + '.js');
    }
    need.push(currentLeague + '/' + currentSeason + '.js');
  }
  var seen = {};
  return need.filter(function(n){ if(seen[n]) return false; seen[n] = 1; return true; });
}
function renderAfterEnsure(){
  normalizeSeason();
  var token = ++_chunkRenderToken;
  var need = neededChunks();
  if(need.every(function(n){ return isChunkLoaded(n); })){ _chunkStatus(''); render(); return; }
  _chunkStatus('正在加载所选数据，当前内容保持不变…');
  ensureChunks(need, function(ok){
    if(token !== _chunkRenderToken) return;
    if(ok && need.every(function(n){ return isChunkLoaded(n); })){ _chunkStatus(''); render(); }
    else { _chunkStatus('网络较慢，数据未切换。请重试。', renderAfterEnsure); }
  });
}
// 弱网下不并发预取全部历史数据：首屏后只低频预取一个相邻 chunk，避免抢占用户点击。
function _preloadRest(){
  var rest = [];
  var lists = [];
  if(currentLeague === '__all__'){ DATA.leagues.forEach(function(L){ lists.push(L.order || []); }); }
  else { var lg = (typeof leagueOf === 'function' ? leagueOf(currentLeague) : null) || DATA.leagues[0]; lists.push(lg.order || []); }
  if(currentLeague === '__all__'){
    DATA.leagues.forEach(function(L){ (L.order || []).forEach(function(k){ var name=L.code+'/'+k+'.js'; if(!isChunkLoaded(name)) rest.push(name); }); });
  } else {
    lists.forEach(function(order){
      (order||[]).forEach(function(k){
        var name = currentLeague + '/' + k + '.js';
        if(!isChunkLoaded(name)) rest.push(name);
      });
    });
  }
  if(!rest.length) return;
  setTimeout(function(){ ensureChunks([rest[0]], function(){}); }, 8000);
}

function render(){
  // 兜底：当前季数据尚未加载（只有 shell stub）时先补齐再渲染，绝不带着 undefined 渲染。
  // normalizeSeason() 在此再调一次，覆盖「不经 renderAfterEnsure 直接调 render()」的路径。
  normalizeSeason();
  if(currentLeague!=='__all__' && !isChunkLoaded(currentLeague+'/'+currentSeason+'.js')){
    renderAfterEnsure(); return;
  }
  buildLeagueTabs(); buildSeasonTabs(); buildWinSwitch();
  if(currentLeague==='__all__'){
    document.getElementById('seasonTabs').style.display='none';
    document.getElementById('overview').innerHTML='';
    document.getElementById('teams').innerHTML='';
    document.getElementById('seq23').innerHTML='';
    renderCombinedChart();
  } else {
    document.getElementById('seasonTabs').style.display='';
    renderOverview(); renderTeams();
    document.getElementById('trend').innerHTML='';
    renderSeq23();
  }
}
function applyGoalUrl(){
  var u = window.FD_URL ? window.FD_URL.read() : {};
  if(_validGoalLeague(u.league)) currentLeague = u.league;
  var lg = currentLeague === '__all__' ? DATA.leagues[0] : leagueOf(currentLeague);
  if(u.season && lg && (lg.order || []).indexOf(u.season) >= 0) currentSeason = u.season;
  if(u.win === '3' || u.win === '5') SEASON_WIN = +u.win;
  syncGoalUrl(true);
  renderAfterEnsure();
}
window.addEventListener('popstate', applyGoalUrl);
syncGoalUrl(true);
renderAfterEnsure(); _preloadRest();
(function(){
  const el=document.getElementById('trend');
  if(!el) return;
  if(!('IntersectionObserver' in window)){ playTrendAnim(); return; }
  const ob=new IntersectionObserver(function(es){
    es.forEach(function(e){ if(e.isIntersecting){ playTrendAnim(); } });
  }, {threshold:0.2});
  ob.observe(el);
})();

(function(){
  const toTop=document.getElementById('toTop');
  const toBottom=document.getElementById('toBottom');
  function onScroll(){
    const y=window.scrollY||document.documentElement.scrollTop;
    const h=document.documentElement.scrollHeight;
    const vh=window.innerHeight;
    const atTop = y < 40;
    const atBottom = (y + vh) >= (h - 40);
    if(toTop) toTop.classList.toggle('hide', atTop);
    if(toBottom) toBottom.classList.toggle('hide', atBottom);
  }
  window.addEventListener('scroll', onScroll, {passive:true});
  window.addEventListener('resize', onScroll);
  onScroll();
})();

// 页脚：填上「本页最近更新」（统一读站点 meta.js 的 SITE_META，
// 与平局统计页同一份账本，保证几页时间永远一致；generated 由每次提交刷新）
(function(){
  const set = (id, v) => { const el = document.getElementById(id); if(el) el.textContent = (v && v !== '–') ? v : '–'; };
  set('ftGen', (window.SITE_META && window.SITE_META.generated) || '');
})();
