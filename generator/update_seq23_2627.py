import json, re, shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
FILES=[(HERE/"football_big5_goals.html",'window.DATA = '),(HERE/"football_mobile.html",'const DATA = ')]
ALIASES={'Paris Saint-Germain':'Paris Saint-Germain FC','RC Lens':'Racing Club de Lens','Olympique Marseille':'Olympique de Marseille','Stade Rennais':'Stade Rennais FC 1901','AS Monaco':'AS Monaco FC','RC Strasbourg':'RC Strasbourg Alsace','SpVgg Greuther Fürth 1903':'SpVgg Greuther Fürth','VfL Bochum 1848':'VfL Bochum'}
TOP=['en','es','it','de','fr']
SEC=['en.2','es.2','de.2','it.2','fr.2']
CODES=TOP+SEC

# 2026-27 内嵌积分榜/总进球必须随赛果重算（修复「同步后积分不刷新」bug）。
# 仅进行中的 2026-27 重算；已完成赛季沿用报告内嵌的官方最终积分榜。
from standings import (compute_table, compute_goals, canon_top,
                       deduct_map, is_regular_match, TIE_RULE)


def standings_2627(code):
    tier='2' if code.endswith('.2') else '1'
    base=code.replace('.2','')
    ms = json.load(open(f"{DATA_DIR}/{base}.{tier}.2026-27.json", encoding="utf-8"))["matches"]
    reg = [m for m in ms if is_regular_match(m)]
    ded = deduct_map(base, "2026-27", "top")
    tbl = compute_table(reg, TIE_RULE.get(base, "gd"), ded)
    goals = compute_goals(reg)
    return tbl, goals
def canon(n): return ALIASES.get(n,n)
def source_path(code, season):
    tier='2' if code.endswith('.2') else '1'
    base=code.replace('.2','')
    # 赛季目录命名偶有 2025-26 / 2025_26 不一致，两种都试
    cands=[f'{base}.{tier}.{season}.json',
           f'{base}.{tier}.{season.replace("-","_")}.json',
           f'{base}.{tier}.{season.replace("_","-")}.json']
    for c in cands:
        p=DATA_DIR/c
        if p.exists(): return p
    return None
def score(m):
 s=m.get('score'); s=s.get('ft') if isinstance(s,dict) else s
 return (int(s[0]),int(s[1])) if isinstance(s,list) and len(s)>=2 and s[0] is not None and s[1] is not None else None
def rnum(x):
 m=re.search(r'(\d+)',str(x or ''));return int(m.group(1)) if m else 0
def longest(seq,p):
 best=cur=0
 for x in seq:
  if p(x):cur+=1;best=max(best,cur)
  else:cur=0
 return best
def build(code, season):
 p=source_path(code,season)
 if p is None: return None
 ms=json.load(open(p,encoding='utf-8'))['matches']; rows=[]
 for i,m in enumerate(ms):
  sc=score(m)
  if sc is not None:rows.append((str(m.get('date','')),str(m.get('time','')),rnum(m.get('round')),i,canon(m['team1']),canon(m['team2']),sc[0],sc[1],sc[0]+sc[1]))
 # 日期序：色带按「比赛真实发生日期」排，不按轮次排 ——
 # 用户确认：色块要反映球队数据的真实演变，日期序 = 真实比赛序，才是最准确的口径；
 # 轮次号因此可能不单调（补赛/提前进行的轮次会让日期与轮次错位），但这是可接受的代价。
 def rkey(x):return (x[0],x[1],x[2] if x[2]>0 else 9999,x[3])
 rows.sort(key=rkey);by={}; buckets={str(i):0 for i in range(7)};buckets['7+']=0;total_goals=0
 for date,time,rnd,i,t1,t2,h,a,tot in rows:
  by.setdefault(t1,[]).append((date,time,rnd,i,tot,h,a,t2,'H'));by.setdefault(t2,[]).append((date,time,rnd,i,tot,h,a,t1,'A'));buckets[str(tot) if tot<=6 else '7+']+=1;total_goals+=tot
 out={}
 for name,items in by.items():
  ordered=sorted(items,key=rkey); seq=[x[4] for x in ordered]; b={str(i):0 for i in range(7)};b['7+']=0; scored=0
  # ha / round 是悬浮框判主客、标轮次的依据，缺了就只能一律按主场、按格子序号显示
  matches=[{'date':x[0],'score':str(x[5])+'-'+str(x[6]),'opponent':x[7],'ha':x[8],'round':x[2]} for x in ordered]
  # team goals are reconstructed from source rows
  for date,time,rnd,i,tot,h,a,opp,ha in items:b[str(tot) if tot<=6 else '7+']+=1
  out[name]={'seq23':seq,'seq23Matches':matches,'b':b,'totalMatches':len(seq),'count2':sum(x==2 for x in seq),'count3':sum(x==3 for x in seq),'streak2':longest(seq,lambda x:x==2),'streak3':longest(seq,lambda x:x==3),'gap2':longest(seq,lambda x:x!=2),'gap3':longest(seq,lambda x:x!=3),'gap23':longest(seq,lambda x:x!=2 and x!=3)}
 return out,len(rows),buckets,total_goals

def payload_end(s,start):
 dep=0;q=False;esc=False
 for i in range(start,len(s)):
  c=s[i]
  if q:
   if esc:esc=False
   elif c=='\\':esc=True
   elif c=='"':q=False
  else:
   if c=='"':q=True
   elif c=='{':dep+=1
   elif c=='}':
    dep-=1
    if dep==0:return i+1
 raise ValueError('payload')
def inject(path,marker,allstats):
 s=path.read_text(encoding='utf-8');start=s.index(marker)+len(marker);data,decend=json.JSONDecoder().raw_decode(s[start:]);actual=payload_end(s,start)
 if actual!=start+decend:raise RuntimeError('payload mismatch')
 for lg in data['leagues']:
  code=lg['code']; stats=allstats.get(code,{})
  for season,sc in lg['scopes'].items():
   st=stats.get(season)
   if st is None:
     # 该赛季无本地赛果数据，跳过（保留报告内嵌值，不强行改写）
     continue
   out,n,buckets,goals_data=st
   if season=='2026-27' and code in TOP:
     sc['totalMatches']=n;sc['buckets']=buckets;sc['avgGoals']=round(goals_data/n,2) if n else 0
     tbl,team_goals=standings_2627(code)
   else:
     tbl=None;team_goals=None
   hit=0
   for t in sc['teams']:
     x=out.get(t['name']) or out.get(canon_top(t['name']))
     if x is None:
       # 队名无法匹配本地赛果：保留报告既有值，不崩溃、不影响其他队
       continue
     hit+=1
     t['seq23']=x['seq23'];t['seq23Matches']=x['seq23Matches'];t['b']=x['b'];t['count2']=x['count2'];t['count3']=x['count3'];t['streak2']=x['streak2'];t['streak3']=x['streak3'];t['gap2']=x['gap2'];t['gap3']=x['gap3'];t['gap23']=x['gap23']
     if tbl is not None:
       c=tbl.get(t['name']) or tbl.get(canon_top(t['name']))
       if c is not None: t['rank'],t['pts']=c
       tg=team_goals.get(t['name'], team_goals.get(canon_top(t['name'])))
       if tg is not None: t['total']=tg
   if hit==0:
     print('  [WARN]',code,season,'0 支球队匹配到本地赛果，该赛季未注入 seq23')
 out=s[:start]+json.dumps(data,ensure_ascii=False,separators=(',',':'))+s[actual:]
 if not out.rstrip().endswith('</html>'):raise RuntimeError('bad output')
 bak=path.with_suffix(path.suffix+'.before-seq23-2627')
 if not bak.exists():shutil.copy2(path,bak)
 path.write_text(out,encoding='utf-8');print(path.name,len(s),'->',len(out))

base_s=FILES[0][0].read_text(encoding='utf-8');base=json.JSONDecoder().raw_decode(base_s[base_s.index('window.DATA = ')+len('window.DATA = '):])[0]
allstats={}
for code in CODES:
 stats={}
 for lg in base['leagues']:
  if lg['code']!=code: continue
  for season in lg['scopes']:
   r=build(code,season)
   if r is not None: stats[season]=r
   else: print('  skip',code,season,'(无本地赛果文件)')
 allstats[code]=stats
 print(code,'已注入赛季:',sorted(stats.keys()))
for path,marker in FILES:inject(path,marker,allstats)
