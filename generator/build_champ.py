# -*- coding: utf-8 -*-
import json, datetime

import os
WS = os.path.dirname(os.path.abspath(__file__))
data = json.load(open(f"{WS}/data/report_champ.json", encoding="utf-8"))

# 队徽（crestByTeam）与各联赛 logo（logoByCode）已随 report_champ.json 一并提供
DATA_JS = json.dumps(data, ensure_ascii=False)

SCORE_COLORS = {"0-0": "#4a9eff", "1-1": "#00b894", "2-2": "#a29bfe", "其他": "#fdcb6e"}
RESULT_COLORS = {"W": "#00b894", "D": "#f1c40f", "L": "#e74c3c"}

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f1117">
<meta name="description" content="叕中啦 · 五大次级联赛（英冠/西乙/德乙/法乙/意乙）近五赛季平局数据专题：平局率、比分分布、各轮走势与各队平局统计。">
<title>叕中啦 · 五大次级联赛近五赛季平局数据（英冠/西乙/德乙/法乙/意乙）</title>
<style>
:root{
  --bg:#0f1117; --card:#1a1d29; --card2:#252836; --border:#2a2d3a;
  --text:#e0e0e0; --text2:#cccccc; --text-dim:#aaaaaa; --text-strong:#ffffff; --text-muted:#8a90a0; --muted:#555555;
  --accent:#4a9eff; --green:#00b894; --axis:#262a38; --chart-bg:#151823;
  --bar-grad:linear-gradient(90deg,#4a9eff,#00b894); --rk:#f1c40f; --note-flag:#e17055; --col-sel-bg:rgba(74,158,255,.12);
  /* 一级 Tab（联赛导航）：选中态用高饱和亮色 + 渐变下划线，避免整块方块抢走内容焦点 */
  --tab-on:#28dcff; --tab-on-bg:rgba(40,200,255,.18); --tab-grad:linear-gradient(90deg,#00e6ff,#3d8bff 52%,#b96bff);
  --tab-glow:0 0 18px rgba(40,200,255,.65);
}
[data-theme="light"]{
  --bg:#eef1f6; --card:#ffffff; --card2:#eef1f6; --border:#d8dee9;
  --text:#1f2430; --text2:#3a4252; --text-dim:#55607a; --text-strong:#10141c; --text-muted:#8a93a6; --muted:#9aa3b2;
  --accent:#2f7bdc; --green:#0a9b73; --axis:#e2e8f0; --chart-bg:#ffffff;
  --bar-grad:linear-gradient(90deg,#2f7bdc,#0a9b73); --rk:#c79a00; --note-flag:#d65a3a; --col-sel-bg:rgba(47,123,220,.10);
  --tab-on:#0077e6; --tab-on-bg:rgba(0,119,230,.14); --tab-grad:linear-gradient(90deg,#1aa3ff,#2f7bdc 52%,#8a3fe4);
  --tab-glow:0 0 14px rgba(26,140,255,.45);
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:"PingFang SC","Microsoft YaHei","Helvetica Neue",Arial,sans-serif; background:var(--bg); color:var(--text); line-height:1.6; padding:20px; transition:background .2s,color .2s; -webkit-tap-highlight-color:transparent; }
.container { max-width:1180px; margin:0 auto; }

.theme-btn { flex:0 0 auto; padding:7px 13px; border-radius:999px; background:var(--card); border:1px solid var(--border); color:var(--text-dim); cursor:pointer; font-size:12.5px; font-weight:600; line-height:1.4; transition:all .15s; white-space:nowrap; }
.theme-btn:hover { border-color:var(--accent); color:var(--accent); }

/* ---------- 站点页头：品牌「球中了」+ 面包屑 + 主题 ---------- */
/* 与正文同一条 1180px 中轴，保证页头与内容左右对齐 */
.site-head { display:flex; align-items:center; gap:12px; max-width:1180px; margin:0 auto; padding:2px 2px 12px; }
.brand { display:flex; align-items:center; gap:10px; min-width:0; }
.brand .mark { width:38px; height:38px; flex:0 0 auto; border-radius:11px; display:block; box-shadow:0 4px 12px rgba(74,158,255,.28); }
.brand-txt { display:flex; flex-direction:column; min-width:0; }
.brand-txt .nm { font-size:22px; font-weight:800; letter-spacing:2px; color:var(--text-strong); line-height:1.15; }
.brand-txt .sl { font-size:10.5px; letter-spacing:.6px; color:var(--text-muted); white-space:nowrap; }
.crumb { margin-left:auto; display:flex; align-items:center; gap:6px; flex-wrap:wrap; justify-content:flex-end; font-size:12px; color:var(--text-muted); }
.crumb .sepi { opacity:.45; }
.crumb b { color:var(--text-strong); font-weight:700; }
.scroll-nav { position:fixed; right:24px; bottom:18px; z-index:70; display:flex; flex-direction:column; gap:10px; }
.scroll-btn { width:46px; height:46px; border-radius:13px; background:var(--card); border:1px solid var(--border); color:var(--text-strong); cursor:pointer; box-shadow:0 6px 18px rgba(0,0,0,.22); display:flex; align-items:center; justify-content:center; transition:background .18s,color .18s,border-color .18s,transform .18s,box-shadow .18s,opacity .2s; }
.scroll-btn svg { width:20px; height:20px; display:block; }
.scroll-btn:hover { background:var(--accent); color:#fff; border-color:var(--accent); transform:translateY(-2px); box-shadow:0 9px 22px rgba(74,158,255,.42); }
.scroll-btn.hide { opacity:0; pointer-events:none; transform:translateY(10px); }

/* 联赛 + 赛季切换（吸顶导航条） */
.stickynav { position:sticky; top:0; z-index:45; background:var(--bg); padding:0 0 6px; margin-bottom:6px; box-shadow:0 1px 0 var(--border); }
.league-tabs { display:flex; flex-wrap:nowrap; gap:2px; justify-content:center; overflow-x:auto; scrollbar-width:none; -ms-overflow-style:none; }
.league-tabs::-webkit-scrollbar { display:none; }
/* 字号/图标整体放大，未选中也用 text2（比 text-dim 更亮），选中态走高饱和亮色 */
.league-tab { position:relative; display:inline-flex; align-items:center; gap:9px; padding:15px 22px 13px; background:transparent; border:0; border-radius:11px; color:var(--text2); cursor:pointer; font-size:18px; font-weight:800; letter-spacing:.3px; transition:color .15s,background .15s; user-select:none; white-space:nowrap; min-width:0; flex:0 0 auto; }
/* 选中态用渐变下划线（主站导航栏风格），替代原来抢眼的渐变方块 */
.league-tab::after { content:''; position:absolute; left:12px; right:12px; bottom:2px; height:3px; border-radius:3px; background:var(--tab-grad); transform:scaleX(0); transform-origin:center; transition:transform .18s ease; }
.league-tab:hover { color:var(--text-strong); background:var(--card2); }
.league-tab:hover::after { transform:scaleX(.45); }
.league-tab.active { color:var(--tab-on); background:var(--tab-on-bg); font-weight:800; }
.league-tab.active::after { transform:scaleX(1); box-shadow:var(--tab-glow); }
.league-tab img { width:26px; height:26px; object-fit:contain; border-radius:6px; background:transparent; flex:0 0 auto; }
.league-tab .uefa-logo { width:25px; height:15px; border-radius:3px; display:block; flex:0 0 auto; }
.league-tab .rt { font-size:12px; font-weight:600; opacity:.6; margin-left:2px; }
.league-tab.active .rt { opacity:.92; }
.season-tabs { display:flex; flex-wrap:wrap; gap:6px; justify-content:center; padding:8px 0 2px; flex:1 1 auto; min-width:0; }
.season-tab { padding:5px 13px; border-radius:999px; background:transparent; border:1px solid var(--border); color:var(--text-muted); cursor:pointer; font-size:12.5px; font-weight:600; transition:all .15s; user-select:none; white-space:nowrap; }
.season-tab:hover { border-color:var(--accent); color:var(--text-strong); }
.season-tab.active { background:var(--accent); color:#fff; border-color:var(--accent); }
.season-tab.ov { border-style:dashed; }
.season-tab.ov.active { border-style:solid; }
.season-tab .cnt { font-size:11px; font-weight:500; opacity:.7; margin-left:5px; }
.season-tab.active .cnt { opacity:.85; }
/* 二级行右侧：赛季范围（近五季 / 近三季）分段开关 */
.navrow { display:flex; align-items:flex-start; gap:10px; }
.win-switch { flex:0 0 auto; display:inline-flex; align-items:center; gap:3px; margin-top:8px; padding:3px;
  border:1px solid var(--border); border-radius:999px; background:var(--card); }
.win-switch .wlab { display:inline-flex; align-items:center; gap:4px; padding:0 6px 0 8px; font-size:11.5px; font-weight:700; color:var(--text-muted); white-space:nowrap; }
.win-switch .wlab svg { width:12px; height:12px; display:block; }
.win-switch .wbtn { border:0; background:transparent; color:var(--text-muted); cursor:pointer; padding:3px 11px;
  border-radius:999px; font-size:12px; font-weight:700; line-height:1.5; transition:color .15s,background .15s; white-space:nowrap; }
.win-switch .wbtn:hover { color:var(--text-strong); }
.win-switch .wbtn.on { background:var(--tab-grad); color:#fff; box-shadow:var(--tab-glow); }
@media (max-width:760px){
  .navrow { flex-direction:column; align-items:stretch; }
  .win-switch { align-self:center; margin-top:2px; }
}

/* 跨赛季总榜 */
.findings { background:var(--card); border:1px solid var(--border); border-left:4px solid var(--rk); border-radius:10px; padding:14px 16px; margin-bottom:14px; }
.top-tools { display:flex; align-items:center; flex-wrap:wrap; gap:8px 10px; margin:0 0 12px; }
.top-tools .tg { display:inline-flex; align-items:center; gap:6px; }
.top-tools .tgl { font-size:12px; color:var(--text-dim); font-weight:600; margin-right:1px; }
.top-tools .fb { font:inherit; font-size:12.5px; font-weight:600; color:var(--text-dim); background:var(--card); border:1px solid var(--border); border-radius:999px; padding:5px 11px; cursor:pointer; transition:color .15s,border-color .15s,background .15s; }
.top-tools .fb:hover { color:var(--accent); border-color:var(--accent); }
.top-tools .fb.on { color:#fff; background:var(--accent); border-color:var(--accent); }
/* 「范围」分段开关：两段拼成一体的胶囊，一眼看出是二选一（区别于各自独立的筛选开关） */
.top-tools .seg { display:inline-flex; }
.top-tools .seg .fb { border-radius:0; margin-left:-1px; }
.top-tools .seg .fb:first-child { border-radius:999px 0 0 999px; margin-left:0; }
.top-tools .seg .fb:last-child { border-radius:0 999px 999px 0; }
.top-tools .seg .fb.on { position:relative; z-index:1; }
.top-tools .tg + .tg { padding-left:10px; border-left:1px solid var(--border); }
/* 状态说明：独占一行，把「命中队数 + 当前范围 + 已启用筛选」一次说清，消除歧义 */
.top-tools .cnt-note { flex-basis:100%; font-size:11.5px; color:var(--text-muted); line-height:1.6; }
.top-tools .cnt-note b { color:var(--text-strong); }
.top-table td.hov-cell { cursor:pointer; }
.findings .fl { display:flex; gap:9px; align-items:flex-start; font-size:13.5px; color:var(--text2); line-height:1.8; }
.findings .fl + .fl { margin-top:5px; }
.findings .fi { flex:0 0 auto; }
.findings b { color:var(--text-strong); }
.findings .hi { color:var(--rk); font-weight:700; }
.findings .ok { color:var(--green); font-weight:700; }
@media(max-width:520px){ .findings .fl{ font-size:12.5px; } .findings{ padding:12px 13px; } }


.top-table { min-width:0; white-space:normal; word-break:break-word; overflow-wrap:anywhere; }
.top-table th.namecol, .top-table td.namecol { width:150px; }
.top-table th.yrcol, .top-table td.yrcol { width:210px; }
.top-table th.totalcol, .top-table td.totalcol { width:72px; }
.top-table td.yr { padding:6px 8px; }
.form5-filter { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:6px 0 10px; }
.form5-filter .form5-toggle { padding:6px 13px; border:1px solid var(--border); border-radius:18px; background:var(--card); color:var(--text2); font:inherit; font-size:12.5px; font-weight:700; cursor:pointer; opacity:.55; }
.form5-filter .form5-toggle.on { opacity:1; color:var(--text-strong); background:var(--card2); }
.form5-toggle[data-r="W"].on { border-color:#00b894; }
.form5-toggle[data-r="D"].on { border-color:#4a9eff; box-shadow:inset 0 -3px 0 #4a9eff; }
.form5-toggle[data-r="L"].on { border-color:#e74c3c; }
.form5-filter .form5-hint { color:var(--text-muted); font-size:11.5px; margin-left:auto; }
.form5-strips { --f5-w:#00b894; --f5-d:#4a9eff; --f5-l:#e74c3c; display:flex; flex-direction:column; gap:7px; background:var(--card); border:1px solid var(--border); border-radius:10px; padding:10px 12px; overflow-x:auto; }
.form5-row { display:flex; flex-wrap:wrap; align-items:center; gap:10px; min-width:700px; }
.form5-name { width:206px; flex:0 0 206px; display:flex; align-items:center; gap:6px; white-space:nowrap; color:var(--text-strong); font-size:13px; font-weight:600; }
.form5-name .crest { width:20px; height:20px; flex:0 0 auto; }
.form5-name .nm { overflow:hidden; text-overflow:ellipsis; min-width:0; flex:0 1 auto; }
.form5-tlink { flex:0 0 auto; margin-left:6px; font-size:11px; font-weight:400; color:var(--text-muted); white-space:nowrap; cursor:pointer; user-select:none; }
.form5-tlink:hover { color:var(--text2); }
.form5-strip { display:flex; flex:1; gap:2px; min-width:320px; }
.form5-strip.off { display:none; }
.form5-row.off .form5-meta { display:none; }
.form5-cell { flex:1 1 0; min-width:3px; height:20px; border-radius:2px; cursor:default; transition:opacity .12s, box-shadow .12s; }
.form5-cell.w { background:var(--f5-w); }
.form5-cell.d { background:var(--f5-d); box-shadow:0 0 0 1px rgba(74,158,255,.55); }
.form5-cell.l { background:var(--f5-l); }
.form5-cell.start { margin-left:5px; box-shadow:inset 2px 0 0 var(--border); }
.form5-cell.d.start { box-shadow:inset 2px 0 0 var(--border), 0 0 0 1px rgba(74,158,255,.55); }
.form5-cell.off { opacity:.42; }
.form5-cell:hover { opacity:1; box-shadow:0 0 0 2px var(--text-strong); }
.form5-meta { flex:0 0 auto; min-width:118px; text-align:right; font-size:11px; color:var(--text-muted); white-space:nowrap; font-variant-numeric:tabular-nums; }
.form5-legend { display:flex; gap:14px; margin:0 0 7px 216px; font-size:11.5px; color:var(--text-muted); }
.form5-legend span::before { content:''; display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:4px; vertical-align:-1px; }
.form5-legend .fw::before { background:var(--f5-w); } .form5-legend .fd::before { background:var(--f5-d); } .form5-legend .fl::before { background:var(--f5-l); }
.yrcell { display:inline-flex; gap:4px; }
.yrcell i { display:inline-flex; align-items:center; justify-content:center; width:27px; height:24px; border-radius:6px; font-size:12px; font-weight:700; font-variant-numeric:tabular-nums; font-style:normal; color:var(--text-strong); border:1px solid var(--border); }
.yrcell i.na { color:var(--muted); background:transparent; }
.yrcell i.cur { box-shadow:0 0 0 2px var(--accent); }
.sdb { display:inline-flex; align-items:center; gap:6px; justify-content:center; }
.sdb .sb { width:40px; max-width:40px; height:6px; border-radius:3px; background:var(--card2); overflow:hidden; }
.sdb .sb i { display:block; height:100%; border-radius:3px; }
.sdb .sv { font-variant-numeric:tabular-nums; min-width:30px; text-align:right; }

/* 单赛季关键指标：轻量「指标条」（细分隔线 + 文字），避免方块卡片比 Tab 还抢眼 */
.stat-strip { display:grid; grid-template-columns:repeat(6,1fr); margin:12px 0 2px; padding:9px 0 10px; border-top:1px solid var(--border); border-bottom:1px solid var(--border); }
.stat-strip .stat { padding:0 14px; border-left:1px solid var(--border); min-width:0; text-align:left; }
.stat-strip .stat:first-child { border-left:0; padding-left:0; }
.stat-strip .stat .k { font-size:11.5px; color:var(--text-muted); line-height:1.4; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.stat-strip .stat .v { font-size:19px; font-weight:800; color:var(--text-strong); font-variant-numeric:tabular-nums; line-height:1.4; white-space:nowrap; }
.stat-strip .stat .v.green { color:var(--green); } .stat-strip .stat .v.accent { color:var(--accent); } .stat-strip .stat .v.rk { color:var(--rk); }
.stat-strip .stat .v.stat-combo { display:flex; align-items:baseline; gap:6px; min-width:0; }
.stat-combo .stat-team { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; font-size:12px; font-weight:700; color:var(--text-dim); }
.delta { font-size:12px; font-weight:700; margin-left:5px; cursor:default; }
.delta.up { color:var(--green); } .delta.down { color:#e74c3c; } .delta.eq { color:var(--text-muted); }
@media(max-width:900px){
  .stat-strip{ grid-template-columns:repeat(3,1fr); }
  .stat-strip .stat{ padding:6px 14px; border-left:1px solid var(--border); border-top:1px solid var(--border); }
  .stat-strip .stat:first-child{ padding-left:14px; border-left:1px solid var(--border); }
  .stat-strip .stat:nth-child(3n+1){ border-left:0; padding-left:0; }
  .stat-strip .stat:nth-child(-n+3){ border-top:0; padding-top:0; }
}
@media(max-width:520px){
  .stat-strip{ grid-template-columns:repeat(2,1fr); }
  .stat-strip .stat{ padding:6px 12px; border-left:1px solid var(--border); border-top:1px solid var(--border); }
  .stat-strip .stat:nth-child(3n+1){ border-left:1px solid var(--border); padding-left:12px; }
  .stat-strip .stat:nth-child(2n+1){ border-left:0; padding-left:0; }
  .stat-strip .stat:nth-child(-n+2){ border-top:0; padding-top:0; }
  .stat-strip .stat .v{ font-size:17px; } body{padding:12px;}
}

.section-title { font-size:18px; font-weight:700; color:var(--text-strong); margin:26px 0 12px; padding-left:12px; border-left:4px solid var(--accent); }
.section-title .note-flag { display:block; font-size:12px; color:var(--note-flag); font-weight:400; margin-top:4px; }

.ov-table { width:100%; border-collapse:collapse; font-size:13px; background:var(--card); border-radius:10px; overflow:hidden; margin-bottom:6px; }
.ov-table th, .ov-table td { padding:11px 8px; text-align:center; color:var(--text2); border-bottom:1px solid var(--border); white-space:nowrap; }
.ov-table th { background:var(--card2); color:var(--text-dim); font-weight:600; border-bottom:2px solid var(--border); cursor:pointer; user-select:none; }
.ov-table th.left, .ov-table td.left { text-align:left; }
.ov-table th.sortable:hover { color:var(--text-strong); }
.ov-table th.sortable.sorted { color:var(--accent); box-shadow:inset 0 -2px 0 var(--accent); }
.ov-table th .arr { font-size:10px; margin-left:2px; }
.ov-table tbody tr:hover { background:var(--card2); }
.ov-table tfoot td { background:var(--card2); font-weight:700; color:var(--text-strong); border-top:2px solid var(--border); }
.ov-table .dot { width:11px; height:11px; border-radius:3px; display:inline-block; vertical-align:middle; margin-right:6px; }
/* 注：不要再定义全局 .bar —— 走势图柱体 <rect class="bar"> 的 height 是几何属性，CSS 会覆盖属性值 */
.per-round { font-size:12px; color:var(--text-dim); min-width:64px; text-align:left; font-variant-numeric:tabular-nums; }
.bignum { font-size:15px; font-weight:700; color:var(--text-strong); }
.ov-note { font-size:11.5px; color:var(--text-muted); line-height:1.6; margin-top:6px; }

.tw-wrap { position:relative; margin-bottom:6px; }
.tw { overflow:visible; border:1px solid var(--border); border-radius:10px; background:var(--card); }
.team-table { width:100%; border-collapse:separate; border-spacing:0; font-size:13px; table-layout:fixed; }
.cmp-table { width:100%; border-collapse:separate; border-spacing:0; font-size:13px; table-layout:fixed; white-space:normal; word-break:break-word; overflow-wrap:anywhere; }
.cmp-table th, .cmp-table td { padding:10px 8px; text-align:center; border-bottom:1px solid var(--border); white-space:normal; word-break:break-word; overflow-wrap:anywhere; color:var(--text2); }
.cmp-table th { background:var(--card2); color:var(--text-dim); font-weight:600; }
.cmp-table th.left, .cmp-table td.left { text-align:left; }
.cmp-table tbody tr:hover { background:var(--card2); }
.cmp-table tr.cur { background:var(--col-sel-bg); }
.cmp-table tbody tr.cur:hover { background:var(--col-sel-bg); }
.cmp-table .sn { font-weight:700; color:var(--text-strong); cursor:pointer; text-decoration:underline; text-decoration-style:dotted; text-underline-offset:3px; text-decoration-color:var(--border); }
.cmp-table .sn:hover { color:var(--accent); text-decoration-color:var(--accent); }
.cmp-table th.sortable { cursor:pointer; user-select:none; }
.cmp-table th.sortable:hover { color:var(--text-strong); }
.cmp-table th.sortable.sorted { color:var(--accent); box-shadow:inset 0 -2px 0 var(--accent); }
.cmp-table th .arr { font-size:10px; margin-left:2px; }
.team-table th, .team-table td { padding:9px 8px; text-align:center; border-bottom:1px solid var(--border); white-space:normal; word-break:break-word; overflow-wrap:anywhere; }
.team-table th { background:var(--card2); color:var(--text-dim); font-weight:600; cursor:pointer; user-select:none; }
.team-table th.sortable:hover { color:var(--text-strong); }
.team-table th.sortable.sorted { color:var(--accent); box-shadow:inset 0 -2px 0 var(--accent); }
.team-table th .arr { font-size:10px; margin-left:2px; }
.team-table tbody tr:hover { background:var(--card2); }
/* PC：排名为独立窄列，队名另起一列（与参考榜单一致） */
.team-table th.rkcol, .team-table td.rkcol { width:52px; min-width:52px; max-width:52px; padding-left:0; padding-right:0; }
.team-table td.rk { color:var(--rk); font-weight:700; font-variant-numeric:tabular-nums; }
.team-table th.namecol, .team-table td.namecol { width:232px; min-width:204px; max-width:268px; text-align:left; padding-left:10px; }
/* 队名过长时只让「队名」这一段省略，积分 / 🏆 / 升降 icon 一律不参与压缩，避免 icon 被切掉 */
.team-table td.namecol { overflow:hidden; }
.tcell { display:flex; align-items:center; gap:8px; min-width:0; }
.crest { width:24px; height:24px; object-fit:contain; border-radius:4px; background:transparent; padding:1px; filter:drop-shadow(0 0 1px rgba(0,0,0,.55)); flex:0 0 auto; }
[data-theme="light"] .crest { filter:drop-shadow(0 0 1px rgba(0,0,0,.3)); }
.crest-fallback { display:inline-flex; align-items:center; justify-content:center; width:24px; height:24px; border-radius:50%; color:#fff; font-size:11px; font-weight:700; flex:0 0 auto; }
.lg-logo { width:22px; height:22px; object-fit:contain; border-radius:4px; flex:0 0 auto; background:transparent; }
.lg-leg { display:inline-flex; align-items:center; gap:5px; margin-right:14px; font-size:12px; color:var(--text2); cursor:pointer; user-select:none; -webkit-user-select:none; }
.lg-leg:hover { color:var(--text-strong); }
.lg-leg.off { opacity:.35; text-decoration:line-through; }
.lg-leg i { width:11px; height:11px; border-radius:3px; display:inline-block; }
.sub { font-size:10px; color:var(--text-muted); font-weight:400; }
/* 队伍列按内容自适应（不撑满整列），冠军/升班马图标紧跟积分，避免被推到列尾 */
.tmeta { display:flex; align-items:center; gap:0; min-width:0; flex:1 1 auto; }
.tagroup { display:inline-flex; align-items:center; gap:0; flex:0 0 auto; margin-left:6px; }
.tcell .nm { font-weight:600; color:var(--text-strong); white-space:pre; overflow:hidden; text-overflow:ellipsis; min-width:0; flex:0 1 auto; }
.tcell .nm.up-clr { color:var(--green); }
.tcell .nm.down-clr { color:#e74c3c; }
.pts-inline { margin-left:0; font-size:11.5px; font-weight:700; color:var(--text-muted); font-variant-numeric:tabular-nums; white-space:nowrap; }
.pts-inline .u { font-size:10px; font-weight:600; opacity:.75; margin-left:1px; }
.champ { color:var(--rk); margin-left:3px; display:inline-flex; flex:0 0 auto; vertical-align:-2px; }
.champ svg { width:13px; height:13px; display:block; }
.move { display:inline-flex; align-items:center; justify-content:center; width:16px; height:16px; border-radius:4px; margin-left:3px; flex:0 0 auto; font-size:10px; line-height:1; font-weight:800; }
.move.up { color:#fff; background:var(--green); }
.move.down { color:#fff; background:#e74c3c; }
/* 行政降级 / 除名：非竞技原因（财务、注册裁定）被迫离队，与竞技降级区分 */
.move.adm { color:#2a1c05; background:#f0a92e; box-shadow:0 0 0 1px rgba(240,169,46,.9) inset; }
.bcell { display:inline-flex; align-items:center; gap:7px; justify-content:center; }
.bcell .bb { width:46px; max-width:46px; height:6px; border-radius:3px; background:var(--card2); overflow:hidden; }
.bcell .bb i { display:block; height:100%; border-radius:3px; }
.bcell .bn { font-variant-numeric:tabular-nums; color:var(--text2); min-width:16px; text-align:right; }
.team-table td.col-sel { background:var(--col-sel-bg); }
.team-table td.col-sel .bn { color:var(--accent); font-weight:700; }
.team-table th.th2 { white-space:normal; line-height:1.25; font-size:11.5px; }
.team-table td.ev { font-variant-numeric:tabular-nums; color:var(--text2); }
.team-table td.ev.na { color:var(--text-muted); opacity:.5; }

/* ---------- 表格工具条：比分明细折叠 / 展开 ---------- */
.teamtools { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin:0 0 9px; }
.ttbtn { display:inline-flex; align-items:center; gap:6px; font:inherit; font-size:12.5px; font-weight:600; color:var(--text-dim); background:var(--card); border:1px solid var(--border); border-radius:999px; padding:6px 13px; cursor:pointer; transition:color .15s,border-color .15s,background .15s; }
.ttbtn:hover { color:var(--accent); border-color:var(--accent); }
.ttbtn svg { width:14px; height:14px; display:block; }
.ttbtn.on { color:var(--accent); border-color:var(--accent); background:var(--col-sel-bg); }
.ttsort { font-size:12px; color:var(--accent); background:var(--col-sel-bg); border:1px solid var(--border); border-radius:999px; padding:5px 11px; cursor:pointer; display:none; }
.tthint { font-size:12px; color:var(--text-muted); }
@media(max-width:820px){ .tthint { display:none; } }

/* 悬停浮层（查看该队各比分平局明细） */
.rtip { position:fixed; z-index:70; pointer-events:none; background:var(--card); border:1px solid var(--border); border-radius:10px; box-shadow:0 6px 22px rgba(0,0,0,.30); padding:9px 12px; font-size:12.5px; color:var(--text-dim); display:none; white-space:nowrap; line-height:1.75; }
.rtip .rt-h { font-weight:700; color:var(--text-strong); margin-bottom:3px; }
.rtip .rt-r { display:flex; align-items:center; gap:7px; }
.rtip .rt-r i.dot { width:8px; height:8px; border-radius:50%; display:inline-block; }
.rtip .rt-r b { color:var(--text-strong); font-variant-numeric:tabular-nums; margin-left:auto; padding-left:18px; }
.rtip .rt-f { margin-top:4px; padding-top:4px; border-top:1px solid var(--border); color:var(--text-muted); font-size:11.5px; }

/* 移动端：排名列与队名列一起冻结，横向滑动时始终可见 */
@media(max-width:820px){
  .team-table th.rkcol, .team-table td.rkcol { position:sticky; left:0; z-index:3; width:38px; min-width:38px; max-width:38px; background:var(--card); }
  .team-table th.rkcol { background:var(--card2); z-index:4; }
  .team-table tbody tr:hover td.rkcol { background:var(--card2); }
  .team-table th.namecol, .team-table td.namecol { position:sticky; left:38px; z-index:2; min-width:126px; max-width:146px; background:var(--card); box-shadow:-1px 0 0 var(--border); }
  .team-table th.namecol { background:var(--card2); z-index:3; }
  .team-table tbody tr:hover td.namecol { background:var(--card2); }
  .tmeta { flex-direction:column; align-items:flex-start; line-height:1.25; }
  .tagroup .pts-inline { margin-left:0; font-size:10.5px; }
  /* 联赛条/赛季条在移动端改为横向滑动单行 */
  .season-tabs, .league-tabs { flex-wrap:nowrap; overflow-x:auto; justify-content:flex-start; scrollbar-width:none; -webkit-overflow-scrolling:touch; }
  .season-tabs::-webkit-scrollbar, .league-tabs::-webkit-scrollbar { display:none; }
  .stickynav { padding:0 0 5px; }
  /* 页头在窄屏收起副标题与面包屑，只留 标志 + 站名 + 主题 */
  .site-head { gap:8px; padding:0 0 10px; }
  .brand .mark { width:32px; height:32px; border-radius:9px; }
  .brand-txt .nm { font-size:19px; letter-spacing:1.5px; }
  .brand-txt .sl { display:none; }
  .crumb { display:none; }
  .theme-btn { margin-left:auto; padding:6px 11px; font-size:12px; }
  .scroll-nav { right:auto; left:14px; bottom:14px; }
}
@media(max-width:400px){ .brand-txt .nm { font-size:18px; letter-spacing:1px; } .theme-btn { padding:6px 9px; font-size:11px; } }

.more-hint { position:absolute; right:1px; top:50%; transform:translateY(-50%); height:48px; width:34px; padding-left:14px; border-radius:24px 0 0 24px; background:linear-gradient(90deg,transparent,var(--card) 55%); display:flex; align-items:center; justify-content:flex-end; color:var(--text-dim); pointer-events:none; transition:opacity .25s; }
.more-hint svg { width:16px; height:16px; display:block; }
.at-end .more-hint { opacity:0; }

.chart-card { background:var(--chart-bg); border:1px solid var(--border); border-radius:12px; padding:16px 12px 8px; overflow-x:auto; }
.trend-svg { display:block; width:100%; height:auto; }
.trend-svg rect.bar { transition:opacity .15s; cursor:pointer; }
.trend-svg rect.bar:hover { opacity:.78; }
.trend-svg circle.pt { cursor:pointer; }
.trend-tip { position:fixed; z-index:60; pointer-events:none; background:var(--card); border:1px solid var(--border); color:var(--text); font-size:12px; line-height:1.5; padding:8px 10px; border-radius:8px; box-shadow:0 4px 16px rgba(0,0,0,.25); display:none; max-width:280px; white-space:normal; word-break:break-word; }
.trend-tip b { color:var(--text-strong); }
.trend-tip .tip-sep { height:1px; background:var(--border); margin:6px -2px 5px; }
.trend-tip .tip-draw { display:flex; gap:8px; align-items:baseline; padding:1px 0; }
.trend-tip .tip-draw .sc { color:var(--green); font-weight:700; font-variant-numeric:tabular-nums; }

.note { font-size:12px; color:var(--text-muted); background:var(--card); padding:12px 14px; border-radius:8px; border:1px solid var(--border); margin:10px 0 4px; line-height:1.7; }
.footer { text-align:center; padding:20px 12px; color:var(--muted); font-size:12px; margin-top:18px; line-height:1.8; }
.footer .ft-brand { color:var(--text-strong); font-weight:800; letter-spacing:1px; }
.footer a { color:var(--text-dim); text-decoration:underline; text-underline-offset:2px; text-decoration-color:var(--border); }
.footer a:hover { color:var(--accent); text-decoration-color:var(--accent); }
.ft-meta { margin-top:6px; display:flex; flex-wrap:wrap; align-items:center; justify-content:center; gap:7px; font-size:11.5px; color:var(--muted); }
.ft-meta b { color:var(--text-dim); font-weight:700; }
.ft-meta .ft-dot { opacity:.5; }
.ft-meta .ft-auto { display:inline-flex; align-items:center; gap:4px; color:var(--text-dim); }
.ft-meta .ft-auto svg { width:12px; height:12px; display:block; opacity:.85; }
</style>
</head>
<body>
<div class="trend-tip" id="avgTip"></div>

<header class="site-head">
  <div class="brand">
    <svg class="mark" viewBox="0 0 40 40" aria-hidden="true">
      <defs><linearGradient id="qzlGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4a9eff"/><stop offset="1" stop-color="#00b894"/></linearGradient></defs>
      <rect width="40" height="40" rx="11" fill="url(#qzlGrad)"/>
      <g fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="20" cy="20" r="9.4"/>
        <path d="M20 15 L24.76 18.55 L22.94 24.05 L17.06 24.05 L15.24 18.55 Z" fill="#fff" stroke="none"/>
        <path d="M20 15 V10.6"/><path d="M24.76 18.55 L28.99 17.26"/><path d="M22.94 24.05 L25.53 27.61"/>
        <path d="M17.06 24.05 L14.47 27.61"/><path d="M15.24 18.55 L11.01 17.26"/>
      </g>
    </svg>
    <span class="brand-txt">
      <span class="nm">叕中啦</span>
      <span class="sl">叕中啦 · 五大次级联赛平局数据站</span>
    </span>
  </div>
  <nav class="crumb" id="headCrumb" aria-label="当前位置"></nav>
  <button class="theme-btn" id="themeBtn" onclick="toggleTheme()">🌗 自动</button>
</header>
<div class="scroll-nav">
  <button class="scroll-btn" id="toTop" onclick="window.scrollTo({top:0,behavior:'smooth'})" title="回到页头"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5"/><path d="M6 11l6-6 6 6"/></svg></button>
  <button class="scroll-btn" id="toBottom" onclick="window.scrollTo({top:document.documentElement.scrollHeight,behavior:'smooth'})" title="回到页脚"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M6 13l6 6 6-6"/></svg></button>
</div>

<div class="container">
  <div class="stickynav">
    <div class="league-tabs" id="leagueTabs"></div>
    <div class="navrow">
      <div class="season-tabs" id="seasonTabs"></div>
      <div class="win-switch" id="winSwitch" role="group" aria-label="赛季范围"></div>
    </div>
  </div>

  <div id="viewSeason">
    <div class="stat-strip" id="statGrid"></div>

    <div class="section-title" id="stOverall"></div>
    <div id="overview"></div>
    <div class="ov-note" id="ovNote"></div>

    <div class="section-title" id="stTrend"></div>
    <div class="chart-card"><div id="trend"></div></div>

    <div class="section-title" id="stTeams"></div>
    <div class="teamtools" id="teamTools">
      <button class="ttbtn" id="bkToggleTeam" type="button"></button>
      <span class="ttsort" id="teamSortChip"></span>
    </div>
    <div class="tw-wrap" id="teamWrap">
      <div class="tw" id="teamScroll">
        <table class="team-table" id="teamTable"></table>
      </div>
      <div class="more-hint"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
    </div>
    <div class="note" id="teamNote"></div>
    <div class="section-title" id="form5Title">本赛季各队胜平负走势分布</div>
    <div class="note" id="form5Note"></div>
    <div class="form5-filter" id="form5Filter"></div>
    <div class="form5-strips" id="form5Strips"></div>
  </div>

  <div id="viewOverview">
    <div class="section-title" id="stTop"></div>
    <div class="findings" id="findings"></div>
    <div class="top-tools" id="topTools">
      <span id="topGroups"></span>
      <span class="cnt-note" id="topCount"></span>
    </div>
    <div class="tw-wrap" id="topWrap">
      <div class="tw" id="topScroll">
        <table class="team-table top-table" id="topTable"></table>
      </div>
      <div class="more-hint"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
    </div>
    <div class="note" id="topNote"></div>

    <div class="section-title" id="cmpTitle">近五赛季横向对比
      <span class="note-flag">五个赛季的平局总量、平局率与比分结构对照；右侧三列为「球队 + 场次数」，🏆 表示该队为该季冠军；点击表格中的赛季名或折线上的圆点可直接跳转查看该赛季。</span>
    </div>
    <div class="tw-wrap" id="cmpWrap">
      <div class="tw" id="cmpScroll">
        <table class="cmp-table" id="cmpTable"></table>
      </div>
      <div class="more-hint"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
    </div>
    <div class="chart-card" style="margin-top:12px"><div id="cmpChart"></div></div>
    <div class="note" id="cmpNote"></div>
  </div>

  <div id="viewBig5">
    <div class="section-title" id="big5Title">五大次级联赛横向对照
      <span class="note-flag" id="big5TitleNote"></span>
    </div>
    <div class="tw-wrap" id="big5Wrap">
      <div class="tw" id="big5Scroll">
        <table class="cmp-table" id="big5Table"></table>
      </div>
      <div class="more-hint"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg></div>
    </div>
    <div class="chart-card" style="margin-top:12px"><div id="big5Chart"></div></div>
    <div class="note" id="big5Note"></div>
  </div>

  <div class="footer">
    <div><span class="ft-brand">叕中啦</span> · 五大次级联赛平局数据站　｜　数据源：<a href="https://github.com/openfootball" target="_blank">openfootball</a>（football.json 与各联赛国别仓库）</div>
    <div class="ft-meta">
      <span title="原始赛果文件最近一次抓取落盘的时间">数据源更新 <b id="ftSrc">–</b></span>
      <span class="ft-dot">·</span>
      <span title="本页最近一次重新生成的时间">本页更新 <b id="ftGen">–</b></span>
      <span class="ft-dot">·</span>
      <span class="ft-auto" title="由本机定时任务每日 09:00 拉取赛果并重新生成本页">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/></svg>每日 09:00 自动更新
      </span>
    </div>
  </div>
</div>

<div class="rtip" id="rowTip"></div>
<div class="trend-tip" id="topTip"></div>
<div class="trend-tip" id="formTip" style="max-width:300px"></div>

<script>
const DATA = __DATA__;
const esc = s => String(s==null?'':s).replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const SCORE_COLORS = __SCORES__;
const RESULT_COLORS = __RESULTS__;
const CRESTS = DATA.crestByTeam;
const LG_LOGO = DATA.logoByCode;
const LG_COLOR = {en:'#4a9eff', es:'#fdcb6e', de:'#e17055', it:'#00b894', fr:'#a29bfe'};

/* ---------------- 主题：自动 → 浅色 → 深色 三态循环 ----------------
   〔自动〕跟随系统外观（prefers-color-scheme），系统一变页面立刻跟着变；
   浏览器不支持该媒体查询时，退回按本地时间 6:00–18:00 为浅色。
   全程离线判定、不发任何网络请求（保持单文件离线可用），选择存 localStorage 持久化。   */
const THEME_KEY = 'qzl_theme';
function paintTheme(t){
  document.documentElement.setAttribute('data-theme', t);
  const m = document.querySelector('meta[name="theme-color"]');
  if(m) m.setAttribute('content', t === 'dark' ? '#0f1117' : '#eef1f6');
}
function sysTheme(){
  try{
    if(typeof window.matchMedia === 'function'){
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
  }catch(e){}
  const h = new Date().getHours();          // 兜底：白天浅色、夜间深色
  return (h >= 6 && h < 18) ? 'light' : 'dark';
}
function refreshThemeBtn(mode, actual){
  const b = document.getElementById('themeBtn'); if(!b) return;
  if(mode === 'auto'){ b.textContent = (actual === 'dark' ? '🌗 自动·深色' : '🌗 自动·浅色'); b.title = '自动跟随系统外观（点击切换）'; }
  else if(mode === 'light'){ b.textContent = '☀️ 浅色'; b.title = '固定浅色（点击切换）'; }
  else { b.textContent = '🌙 深色'; b.title = '固定深色（点击切换）'; }
}
// 模式以内存变量为准（localStorage 只是持久化；file://、隐私模式、jsdom 下可能不可用）
let themeMode = 'auto';
function applyMode(mode){
  themeMode = mode;
  try{ localStorage.setItem(THEME_KEY, mode); }catch(e){}
  const actual = (mode === 'auto') ? sysTheme() : mode;
  paintTheme(actual); refreshThemeBtn(mode, actual);
}
function toggleTheme(){
  applyMode(themeMode === 'auto' ? 'light' : (themeMode === 'light' ? 'dark' : 'auto'));
}
function curMode(){ return themeMode; }
(function(){
  let saved = null; try{ saved = localStorage.getItem(THEME_KEY); }catch(e){}
  if(saved !== 'auto' && saved !== 'light' && saved !== 'dark') saved = 'auto';
  applyMode(saved);
  // 系统外观实时切换（仅「自动」模式生效）
  try{
    if(typeof window.matchMedia === 'function'){
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      const onChange = ()=>{ if(curMode() === 'auto') applyMode('auto'); };
      if(mq.addEventListener) mq.addEventListener('change', onChange);
      else if(mq.addListener) mq.addListener(onChange);   // 老 Safari
    }
  }catch(e){}
  // 从后台切回前台时重新判定（可能已跨过日出/日落或改过系统主题）
  if(document.addEventListener && document.visibilityState !== undefined){
    document.addEventListener('visibilitychange', ()=>{
      if(document.visibilityState === 'visible' && curMode() === 'auto') applyMode('auto');
    });
  }
})();

/* ---------------- 联赛 + 赛季切换 ---------------- */
let curLeague = DATA.leagues[0].code;
let currentSeason = DATA.seasonOrder[0];
let curView = 'overview';   // 'overview' = 跨赛季总览页；否则为某个赛季键
let showBig5 = false;       // true = 一级「五大次级联赛」Tab：跨联赛横向对照（模块六）
// 赛季窗口：5 = 近五赛季（2021-22~2025-26）；3 = 近三赛季（2023-24~2025-26）
// 所有「跨赛季」口径（总览页 / 逐年格 / 横向对比 / 五大对照）都跟着它走，由数据层预生成两套结果
let SEASON_WIN = 5;
function LG(){ return DATA.leagues.find(l=>l.code===curLeague); }
function sc(){ return LG().seasons[currentSeason]; }
function winKey(){ return SEASON_WIN === 3 ? 'cross3' : 'cross'; }
function CMP(){ return (SEASON_WIN === 3 ? DATA.compare3 : DATA.compare) || DATA.compare; }
function CR(){ return LG()[winKey()] || LG().cross; }
function winSeq(){ return DATA.seasonOrder.filter(k=>k!=='2026-27').slice(0, SEASON_WIN); }   // 新 → 旧；进行中的 2026-27 不进入总览窗口
function WN(){ return SEASON_WIN === 3 ? '三' : '五'; }              // 中文数字，用于文案
function WLAB(){ return SEASON_WIN === 3 ? '近三赛季' : '近五赛季'; }
function setWin(n){
  n = +n;
  if(n !== 3 && n !== 5) return;
  if(n === SEASON_WIN) return;
  SEASON_WIN = n;
  // 当前赛季若已被窗口裁掉（如从近五季切到近三季时还停在 2022-23），自动落到窗口内最新一季
  if(curView !== 'overview' && winSeq().indexOf(currentSeason) < 0) currentSeason = winSeq()[0];
  applyWinLabels();   // 同步所有「近X季/三/五」硬编码文案
  render();
}
function applyWinLabels(){
  // 把分散在 HTML 模板里的「近五赛季」「五季全勤」等硬编码文案统一跟随机型窗口
  const t = document.getElementById('cmpTitle');
  if(t) t.textContent = WLAB()+'横向对比';
  const n = document.getElementById('cmpNote');
  if(n) n.textContent = '五个联赛'+WLAB()+'的平局总量、平局率与比分结构对照；点击表头可按平局场次 / 平局率 / 各比分排序；折线按联赛着色展示各自走势。';
  const b5 = document.getElementById('big5TitleNote');
  if(b5) b5.innerHTML = '五个联赛'+WLAB()+'的平局总量、平局率与比分结构对照；点击表头可按平局场次 / 平局率 / 各比分排序；折线按联赛着色展示各自走势。';
}
function lgLogo(code){ return LG_LOGO[code] || ''; }
function prevSeasonKey(){
  const i = DATA.seasonOrder.indexOf(currentSeason);
  return (i>=0 && i+1<DATA.seasonOrder.length) ? DATA.seasonOrder[i+1] : null;
}
function fmtSeason(code){
  // 短码 '2025-26' → 完整 '2025-2026'，便于统一展示、避免歧义
  const m = /^(\d{4})-(\d{2})$/.exec(code||'');
  if(!m) return code;
  return m[1] + '-' + (m[1].slice(0,2) + m[2]);
}
// 自由文本里的赛季码同样统一为完整格式（如「2026-27 赛季名单尚不完整」→「2026-2027 赛季…」）
// 仅匹配 4 位-2 位的年份组合，比分「3-3」这类不会被误伤
function fmtText(t){
  return String(t==null?'':t).replace(/(\d{4})-(\d{2})\b/g, (m,a,b)=> a + '-' + (a.slice(0,2) + b));
}
function buildLeagueTabs(){
  const el = document.getElementById('leagueTabs');
  const lg = DATA.leagues.map(l=>{
    const cr = (CMP().rows.find(r=>r.code===l.code)||{});
    const s0 = l.seasons[winSeq()[0]];
    return '<div class="league-tab'+(l.code===curLeague && !showBig5?' active':'')+'" data-k="'+l.code+'" title="'+l.name+'：'+fmtSeason(winSeq()[0])+' 平局 '+s0.totalDraws+' 场，平局率 '+s0.drawRate+'%">'+
      '<img src="'+lgLogo(l.code)+'" alt="'+l.cn+'">'+l.cn+
      '<span class="rt">'+(cr.drawRate!=null?cr.drawRate:'–')+'%</span></div>';
  }).join('');
  // 模块六：五大次级联赛横向对照，作为第 6 个一级 Tab，放在「法乙」之后
  const big5 = '<div class="league-tab big5'+(showBig5?' active':'')+'" data-k="__big5__" title="五大次级联赛（英冠/西乙/德乙/法乙/意乙）'+WLAB()+'平局横向对照（模块六）：跨联赛的总平局、平局率与比分结构"><svg class="uefa-logo" viewBox="0 0 30 18" aria-label="次级联赛"><rect x="0" y="0" width="30" height="18" rx="3" fill="#0a1f44"/><text x="15" y="12.5" font-family="Arial,Helvetica,sans-serif" font-size="9" font-weight="800" fill="#fff" text-anchor="middle" letter-spacing="0.5">2ND</text></svg>五大次级联赛<span class="rt">对照</span></div>';
  el.innerHTML = lg + big5;
  el.querySelectorAll('.league-tab').forEach(b=>{
    b.onclick = ()=>{
      const k = b.getAttribute('data-k');
      if(k==='__big5__'){ showBig5=true; }
      else { showBig5=false; curLeague = k; }
      render();
    };
  });
}
function buildSeasonTabs(){
  const el = document.getElementById('seasonTabs');
  // 「五大次级联赛」Tab 是跨联赛横向对照，没有单赛季维度 —— 只清空年份按钮；
  // 容器本身保留占位（flex:1），这样右侧「范围」开关仍停在原来的位置不动。
  if(showBig5){ el.innerHTML=''; buildWinSwitch(); return; }   // 只清空年份按钮；容器保留 flex:1 占位，「范围」开关不位移
  el.style.display='';
  // 范围开关同时控制「赛季 tab 按钮」：近三季时隐藏 2022-23/2021-22，进行中的 2026-27 始终保留。
  // 跨赛季口径（总览页）一直跟着 winSeq() 走，这一步把单联赛视图下的 tab 也接上，避免「
  // 切到近三季后，赛季栏还出现被裁掉的旧年份按钮」的不一致。
  const ws = DATA.seasonOrder.filter(k => k === '2026-27' || winSeq().indexOf(k) >= 0);
  const ov = '<div class="season-tab ov'+(curView==='overview' && !showBig5?' active':'')+'" data-k="__overview__" title="赛季总览：跨赛季总览（模块四 / 五），口径随右侧「近五季 / 近三季」切换">赛季总览</div>';
  const seas = ws.map(k=>{
    const s = LG().seasons[k];
    return '<div class="season-tab'+(k===currentSeason && curView!=='overview' && !showBig5?' active':'')+'" data-k="'+k+'" title="'+LG().cn+' '+fmtSeason(k)+' 赛季：'+s.totalMatches+' 场中 '+s.totalDraws+' 场平局，平局率 '+s.drawRate+'%">'+fmtSeason(k)+'<span class="cnt">'+s.totalDraws+'场</span></div>';
  }).join('');
  el.innerHTML = seas + ov;   // 总览 Tab 放到赛季 Tab 最后
  buildWinSwitch();
  el.querySelectorAll('.season-tab').forEach(b=>{
    b.onclick = ()=>{
      const k = b.getAttribute('data-k');
      showBig5 = false;   // 切赛季/总览即离开「五大次级联赛」Tab
      if(k==='__overview__'){ curView='overview'; }
      else { curView=k; currentSeason=k; }
      render();
    };
  });
}
/* 赛季范围开关：近五季 ⇄ 近三季。
   用「分段开关」而不是单个切换按钮 —— 两个选项常驻、高亮项即当前口径，
   避免「按钮文案写下一步动作、高亮写当前状态」造成的歧义（与总榜的范围开关同理）。 */
function buildWinSwitch(){
  const el = document.getElementById('winSwitch');
  if(!el) return;
  const seq = winSeq(), last = fmtSeason(seq[seq.length-1]), first = fmtSeason(seq[0]);
  const opt = (n, label) => '<button type="button" class="wbtn'+(SEASON_WIN===n?' on':'')+'" data-win="'+n+
    '" title="跨赛季统计口径切换为最近 '+n+' 个赛季（'+last+' → '+first+'）">'+label+'</button>';
  el.innerHTML =
    '<span class="wlab" title="跨赛季统计的赛季范围"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.2 2"/></svg>范围</span>'+
    opt(5,'近五季') + opt(3,'近三季');
  el.querySelectorAll('[data-win]').forEach(b=>{
    b.onclick = ()=> setWin(+b.getAttribute('data-win'));
  });
}

function crestImg(name){
  const c = CRESTS[name];
  if(c) return '<img class="crest" src="'+c+'" alt="'+name+'">';
  const init = name.replace(/[^A-Za-z ]/g,'').split(' ').map(w=>w[0]).join('').slice(0,3).toUpperCase();
  return '<span class="crest-fallback" style="background:#4a9eff">'+init+'</span>';
}
const CHAMP_SVG = '<span class="champ" title="当季冠军"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9H4.5a2.5 2.5 0 0 1 0-5H6"/><path d="M18 9h1.5a2.5 2.5 0 0 0 0-5H18"/><path d="M4 22h16"/><path d="M10 14.66V17c0 .55-.47.98-.97 1.21C7.85 18.75 7 20.24 7 22"/><path d="M14 14.66V17c0 .55.47.98.97 1.21C16.15 18.75 17 20.24 17 22"/><path d="M18 2H6v7a6 6 0 0 0 12 0V2Z"/></svg></span>';

/* ---------------- 比分明细折叠：默认收起，hover 浮层查看 ----------------
   队表四列比分（0-0/1-1/2-2/其他）默认收起以保持整洁；点「展开比分明细」按钮可展开为四列。
   跨赛季总榜（近五赛季平局总榜）无比分明细列。
   需要明细时：鼠标悬停任意一行即弹出浮层，显示该队各比分平局场数。         */
const BK_KEYS = ['d00','d11','d22','dother'];
let showBuckets = false;          // 队表比分明细默认收起（保持整洁）
let showBucketsTop = true;        // 总榜已无比分明细列，此开关仅保留兼容
try { const _bk = localStorage.getItem('wb5_buckets'); if (_bk !== null) showBuckets = _bk === '1'; } catch(e){}
try { const _bk = localStorage.getItem('wb5_buckets_top'); if (_bk !== null) showBucketsTop = _bk === '1'; } catch(e){}
const ICO_SHOW = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1.8 12S5.4 5.6 12 5.6 22.2 12 22.2 12 18.6 18.4 12 18.4 1.8 12 1.8 12Z"/><circle cx="12" cy="12" r="3"/></svg>';
const ICO_HIDE = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.6 10.6 0 0 1 12 19.4C5.4 19.4 1.8 12 1.8 12a19 19 0 0 1 5.06-6.06"/><path d="M9.9 4.3A9.1 9.1 0 0 1 12 4.6c6.6 0 10.2 7.4 10.2 7.4a19.4 19.4 0 0 1-2.16 3.19"/><path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="2" y1="2" x2="22" y2="22"/></svg>';
function visCols(cols, flag){ const f = (flag===undefined?showBuckets:flag); return f ? cols : cols.filter(c=>c.grp!=='score'); }
function numOf(v){ return (v===null || v===undefined) ? Infinity : v; }
function cmpVal(a,b,key,dir){
  const va=numOf(a[key]), vb=numOf(b[key]);
  if(va===vb) return 0;
  if(typeof va==='string' || typeof vb==='string') return dir*String(va).localeCompare(String(vb));
  return dir*(va-vb);
}
function labelOf(c){ return String(c.label).replace(/<br\s*\/?>/gi,' '); }
function syncBkBtns(){
  // 总榜已无比分明细列，隐藏其折叠按钮
  const bt = document.getElementById('bkToggleTop');
  if(bt) bt.style.display='none';
  const map = {bkToggleTeam: showBuckets};
  Object.entries(map).forEach(([id, on])=>{
    const b = document.getElementById(id);
    if(!b) return;
    const txt = on ? '收起比分明细' : '展开比分明细（0-0 / 1-1 / 2-2 / 其他）';
    b.innerHTML = (on?ICO_HIDE:ICO_SHOW)+'<span>'+txt+'</span>';
    b.className = 'ttbtn'+(on?' on':'');
    b.title = on ? '点击隐藏 0-0 / 1-1 / 2-2 / 其他 四列，表格更紧凑'
                 : '点击显示 0-0 / 1-1 / 2-2 / 其他 四列';
  });
}
function bindBkToggle(){
  const hand = {
    bkToggleTop:  ()=>{ showBucketsTop = !showBucketsTop;
      try { localStorage.setItem('wb5_buckets_top', showBucketsTop?'1':'0'); } catch(e){} },
    bkToggleTeam: ()=>{ showBuckets = !showBuckets;
      try { localStorage.setItem('wb5_buckets', showBuckets?'1':'0'); } catch(e){} }
  };
  ['bkToggleTop','bkToggleTeam'].forEach(id=>{
    const b = document.getElementById(id);
    if(b) b.onclick = ()=>{
      hand[id]();
      if(!showBuckets && BK_KEYS.indexOf(teamSort.key)>=0) teamSort = {key:'rank', dir:1};   // 队表收起：复位被隐藏列的排序
      if(!showBucketsTop && BK_KEYS.indexOf(topSort.key)>=0) topSort = {key:'total', dir:-1}; // 总榜同理
      syncBkBtns(); renderTop(); renderTeams();
    };
  });
}
function bindSortChip(elId, cols, sortState, resetFn, collapsed){
  const el = document.getElementById(elId);
  if(!el) return;
  const c = cols.find(x=>x.key===sortState.key);
  if(!c || !c.grp || collapsed){ el.style.display='none'; return; }
  el.style.display='inline-block';
  el.innerHTML = '当前按「'+labelOf(c)+'」'+(sortState.dir<0?'降序 ▼':'升序 ▲')+'排序 · 点此恢复默认';
  el.onclick = resetFn;
}
function bkCells(t){
  return [['0-0',t.d00],['1-1',t.d11],['2-2',t.d22],['其他',t.dother]];
}
function totalOf(t){ return (t.draws!==undefined) ? t.draws : t.total; }
let rowTip = null;
function tipEl(){ rowTip = rowTip || document.getElementById('rowTip'); return rowTip; }
function showRowTip(t, e){
  const el = tipEl(); if(!el) return;
  const S = SCORE_COLORS;
  const rows = bkCells(t).map(function(x){
    return '<div class="rt-r"><i class="dot" style="background:'+S[x[0]]+'"></i>'+x[0]+'<b>'+(x[1]||0)+' 场</b></div>';
  }).join('');
  const foot = (t.every===null||t.every===undefined) ? '全季 0 平局' : '平均 '+t.every+' 轮出一次平局';
  el.innerHTML = '<div class="rt-h">'+t.cn+'</div>'+rows+
    '<div class="rt-f">'+(t.seasons?('五年累计 '):'')+'平局 '+totalOf(t)+' 场 · '+foot+'</div>';
  el.style.display='block'; moveRowTip(e);
}
function moveRowTip(e){
  const el = tipEl(); if(!el || !e) return;
  const w = el.offsetWidth || 190, h = el.offsetHeight || 100;
  let x = e.clientX + 14, y = e.clientY + 14;
  if(x + w > window.innerWidth - 8)  x = e.clientX - w - 14;
  if(y + h > window.innerHeight - 8) y = e.clientY - h - 14;
  el.style.left = Math.max(6,x)+'px';
  el.style.top  = Math.max(6,y)+'px';
}
function hideRowTip(){ const el = tipEl(); if(el) el.style.display='none'; }
function bindMiniTips(nodes){
  const tip = document.getElementById('avgTip');
  if(!tip) return;
  nodes.forEach(el=>{
    el.addEventListener('mousemove', e=>{
      tip.style.display='block';
      tip.innerHTML = el.getAttribute('data-tip') || '';
      let x=e.clientX+12, y=e.clientY+12;
      tip.style.left=x+'px'; tip.style.top=y+'px';
      const r=tip.getBoundingClientRect(), pad=8;
      if(x+r.width>window.innerWidth-pad) x=Math.max(pad,window.innerWidth-r.width-pad);
      if(y+r.height>window.innerHeight-pad) y=Math.max(pad,window.innerHeight-r.height-pad);
      tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    el.addEventListener('mouseleave', ()=>{ tip.style.display='none'; });
  });
}
/* 给表格行挂上「悬停浮层」查看比分明细（不挂点击事件：行不再可点开） */
function bindRowDetail(table, rows){
  table.querySelectorAll('tbody tr.trow').forEach(tr=>{
    const t = rows[+tr.getAttribute('data-i')];
    if(!t) return;
    tr.addEventListener('mouseenter', e=>{ showRowTip(t, e); });
    tr.addEventListener('mousemove',  e=>{ moveRowTip(e); });
    tr.addEventListener('mouseleave', hideRowTip);
  });
}

/* ---------------- 近五赛季跨赛季总榜（页头） ---------------- */
const TOP_COLS=[
  {key:'rank',      label:'#',      rk:true},
  {key:'name',      label:'球队',    namecol:true},
  {key:'per',       label:'逐年平局', yrcol:true},
  {key:'total',     label:'总平局', totalcol:true},
  {key:'avgSeason', label:'季均'},
  {key:'sd',        label:'稳定度 σ', sdcol:true},
  {key:'rate',      label:'平局率', ratecol:true, title:'平局率：该队在窗口内（近五/近三赛季）全部比赛里的平局比例（＝平局场次 ÷ 总场次 ×100%）。直接回答「这支球队多大概率出平局」，比 σ 与「平局粘性」更直观；越高越爱平局。'},
  {key:'maxStreak', label:'最长连平', hov:'streakSeason', hovtxt:'最长连平'},
  {key:'gap',       label:'最长<br>间隔', hov:'gapSeason', hovtxt:'最长无平局间隔'},
];
let topSort   = {key:'total', dir:-1};
// 跨赛季总榜筛选：三个独立开关（五季全勤 / 稳定度≤2 / 高平局率≥25%），选中=只看该子集，非选中=清除
const RATE_HI = 25;                                  // 高平局率门槛（=25%）
let topFilter = {full:false, stab2:false, rateHi:false, limit:10};
let big5Sort  = {key:'order', dir:1};   // order = 联赛 Tab 顺序（默认）；其余按列排序

function topRows(){
  // ⚠ 必须拷贝：CR().teams 是 DATA 里的常驻数组，直接 sort 会把底层数据的顺序改掉
  let rows = CR().teams.slice();
  // 平局率 t.rate 已由数据层产出（窗口感知：近五季 / 近三季），此处无需重算，直接用于排序与展示

  // ① 先定「数据范围」：不限量=当前联赛全部球队；限量=按总平局取前 N 名作为固定候选池
  if(topFilter.limit){
    rows = rows.sort((a,b)=> b.total - a.total).slice(0, topFilter.limit);
  }
  // ② 再在候选池内筛选——只做减法，绝不从池外补数据
  //    （例：前 10 名 + 五季全勤 = 前 10 名里的全勤队，不会拿 10 名外的全勤队补满 10 行）
  // 「全勤」= 窗口内每个赛季都在：窗口 5 季即 5 季全勤，切到近三季即 3 季全勤
  if(topFilter.full)  rows = rows.filter(t=>t.seasons===SEASON_WIN);
  if(topFilter.stab2) rows = rows.filter(t=>t.seasons>=3 && t.sd<=2);
  if(topFilter.rateHi) rows = rows.filter(t=> (t.rate||0) >= RATE_HI);   // 高平局率：≥25%
  // ③ 排序只在最终名单内重排，同样不引入池外球队
  return rows.sort((a,b)=>{
    const r = cmpVal(a,b,topSort.key,topSort.dir);
    return r !== 0 ? r : (b.total - a.total);
  });
}
function yrCell(t){
  const seq = CR().seasonSeq;                          // 原始顺序（旧→新）
  const idxOf = s => seq.indexOf(s);
  const seqRev = seq.slice().reverse();                // 显示顺序：新→旧（左→右 2025-26 … 2021-22）
  const mx = Math.max(...t.per.filter(x=>x!==null && x!==undefined), 1);
  return '<span class="yrcell">'+seqRev.map(s=>{
    const v = t.per[idxOf(s)];
    if(v===null || v===undefined) return '<i class="na" title="'+fmtSeason(s)+' 赛季未征战'+LG().cn+'">–</i>';
    const a = (0.10 + 0.70*(v/mx)).toFixed(3);
    return '<i class="'+(s===currentSeason?'cur':'')+'" style="background:rgba(74,158,255,'+a+')" title="'+fmtSeason(s)+'：'+v+' 场平局">'+v+'</i>';
  }).join('')+'</span>';
}
function sdColor(v){ return v<=1 ? 'var(--green)' : (v<=2 ? 'var(--accent)' : '#e17055'); }

function renderFindings(){
  const m = CR().meta, top = m.topTotal, L = LG().cn;
  const perStr = top.per.map(x=>(x===null?'–':x)).join(' / ');
  const nSeas = top.per.filter(x=>x!==null).length;
  const WY = WN()+'年';                                  // 五年 / 三年
  const sHi = m.stableHi.length
    ? '只剩 <span class="hi">'+m.stableHi.join('、')+'</span>：'+top.cn+' '+WY+' '+perStr+'，合计 <b>'+top.total+
      '</b> 场（季均 '+(top.total/nSeas).toFixed(1)+' 场），最低的一季也有 <b>'+Math.min(...top.per.filter(x=>x!==null))+'</b> 场。'
    : '无一队达到。';
  const sdList = m.steady.map(s=>'<b>'+s.cn+'</b> σ='+s.sd.toFixed(2)+'（极差 '+s.range+'）').join('、');
  const stList = m.stable.length ? '<span class="ok">'+m.stable.join('、')+'</span>'
                                 : '<span class="hi">无</span>';
  const f = [
    '<span class="fi">📌</span><div>'+WLAB()+'共 <b>'+m.nTeams+'</b> 支球队征战'+L+'，其中 <b>'+m.nFull+'</b> 支'+WN()+'季全勤。</div>',
    '<span class="fi">✅</span><div><b>有 '+m.stable.length+' 支球队连续 '+SEASON_WIN+' 季每年至少 '+m.th+' 场平局</b>：'+stList+' —— 这才是真正「稳定输出平局」的球队。</div>',
    '<span class="fi">🏆</span><div>门槛提到<b>每年至少 '+m.thHi+' 场</b>，'+sHi+'</div>',
    '<span class="fi">📉</span><div>若看<b>年际波动</b>（σ 越小越稳）：'+sdList+'。</div>',
  ];
  document.getElementById('findings').innerHTML = f.map(x=>'<div class="fl">'+x+'</div>').join('');
}
function renderTop(){
  const rows = topRows();
  const cols = visCols(TOP_COLS, showBucketsTop);
  const mxSd = Math.max(...CR().teams.map(t=>t.sd), 1);
  const vcol = c => (c.cls ? c.cls+' ' : '')+(c.rk?'rkcol ':'')+'sortable'+(topSort.key===c.key?' sorted':'');
  let head = '<thead><tr>'+cols.map(c=>{
    if(c.namecol) return '<th class="namecol left">'+c.label+'</th>';
    if(c.yrcol){ const seqRev=CR().seasonSeq.slice().reverse();
      return '<th class="yr yrcol" title="最新赛季在左，从左到右为 '+seqRev.map(fmtSeason).join(' → ')+'">'+c.label+'</th>'; }
    const arr = topSort.key===c.key?(topSort.dir<0?'▼':'▲'):'';
    const tip = c.title ? ' title="'+c.title+'"' : '';
    return '<th class="'+vcol(c).trim()+(c.totalcol?' totalcol':'')+'" data-k="'+c.key+'"'+tip+'><span class="arr">'+arr+'</span>'+c.label+'</th>';
  }).join('')+'</tr></thead>';

  let body = '<tbody>';
  rows.forEach((t,i)=>{
    let cells = '';
    cols.forEach(c=>{
      const sel = (topSort.key===c.key?' col-sel':'');
      if(c.rk){
        cells += '<td class="rkcol rk'+sel+'">'+t.rank+'</td>';
      } else if(c.namecol){
        cells += '<td class="namecol left"><div class="tcell">'+crestImg(t.name)+
          '<span class="tmeta"><span class="nm">'+t.cn+'</span></span></div></td>';
      } else if(c.yrcol){
        cells += '<td class="yr yrcol">'+yrCell(t)+'</td>';
      } else if(c.totalcol){
        cells += '<td class="totalcol '+sel.trim()+'">'+t[c.key]+'</td>';
      } else if(c.sdcol){
        const w = Math.round(t.sd/mxSd*40);
        cells += '<td class="'+sel.trim()+'"><span class="sdb"><span class="sb"><i style="width:'+w+'px;background:'+sdColor(t.sd)+'"></i></span><span class="sv">'+t.sd.toFixed(2)+'</span></span></td>';
      } else if(c.ratecol){
        const v = (t.rate||0);
        const RATE_MAX = 35;                                  // 平局率色阶/进度条满格基准（≈联赛上限）
        const w = Math.max(2, Math.round(v/RATE_MAX*46));
        const col = v>=28 ? 'var(--green)' : (v>=24 ? 'var(--accent)' : '#e17055');
        const rateTip = t.cn+'　'+WLAB()+'平局率：<b>'+v.toFixed(2)+'%</b>（平局 '+t.total+' 场 ÷ 总场次 '+t.matches+' 场）';
        cells += '<td class="'+sel.trim()+' mini-tip" data-tip="'+rateTip+'"><span class="bcell"><span class="bb"><i style="width:'+w+'px;background:'+col+'"></i></span><span class="bn">'+v.toFixed(1)+'%</span></span></td>';
      } else if(c.evcol){
        const v = t[c.key];
        cells += '<td class="ev'+(sel||(v===null||v===undefined?' na':''))+'">'+
          ((v===null||v===undefined)?'—':v.toFixed(2))+'</td>';
      } else if(c.color){
        const mx = Math.max(...CR().teams.map(x=>x[c.key]), 1);
        const w = Math.round((t[c.key]||0)/mx*46);
        cells += '<td class="'+sel.trim()+'"><span class="bcell"><span class="bb"><i style="width:'+w+'px;background:'+c.color+'"></i></span><span class="bn">'+(t[c.key]||0)+'</span></span></td>';
      } else if(c.hov){
        const sv = t[c.hov];
        const tip = sv ? (t.cn+'　'+c.hovtxt+' <b>'+t[c.key]+'</b> · '+fmtSeason(sv)+' 赛季')
                      : (t.cn+'　'+c.hovtxt+'：该队'+WN()+'年无此记录');
        cells += '<td class="'+sel.trim()+' hov-cell" data-tip="'+tip+'">'+t[c.key]+'</td>';
      } else {
        cells += '<td class="'+sel.trim()+'">'+t[c.key]+'</td>';
      }
    });
    body += '<tr class="trow" data-i="'+i+'">'+cells+'</tr>';
  });
  body += '</tbody>';

  const table = document.getElementById('topTable');
  // 筛选只做减法，所以「前 10 名 + 某筛选」完全可能筛出 0 队；此时要提示可放宽范围，而不是默默补数据
  const emptyMsg = (topFilter.full || topFilter.stab2)
    ? '当前范围内没有符合条件的球队 —— 筛选只做减法、不会补入范围外的球队，可切到「全部球队」扩大范围'
    : '没有符合条件的球队';
  table.innerHTML = head + (rows.length?body:'<tbody><tr><td colspan="'+cols.length+'">'+emptyMsg+'</td></tr></tbody>');
  table.querySelectorAll('th.sortable').forEach(th=>{
    th.onclick = ()=>{
      const k = th.getAttribute('data-k');
      if(topSort.key===k){ topSort.dir*=-1; }
      else { topSort.key=k; topSort.dir=(k==='rank'||k==='sd')?1:-1; }
      renderTop();
    };
  });
  // 跨赛季总榜无比分明细列，不挂悬停浮层
  // 最长间隔 / 最长连平：用与走势图同款的自定义浮层（替代原生 title，更快更美观）
  const topTip = document.getElementById('topTip');
  table.querySelectorAll('td.hov-cell').forEach(td=>{
    td.addEventListener('mousemove', e=>{
      if(!topTip) return;
      topTip.style.display='block';
      topTip.innerHTML = td.getAttribute('data-tip');
      // 先按默认偏移定位，再根据实际尺寸把浮层夹在视口内，避免内容溢出屏幕
      let x = e.clientX + 12, y = e.clientY + 12;
      topTip.style.left = x + 'px';
      topTip.style.top  = y + 'px';
      const r = topTip.getBoundingClientRect();
      const pad = 8;
      if (x + r.width  > window.innerWidth  - pad) x = Math.max(pad, window.innerWidth  - r.width  - pad);
      if (y + r.height > window.innerHeight - pad) y = Math.max(pad, window.innerHeight - r.height - pad);
      topTip.style.left = x + 'px';
      topTip.style.top  = y + 'px';
    });
    td.addEventListener('mouseleave', ()=>{ if(topTip) topTip.style.display='none'; });
  });
  bindSortChip('topSortChip', TOP_COLS, topSort, ()=>{ topSort={key:'total',dir:-1}; renderTop(); }, showBucketsTop);
  const total = rows.length;
  const cnt = document.getElementById('topCount');
  if(cnt) cnt.innerHTML = '显示 <b style="color:var(--text-strong)">'+total+'</b> 队'+
    (topFilter.limit ? '（范围＝总平局前 '+topFilter.limit+' 名，筛选只在此范围内做减法）' : '');
  renderTopTools();
  syncHint();
}
// 跨赛季总榜：范围 + 筛选按钮区（置于结论模块下方、表格上方）
// ① 范围（前 10 名 / 全部球队）：二选一的**分段开关**，两个选项常驻，高亮项＝当前范围。
//    旧版是单个按钮「显示全部球队 ⇄ 仅看前 10 名」——按钮文案写的是「点下去会做什么」，
//    而高亮表示的是「当前处于什么状态」，两者说的不是一回事，因此有歧义。分段开关可消除该歧义。
// ② 筛选（五季全勤 / 稳定度≤2）：两个**独立开关**，选中=只看该子集，再点=清除。
//    只在①确定的范围内做减法，绝不从范围外补数据。
function renderTopTools(){
  const seg = (val, label) =>
    '<button type="button" class="fb'+(topFilter.limit===val?' on':'')+'" data-lim="'+val+'">'+label+'</button>';
  const item = (id, label) =>
    '<button type="button" class="fb'+(topFilter[id]?' on':'')+'" data-f="'+id+'">'+label+'</button>';
  document.getElementById('topGroups').innerHTML =
    '<span class="tg"><i class="tgl">范围</i><span class="seg" title="按「总平局」取前 10 名作为固定候选范围；筛选只在此范围内做减法，不会从 10 名外补数据">'+
      seg(10,'前 10 名') + seg(0,'全部球队') + '</span></span>'+
    '<span class="tg"><i class="tgl">筛选</i>'+
      item('full', WN()+'季全勤') + item('stab2','稳定度≤2') + item('rateHi','平局率≥25%') + '</span>';
  document.querySelectorAll('#topGroups [data-lim]').forEach(b=> b.onclick=()=>{
    topFilter.limit = +b.getAttribute('data-lim');
    renderTop();
  });
  document.querySelectorAll('#topGroups [data-f]').forEach(b=> b.onclick=()=>{
    const f = b.getAttribute('data-f');
    topFilter[f] = !topFilter[f];
    renderTop();
  });
}
function renderTopMeta(){
  const seqRev = CR().seasonSeq.slice().reverse();   // 显示顺序：新→旧（左→右 2025-2026 … 2021-2022）
  document.getElementById('stTop').innerHTML = LG().cn+'近'+WN()+'赛季平局总榜（'+fmtSeason(CR().seasonSeq[0])+' → '+fmtSeason(CR().seasonSeq[CR().seasonSeq.length-1])+'）'+
    '<span class="note-flag">汇总 '+CR().meta.nTeams+' 支球队'+WN()+'个赛季的平局产出，用于识别「连续多年稳定输出平局」的球队；默认范围为总平局最多的前 10 名，切到「全部球队」可看完整名单，点击表头可排序。</span>';
  const m = CR().meta;
  document.getElementById('topNote').innerHTML =
    '<b>逐年平局</b>：从左到右为 '+seqRev.map(fmtSeason).join(' / ')+'（最新赛季在左），格内为该季平局场数，<b>底色越深越多</b>；「–」表示该季未征战'+LG().cn+'；当前选中赛季的格子带蓝框。'+
    '<b>总平局</b>＝'+WN()+'个赛季平局之和。<b>季均</b>＝总平局 ÷ 参赛赛季数。'+
    '<b>σ（稳定度）</b>＝'+WN()+'个赛季平局数的标准差，<b>越小代表年际波动越小</b>（但只衡量波动大小，不代表平局多寡——σ 低可能只是「稳定地少平局」，σ 高也可能只是个别赛季平局暴涨）。'+
    '<b>平局率</b>＝该队在窗口内全部比赛里的平局比例（平局场次 ÷ 总场次 ×100%，<b>越大越爱平局</b>），比 σ 与「平局粘性」更直观——它直接回答「这支球队多大概率出平局」。'+
    '<b>最长连平</b>＝'+WN()+'年中单季最长连平（悬停看发生赛季）。<b>最长间隔</b>＝'+WN()+'年中单季最长无平局间隔（悬停看发生赛季）。';
}

function renderStats(){
  const s = sc(), teams = s.teams;
  const maxDraw = Math.max(...teams.map(t=>t.draws));
  const maxStreak = Math.max(...teams.map(t=>t.streak));
  const maxGap = Math.max(...teams.map(t=>t.gap));
  const topDraw = teams.filter(t=>t.draws===maxDraw).map(t=>t.cn).join('、');
  const pk = prevSeasonKey();
  let delta = '';
  if(pk){
    const d = +(s.drawRate - LG().seasons[pk].drawRate).toFixed(2);
    const cls = d>0?'up':(d<0?'down':'eq');
    const sym = d>0?'▲':(d<0?'▼':'—');
    delta = '<span class="delta mini-tip '+cls+'" data-tip="较上一赛季（'+LG().cn+' '+fmtSeason(pk)+'，'+LG().seasons[pk].drawRate+'%）变化 '+(d>0?'+':'')+d.toFixed(2)+' 个百分点">'+sym+Math.abs(d).toFixed(2)+'</span>';
  }
  const cards = [
    {v:s.totalMatches, k:'总场次', cls:'', t:'该赛季全部已赛场次'},
    {v:s.totalDraws, k:'平局场次', cls:'green', t:'打平的比赛场数'},
    {v:s.drawRate+'%'+delta, k:'平局率', cls:'green', t:'平局场次 ÷ 总场次'},
    {v:(s.totalDraws*2/teams.length).toFixed(1), k:'场均平局/队', cls:'accent', t:'每支球队平均每季打出多少场平局'},
    {v:maxDraw, k:'最多平局', team:topDraw, cls:'accent', t:'单季平局最多的球队'},
    {v:maxStreak+' / '+maxGap, k:'最长连平 / 最长无平局间隔', cls:'rk', t:'全联盟单季最长连平轮数 / 最长无平局轮数'},
  ];
  document.getElementById('statGrid').innerHTML = cards.map(c=>
    '<div class="stat"><div class="k" title="'+c.t+'">'+c.k+'</div>'+
    (c.team ? '<div class="v '+c.cls+' stat-combo" title="'+c.t+'"><b>'+c.v+'</b><span class="stat-team mini-tip" data-tip="'+c.team+'：'+c.v+' 场平局">'+c.team+'</span></div>' : '<div class="v '+c.cls+'" title="'+c.t+'">'+c.v+'</div>')+'</div>').join('');
  bindMiniTips(Array.from(document.querySelectorAll('#statGrid .mini-tip')));
}

let ovSort = {key:'n', dir:-1};
function renderOverall(){
  const s = sc();
  const cats = s.overall, totalDraws = s.totalDraws, rounds = s.perRound.length || 38;
  const cols = [
    {key:'score', label:'比分', left:true},
    {key:'n', label:'场次'},
    {key:'pct', label:'占比(占平局)'},
    {key:'pctMatch', label:'占全部比赛'},
    {key:'pr', label:'场/轮'},
  ];
  let head = '<thead><tr>'+cols.map(c=>{
    const sorted = ovSort.key===c.key?' sorted':'';
    const arr = ovSort.key===c.key?(ovSort.dir<0?'▼':'▲'):'';
    return '<th class="'+(c.left?'left ':'')+'sortable'+sorted+'" data-k="'+c.key+'"><span class="arr">'+arr+'</span>'+c.label+'</th>';
  }).join('')+'</tr></thead>';

  const rows = cats.slice().sort((a,b)=>{
    if(ovSort.key==='score') return ovSort.dir*a.score.localeCompare(b.score);
    let va=a[ovSort.key], vb=b[ovSort.key];
    return ovSort.dir*(va-vb);
  });
  let body='<tbody>'+rows.map(c=>{
    const col=SCORE_COLORS[c.score]||'#8a90a0';
    return '<tr><td class="left"><span class="dot" style="background:'+col+'"></span>'+c.score+'</td>'+
      '<td class="bignum">'+c.n+'</td><td>'+c.pct+'%</td><td>'+c.pctMatch+'%</td>'+
      '<td class="per-round">'+(c.n/rounds).toFixed(2)+'</td></tr>';
  }).join('')+'</tbody>';
  let foot='<tfoot><tr><td class="left">合计</td><td class="bignum">'+totalDraws+'</td><td>100%</td>'+
    '<td>'+(totalDraws/s.totalMatches*100).toFixed(2)+'%</td>'+
    '<td class="per-round">'+(totalDraws/rounds).toFixed(2)+'</td></tr></tfoot>';

  const wrap=document.getElementById('overview');
  wrap.innerHTML='<table class="ov-table">'+head+body+foot+'</table>';
  wrap.querySelectorAll('th.sortable').forEach(th=>{
    th.onclick=()=>{
      const k=th.getAttribute('data-k');
      if(ovSort.key===k){ ovSort.dir*=-1; } else { ovSort.key=k; ovSort.dir=(k==='score')?1:-1; }
      renderOverall();
    };
  });
  const other = cats.find(c=>c.score==='其他');
  document.getElementById('ovNote').innerHTML='口径：「其他」＝ 3-3 及以上的平局（本季共 '+(other?other.n:0)+' 场）；占比＝该比分平局 ÷ 全部平局（'+totalDraws+' 场）；场/轮＝场数 ÷ 已进行 '+rounds+' 轮（'+LG().cn+'每轮 '+(s.perRoundCount||Math.round(s.totalMatches/rounds))+' 场）。';
}

function renderTrend(){
  const s = sc();
  const pr=s.perRound, W=920,H=240,padL=34,padR=10,padT=14,padB=28;
  // 轮次号不一定连续：进行中的赛季会出现「第 N 轮提前踢、第 1 轮推迟」，
  // 所以横轴标签必须用真实轮次号，不能用 i+1。
  const rnum=(d,i)=>parseInt(String(d.round).replace(/\D/g,''),10)||(i+1);
  const maxV=Math.max(...pr.map(d=>d.n),1), n=pr.length, bw=(W-padL-padR)/n;
  const avg = s.totalDraws/n;
  let rects='';
  pr.forEach((d,i)=>{
    const bh=maxV?Math.round(d.n/maxV*(H-padT-padB)):0;
    const drs=(d.draws||[]).map(x=>({h:x.h,a:x.a,hs:x.hs,as:x.as}));
    rects+='<rect class="bar" x="'+(padL+i*bw+1.5)+'" y="'+(H-padB-bh)+'" width="'+(bw-3)+'" height="'+bh+'" rx="2" fill="url(#gg)" data-r="第'+rnum(d,i)+'轮" data-n="'+d.n+'" data-draws="'+encodeURIComponent(JSON.stringify(drs))+'"></rect>';
  });
  const yt=[]; for(let v=0;v<=maxV;v++){ const y=H-padB-Math.round(v/maxV*(H-padT-padB)); yt.push('<line x1="'+padL+'" y1="'+y+'" x2="'+(W-padR)+'" y2="'+y+'" stroke="var(--axis)" stroke-width="1"/><text x="'+(padL-6)+'" y="'+(y+4)+'" text-anchor="end" font-size="10" fill="var(--text-muted)">'+v+'</text>'); }
  const xt=[]; for(let i=0;i<n;i+=Math.max(1,Math.ceil(n/9))){ xt.push('<text x="'+(padL+i*bw+bw/2)+'" y="'+(H-padB+16)+'" text-anchor="middle" font-size="10" fill="var(--text-muted)">'+rnum(pr[i],i)+'</text>'); }
  const ay = H-padB-Math.round(avg/maxV*(H-padT-padB));
  const avgLine = '<line x1="'+padL+'" y1="'+ay+'" x2="'+(W-padR)+'" y2="'+ay+'" stroke="var(--rk)" stroke-width="1.2" stroke-dasharray="5 4" opacity=".85"/>'+
    '<text x="'+(W-padR)+'" y="'+(ay-5)+'" text-anchor="end" font-size="10" fill="var(--rk)">场均 '+avg.toFixed(2)+'</text>';
  document.getElementById('trend').innerHTML='<svg class="trend-svg" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">'+
    '<defs><linearGradient id="gg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4a9eff"/><stop offset="1" stop-color="#00b894"/></linearGradient></defs>'+
    yt.join('')+rects+avgLine+xt.join('')+'<text x="'+padL+'" y="10" font-size="11" fill="var(--text-dim)">平局/轮</text></svg>';
  const tip=document.getElementById('avgTip');
  document.querySelectorAll('#trend rect.bar').forEach(r=>{
    r.addEventListener('mousemove',e=>{
      tip.style.display='block';
      let html='<b>'+r.getAttribute('data-r')+'</b>　平局 <b>'+r.getAttribute('data-n')+'</b> 场';
      try{
        const ds=JSON.parse(decodeURIComponent(r.getAttribute('data-draws')||'[]'));
        if(ds&&ds.length){
          html+='<div class="tip-sep"></div>'+ds.map(x=>
            '<div class="tip-draw"><span class="tm">'+x.h+'</span> <span class="sc">'+x.hs+'-'+x.as+'</span> <span class="tm">'+x.a+'</span></div>').join('');
        }
      }catch(err){}
      tip.innerHTML=html;
      tip.style.left=Math.min(e.clientX+12,window.innerWidth-220)+'px'; tip.style.top=(e.clientY+12)+'px';
    });
    r.addEventListener('mouseleave',()=>{ tip.style.display='none'; });
  });
}

const COLS=[
  {key:'rank',   label:'排名', rk:true},
  {key:'name',   label:'队伍', namecol:true},
  {key:'draws',  label:'平局'},
  {key:'every',  label:'平均几轮<br>出一次平局', cls:'th2', evcol:true},
  {key:'d00',    label:'0-0', color:SCORE_COLORS['0-0'], grp:'score'},
  {key:'d11',    label:'1-1', color:SCORE_COLORS['1-1'], grp:'score'},
  {key:'d22',    label:'2-2', color:SCORE_COLORS['2-2'], grp:'score'},
  {key:'dother', label:'其他', color:SCORE_COLORS['其他'], grp:'score'},
  {key:'streak', label:'最长连平'},
  {key:'gap',    label:'最长无平局间隔'},
];
let teamSort={key:'rank',dir:1};

function renderTeams(){
  const s = sc(), teams = s.teams;
  const moveFinal = s.moveFinal !== false;      // 下赛季名单未定的进行中赛季 → 不显示升降 icon
  const cols = visCols(COLS);
  const rows=teams.slice().sort((a,b)=>{
    const r = cmpVal(a,b,teamSort.key,teamSort.dir);
    return r !== 0 ? r : (a.rank - b.rank);
  });
  let head='<thead><tr>'+cols.map(c=>{
    if(c.namecol) return '<th class="namecol left">'+c.label+'</th>';
    const sorted=teamSort.key===c.key?' sorted':'';
    const arr=teamSort.key===c.key?(teamSort.dir<0?'▼':'▲'):'';
    return '<th class="'+((c.cls?c.cls+' ':'')+(c.rk?'rkcol ':'')+'sortable'+sorted).trim()+'" data-k="'+c.key+'"><span class="arr">'+arr+'</span>'+c.label+'</th>';
  }).join('')+'</tr></thead>';

  let body='<tbody>';
  rows.forEach((t,i)=>{
    let cells='';
    cols.forEach(c=>{
      const sel = (teamSort.key===c.key?' col-sel':'');
      if(c.rk){
        cells+='<td class="rkcol rk'+sel+'">'+t.rank+'</td>';
      } else if(c.namecol){
        // icon ＝ 本季「最终裁定」的去向：升入顶级 → 升；降级离队 → 降。进行中的赛季不判定。
        // 队名配色 ＝ 上季的来源：从顶级降入 → 红；从次次级联赛升入 → 绿。
        let mark='';
        if(moveFinal){
          if(t.upTop) mark+='<span class="move up" title="本季最终升级：下赛季升入顶级联赛">升</span>';
          if(t.releg) mark+='<span class="move down" title="本季最终降级：下赛季降出本联赛">降</span>';
          // 行政降级 / 除名：不在降级区，但因财务、注册裁定被勒令离队，单独标记
          if(t.demoted) mark+='<span class="move adm" title="行政降级，非竞技排名原因：'+
            esc(t.demoteWhy||'财务 / 注册裁定')+(t.demoteTo?'，降入 '+esc(t.demoteTo):'')+'">降</span>';
        }
        const nmCls = t.fromTop ? ' down-clr' : (t.promo ? ' up-clr' : '');
        cells+='<td class="namecol left"><div class="tcell">'+crestImg(t.name)+
          '<span class="tmeta"><span class="nm'+nmCls+'">'+t.cn+'</span>'+
          '<span class="tagroup"><span class="pts-inline" title="当季积分">'+t.pts+'<span class="u">分</span></span>'+
          ((t.rank===1&&moveFinal)?CHAMP_SVG:'')+mark+'</span></span></div></td>';
      } else if(c.evcol){
        const v=t[c.key];
        cells+='<td class="ev'+(sel||(v===null||v===undefined?' na':''))+'">'+
          ((v===null||v===undefined)?'—':v.toFixed(2))+'</td>';
      } else if(c.color){
        // 去掉占宽度的进度条，改用同色数字 —— 表更窄、更好读
        cells+='<td class="'+sel.trim()+'"><span class="bn" style="color:'+c.color+';font-weight:700">'+(t[c.key]||0)+'</span></td>';
      } else {
        cells+='<td class="'+sel.trim()+'">'+(t[c.key]||0)+'</td>';
      }
    });
    body += '<tr class="trow" data-i="'+i+'">'+cells+'</tr>';
  });
  body += '</tbody>';

  const table=document.getElementById('teamTable');
  table.innerHTML=head+body;
  table.querySelectorAll('th.sortable').forEach(th=>{
    th.onclick=()=>{
      const k=th.getAttribute('data-k');
      if(teamSort.key===k){ teamSort.dir*=-1; } else { teamSort.key=k; teamSort.dir=(k==='rank')?1:-1; }
      renderTeams(); syncHint();
    };
  });
  bindRowDetail(table, rows);
  bindSortChip('teamSortChip', COLS, teamSort, ()=>{ teamSort={key:'rank',dir:1}; renderTeams(); }, showBuckets);
  syncHint();
  // 进行中的赛季：下赛季名单未定，不标任何升降 icon，也不做「降班马」推断
  const colorTxt = '；<b style="color:#e74c3c">队名标红</b>＝上季从顶级联赛降入'+
                   '；<b style="color:var(--green)">队名标绿</b>＝上季从次次级联赛升入';
  const moveTxt = (moveFinal
    ? '；<span class="move up">升</span> 本季最终升级，下季升入顶级联赛'+
      '；<span class="move down">降</span> 本季竞技降级，下季降出本联赛'+
      (rows.some(t=>t.demoted)?'；<span class="move adm">降</span> 行政降级，非竞技原因':'')
    : '；本季尚在进行、下季升降名单未定，暂不标注升 / 降 icon')+colorTxt;
  document.getElementById('teamNote').innerHTML=
    (moveFinal?'🏆 当季冠军':'🏆 当前榜首')+moveTxt+'。';
}

/* ---------------- 近五赛季各队胜平负走势 ---------------- */
let form5Show = {W:false, D:true, L:false};
let form5Off = {};                        // 队名 → true 表示隐藏该行色块
const RS = {W:'胜', D:'平', L:'负'};
function form5Rows(){
  // 严格按当季最终积分榜名次（冠军 → 垫底）排列，与上方「各队平局统计」口径一致
  return (LG().seasons[currentSeason].teams || []).slice().sort((a,b)=>
    ((a.rank||999)-(b.rank||999)) || String(a.cn).localeCompare(String(b.cn)));
}
function form5SeasonAt(t, idx){
  if(!t.formBySeason || !t.formBySeason.length) return currentSeason;
  let n=0;
  for(const seg of (t.formBySeason||[])){
    const len=seg.matches||0;
    if(idx<n+len) return seg.season;
    n+=len;
  }
  return '';
}
function form5TipHTML(t, roster, i){
  const det = t.formDetail || [], seq = t.formSeq || [];
  const raw = det[i];
  if(!raw) return '<b>'+t.cn+'</b>　'+(RS[seq[i]]||'');
  const p = String(raw).split('|');
  const rn=p[0]||'', dt=p[1]||'', ha=p[2]||'', oi=parseInt(p[3],10), sc=(p[4]||'');
  const opp = (roster[oi] && roster[oi].cn) || '—';
  const r = seq[i] || '';
  let line = t.cn + ' <b>' + sc + '</b> ' + opp;
  const sp = sc.split('-');
  if(ha!=='H' && sp.length===2) line = opp + ' <b>' + sp[1] + '-' + sp[0] + '</b> ' + t.cn;
  return '<b>'+fmtSeason(currentSeason)+' 第 '+rn+' 轮</b> · '+dt+' · '+(ha==='H'?'主场':'客场')+
    '<br>'+line+'　<span style="color:'+({W:'#00b894',D:'#4a9eff',L:'#e74c3c'}[r]||'inherit')+'">'+(RS[r]||'')+'</span>';
}
function bindFormTips(box){
  const tip = document.getElementById('formTip');
  if(!tip) return;
  box.querySelectorAll('.form5-cell').forEach(el=>{
    el.addEventListener('mousemove', e=>{
      tip.style.display='block';
      tip.innerHTML = el.getAttribute('data-tip') || '';
      let x=e.clientX+12, y=e.clientY+12;
      tip.style.left=x+'px'; tip.style.top=y+'px';
      const r=tip.getBoundingClientRect(), pad=8;
      if(x+r.width >window.innerWidth -pad) x=Math.max(pad, window.innerWidth -r.width -pad);
      if(y+r.height>window.innerHeight-pad) y=Math.max(pad, window.innerHeight-r.height-pad);
      tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    el.addEventListener('mouseleave', ()=>{ tip.style.display='none'; });
  });
}
function renderForm5(){
  const title=document.getElementById('form5Title'), note=document.getElementById('form5Note'), filter=document.getElementById('form5Filter'), box=document.getElementById('form5Strips');
  if(!title||!box) return;
  const tip = document.getElementById('formTip'); if(tip) tip.style.display='none';
  title.setAttribute('data-season', currentSeason);
  const season=LG().seasons[currentSeason];
  const ROSTER = season.teams || [];
  title.textContent=fmtSeason(currentSeason)+' '+LG().cn+'各队胜平负走势分布';
  note.innerHTML='按当季积分榜名次自上而下排列；每一格为一场常规赛（升降级附加赛不计入），'+
    '绿＝胜、蓝＝平、红＝负，默认只突出平局；鼠标悬停任意色块可看该场日期、对手与比分，点队名后的「隐藏 / 显示」可收起或展开该队整行数据（色带与胜负统计）。';
  filter.innerHTML=['W','D','L'].map(k=>'<button type="button" class="form5-toggle'+(form5Show[k]?' on':'')+'" data-r="'+k+'">'+RS[k]+'</button>').join('');
  filter.querySelectorAll('.form5-toggle').forEach(btn=>btn.onclick=()=>{ const k=btn.dataset.r; form5Show[k]=!form5Show[k]; renderForm5(); });
  const rows=form5Rows();
  const legend='<div class="form5-legend"><span class="fw">胜</span><span class="fd">平</span><span class="fl">负</span></div>';
  box.innerHTML=legend+rows.map(t=>{
    const seq=t.formSeq||[], counts=t.formCounts||{};
    const cells=seq.map((v,i)=>{
      const s0=form5SeasonAt(t,i), prev=i?form5SeasonAt(t,i-1):'';
      const start=(i>0&&s0!==prev)?' start':'';
      return '<i class="form5-cell '+v.toLowerCase()+start+(form5Show[v]?'':' off')+'" data-tip="'+form5TipHTML(t, ROSTER, i).replace(/"/g,'&quot;')+'"></i>';
    }).join('');
    const off = !!form5Off[t.name];
    return '<div class="form5-row'+(off?' off':'')+'" data-n="'+String(t.name).replace(/"/g,'&quot;')+'">'+
      '<div class="form5-name">'+crestImg(t.name)+'<span class="nm">'+t.cn+'</span>'+
      '<span class="form5-tlink" data-t="'+String(t.name).replace(/"/g,'&quot;')+'">'+(off?'显示':'隐藏')+'</span></div>'+
      '<div class="form5-strip'+(off?' off':'')+'">'+cells+'</div>'+
      '<div class="form5-meta">胜 '+(counts.W||0)+' · 平 '+(counts.D||0)+' · 负 '+(counts.L||0)+'</div>'+
      '</div>';
  }).join('');
  bindFormTips(box);
  box.querySelectorAll('.form5-tlink').forEach(a=>{
    a.onclick=()=>{
      const n=a.getAttribute('data-t');
      form5Off[n]=!form5Off[n];
      renderForm5();
    };
  });
}

/* ---------------- 近五赛季横向对比 ---------------- */
function seasonAgg(k){
  const s = LG().seasons[k], teams = s.teams;
  const md = Math.max(...teams.map(t=>t.draws));
  const ms = Math.max(...teams.map(t=>t.streak));
  const mg = Math.max(...teams.map(t=>t.gap));
  const bucket = cat => (s.overall.find(o=>o.score===cat)||{n:0}).n;
  const sFinal = s.moveFinal !== false;
  const champ = sFinal ? (teams.find(t=>t.rank===1)||{}).cn : '';
  // 并列多队时，奖杯必须跟在「冠军那一队的名字」后面 —— 不能挂在末尾的数字后，否则归属不清
  const mark = names => names.map(n => (n === champ ? n + CHAMP_SVG : n)).join('、');
  const nt = teams.filter(t=>t.draws===md).map(t=>t.cn);
  const ns = teams.filter(t=>t.streak===ms).map(t=>t.cn);
  const ng = teams.filter(t=>t.gap===mg).map(t=>t.cn);
  return {
    k, totalMatches:s.totalMatches, totalDraws:s.totalDraws, drawRate:s.drawRate,
    b00:bucket('0-0'), b11:bucket('1-1'), b22:bucket('2-2'), both:bucket('其他'),
    top: mark(nt)+' '+md,
    streak: mark(ns)+' '+ms,
    gap: mark(ng)+' '+mg,
    champ
  };
}
/* 联赛规模说明：五大次级规模不一（英冠 24 / 西乙 22 / 意乙·法乙 20 / 德乙 18），必须按实际分档描述 */
function fmtSizes(){
  const seq = DATA.seasonOrder.slice().reverse();   // 旧 → 新
  const parts = [];
  seq.forEach(k=>{
    const s = LG().seasons[k];
    const sig = s.nteams + '|' + s.totalMatches + '|' + s.rounds;
    const last = parts[parts.length - 1];
    if(last && last.sig === sig){ last.to = k; }
    else parts.push({sig, from:k, to:k, m:s.totalMatches, n:s.nteams, r:s.rounds});
  });
  if(parts.length === 1){
    const p = parts[0];
    return '每季均为 ' + p.m + ' 场、' + p.n + ' 队、' + p.r + ' 轮';
  }
  return parts.map(p => (p.from === p.to ? fmtSeason(p.from) : fmtSeason(p.from) + '~' + fmtSeason(p.to)) +
    ' 为 ' + p.m + ' 场 / ' + p.n + ' 队 / ' + p.r + ' 轮').join('，');
}
function renderCompare(){
  const rows = winSeq().map(seasonAgg);
  const head = '<thead><tr><th class="left">赛季</th><th>平局场次</th><th>平局率</th>'+
    DATA.cats.map(c=>'<th><span class="dot" style="background:'+SCORE_COLORS[c]+'"></span>'+c+'</th>').join('')+
    '<th class="left">最多平局</th><th class="left">最长连平</th><th class="left">最长无平局间隔</th></tr></thead>';
  const body = '<tbody>'+rows.map(r=>{
    return '<tr'+(r.k===currentSeason?' class="cur"':'')+'>'+
      '<td class="left"><span class="sn" data-k="'+r.k+'" title="点击查看该赛季">'+fmtSeason(r.k)+'</span></td>'+
      '<td class="bignum">'+r.totalDraws+'</td><td style="font-weight:700;color:var(--green)">'+r.drawRate+'%</td>'+
      '<td>'+r.b00+'</td><td>'+r.b11+'</td><td>'+r.b22+'</td><td>'+r.both+'</td>'+
      '<td class="left">'+r.top+'</td><td class="left">'+r.streak+'</td><td class="left">'+r.gap+'</td></tr>';
  }).join('')+'</tbody>';
  const t = document.getElementById('cmpTable');
  t.innerHTML = head+body;
  document.getElementById('cmpTitle').innerHTML = WLAB()+'横向对比<span class="note-flag">'+WN()+'个赛季的平局总量、平局率与比分结构对照；右侧三列为「球队 + 场次数」，🏆 表示该队为该季冠军；点击表格中的赛季名或折线上的圆点可直接跳转查看该赛季。</span>';
  t.querySelectorAll('.sn').forEach(el=>{
    el.onclick = ()=>{ currentSeason = el.getAttribute('data-k'); render(); window.scrollTo({top:0,behavior:'smooth'}); };
  });
  syncHint();

  // 平局率折线（老 → 新，随赛季窗口收缩为近三/近五季）
  const seq = winSeq().slice().reverse();
  const vals = seq.map(k=>+LG().seasons[k].drawRate);
  // mr 与 ml 对称留白：x 轴末位标签为完整赛季「2025-2026」（约 55px），mr=20 会被 viewBox 裁掉右侧
  const W=900,H=250,ml=46,mr=46,mt=28,mb=42;
  const pw=W-ml-mr, ph=H-mt-mb, n=seq.length;
  let lo=Math.min(...vals), hi=Math.max(...vals);
  const pad=Math.max(0.8,(hi-lo)*0.35);
  lo=Math.floor((lo-pad)*2)/2; hi=Math.ceil((hi+pad)*2)/2;
  const X=i=> ml + (n===1? pw/2 : pw*i/(n-1));
  const Y=v=> mt + ph*(1-(v-lo)/(hi-lo||1));
  let g='';
  for(let s=0;s<=4;s++){
    const v=lo+(hi-lo)*s/4, y=Y(v);
    g+='<line x1="'+ml+'" y1="'+y+'" x2="'+(W-mr)+'" y2="'+y+'" stroke="var(--axis)" stroke-width="1"/>'+
       '<text x="'+(ml-8)+'" y="'+(y+4)+'" text-anchor="end" font-size="10" fill="var(--text-muted)">'+v.toFixed(1)+'%</text>';
  }
  const pts = seq.map((k,i)=>X(i)+','+Y(vals[i])).join(' ');
  g+='<polyline points="'+pts+'" fill="none" stroke="var(--accent)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>';
  seq.forEach((k,i)=>{
    const x=X(i), y=Y(vals[i]), on=(k===currentSeason);
    g+='<circle class="pt" cx="'+x+'" cy="'+y+'" r="'+(on?6.5:5)+'" fill="'+(on?'var(--green)':'var(--card)')+'" stroke="var(--accent)" stroke-width="2.5" data-k="'+k+'" data-v="'+vals[i]+'"></circle>';
    g+='<text x="'+x+'" y="'+(y-13)+'" text-anchor="middle" font-size="11" font-weight="'+(on?700:600)+'" fill="'+(on?'var(--green)':'var(--text-dim)')+'">'+vals[i].toFixed(2)+'%</text>';
    g+='<text x="'+x+'" y="'+(H-mb+20)+'" text-anchor="middle" font-size="11" fill="'+(on?'var(--accent)':'var(--text-muted)')+'">'+fmtSeason(k)+'</text>';
  });
  document.getElementById('cmpChart').innerHTML='<svg class="trend-svg" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">'+
    g+'<text x="'+ml+'" y="14" font-size="11" fill="var(--text-dim)">'+WLAB()+'平局率走势（点圆点可切换赛季）</text></svg>';
  const tip=document.getElementById('avgTip');
  document.querySelectorAll('#cmpChart circle.pt').forEach(c=>{
    c.addEventListener('click',()=>{ currentSeason=c.getAttribute('data-k'); render(); });
    c.addEventListener('mousemove',e=>{
      tip.style.display='block';
      tip.innerHTML='<b>'+fmtSeason(c.getAttribute('data-k'))+'</b>　平局率 <b>'+c.getAttribute('data-v')+'%</b>';
      let x=e.clientX+12, y=e.clientY+12;
      tip.style.left=x+'px'; tip.style.top=y+'px';
      const r=tip.getBoundingClientRect(), pad=8;
      if(x+r.width  > window.innerWidth -pad) x=Math.max(pad, window.innerWidth -r.width -pad);
      if(y+r.height > window.innerHeight-pad) y=Math.max(pad, window.innerHeight-r.height-pad);
      tip.style.left=x+'px'; tip.style.top=y+'px';
    });
    c.addEventListener('mouseleave',()=>{ tip.style.display='none'; });
  });

  const best = rows.slice().sort((a,b)=>b.drawRate-a.drawRate);
  const avg = rows.reduce((a,r)=>a+r.drawRate,0)/rows.length;
  document.getElementById('cmpNote').innerHTML=WLAB()+'平均平局率 <b>'+avg.toFixed(2)+'%</b>；最高 '+fmtSeason(best[0].k)+'（'+best[0].drawRate+'%，'+best[0].totalDraws+' 场），最低 '+fmtSeason(best[best.length-1].k)+'（'+best[best.length-1].drawRate+'%，'+best[best.length-1].totalDraws+' 场）。'+fmtSizes()+'，口径一致可直接横向比较。';
}

/* ---------------- 模块六：五大次级联赛横向对照（一级「五大次级联赛」Tab） ---------------- */
function big5Rows(){
  // 默认按「联赛 Tab 顺序」排列（英冠→西乙→德乙→意乙→法乙）
  const order = DATA.leagues.map(l=>l.code);
  let rows = CMP().rows.slice().sort((a,b)=> order.indexOf(a.code)-order.indexOf(b.code));
  if(big5Sort.key==='order') return rows;
  const get = r => big5Sort.key==='totalDraws' ? r.totalDraws
                : big5Sort.key==='drawRate'  ? r.drawRate
                : big5Sort.key.startsWith('b:') ? r.buckets[+big5Sort.key.slice(2)]
                : 0;
  rows.sort((a,b)=> (get(a)-get(b))*big5Sort.dir);
  return rows;
}
let big5Hide = {};                       // 联赛代码 → true 表示在走势曲线里隐藏该联赛
function renderBig5(){
  const rows = big5Rows();
  const cats = DATA.cats;                  // ['0-0','1-1','2-2','其他']
  const sTh = (k,label)=>{
    const on = big5Sort.key===k;
    const arr = on ? (big5Sort.dir<0?'▼':'▲') : '';
    return '<th class="sortable'+(on?' sorted':'')+'" data-k="'+k+'"><span class="arr">'+arr+'</span>'+label+'</th>';
  };
  const head = '<thead><tr><th class="left">联赛</th>'+
    sTh('totalDraws','平局场次')+sTh('drawRate','平局率')+
    cats.map((c,i)=>sTh('b:'+i,'<span class="dot" style="background:'+SCORE_COLORS[c]+'"></span>'+c)).join('')+
    '<th>全勤队</th><th class="left">稳定平局队（'+WN()+' 季每年≥门槛）</th><th class="left">平局王</th></tr></thead>';
  const body='<tbody>'+rows.map(r=>{
    const bk = cats.map((c,i)=>'<td>'+r.buckets[i]+'<br><span class="sub">'+r.bucketPct[i].toFixed(1)+'%</span></td>').join('');
    const st = r.stable.length ? r.stable.join('、') : '无';
    return '<tr>'+
      '<td class="left"><div class="tcell"><img class="lg-logo" src="'+lgLogo(r.code)+'" alt="'+r.cn+'"><span class="tmeta"><span class="nm">'+r.cn+'</span></span></div></td>'+
      '<td class="bignum">'+r.totalDraws+'</td>'+
      '<td style="font-weight:700;color:var(--green)">'+r.drawRate.toFixed(2)+'%</td>'+
      bk+
      '<td>'+r.nFull+'<span class="sub">/'+r.nTeams+'</span></td>'+
      '<td class="left">'+st+'</td>'+
      '<td class="left"><b>'+r.top.cn+'</b> · '+r.top.total+'</td></tr>';
  }).join('')+'</tbody>';
  const tbl = document.getElementById('big5Table');
  tbl.innerHTML = head+body;
  tbl.querySelectorAll('th.sortable').forEach(th=>{
    th.onclick = ()=>{
      const k = th.getAttribute('data-k');
      if(big5Sort.key===k){ big5Sort.dir *= -1; }
      else { big5Sort.key = k; big5Sort.dir = (k==='order') ? 1 : -1; }   // 数值列首点默认降序
      renderBig5();
    };
  });

  // 折线：各联赛平局率（seasonSeq 旧→新，随范围开关切换为近五/近三季）
  const seq = CMP().seasonSeq;
  // 同对比图：mr 留足右侧，避免完整的 2025-2026 标签被 viewBox 裁切
  const W=900,H=260,ml=46,mr=46,mt=30,mb=42;
  const pw=W-ml-mr, ph=H-mt-mb, n=seq.length;
  const visRows = rows.filter(r=>!big5Hide[r.code]);
  const allV = (visRows.length?visRows:rows).flatMap(r=>r.rates);
  let lo=Math.min(...allV), hi=Math.max(...allV);
  const pad=Math.max(0.8,(hi-lo)*0.3);
  lo=Math.floor((lo-pad)*2)/2; hi=Math.ceil((hi+pad)*2)/2;
  const X=i=> ml + (n===1? pw/2 : pw*i/(n-1));
  const Y=v=> mt + ph*(1-(v-lo)/(hi-lo||1));
  let g='';
  for(let s=0;s<=4;s++){
    const v=lo+(hi-lo)*s/4, y=Y(v);
    g+='<line x1="'+ml+'" y1="'+y+'" x2="'+(W-mr)+'" y2="'+y+'" stroke="var(--axis)" stroke-width="1"/>'+
       '<text x="'+(ml-8)+'" y="'+(y+4)+'" text-anchor="end" font-size="10" fill="var(--text-muted)">'+v.toFixed(1)+'%</text>';
  }
  seq.forEach((k,i)=>{ g+='<text x="'+X(i)+'" y="'+(H-mb+20)+'" text-anchor="middle" font-size="11" fill="var(--text-muted)">'+fmtSeason(k)+'</text>'; });
  rows.forEach(r=>{
    if(big5Hide[r.code]) return;
    const col = LG_COLOR[r.code]||'#888';
    const pts = r.rates.map((v,i)=>X(i)+','+Y(v)).join(' ');
    g+='<polyline points="'+pts+'" fill="none" stroke="'+col+'" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/>';
    r.rates.forEach((v,i)=>{ g+='<circle cx="'+X(i)+'" cy="'+Y(v)+'" r="3.5" fill="'+col+'"></circle>'; });
  });
  document.getElementById('big5Chart').innerHTML='<svg class="trend-svg" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg">'+g+
    '<text x="'+ml+'" y="14" font-size="11" fill="var(--text-dim)">五大次级联赛'+WLAB()+'平局率走势（按联赛着色）</text></svg>';
  const legend = rows.map(r=>'<span class="lg-leg'+(big5Hide[r.code]?' off':'')+'" data-code="'+r.code+'" role="button" tabindex="0"><i style="background:'+(LG_COLOR[r.code]||'#888')+'"></i>'+r.cn+'</span>').join('');
  const noteEl=document.getElementById('big5Note');
  noteEl.innerHTML='五大次级联赛'+WLAB()+'累计平局率对照；'+legend+'。点击底部色块说明可显示 / 隐藏对应联赛的曲线；点击表头可按平局场次 / 平局率 / 各比分排序（再次点击反向）；点击「五大次级联赛」Tab 左邻的赛季 Tab 可回到单季或总览。';
  noteEl.querySelectorAll('.lg-leg').forEach(el=>{
    const toggle=()=>{ const c=el.getAttribute('data-code'); big5Hide[c]=!big5Hide[c]; renderBig5(); };
    el.onclick=toggle;
    el.onkeydown=(e)=>{ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); toggle(); } };
  });
  const b5tn=document.getElementById('big5TitleNote');
  if(b5tn) b5tn.innerHTML='五个联赛'+WLAB()+'的平局总量、平局率与比分结构对照；点击表头可按平局场次 / 平局率 / 各比分排序；折线按联赛着色展示各自走势。';
  syncHint();
}

function syncHint(){
  [['topWrap','topScroll'],['teamWrap','teamScroll'],['cmpWrap','cmpScroll'],['big5Wrap','big5Scroll']].forEach(p=>{
    const wrap=document.getElementById(p[0]), el=document.getElementById(p[1]);
    if(!wrap||!el) return;
    if(el.scrollWidth>el.clientWidth+4) wrap.classList.remove('at-end'); else wrap.classList.add('at-end');
  });
}
function bindScrollHint(){
  [['topWrap','topScroll'],['teamWrap','teamScroll'],['cmpWrap','cmpScroll'],['big5Wrap','big5Scroll']].forEach(p=>{
    const wrap=document.getElementById(p[0]), el=document.getElementById(p[1]);
    el.addEventListener('scroll',()=>{ if(el.scrollLeft+el.clientWidth>=el.scrollWidth-4) wrap.classList.add('at-end'); else wrap.classList.remove('at-end'); });
  });
  window.addEventListener('resize',syncHint);
}
function bindScrollBtns(){
  const top=document.getElementById('toTop'), bot=document.getElementById('toBottom');
  function upd(){
    const y=window.scrollY||document.documentElement.scrollTop;
    const h=document.documentElement.scrollHeight-window.innerHeight;
    top.classList.toggle('hide', y<300); bot.classList.toggle('hide', y>h-300);
  }
  window.addEventListener('scroll',upd,{passive:true}); upd();
}

function renderTitles(){
  const s = sc(), L = LG().cn;
  const flag = s.note ? '<span class="note-flag">'+fmtText(s.note)+'</span>' : '';
  const inProg = s.totalMatches < s.nteams*(s.nteams-1);      // 赛季尚未打完
  const rTxt = inProg ? ('已进行 '+s.perRound.length+' 轮（最大第 '+(s.roundMax||s.rounds)+' 轮）')
                      : ('全季 '+(s.roundMax||s.rounds)+' 轮');
  document.getElementById('stOverall').innerHTML = '一、'+fmtSeason(s.season)+' 平局比分分布（全联盟）'+flag+
    '<span class="note-flag">各比分平局的场次、占全部平局的百分比，以及「场/轮」＝该比分平均每轮出现几场（'+L+'每轮 '+s.perRoundCount+' 场，'+rTxt+'）。</span>';
  document.getElementById('stTrend').innerHTML = '二、'+fmtSeason(s.season)+' 各轮平局走势'+
    '<span class="note-flag">横轴为已进行的轮次（'+rTxt+'），纵轴为该轮产生的平局场数（每轮共 '+s.perRoundCount+' 场）；黄色虚线为该季场均平局数。</span>';
  document.getElementById('stTeams').innerHTML = '三、'+fmtSeason(s.season)+' 各队平局统计（按当季积分榜排序）'+
    '<span class="note-flag">默认按积分榜排名（冠军→垫底）排列；点击任意表头可单独升降序排序。</span>';
}

function renderCrumb(){
  const el = document.getElementById('headCrumb'); if(!el) return;
  let parts;
  if(showBig5)      parts = ['五大次级联赛', '横向对照'];
  else if(curView==='overview') parts = [LG().cn, '赛季总览'];
  else              parts = [LG().cn, fmtSeason(currentSeason)+' 赛季'];
  el.innerHTML = '<span>数据中心</span>' + parts.map(p=>'<span class="sepi">›</span><b>'+p+'</b>').join('');
}

function render(){
  syncBkBtns();
  buildLeagueTabs(); buildSeasonTabs(); renderCrumb();
  const vs = document.getElementById('viewSeason');
  const vo = document.getElementById('viewOverview');
  const vb = document.getElementById('viewBig5');
  if(showBig5){
    vs.style.display='none'; vo.style.display='none'; vb.style.display='';
    renderBig5();
  } else if(curView==='overview'){
    vb.style.display='none'; vs.style.display='none'; vo.style.display='';
    // 页头总榜的结论/逐年格高亮都跟联赛走，切换时必须一起重绘
    renderTopMeta(); renderFindings(); renderTop();
    renderCompare();
  } else {
    vb.style.display='none'; vo.style.display='none'; vs.style.display='';
    renderTitles(); renderStats(); renderOverall(); renderTrend(); renderTeams(); renderForm5();
  }
}

render(); bindBkToggle(); bindScrollHint(); bindScrollBtns();

// 页脚：填上「数据源更新时间」与「本页最近更新」（来自数据层 meta）
(function(){
  const set = (id, v) => { const el = document.getElementById(id); if(el) el.textContent = (v && v !== '–') ? v : '–'; };
  set('ftSrc', (DATA.meta && DATA.meta.srcUpdated) || '');
  set('ftGen', (DATA.meta && DATA.meta.generated) || '');
})();

// 滚动时收起悬停浮层，避免浮层跟着页面漂走
window.addEventListener('scroll', ()=>{ hideRowTip(); }, {passive:true});
</script>
</body>
</html>
"""

HTML = (HTML.replace("__DATA__", DATA_JS)
            .replace("__SCORES__", json.dumps(SCORE_COLORS, ensure_ascii=False))
            .replace("__RESULTS__", json.dumps(RESULT_COLORS, ensure_ascii=False)))

out = f"{WS}/football_champ_draws.html"
open(out, "w", encoding="utf-8").write(HTML)
print("written:", out, "bytes:", len(HTML))
