/* 单页视图 URL：不刷新页面，只把当前联赛 / 赛季 / 视图写进地址栏。 */
(function(){
  'use strict';
  function read(){
    var p = new URLSearchParams(window.location.search || '');
    return {
      league: p.get('l') || '',
      season: p.get('s') || '',
      view: p.get('v') || '',
      win: p.get('w') || ''
    };
  }
  function write(state, replace){
    var p = new URLSearchParams();
    if(state && state.league) p.set('l', state.league);
    if(state && state.season) p.set('s', state.season);
    if(state && state.view) p.set('v', state.view);
    if(state && state.win) p.set('w', String(state.win));
    var qs = p.toString();
    var url = window.location.pathname + (qs ? '?' + qs : '') + window.location.hash;
    try {
      window.history[replace ? 'replaceState' : 'pushState']({view: state || {}}, '', url);
    } catch (e) {}
  }
  window.FD_URL = {read: read, write: write};
})();
