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
let currentLeague = DATA.leagues[0].code;
let currentSeason = defaultSeason(DATA.leagues[0]);
let teamSort = {key:'rank', dir:1};
let teamGoalsShowAll = false;
function toggleTeamGoals(){ teamGoalsShowAll = !teamGoalsShowAll; renderTeams(); }
// 2/3 球走势面板筛选状态：关键词、2 球 / 3 球开关、被隐藏的球队
let seqQuery = '', seqShow2 = true, seqShow3 = true, seqHidden = {};

// 跨赛季统计口径：近五季 / 近三季（与平局页一致，由外壳顶部「范围」下拉菜单驱动）
let SEASON_WIN = 5;
// lg.order 为「新 → 旧」，取最近 N 季；进行中的最新季天然落在最前，始终在窗口内
function winSeasons(lg){ return (lg && lg.order ? lg.order : []).slice(0, SEASON_WIN); }

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
    b.onclick=()=>{ currentLeague=l.code; currentSeason=defaultSeason(l); render(); };
    el.appendChild(b);
  });
  const all=document.createElement('div');
  all.className='league-tab big5'+('__all__'===currentLeague?' active':'');
  all.innerHTML='<svg class="uefa-logo" viewBox="0 0 30 18" aria-label="UEFA"><rect x="0" y="0" width="30" height="18" rx="3" fill="#0a1f44"/><text x="15" y="12.5" font-family="Arial,Helvetica,sans-serif" font-size="9" font-weight="800" fill="#fff" text-anchor="middle" letter-spacing="0.5">UEFA</text></svg><span>五大联赛</span><span class="rt">对照</span>';
  all.onclick=()=>{ currentLeague='__all__'; render(); };
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
    b.onclick=()=>{ currentSeason=k; render(); };
    el.appendChild(b);
  });
}

/* 赛季范围开关：近五季 ⇄ 近三季（与平局页同一套分段开关交互）。
   页面只负责把按钮渲染进 #winSwitch，外壳顶部「范围」下拉会读取它们并反向触发点击。 */
function buildWinSwitch(){
  const el=document.getElementById('winSwitch');
  if(!el) return;
  const opt=(n,label)=>'<button type="button" class="wbtn'+(SEASON_WIN===n?' on':'')+'" data-win="'+n+
    '" title="跨赛季统计口径切换为最近 '+n+' 个赛季">'+label+'</button>';
  el.innerHTML='<span class="wlab" title="跨赛季统计的赛季范围"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/></svg>范围</span>'+
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
  render();
}

function maxBucket(sc){ return Math.max(...BUCKETS.map(b=>sc.buckets[b])); }
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
  const total=sc.totalMatches;
  const idx=lg.order.indexOf(currentSeason);
  const prevKey = (idx>=0 && idx+1<lg.order.length) ? lg.order[idx+1] : null;
  const nextKey = (idx>0) ? lg.order[idx-1] : null;
  const teamSetOf = s => new Set(lg.scopes[s].teams.map(t=>t.name));
  const prevSet = prevKey ? teamSetOf(prevKey) : null;
  const nextSet = nextKey ? teamSetOf(nextKey) : null;
  let teams=sc.teams.slice();
  // 每队每轮只踢 1 场，故「已赛场次」= 经历轮次
  const roundsOfT = t => BUCKETS.reduce((s,bb)=>s+(t.b[bb]||0),0);
  const avgKey = (t,n) => { const r=roundsOfT(t); const c=(n===2?t.count2:t.count3); return (c&&r)? r/c : null; };
  // 进球数 / 失球数 / 净胜球数：直接从 seq23Matches 汇总（每条 score 都是已规范化的球队视角）
  const goalsOf = t => {
    const ms = (t && t.seq23Matches) || [];
    let gf=0, ga=0;
    for (const m of ms) {
      const sp = String((m && m.score) || '').split('-');
      if (sp.length === 2) { gf += +sp[0] || 0; ga += +sp[1] || 0; }
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
  BUCKETS.forEach((b,i)=>{
    // 列太多时默认只保留 2 球 / 3 球两档，其余进球档折叠，点「展开明细」再看
    const hide = (!teamGoalsShowAll && i!==2 && i!==3);
    head+='<th class="sortable'+(String(teamSort.key)===String(b)?' sorted':'')+(hide?'" style="display:none':'')+'" data-k="'+b+'">'+LABELS[i]+arr(b)+'</th>';
  });
  // 赛季汇总：进球数 / 失球数 / 净胜球（各队赛季累计的得失球 + 净胜球，所有列均可点表头参与排序）
  head+='<th class="sortable total-h'+(teamSort.key==='gf'?' sorted':'')+'" data-k="gf" title="该队全赛季累计进球数（进球总和）">进球数'+arr('gf')+'</th>';
  head+='<th class="sortable total-h'+(teamSort.key==='ga'?' sorted':'')+'" data-k="ga" title="该队全赛季累计失球数（失球总和）">失球数'+arr('ga')+'</th>';
  head+='<th class="sortable total-h'+(teamSort.key==='gd'?' sorted':'')+'" data-k="gd" title="净胜球数 = 进球数 - 失球数（正数=净胜、负数=净负）">净胜球数'+arr('gd')+'</th>';
  if(hasSeq){
    head+='<th class="sortable b2-h'+(teamSort.key==='avg2'?' sorted':'')+'" data-k="avg2" title="该队平均每隔多少轮（场）打出一次 2 球">平均出2球'+arr('avg2')+'</th>';
    head+='<th class="sortable b3-h'+(teamSort.key==='avg3'?' sorted':'')+'" data-k="avg3" title="该队平均每隔多少轮（场）打出一次 3 球">平均出3球'+arr('avg3')+'</th>';
  }
  head+='<th class="sortable'+(teamSort.key==='gap2'?' sorted':'')+'" data-k="gap2" title="最长连续多少轮（场）该队总进球 ≠ 2 球">不出2球'+arr('gap2')+'</th>';
  head+='<th class="sortable'+(teamSort.key==='gap3'?' sorted':'')+'" data-k="gap3" title="最长连续多少轮（场）该队总进球 ≠ 3 球">不出3球'+arr('gap3')+'</th>';
  if(hasSeq){
    head+='<th class="sortable b2-h'+(teamSort.key==='streak2'?' sorted':'')+'" data-k="streak2" title="最长连续多少场打出 2 球">连续2球'+arr('streak2')+'</th>';
    head+='<th class="sortable b3-h'+(teamSort.key==='streak3'?' sorted':'')+'" data-k="streak3" title="最长连续多少场打出 3 球">连续3球'+arr('streak3')+'</th>';
  }
  head+='</tr>';
  let rows='';
  teams.forEach(t=>{
    const isNewSeason = (currentSeason==='2026-27');
    let mark='';
    if(!isNewSeason && prevSet && !prevSet.has(t.name)) mark+='<span class="move up" title="升班马（本季新升入）">升</span>';
    // 降级判定：优先用"下赛季名单差集"，但只有当下赛季名单完整（球队数不少于本赛季）才可信。
    // 进行中的最新赛季（如 2026-27 只打了首轮）名单只有已出场球队，用它做差集会把大量球队误判为降级。
    // 名单不完整时，退化为"本赛季已完赛 → 按积分榜末 N 位"推断；本赛季也未完赛则不标 ↓。
    const nextSetFull = nextSet && (nextSet.size >= sc.teams.length);
    const curComplete = sc.expected>0 && sc.totalMatches>=sc.expected;
    if(!isNewSeason && nextSetFull){ if(!nextSet.has(t.name)) mark+='<span class="move down" title="降班马（本季结束后降级）">降</span>'; }
    else if(!isNewSeason && curComplete){ const relN=(sc.teams.length===20)?3:2;   // 20 队降 3，18 队降 2（第 3 席为附加赛）
      if(t.rank > sc.teams.length-relN) mark+='<span class="move down" title="降班马（本季结束后降级）">降</span>'; }
    const rkCls = (teamSort.key==='rank')?' col-sel':'';
    const champ = (!isNewSeason && t.rank===1)?'<span class="champ" title="当季冠军"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg></span>':'';
    let cells='<td class="rk'+rkCls+'">'+t.rank+'</td><td class="left name">'+crestHtml(t.name,t.cn)+t.cn+'<span class="pts-inline">'+t.pts+'</span>'+champ+mark+'</td>';
    BUCKETS.forEach((b,i)=>{
      const c=t.b[b];
      let tdcls=(String(teamSort.key)===String(b))?' col-sel':'';
      if(i===2) tdcls+=' col-2'; if(i===3) tdcls+=' col-3';
      const hide = (!teamGoalsShowAll && i!==2 && i!==3);
      cells+='<td class="'+tdcls.trim()+(hide?'" style="display:none':'')+'">'+c+'</td>';
    });
    // 进球数 / 失球数 / 净胜球数 三列：在数据驱动的循环里就地计算，不依赖预存字段
    const g = goalsOf(t);
    const gdCls = g.gd>0 ? ' gd-pos' : (g.gd<0 ? ' gd-neg' : ' gd-zero');
    const gdDisp = (g.gd>0?'+':'') + g.gd;
    cells+='<td class="'+(teamSort.key==='gf'?'col-sel':'')+'" style="text-align:center;font-weight:600">'+g.gf+'</td>';
    cells+='<td class="'+(teamSort.key==='ga'?'col-sel':'')+'" style="text-align:center;font-weight:600">'+g.ga+'</td>';
    cells+='<td class="'+(teamSort.key==='gd'?'col-sel':'')+gdCls+'" style="text-align:center;font-weight:700" title="进球 '+g.gf+' − 失球 '+g.ga+'">'+gdDisp+'</td>';
    if(hasSeq){
      const rnd=roundsOfT(t);
      const a2=(t.count2&&rnd)?(rnd/t.count2).toFixed(1):'—';
      const a3=(t.count3&&rnd)?(rnd/t.count3).toFixed(1):'—';
      cells+='<td class="'+(teamSort.key==='avg2'?'col-sel':'')+'">'+a2+'</td>';
      cells+='<td class="'+(teamSort.key==='avg3'?'col-sel':'')+'">'+a3+'</td>';
    }
    const g2=(t.gap2==null)?'—':t.gap2, g3=(t.gap3==null)?'—':t.gap3;
    cells+='<td class="gap-cell'+(teamSort.key==='gap2'?' col-sel':'')+'" style="text-align:center;font-weight:600">'+g2+'</td>';
    cells+='<td class="gap-cell'+(teamSort.key==='gap3'?' col-sel':'')+'" style="text-align:center;font-weight:600">'+g3+'</td>';
    if(hasSeq){
      cells+='<td class="'+(teamSort.key==='streak2'?'col-sel':'')+'" style="font-weight:600">'+(t.streak2==null?'—':t.streak2)+'</td>';
      cells+='<td class="'+(teamSort.key==='streak3'?'col-sel':'')+'" style="font-weight:600">'+(t.streak3==null?'—':t.streak3)+'</td>';
    }
    rows+='<tr>'+cells+'</tr>';
  });
  const flag=sc.note?'<span class="note-flag">'+sc.note+'</span>':'';
  document.getElementById('teams').innerHTML=
    '<div class="section-title">'+lg.cn+' · 各球队总进球分布'+flag
    +'<button class="gap-toggle" onclick="toggleTeamGoals()" style="margin-left:10px;padding:4px 12px;border:1px solid var(--border);background:var(--accent);color:#fff;font-size:12.5px;border-radius:8px;cursor:pointer;vertical-align:middle">'+ (teamGoalsShowAll?'隐藏 4–7+ 球列':'显示全部进球数')+'</button></div>'
    +'<div class="note">当前赛季请使用上方赛季 Tab 切换。每格数字 = 该队参与（主 or 客）且全场总进球落在该区间的比赛场次数。默认按当赛季积分榜排名排序（点击表头可切换并高亮整列；升班马标「升」，降班马标「降」）。<b>0/1/4/5/6/7+ 球列默认隐藏</b>，点「显示全部进球数」展开；「不出2球 / 不出3球」= 该队最长连续多少轮（场）总进球 ≠ 2 / 3 球。<b>进球数 / 失球数 / 净胜球数</b> = 该队全赛季累计进球 / 失球 / 净胜差（净胜球正绿负红）。</div>'
    +'<table class="team-table"><thead>'+head+'</thead><tbody>'+rows+'</tbody></table>';
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
  var seasons=leagues[0].order.filter(function(s){return s!=='2026-27';}).sort().slice(-SEASON_WIN).reverse();
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
}
function renderSeq23(){
  var el=document.getElementById('seq23'); if(!el)return;
  if(currentLeague==='__all__'||!['2026-27','2025-26','2024-25','2023-24','2022-23','2021-22'].includes(currentSeason)){el.innerHTML='';return;}
  var lg=leagueOf(currentLeague),sc=lg.scopes[currentSeason]; if(!sc||!sc.teams.some(function(t){return t.seq23&&t.seq23.length;})){el.innerHTML='';return;}
  seqHidden={};
  el.innerHTML='<div class="section-title">'+lg.cn+' '+fullSeason(currentSeason)+' · 各队 2 球 / 3 球走势分布</div>'
    +'<div class="note">每条色带按时间顺序显示该队逐场总进球：2 球、3 球及其他。量化指标已并入上方球队表，可点表头或排序条排序；直接点击每条色带左侧球队名称，可显示或隐藏该球队。</div>'
    +'<div class="seq-filter"><button type="button" class="seq-tg'+(seqShow2?' on':'')+'" data-b="2">2 球</button><button type="button" class="seq-tg'+(seqShow3?' on':'')+'" data-b="3">3 球</button></div>'
    +'<div class="seq-strips" id="seqStrips"></div>';
  el.querySelectorAll('.seq-tg[data-b]').forEach(function(btn){btn.onclick=function(){var b=btn.getAttribute('data-b');if(b==='2')seqShow2=!seqShow2;else seqShow3=!seqShow3;btn.classList.toggle('on');updateSeqStrips(sc);};});
  updateSeqStrips(sc);
}

function render(){
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
render();
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
