window.LABELS = ["0 球", "1 球", "2 球", "3 球", "4 球", "5 球", "6 球", "7+ 球"];
window.BUCKETS = window.DATA.buckets;
(function(){
  // 设备判定：优先 matchMedia(min-width:820px)（最贴近 CSS 真实断点）；
  // 不可用时回退到 内宽 + 触屏点数 + UA 三重判断，尽量别把平板/大屏手机误判成桌面。
  function detectPC(){
    try{
      if(window.matchMedia){
        var mq = window.matchMedia('(min-width:820px)');
        if(mq && typeof mq.matches === 'boolean') return mq.matches;
      }
    }catch(e){}
    var w = window.innerWidth || document.documentElement.clientWidth || 1024;
    var coarse = (navigator.maxTouchPoints && navigator.maxTouchPoints > 0);
    var ua = navigator.userAgent || '';
    if(/Android|iPhone|iPad|iPod|Mobile|Windows Phone|HarmonyOS/i.test(ua)) return false;
    if(coarse && w < 1024) return false;
    return w >= 820;
  }
  function txt(id){ return document.getElementById(id).textContent; }
  function injectStyle(href){ var l=document.createElement('link'); l.rel='stylesheet'; l.href=href; document.head.appendChild(l); }
  var isPC = detectPC();
  injectStyle(window.GOALS_ASSET + (isPC ? 'css/goals-pc.css' : 'css/goals-mb.css'));
  document.getElementById('mount').innerHTML = isPC ? txt('pcBody') : txt('mbBody');
  document.body.className = isPC ? 'mode-pc' : 'mode-mb';
  // 只执行被选中那一份逻辑脚本（桌面 / 移动二选一）。
  // 原先是内联 textContent 同步执行；改成外链后为异步，故用 onload 串联后置模块。
  var s = document.createElement('script');
  s.src = window.GOALS_ASSET + (isPC ? 'js/goals-pc.js' : 'js/goals-mb.js');
  s.onload = function(){ postModules(); };
  s.onerror = function(){ postModules(); };
  document.body.appendChild(s);

  // 后置模块：横屏全屏按钮 + 连续场次浮层，需要等版本脚本把 render() 挂到全局后再跑
  function postModules(){

// H5 移动端外壳：手机端把顶部的 pill 行换成「联赛 / 赛季 下拉 + 范围分段」，
// 并挂上底部 3 tab。桌面端整段跳过，页面上原本的外壳（site.js）保持不动。
(function(){
  var force = /[?&]forcemb\b/.test(location.search||'');
  var isMobile = force || !isPC;
  if(!isMobile) return;                       // 桌面端跳过：保留 site.js 的顶部外壳
  if(!window.QZL_SHELL) return;
  if(window.__goalsH5Mounted) return; window.__goalsH5Mounted=true;

  document.documentElement.setAttribute('data-h5','on');

  function leagueFilter(){
    var D=window.DATA;
    return {
      type:'select', id:'gLg', label:'联赛',
      value:(typeof currentLeague!=='undefined'?currentLeague:(D.leagues[0]&&D.leagues[0].code)),
      options:[{v:'__all__',t:'走势总览'}].concat((D.leagues||[]).map(function(l){ return {v:l.code,t:l.cn}; }))
    };
  }
  function seasonFilter(){
    var D=window.DATA, lg=(D.leagues||[]).find(function(l){ return l.code===currentLeague; });
    var opts=[];
    if(lg && lg.scopes){
      var win=(typeof SEASON_WIN!=='undefined'?SEASON_WIN:5);
      var seq=(lg.order||[]).filter(function(k){ return true; }).slice(0,win);
      seq.forEach(function(k){ opts.push({v:k,t:seasonLabel(k)+(lg.scopes[k]?'（'+lg.scopes[k].totalMatches+'场）':'')}); });
    }
    return { type:'select', id:'gSn', label:'赛季', value:(typeof currentSeason!=='undefined'?currentSeason:''), options:opts };
  }
  function seasonLabel(s){ var m=/^(\d{4})-(\d{2})$/.exec(s||''); return m?(m[1]+'-'+(m[1].slice(0,2)+m[2])):s; }

  window.QZL_SHELL.mount({
    page:'进球数 · 五大',
    tab:'goals',
    filters:[
      leagueFilter(),
      seasonFilter(),
      { type:'segment', id:'gWin', label:'赛季范围', value:(typeof SEASON_WIN!=='undefined'?SEASON_WIN:5),
        options:[{v:5,t:'近五季'},{v:3,t:'近三季'}] }
    ],
    onChange:function(id,v){
      if(id==='gLg'){ if(typeof currentLeague!=='undefined'){ currentLeague=v; if(typeof hideTip==='function')hideTip(); render(); } }
      else if(id==='gSn'){ if(typeof currentSeason!=='undefined'){ currentSeason=v; if(typeof hideTip==='function')hideTip(); render(); } }
      else if(id==='gWin'){ if(typeof setWin==='function') setWin(+v); }
    }
  });

  var _r=window.render;
  if(typeof _r==='function' && !window.__goalsH5Wrapped){
    window.__goalsH5Wrapped=true;
    window.render=function(){
      _r.apply(this,arguments);
      if(window.QZL_SHELL){
        window.QZL_SHELL.setFilter('gLg', currentLeague);
        window.QZL_SHELL.setFilter('gSn', currentSeason);
        window.QZL_SHELL.setFilter('gWin', SEASON_WIN);
      }
    };
  }
})();

// 横屏全屏：实现已抽到公共文件 assets/js/landscape.js（页面里以 <script> 引入）。
// 这里只负责「何时启用 + 用哪些面板」，并保证每次 render() 后按钮跟得上。
(function(){
  var force = /[?&]forcemb\b/.test(location.search||'');
  var isMobile = force || !(window.matchMedia && window.matchMedia('(min-width:820px)').matches);
  if(!isMobile) return;
  if(!window.QZL_LANDSCAPE) return;          // 未引入公共模块则静默跳过
  if(window.__landscapeMod) return; window.__landscapeMod=true;

  function boot(){ window.QZL_LANDSCAPE.init({ panels:['overview','teams','trend','seq23'] }); }
  if(typeof window.render==='function'){
    var _o=window.render;
    window.render=function(){ _o.apply(this,arguments); boot(); };
  }
  boot();
})();

  (function(){
    try{
      var css=document.createElement('style');
      css.textContent='.seq-tip{position:fixed;z-index:90;pointer-events:none;background:var(--card);border:1px solid var(--border);border-radius:10px;padding:9px 12px;font-size:12.5px;color:var(--text);box-shadow:0 8px 22px rgba(0,0,0,.22);display:none;max-width:260px;line-height:1.5;}.seq-tip .seq-tip-teams{display:flex;align-items:center;gap:7px;font-weight:700;color:var(--text-strong);}.seq-tip .seq-tip-teams .vs{color:var(--text-muted);font-weight:400;font-size:11px;}.seq-tip .seq-tip-teams .score{font-size:15px;color:var(--accent);font-variant-numeric:tabular-nums;margin-left:2px;}.seq-tip .seq-tip-round{font-weight:800;color:var(--text-strong);font-size:13px;margin-bottom:4px;}.seq-tip .seq-tip-date{margin-top:5px;color:var(--text-muted);font-size:11.5px;}.seq-score-cell{cursor:pointer;transition:transform .12s,filter .12s;}.seq-score-cell:hover{filter:brightness(1.32);transform:translateY(-2px);}.trend-tip{position:fixed;z-index:80;pointer-events:none;background:var(--card);border:1px solid var(--border);border-radius:8px;padding:8px 11px;font-size:12.5px;color:var(--text);box-shadow:0 6px 18px rgba(0,0,0,.20);display:none;max-width:240px;line-height:1.5;}';
      document.head.appendChild(css);
    }catch(e){}
    if(window.__seqTipReady) return; window.__seqTipReady=true;
    var tip=document.createElement('div'); tip.className='seq-tip'; tip.id='seqTip'; document.body.appendChild(tip);
    function show(e){
      var t=e.target; if(!t||!t.closest) return;
      var el=t.closest('.seq-score-cell'); if(!el) return;
      var home=el.getAttribute('data-home'), away=el.getAttribute('data-away'), score=el.getAttribute('data-score'), date=el.getAttribute('data-date'), round=el.getAttribute('data-round'), ha=el.getAttribute('data-ha'), season=el.getAttribute('data-season');
      if(!home && !away) return;
      var line=home+' <b>'+score+'</b> '+away, sp=(''+score).split('-');
      if(ha!=='H' && sp.length===2) line=away+' <b>'+score+'</b> '+home;
      tip.innerHTML='<b>'+season+' 第 '+round+' 轮</b> · '+date+' · '+(ha==='H'?'主场':'客场')+'<br>'+line;
      tip.style.display='block';
      var x=e.clientX, y=e.clientY; if((x==null)&&e.touches&&e.touches[0]){x=e.touches[0].clientX;y=e.touches[0].clientY;}
      tip.style.left=(x+14)+'px'; tip.style.top=(y+14)+'px';
    }
    function move(e){ if(tip.style.display!=='block') return; var x=e.clientX,y=e.clientY; if((x==null)&&e.touches&&e.touches[0]){x=e.touches[0].clientX;y=e.touches[0].clientY;} tip.style.left=(x+14)+'px'; tip.style.top=(y+14)+'px'; }
    function hide(e){ var t=e.target; if(!t||!t.closest) return; var el=t.closest('.seq-score-cell'); if(!el) return; var rel=e.relatedTarget; if(rel && el.contains(rel)) return; tip.style.display='none'; }
    document.addEventListener('mouseover',show);
    document.addEventListener('mousemove',move);
    document.addEventListener('mouseout',hide);
  })();

    // 页脚：填入「数据源更新时间」与「本页更新时间」（来自数据层 meta，与平局页一致）
    (function(){
      try{
        var m = (window.DATA && window.DATA.meta) || {};
        var s = document.getElementById('ftSrc'), g = document.getElementById('ftGen');
        if(s) s.textContent = m.srcUpdated || '–';
        if(g) g.textContent = m.generated || '–';
      }catch(e){}
    })();

    // 版本脚本已加载并执行过 render()，真实内容就位 —— 通知外壳把首屏骨架淡出
    try{ if(window.QZL_BOOT_DONE) window.QZL_BOOT_DONE(); }catch(e){}
  }
})();
