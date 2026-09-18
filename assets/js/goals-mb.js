const SHORT = LABELS.map(function(x){ return x.replace(' 球',''); });

// 默认落在"数据完整的最新赛季"：新赛季刚开踢只有几场，分布没有参考价值
function defaultSeason(lg){
  for(var i=0;i<lg.order.length;i++){
    var k=lg.order[i], sc=lg.scopes[k];
    if(sc.expected>0 && sc.totalMatches>=sc.expected) return k;
  }
  return lg.order[0];
}
let currentLeague = DATA.leagues[0].code;
// 默认落在进行中的最新赛季 2026-2027（用户要求两个页默认都进该赛季；切换联赛 tab 时赛季保持不变）
let currentSeason = (DATA.leagues[0].order || []).includes('2026-27') ? '2026-27' : defaultSeason(DATA.leagues[0]);
let teamSort = {key:'rank', dir:1};
let teamGoalsShowAll = false;
function toggleTeamGoals(){ teamGoalsShowAll = !teamGoalsShowAll; renderTeams(); }
// 进球数 / 失球数 / 净胜球数 三列（得失球）折叠状态：2026-27 默认收起，其余赛季默认显示；用户点「显示得失球」后锁定
let teamTotalsShow = true;
let teamTotalsPinned = null; // null = 跟随赛季默认；true/false = 用户手动设定
function toggleTeamTotals(){ var cur=(teamTotalsPinned===null)?(currentSeason!=='2026-27'):teamTotalsPinned; teamTotalsPinned=!cur; renderTeams(); }
// 不出预警：从最近一场往前，连续多少轮（场）该队总进球既 ≠2 也 ≠3（即只打出 0/1/4+ 球）
function trailingNot23(seq){ if(!seq||!seq.length) return 0; var n=0; for(var i=seq.length-1;i>=0;i--){ var x=seq[i]; if(x!==2&&x!==3) n++; else break; } return n; }
let seqQuery='', seqShow2=true, seqShow3=true, seqHidden={};

// 跨赛季统计口径：近五季 / 近三季（与平局页一致，由外壳顶部「范围」下拉菜单驱动）
let SEASON_WIN = 5;
// lg.order 为「新 → 旧」，取最近 N 季；进行中的最新季天然落在最前，始终在窗口内
function winSeasons(lg){ return (lg && lg.order ? lg.order : []).slice(0, SEASON_WIN); }
let lastSortKey = 'rank';   // 记录上次排序列，用于判断是否需要自动滚动到该列

const THEME_KEY='fbg_theme';
function paintTheme(t){ document.documentElement.setAttribute('data-theme', t);
  var m=document.querySelector('meta[name="theme-color"]'); if(m) m.setAttribute('content', t==='dark'?'#0f1117':'#eef1f6'); }
// 「自动」全站统一为跟随系统外观；不支持该媒体查询时才退回本地时间 6–18 点
function fixedAuto(){
  try{ if(typeof window.matchMedia==='function') return window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'; }catch(e){}
  var h=new Date().getHours(); return (h>=6 && h<18)?'light':'dark';
}
function sunAuto(){
  return new Promise(function(res, rej){
    try{ var c=sessionStorage.getItem('fbg_sun'); if(c){ var o=JSON.parse(c); if(o.d===new Date().toDateString()){ res(o.t); return; } } }catch(e){}
    var to=setTimeout(function(){ rej(new Error('timeout')); }, 5000);
    function ok(t){ clearTimeout(to); try{ sessionStorage.setItem('fbg_sun', JSON.stringify({d:new Date().toDateString(), t:t})); }catch(e){} res(t); }
    function no(e){ clearTimeout(to); rej(e); }
    fetch('https://ipapi.co/json/').then(function(r){return r.json();}).then(function(g){
      if(typeof g.latitude!=='number' || typeof g.longitude!=='number') throw new Error('no geo');
      return fetch('https://api.sunrise-sunset.org/json?lat='+g.latitude+'&lng='+g.longitude+'&formatted=0');
    }).then(function(r){return r.json();}).then(function(j){
      if(!j.results||!j.results.sunrise||!j.results.sunset) throw new Error('no sun');
      var now=Date.now(), sr=Date.parse(j.results.sunrise), ss=Date.parse(j.results.sunset);
      ok((now>=sr && now<ss)?'light':'dark');
    }).catch(no);
  });
}
function refreshThemeBtn(mode, actual){
  var b=document.getElementById('themeBtn'); if(!b) return;
  if(mode==='auto') b.textContent = (actual==='dark' ? '🌗 自动·深色' : '🌗 自动·浅色');
  else if(mode==='light') b.textContent = '☀️ 浅色';
  else b.textContent = '🌙 深色';
}
function applyMode(mode){
  try{ localStorage.setItem(THEME_KEY, mode); }catch(e){}
  if(mode==='auto'){
    var a=fixedAuto(); paintTheme(a); refreshThemeBtn('auto', a);
    // sunAuto() 联网判定日出日落已被站点外壳的 prefers-color-scheme 方案取代，
    // 不再发起网络请求；保留函数定义便于兼容老调用，但不再触发。
  } else {
    paintTheme(mode); refreshThemeBtn(mode, mode);
  }
}
function toggleTheme(){
  var cur=null; try{ cur=localStorage.getItem(THEME_KEY); }catch(e){}
  cur = cur || 'auto';
  var nxt = (cur==='auto') ? 'light' : (cur==='light' ? 'dark' : 'auto');
  applyMode(nxt);
}
(function(){
  // 主题的初始化与切换已统一交给站点外壳（assets/js/site.js）：
  // 本页不再自行读 localStorage 决定明暗，避免与外壳按钮 / 其他页面状态不一致。
  // 外壳缺失时（例如单独打开本文件）退回本页默认的「自动」。
  if(window.SITE_THEME_READY) window.SITE_THEME_READY();
  else applyMode('auto');
})();

// 粘性导航高度 -> CSS 变量，供排序栏/表头定位
function syncNavH(){
  var n=document.getElementById('stickynav');
  if(n) document.documentElement.style.setProperty('--navh', n.offsetHeight+'px');
}
window.addEventListener('resize', syncNavH);

/* ---------- 轻点提示（替代 hover tooltip） ---------- */
let tipTimer=null;
function showTip(x,y,html){
  var t=document.getElementById('tip');
  t.innerHTML=html; t.style.display='block';
  var w=t.offsetWidth, h=t.offsetHeight;
  var left=x+14, top=y+14;
  if(left+w>window.innerWidth-8) left=window.innerWidth-w-8;
  if(left<8) left=8;
  if(top+h>window.innerHeight-8) top=y-h-16;
  if(top<8) top=8;
  t.style.left=left+'px'; t.style.top=top+'px';
  clearTimeout(tipTimer); tipTimer=setTimeout(hideTip, 2800);
}
function hideTip(){ var t=document.getElementById('tip'); if(t) t.style.display='none'; }
// 点空白处收起气泡
document.addEventListener('click', function(e){
  var el=e.target;
  if(!el || !el.classList || !el.classList.contains('tap-target')) hideTip();
}, false);

function fmtPct(c,total){ return total ? (c/total*100).toFixed(1)+'%' : '0%'; }
function leagueOf(code){ return DATA.leagues.find(function(l){ return l.code===code; }); }
function colorFor(s){ var h=0; for(var i=0;i<s.length;i++) h=(h*31+s.charCodeAt(i))%360; return 'hsl('+h+',55%,45%)'; }
function crestHtml(name, cn){
  var uri = DATA.crests[name];
  if(uri) return '<img class="crest" src="'+uri+'" alt="'+cn+'">';
  var ini = /[A-Za-z]/.test(cn) ? cn.slice(0,2).toUpperCase() : cn.slice(0,1);
  return '<span class="crest-fallback" style="background:'+colorFor(name)+'">'+ini+'</span>';
}
function fullSeason(s){ var p=String(s).split('-'); return p[0]+'-20'+p[1]; }
function dispSeason(s){ return fullSeason(s); }
function shortSeason(s){ return fullSeason(s); }

/* ---------- 横向滚动容器 ---------- */
var CHEV='<span class="more-hint"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor"'
  +' stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></span>';
// 滚到最右端就给容器打 .at-end，箭头淡出（到底了就不用再暗示了）
function syncHints(){
  document.querySelectorAll('#teams .sortbar, #teams .tw-wrap').forEach(function(box){
    var sc=box.querySelector('.pillrow') || box.querySelector('.tw');
    if(!sc) return;
    var atEnd = sc.scrollLeft + sc.clientWidth >= sc.scrollWidth - 2;
    box.classList.toggle('at-end', atEnd);
  });
}
// 点排序胶囊后把对应数据列滚进可视区（冻结列会盖住左边，要把它让出来）
var pendingColScroll=false;
function scrollColIntoView(){
  var tw=document.querySelector('#teams .tw');
  if(!tw) return;
  var key=String(teamSort.key), idx=-1;
  for(var i=0;i<BUCKETS.length;i++){ if(String(BUCKETS[i])===key){ idx=i; break; } }
  if(idx<0){ tw.scrollLeft=0; syncHints(); return; }   // 「排名」→ 回到最左
  var th=tw.querySelectorAll('thead th')[idx+1];        // +1 跳过冻结的「球队」列
  if(!th) return;
  var fz=tw.querySelector('th.freeze');
  var fw=fz?fz.offsetWidth:0;
  var target=th.offsetLeft-fw;                          // 贴着冻结列右侧，整列即可完整显示
  var max=tw.scrollWidth-tw.clientWidth;
  if(target<0) target=0;
  if(target>max) target=max;
  // 用平滑滚动：从 0 滑过去的过程本身就在告诉用户"这张表能横滑"
  if(tw.scrollTo) tw.scrollTo({left:target, behavior:'smooth'});
  else tw.scrollLeft=target;
  // 滚动过程中浏览器会持续派发 scroll 事件刷新箭头，这里再补一次是为了
  // 平滑滚动被系统禁用 / 走了 scrollLeft 兜底分支时，箭头状态也能立刻对上
  syncHints();
}

/* ---------- 联赛 / 赛季 切换 ---------- */
function buildLeagueTabs(){
  var el=document.getElementById('leagueTabs'); el.innerHTML='';
  var all=document.createElement('div');
  all.className='pill'+('__all__'===currentLeague?' active':'');
  all.innerHTML='<span class="lg-fallback" style="background:linear-gradient(135deg,var(--accent),var(--green));width:20px;height:20px;border-radius:50%;display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:13px;font-weight:700">∑</span><span>走势总览</span>';
  all.onclick=function(){ currentLeague='__all__'; hideTip(); renderAfterEnsure(); };
  el.appendChild(all);
  DATA.leagues.forEach(function(l){
    var b=document.createElement('div');
    b.className='pill'+(l.code===currentLeague?' active':'');
    var logo = l.logo ? '<img src="'+l.logo+'" alt="'+l.cn+'">' : '';
    b.innerHTML=logo+'<span>'+l.cn+'</span>';
    b.onclick=function(){ currentLeague=l.code; hideTip(); renderAfterEnsure(); };   // 切换联赛：保留当前赛季不变
    el.appendChild(b);
  });
}
function buildSeasonTabs(){
  var el=document.getElementById('seasonTabs');
  if(currentLeague==='__all__'){ el.innerHTML=''; el.style.display='none'; return; }
  el.style.display='';
  el.innerHTML='';
  var lg=leagueOf(currentLeague);
  // 窗口裁掉旧赛季：只显示最近 N 季，进行中的最新季始终保留
  var ws=winSeasons(lg);
  if(ws.indexOf(currentSeason)<0) currentSeason=ws[0];
  ws.forEach(function(k){
    var b=document.createElement('div');
    b.className='pill'+(k===currentSeason?' active':'');
    b.textContent=dispSeason(k);
    b.onclick=function(){ currentSeason=k; hideTip(); renderAfterEnsure(); };
    el.appendChild(b);
  });
  // 让选中的赛季滚到可见区域。这里手动改 scrollLeft 而不用 scrollIntoView——
  // 后者即便 block:'nearest' 也可能连带把整个页面纵向滚动一下，体验很突兀。
  var act=el.querySelector('.pill.active');
  if(act) el.scrollLeft = act.offsetLeft - (el.clientWidth - act.offsetWidth)/2;
}
/* 赛季范围开关：近五季 ⇄ 近三季（与平局页同一套分段开关交互）。 */
function buildWinSwitch(){
  var el=document.getElementById('winSwitch');
  if(!el) return;
  var opt=function(n,label){ return '<button type="button" class="wbtn'+(SEASON_WIN===n?' on':'')+'" data-win="'+n+'">'+label+'</button>'; };
  el.innerHTML='<span class="wlab"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/></svg>范围</span>'+
    opt(5,'近五季')+opt(3,'近三季');
  el.querySelectorAll('[data-win]').forEach(function(b){ b.onclick=function(){ setWin(+b.getAttribute('data-win')); }; });
}
function setWin(n){
  if(n!==3 && n!==5) return;
  SEASON_WIN=n;
  if(currentLeague!=='__all__'){
    var ws=winSeasons(leagueOf(currentLeague));
    if(ws.indexOf(currentSeason)<0) currentSeason=ws[0];
  }
  renderAfterEnsure();
}

function maxBucket(sc){ return Math.max.apply(null, BUCKETS.map(function(b){ return sc.buckets[b]; })); }
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

/* ---------- 总览：统计条 + 条形图 ---------- */
function renderOverview(){
  var lg=leagueOf(currentLeague), sc=lg.scopes[currentSeason];
  var total=sc.totalMatches, maxv=maxBucket(sc);
  var rows='';
  var fmtPR=function(v){ return (v===null||v===undefined) ? '—' : (v.toFixed(2)+' 场/轮'); };
  BUCKETS.forEach(function(b,i){
    var c=sc.buckets[b], pct=total?c/total*100:0, w=maxv?(c/maxv*100):0;
    // 移动端没有 hover —— 占比 / 场/轮 都做成轻点弹气泡（tap-target 让全局"点空白收起"不误伤）
    rows+='<div class="bar-row"><div class="bar-lab">'+LABELS[i]+'</div>'
      +'<div class="bar-track"><div class="bar-fill" style="width:'+w.toFixed(1)+'%"></div></div>'
      +'<div class="bar-val"><span class="vp cmp-able tap-target" data-t="'+i+'" data-m="pct">'
      +'<b>'+c+'</b>'+pct.toFixed(1)+'%</span>'
      +'<span class="vr cmp-able tap-target" data-t="'+i+'" data-m="pr">'
      +fmtPR(perRound(sc,c))+'</span></div></div>';
  });
  var idx=lg.order.indexOf(currentSeason);
  var prevKey=(idx>=0 && idx+1<lg.order.length)?lg.order[idx+1]:null;
  var avgCmp='';
  if(prevKey){
    var prevAvg=lg.scopes[prevKey].avgGoals;
    var d=+(sc.avgGoals-prevAvg).toFixed(2);
    var pp=prevAvg.toFixed(2), cc=sc.avgGoals.toFixed(2);
    var dir = d>0?'up':(d<0?'down':'eq');
    var sym = dir==='up'?'▲':(dir==='down'?'▼':'—');
    var col = dir==='up'?'var(--green)':(dir==='down'?'#e74c3c':'var(--text-muted)');
    avgCmp=' <span class="tap-target" style="color:'+col+'" data-p="'+pp+'" data-c="'+cc
      +'" data-d="'+Math.abs(d).toFixed(2)+'" data-dir="'+dir+'">'+sym+'</span>';
  }
  var flag=sc.note?'<span class="note-flag">'+sc.note+'</span>':'';
  document.getElementById('overview').innerHTML=
    '<div class="section-title">'+lg.cn+' '+dispSeason(currentSeason)+' · 总进球分布'+flag+'</div>'
    +'<div class="stat-strip">'
      +'<div class="stat"><div class="k">已赛场次</div><div class="v">'+total+'</div></div>'
      +'<div class="stat green"><div class="k">场均进球</div><div class="v">'+sc.avgGoals.toFixed(2)+avgCmp+'</div></div>'
    +'</div>'
    +'<div class="card">'+rows+'</div>'
    +'<div class="note">「场/轮」= 平均每轮出现几场。轮次 = 已赛场次 ÷ 每轮场数（每轮场数 = 球队数 ÷ 2）。'
    +'带虚线的<b>占比</b>与<b>场/轮</b>可轻点查看与上一赛季的环比。</div>';
  // 环比气泡（与场均进球 ▲▼ 同一套 showTip）
  var prevSc=prevKey?lg.scopes[prevKey]:null;
  var prevLabel=prevKey?dispSeason(prevKey):'';
  var deltaHTML=function(d,digits,unit){
    var ar=d>0?'↑':(d<0?'↓':'—');
    var cl=d>0?'var(--green)':(d<0?'#e74c3c':'var(--text-muted)');
    return '变化：<span style="color:'+cl+'">'+ar+' '+(d>0?'+':'')+d.toFixed(digits)+unit+'</span>';
  };
  var cmpTip=function(i,mode){
    var b=BUCKETS[i];
    if(!prevSc) return '<b>'+LABELS[i]+'</b><br>无上一赛季数据可比';
    if(mode==='pct'){
      var pt=prevSc.totalMatches||0;
      var pv=pt?prevSc.buckets[b]/pt*100:0, cv=total?sc.buckets[b]/total*100:0;
      var d1=+(cv-pv).toFixed(1);
      return '<b>'+LABELS[i]+' · 占比环比 '+prevLabel+'</b><br>'
        +'上赛季：<b>'+prevSc.buckets[b]+'</b> 场（'+pv.toFixed(1)+'%）<br>'
        +'本赛季：<b>'+sc.buckets[b]+'</b> 场（'+cv.toFixed(1)+'%）<br>'+deltaHTML(d1,1,' 个百分点');
    }
    var pv2=perRound(prevSc,prevSc.buckets[b]), cv2=perRound(sc,sc.buckets[b]);
    if(pv2===null||cv2===null) return '<b>'+LABELS[i]+'</b><br>上一赛季无场次数据';
    var d2=+(cv2-pv2).toFixed(2);
    return '<b>'+LABELS[i]+' · 场/轮环比 '+prevLabel+'</b><br>'
      +'上赛季：<b>'+pv2.toFixed(2)+'</b> 场/轮<br>'
      +'本赛季：<b>'+cv2.toFixed(2)+'</b> 场/轮<br>'+deltaHTML(d2,2,' 场/轮');
  };
  document.querySelectorAll('#overview .bar-val .tap-target').forEach(function(el){
    el.onclick=function(e){
      e.stopPropagation();
      showTip(e.clientX||0, e.clientY||0,
        cmpTip(+el.getAttribute('data-t'), el.getAttribute('data-m')));
    };
  });
  var avgEl=document.querySelector('#overview .stat .tap-target');
  if(avgEl) avgEl.onclick=function(e){
    e.stopPropagation();
    // 与「占比 / 场·轮」的环比提示保持一致：变化块带颜色（↑绿 / ↓红 / —灰）
    var dir=avgEl.getAttribute('data-dir');
    var abs=+avgEl.getAttribute('data-d');       // data-d 存的是绝对值，按方向还原正负
    var signed = dir==='down' ? -abs : abs;
    showTip(e.clientX||0, e.clientY||0,
      '<b>场均进球 · 环比上一赛季</b><br>上赛季：<b>'+avgEl.getAttribute('data-p')+'</b> 球/场<br>本赛季：<b>'
      +avgEl.getAttribute('data-c')+'</b> 球/场<br>'+deltaHTML(signed, 2, ' 球/场'));
  };
}

/* ---------- 球队表：首列冻结 + 横向滚动 ---------- */
function renderTeams(){
  var lg=leagueOf(currentLeague), sc=lg.scopes[currentSeason];
  // 进入 2026-27 时若停留在历史赛季的「最大同时不出」排序键，复位回默认（该列在 2026-27 已移除）
  if(currentSeason==='2026-27' && teamSort.key==='gap23'){ teamSort={key:'rank',dir:1}; }
  var idx=lg.order.indexOf(currentSeason);
  var prevKey=(idx>=0 && idx+1<lg.order.length)?lg.order[idx+1]:null;
  var nextKey=(idx>0)?lg.order[idx-1]:null;
  var teamSetOf=function(s){ return new Set(lg.scopes[s].teams.map(function(t){ return t.name; })); };
  var prevSet=prevKey?teamSetOf(prevKey):null;
  var nextSet=nextKey?teamSetOf(nextKey):null;
  var teams=sc.teams.slice();
  // 每队每轮只踢 1 场，故「已赛场次」= 经历轮次
  var roundsOfT=function(t){ return BUCKETS.reduce(function(s,bb){ return s+(t.b[bb]||0); },0); };
  var avgKey=function(t,n){ var r=roundsOfT(t); var c=(n===2?t.count2:t.count3); return (c&&r)? r/c : null; };
  // 进球数 / 失球数 / 净胜球数：从 seq23Matches 汇总。
  // 注意 score 的口径是「主客视角」= 主队进球-客队进球（不是球队视角！），
  // 必须按 ha 取自己那一侧，否则所有客场的进失球会整体颠倒。
  var goalsOf=function(t){
    var ms=(t && t.seq23Matches) || [];
    var gf=0, ga=0;
    for (var i=0;i<ms.length;i++){
      var m=ms[i];
      var sp=String((m && m.score) || '').split('-');
      if (sp.length!==2) continue;
      var a=(+sp[0])||0, b=(+sp[1])||0;
      if (m.ha === 'A'){ gf += b; ga += a; }   // 客场：自己是后者
      else             { gf += a; ga += b; }   // 主场：自己是前者
    }
    return {gf:gf, ga:ga, gd:gf-ga};
  };
  var hasSeq=sc.teams.some(function(t){ return t.seq23 && t.seq23.length; });
  // 「不出预警 / 快要🀄️了」列 + 「显示得失球」按钮：仅 2026-27 赛季提供（历史赛季不显示、不收起、不加按钮）
  var showWarn=(currentSeason==='2026-27');
  var k=teamSort.key, dir=teamSort.dir;
  teams.sort(function(a,b){
    var va,vb;
    if(k==='rank'){ va=a.rank; vb=b.rank; }
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
  var arr=function(kk){ return teamSort.key===kk ? (teamSort.dir<0?' ▼':' ▲') : ''; };

  var head='<tr><th class="freeze">球队</th>';
  // 列太多时默认只保留 2 球 / 3 球两档，其余折叠进「展开明细」
  BUCKETS.forEach(function(b,i){ var hide=(!teamGoalsShowAll && i!==2 && i!==3); head+='<th'+(hide?' style="display:none"':'')+'>'+SHORT[i]+'</th>'; });
  // 进球 / 失球 / 净胜（得失球）三列：仅 2026-27 默认收起；历史赛季始终展开（无按钮，不能被 pin 卡在收起态）
  var totalsShown = (currentSeason==='2026-27') ? ((teamTotalsPinned===null)?false:teamTotalsPinned) : true;
  var thHide = totalsShown ? '' : ' style="display:none"';
  head+='<th class="total-h"'+thHide+'>进球</th>';
  head+='<th class="total-h"'+thHide+'>失球</th>';
  head+='<th class="total-h"'+thHide+'>净胜球</th>';
  if(showWarn) head+='<th style="color:#e03131">快要🀄️了</th>';
  head+='<th>不出2球</th><th>不出3球</th>'; if(currentSeason!=='2026-27'){ head+='<th>最大同时不出</th>'; }
  if(hasSeq) head+='<th class="b2-h">均2</th><th class="b3-h">均3</th><th class="b2-h">连2</th><th class="b3-h">连3</th>';
  head+='</tr>';

  var rows='';
  teams.forEach(function(t){
    var isNewSeason=(currentSeason==='2026-27');
    var mark='';
    // 升班马(升 icon)：用"上赛季名单差集"判定，所有赛季(含进行中的最新 2026-27)都显示。
    // 进行中赛季当前名单不全，但这只影响"已出场球队"——升班马一旦出场即被标记，无误判。
    if(prevSet && !prevSet.has(t.name)) mark+='<span class="move up">升</span>';
    var nextSetFull = nextSet && (nextSet.size >= sc.teams.length);
    var curComplete = sc.expected>0 && sc.totalMatches>=sc.expected;
    if(!isNewSeason && nextSetFull){ if(!nextSet.has(t.name)) mark+='<span class="move down">降</span>'; }
    else if(!isNewSeason && curComplete){
      var relN=(sc.teams.length===20)?3:2;
      if(t.rank > sc.teams.length-relN) mark+='<span class="move down">降</span>';
    }
    var champ=(!isNewSeason && t.rank===1)?'<span class="champ"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55-.47.98-.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg></span>':'';
    var cells='<td class="freeze"><div class="tcell">'
      +'<span class="rk">'+t.rank+'</span>'+crestHtml(t.name,t.cn)
      +'<span class="tmeta"><span class="nm">'+t.cn+'</span>'
      +'<span class="pts">'+t.pts+' 分</span></span>'+champ+mark
      +'</div></td>';
    BUCKETS.forEach(function(b,i){
      var c=t.b[b];
      var bcls=(String(teamSort.key)===String(b))?' col-sel':'';
      if(i===2) bcls+=' col-2'; if(i===3) bcls+=' col-3';
      var hide=(!teamGoalsShowAll && i!==2 && i!==3);
      cells+='<td class="'+bcls+(hide?'" style="display:none':'')+'">'+c+'</td>';
    });
    // 进球 / 失球 / 净胜：每队赛季累计（从 seq23Matches 即地汇总），可折叠
    var mg=goalsOf(t);
    var mgdCls = mg.gd>0 ? ' gd-pos' : (mg.gd<0 ? ' gd-neg' : ' gd-zero');
    var mgdDisp = (mg.gd>0?'+':'')+mg.gd;
    var tdHide = totalsShown ? '"' : ';display:none"';
    cells+='<td class="total-h" style="text-align:center;font-weight:600'+tdHide+'">'+mg.gf+'</td>';
    cells+='<td class="total-h" style="text-align:center;font-weight:600'+tdHide+'">'+mg.ga+'</td>';
    cells+='<td class="'+mgdCls.trim()+'" style="text-align:center;font-weight:700'+tdHide+'">'+mgdDisp+'</td>';
    if(showWarn){
      var w23 = trailingNot23(t.seq23);
      var wHi = w23>=5 ? ';color:#c92a2a;font-weight:700' : '';
      cells+='<td class="gap-cell" style="text-align:center;font-weight:600'+wHi+'">'+w23+'</td>';
    }
    var g2=(t.gap2==null)?'—':t.gap2, g3=(t.gap3==null)?'—':t.gap3, g23=(t.gap23==null)?'—':t.gap23;
    cells+='<td class="gap-cell" style="text-align:center;font-weight:600">'+g2+'</td>';
  cells+='<td class="gap-cell" style="text-align:center;font-weight:600">'+g3+'</td>';
  if(currentSeason!=='2026-27'){ cells+='<td class="gap-cell" style="text-align:center;font-weight:600">'+g23+'</td>'; }
  if(hasSeq){
    // 单元格顺序须与表头一致：不出2球 / 不出3球 / 最大同时不出 / 均2 / 均3 / 连2 / 连3
    var rnd=roundsOfT(t);
    var a2=(t.count2&&rnd)?(rnd/t.count2).toFixed(1):'—';
    var a3=(t.count3&&rnd)?(rnd/t.count3).toFixed(1):'—';
    cells+='<td>'+a2+'</td><td>'+a3+'</td>';
    cells+='<td style="font-weight:600">'+(t.streak2==null?'—':t.streak2)+'</td>';
    cells+='<td style="font-weight:600">'+(t.streak3==null?'—':t.streak3)+'</td>';
  }
  rows+='<tr>'+cells+'</tr>';
  });

  // 排序操作条（放在滚动容器外，才能相对视口粘住）
  var chips='<div class="sortbar"><span class="sort-lab">排序</span><div class="pillrow">';
  chips+='<span class="pill tap-target'+(teamSort.key==='rank'?' active':'')+'" data-k="rank">排名'+arr('rank')+'</span>';
  BUCKETS.forEach(function(b,i){
    chips+='<span class="pill tap-target'+(String(teamSort.key)===String(b)?' active':'')+'" data-k="'+b+'">'+SHORT[i]+arr(b)+'</span>';
  });
  if(showWarn) chips+='<span class="pill tap-target'+(teamSort.key==='warn23'?' active':'')+'" data-k="warn23" style="color:#e03131">快要🀄️了'+arr('warn23')+'</span>';
  chips+='<span class="pill tap-target'+(teamSort.key==='gap2'?' active':'')+'" data-k="gap2">不出2球'+arr('gap2')+'</span>';
  chips+='<span class="pill tap-target'+(teamSort.key==='gap3'?' active':'')+'" data-k="gap3">不出3球'+arr('gap3')+'</span>';
  if(currentSeason!=='2026-27'){ chips+='<span class="pill tap-target'+(teamSort.key==='gap23'?' active':'')+'" data-k="gap23">最大同时不出'+arr('gap23')+'</span>'; }
  // 赛季汇总排序列：进球数 / 失球数 / 净胜球数（点击切换并高亮表格里对应列）
  chips+='<span class="pill tap-target total-h'+(teamSort.key==='gf'?' active':'')+'" data-k="gf">进球'+arr('gf')+'</span>';
  chips+='<span class="pill tap-target total-h'+(teamSort.key==='ga'?' active':'')+'" data-k="ga">失球'+arr('ga')+'</span>';
  chips+='<span class="pill tap-target total-h'+(teamSort.key==='gd'?' active':'')+'" data-k="gd">净胜'+arr('gd')+'</span>';
  chips+='</div>'+CHEV+'</div>';

  var flag=sc.note?'<span class="note-flag">'+sc.note+'</span>':'';
  document.getElementById('teams').innerHTML=
    '<div class="section-title">'+lg.cn+' '+dispSeason(currentSeason)+' · 各队分布'+flag
    +'<button class="gap-toggle" onclick="toggleTeamGoals()" style="margin-left:10px;padding:4px 12px;border:1px solid var(--border);background:var(--accent);color:#fff;font-size:12.5px;border-radius:8px;cursor:pointer;vertical-align:middle">'+ (teamGoalsShowAll?'隐藏 4–7+ 球列':'显示全部进球数')+'</button>'
    + (showWarn ? '<button class="gap-toggle" onclick="toggleTeamTotals()" style="margin-left:8px;padding:4px 12px;border:1px solid var(--border);background:var(--accent);color:#fff;font-size:12.5px;border-radius:8px;cursor:pointer;vertical-align:middle">'+ (totalsShown?'隐藏得失球':'显示得失球')+'</button>' : '') +'</div>'
    +chips
    +'<div class="tw-wrap"><div class="tw"><table class="team-table"><thead>'+head+'</thead><tbody>'+rows+'</tbody></table></div>'+CHEV+'</div>';

  document.querySelectorAll('#teams .sortbar .pill').forEach(function(p){
    p.onclick=function(){
      var kk=p.getAttribute('data-k');
      if(teamSort.key===kk){ teamSort.dir*=-1; }
      else { teamSort.key=kk; teamSort.dir = (kk==='rank') ? 1 : -1; }
      // 只在「换了排序列」时自动把该列滚进视野；同列切换升降序不重复滚动，免得晃
      if(lastSortKey!==kk){ pendingColScroll=true; lastSortKey=kk; }
      renderTeams();
    };
  });

  // 滚动箭头：初始算一次，之后随滚动切换（innerHTML 重建后要重新绑定）
  syncHints();
  var pr=document.querySelector('#teams .sortbar .pillrow');
  var tw=document.querySelector('#teams .tw');
  if(pr) pr.addEventListener('scroll', syncHints, {passive:true});
  if(tw) tw.addEventListener('scroll', syncHints, {passive:true});

  // 选中项居中：切联赛/赛季后若排序还停在 7+，胶囊也得看得见
  if(pr){
    var act=pr.querySelector('.pill.active');
    if(act) pr.scrollLeft = act.offsetLeft - (pr.clientWidth - act.offsetWidth)/2;
    syncHints();
  }
  if(pendingColScroll){ pendingColScroll=false; scrollColIntoView(); }
}

/* ---------- 走势图 ---------- */
let trendHidden={};
let trendMetric='count';
function toggleTrendMetric(){ trendMetric=(trendMetric==='count'?'pct':'count'); hideTip(); renderTrendAll(); }

function drawTrendChart(lg){
  var seasons=winSeasons(lg).slice().reverse();
  var COLORS=['#4a9eff','#2ecc71','#ffd43b','#ff5252','#9b59ff','#1ab9c9','#ff9f43','#ff5fa2'];
  var allSeries=BUCKETS.map(function(b,i){
    var count=seasons.map(function(s){ return lg.scopes[s].buckets[b]; });
    var pct=seasons.map(function(s){ var sc=lg.scopes[s]; return sc.buckets[b]/(sc.totalMatches||1)*100; });
    return {i:i, color:COLORS[i], count:count, pct:pct};
  });
  var vis=allSeries.filter(function(s){ return !trendHidden[s.i]; });
  var valOf=function(s){ return trendMetric==='count'?s.count:s.pct; };
  var maxV=0; vis.forEach(function(s){ valOf(s).forEach(function(v){ if(v>maxV) maxV=v; }); });
  var step;
  if(trendMetric==='pct'){ maxV=Math.ceil(maxV/5)*5; if(maxV<5) maxV=5; step=maxV/4; }
  else { maxV=Math.ceil(maxV/10)*10; if(maxV<10) maxV=10; step=maxV/4; }
  var W=440,H=300, ml=60,mr=12,mt=30,mb=46;
  var pw=W-ml-mr, ph=H-mt-mb, n=seasons.length;
  var X=function(i){ return ml + (n===1? pw/2 : pw*i/(n-1)); };
  var Y=function(v){ return mt + ph*(1 - v/maxV); };
  var isPct = trendMetric==='pct';
  var svg='<svg class="trend-svg" data-lg="'+lg.code+'" viewBox="0 0 '+W+' '+H+'">';
  svg+='<rect class="tap-target" x="0" y="0" width="'+ml+'" height="'+H+'" fill="transparent" onclick="toggleTrendMetric()"></rect>';
  for(var g=0; g<=4; g++){
    var val=step*g, y=Y(val);
    svg+='<line x1="'+ml+'" y1="'+y+'" x2="'+(W-mr)+'" y2="'+y+'" style="stroke:var(--axis)" stroke-width="1"/>';
    svg+='<text x="'+(ml-8)+'" y="'+(y+4)+'" style="fill:var(--text-muted)" font-size="13" text-anchor="end">'
      +val.toFixed(0)+(isPct?'%':'球')+'</text>';
  }
  seasons.forEach(function(s,i){
    var anchor='middle', lx=X(i);
    if(i===0){ anchor='start'; lx=ml; }
    else if(i===n-1){ anchor='end'; lx=W-mr; }
    svg+='<text x="'+lx+'" y="'+(H-mb+22)+'" style="fill:var(--text-dim)" font-size="12.5" text-anchor="'+anchor+'">'
      +shortSeason(s)+'</text>';
  });
  svg+='<text class="tap-target" x="'+ml+'" y="18" style="fill:var(--text-strong)" font-size="15" font-weight="600" '
    +'onclick="toggleTrendMetric()">各总进球数 · '+(isPct?'占比':'场次')+'走势</text>';
  if(vis.length===0){
    svg+='<text x="'+(W/2)+'" y="'+(mt+ph/2)+'" style="fill:var(--text-muted)" font-size="14" text-anchor="middle">'
      +'（全部曲线已隐藏，轻点下方图例可恢复）</text>';
  } else {
    vis.forEach(function(s){
      var vals=valOf(s);
      var pts=vals.map(function(v,i){ return X(i)+','+Y(v); }).join(' ');
      svg+='<polyline points="'+pts+'" style="stroke:'+s.color+';fill:none" stroke-width="2.6" '
        +'stroke-linejoin="round" stroke-linecap="round"/>';
      vals.forEach(function(v,i){
        svg+='<circle class="tp" cx="'+X(i)+'" cy="'+Y(v)+'" r="3.8" fill="'+s.color+'"/>';
        svg+='<circle class="tap-target" cx="'+X(i)+'" cy="'+Y(v)+'" r="15" fill="transparent" '
          +'data-l="'+LABELS[s.i]+'" data-s="'+fullSeason(seasons[i])+'" data-c="'+s.count[i]
          +'" data-p="'+s.pct[i].toFixed(1)+'"/>';
      });
    });
  }
  svg+='</svg>';
  return svg;
}
function drawTrendLegend(){
  var COLORS=['#4a9eff','#2ecc71','#ffd43b','#ff5252','#9b59ff','#1ab9c9','#ff9f43','#ff5fa2'];
  var legend='<div class="legend">';
  BUCKETS.forEach(function(b,i){ var off=trendHidden[i]?' off':''; legend+='<span class="lg-item'+off+'" data-i="'+i+'"><span class="sw" style="background:'+COLORS[i]+'"></span>'+LABELS[i]+'</span>'; });
  legend+='</div>';
  return legend;
}
var trendSeason=null; var trendLeagueHidden={}; var trendBucketHidden={};
function renderTrendAll(){
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
  document.querySelectorAll('#trend .comb-season').forEach(function(b){b.onclick=function(){trendSeason=b.getAttribute('data-s'); renderTrendAll();};});
  document.querySelectorAll('#trend .comb-chip[data-b]').forEach(function(b){b.onclick=function(){var k=b.getAttribute('data-b'); if(trendBucketHidden[k]) delete trendBucketHidden[k]; else trendBucketHidden[k]=true; renderTrendAll();};});
  document.querySelectorAll('#trend .comb-chip[data-lg]').forEach(function(b){b.onclick=function(){var c=b.getAttribute('data-lg'); if(trendLeagueHidden[c]) delete trendLeagueHidden[c]; else trendLeagueHidden[c]=true; renderTrendAll();};});
  document.querySelectorAll('#trend .comb-metric .cm').forEach(function(a){a.onclick=function(e){e.preventDefault(); trendMetric=a.getAttribute('data-m'); renderTrendAll();};});
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


// ---------- goals 按季 chunk 懒加载（Phase 2）----------
var _chunkInflight = {};
function _dataDir(){ return (window.SITE_ROOT || '') + 'assets/js/data/goals/'; }
function isChunkLoaded(name){
  var season = name.replace(/\.js$/, '');
  // 校验“当前联赛”当季数据（而非写死 leagues[0]），避免“某联赛当季缺失却误判已加载”。
  var L = leagueOf(currentLeague) || DATA.leagues[0];
  return !!(L && L.scopes && L.scopes[season] && L.scopes[season].teams);
}
function ensureChunks(names, done){
  var pending = (names || []).filter(function(n){ return !isChunkLoaded(n); });
  if(!pending.length){ done(); return; }
  var remaining = pending.slice();
  var called = false, iv = null;
  function finish(){ if(called) return; called = true; if(iv) clearInterval(iv); done(); }
  function maybeFinish(){ if(remaining.every(function(n){ return isChunkLoaded(n); })) finish(); }
  pending.forEach(function(name){
    if(_chunkInflight[name]) return;
    _chunkInflight[name] = true;
    var sc = document.createElement('script');
    sc.src = _dataDir() + name;
    sc.onload = function(){ delete _chunkInflight[name]; maybeFinish(); };
    sc.onerror = function(){ delete _chunkInflight[name]; maybeFinish(); };
    document.head.appendChild(sc);
  });
  iv = setInterval(maybeFinish, 40);
  setTimeout(finish, 10000); // 兜底：10s 内无论如何先渲染，避免卡死
}
function neededChunks(){
  var need = [];
  if(currentLeague === '__all__'){
    DATA.leagues[0].order.forEach(function(k){ need.push(k + '.js'); });
  } else {
    var lg = (typeof leagueOf === 'function' ? leagueOf(currentLeague) : null) || DATA.leagues[0];
    var order = lg.order || [];
    var idx = order.indexOf(currentSeason);
    if(idx >= 0){
      if(idx-1 >= 0) need.push(order[idx-1] + '.js');
      if(idx+1 < order.length) need.push(order[idx+1] + '.js');
    }
    need.push(currentSeason + '.js');
  }
  var seen = {};
  return need.filter(function(n){ if(seen[n]) return false; seen[n] = 1; return true; });
}
function renderAfterEnsure(){
  var need = neededChunks();
  if(need.every(function(n){ return isChunkLoaded(n); })){ render(); return; }
  ensureChunks(need, render);
}
// 首屏渲染后，空闲时后台补齐其余 chunk（保证切赛季 / 切联赛零回归）
function _preloadRest(){
  var rest = [];
  var lists = [];
  if(currentLeague === '__all__'){ DATA.leagues.forEach(function(L){ lists.push(L.order || []); }); }
  else { var lg = (typeof leagueOf === 'function' ? leagueOf(currentLeague) : null) || DATA.leagues[0]; lists.push(lg.order || []); }
  lists.forEach(function(order){ (order||[]).forEach(function(k){ if(!isChunkLoaded(k + '.js')) rest.push(k + '.js'); }); });
  if(!rest.length) return;
  if(window.requestIdleCallback){ window.requestIdleCallback(function(){ ensureChunks(rest, function(){}); }, {timeout:4000}); }
  else { setTimeout(function(){ ensureChunks(rest, function(){}); }, 1200); }
}

// renderTrendAll 可能在 render() 之外被调用（如 toggleTrendMetric），先确保所需赛季 chunk 齐备
var _renderTrendAll0 = renderTrendAll;
renderTrendAll = function(){
  var lg = (currentLeague === '__all__') ? null : (leagueOf(currentLeague) || DATA.leagues[0]);
  var seasons = (currentLeague === '__all__') ? DATA.leagues[0].order.slice() : (lg.order || []);
  var need = seasons.map(function(k){ return k + '.js'; });
  if(need.every(isChunkLoaded)){ _renderTrendAll0(); return; }
  ensureChunks(need, _renderTrendAll0);
};

function render(){
  hideTip();
  buildLeagueTabs(); buildSeasonTabs(); buildWinSwitch();
  if(currentLeague==='__all__'){
    document.getElementById('seasonTabs').style.display='none';
    document.getElementById('overview').innerHTML='';
    document.getElementById('teams').innerHTML='';
    document.getElementById('seq23').innerHTML='';
    renderTrendAll();
  } else {
    document.getElementById('seasonTabs').style.display='';
    renderOverview(); renderTeams();
    document.getElementById('trend').innerHTML='';
    renderSeq23();
  }
  syncNavH();
}
renderAfterEnsure(); _preloadRest();
syncNavH();
(function(){
  var el=document.getElementById('trend');
  if(!el) return;
  if(!('IntersectionObserver' in window)){ playTrendAnim(); return; }
  var ob=new IntersectionObserver(function(es){
    es.forEach(function(e){ if(e.isIntersecting) playTrendAnim(); });
  }, {threshold:0.2});
  ob.observe(el);
})();
(function(){
  var fab=document.getElementById('toTop');
  function onScroll(){ if(fab) fab.classList.toggle('show', (window.scrollY||0) > 220); }
  window.addEventListener('scroll', onScroll, {passive:true});
  onScroll();
})();

/* ==========================================================================
   移动端桥接（仅追加，不改动上方任何渲染逻辑）
   上方 render() 等函数是本文件作用域内的声明，没有挂到 window，
   导致 goals-app.js 里的「横屏按钮挂载」与「外壳筛选同步」拿不到 render()。
   这里把必要的入口暴露出去，让外层能在每次渲染后同步交互层。
   ========================================================================== */
window.render = render;
window.getGoalsState = function(){
  return { league: currentLeague, season: currentSeason, win: SEASON_WIN };
};
