# -*- coding: utf-8 -*-
"""构建 2026-27 赛季数据（五大联赛 + 五大次级联赛）。

数据源：titan007 静态赛果文件（https://zq.titan007.com/jsData/matchResult/2026-2027/s{SclassID}[_{SubSclassID}].js），
自 2026-09-15 起为 2026-27 主源（赛后分钟级、全部轮次、R_N 即官方轮次）。
选择它的原因：
  - 赛果以静态 JS 文件暴露，赛后分钟级更新，远快于 ESPN（ESPN 偶尔漏录最新一日）；
  - 覆盖全部 10 个联赛（含次级联赛）；队名经 cn_map 对齐为 openfootball 规范名。
ESPN 仅作兜底（titan007 整联赛抓取失败时才用）。

队名一律映射为 openfootball 规范名（与译名表 / 队徽表键一致），映射表经人工核对
（见下方 ESPN_MAP，键来自 ESPN 真实返回的 displayName，值为既有规范名）。
任一 ESPN 队名未映射即报错并跳过该联赛（不覆盖旧数据、不影响其它联赛）。

轮次：ESPN 比分接口不含轮次字段，沿用既有来源（openfootball 官方 Matchday ->
fixturedownload 官方 Round Number -> 按日期窗口推导兜底）。轮次源是静态赛程，
不随结果录入滞后，故保留以提升补赛 / 提前赛场景的准确。

产物：data/{code}.{div}.2026-27.json（openfootball JSON 结构，供 analyze_*.py 直接读取）
"""
import csv, json, os, re, subprocess, sys, time, unicodedata
from collections import defaultdict, Counter
from datetime import date

import os
WS = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(WS, "data")
SEASON = "2627"

# ---- 官方轮次源（openfootball）-------------------------------------------
# ESPN 比分接口无轮次字段，任何「按日期推算」的算法在遇到「轮次先赛 / 补赛」时都会错乱
# （西甲 2026-27 第 1 轮有 4 场被推迟到 08-25~08-27，反而晚于 08-20~08-24 进行的第 2 轮）。
# 所以只要 openfootball 收录了该联赛 2026-27 完整赛程，就一律采信它的官方 Matchday 编号。
# 已知收录：en.1 / de.1 / es.1 / it.1 / fr.1 / en.2；de.2 / es.2 / it.2 / fr.2 无（404）。
OF_DIR = os.path.join(WS, "assets", "of_2627")
OF_BASE = "https://raw.githubusercontent.com/openfootball/football.json/master/2026-27"
# 本工程队名 <-> openfootball 2026-27 队名的个别差异（归一化后的 key）。
# ESTAC Troyes 是本工程自 2020-21 起沿用的规范名，openfootball 2026-27 写作 ES Troyes AC，
# 同一家俱乐部；为保持跨季统计连续，改名为官方名会断裂，所以只在对齐轮次时做别名。
OF_ALIAS = {"estactroyes": "estroyesac"}

# ---- 官方轮次源（fixturedownload，兜底）----------------------------------
# openfootball 只覆盖 6 个联赛，fixturedownload 的 CSV 带官方 "Round Number" 列，
# 可作为第二顺位源。已探测：法乙 ligue-2 可用（306 行）；
# 德乙 / 西乙 / 意乙 的所有候选 slug 均 404，仍无官方轮次源，只能沿用推导。
FD_BASE = "https://fixturedownload.com/download/%s-2026-UTC.csv"
FD_SLUG = {("fr", 2): "ligue-2"}
FD_DIR = os.path.join(WS, "assets", "fd_2627")
# fixturedownload 用俱乐部注册全称，与本工程规范名不同的（归一化后的 key）
# 法乙 18 队已逐个核对（2026-09-08），均为一对一、无歧义
FD_ALIAS = {
    "eaguingamp": "enavantguingamp",              # EA Guingamp / EN Avant Guingamp
    "montpellierhsc": "montpellierheraultsc",     # Montpellier HSC / Montpellier Hérault SC
    "rodezaf": "rodezaveyronfootball",            # Rodez AF / Rodez Aveyron Football
    "usboulogne": "usboulogneco",                 # US Boulogne / US Boulogne CO
    "stadelavallois": "stadelavalloismfc",        # Stade Lavallois / Stade Lavallois MFC
    "fcsochaux": "fcsochauxmontbeliard",          # FC Sochaux / FC Sochaux-Montbéliard
}

# (ESPN 代号, 中文, league code, div)
LEAGUES = [
    ("eng.1", "英超", "en", 1), ("ger.1", "德甲", "de", 1), ("esp.1", "西甲", "es", 1),
    ("ita.1", "意甲", "it", 1), ("fra.1", "法甲", "fr", 1),
    ("eng.2", "英冠", "en", 2), ("ger.2", "德乙", "de", 2), ("esp.2", "西乙", "es", 2),
    ("ita.2", "意乙", "it", 2), ("fra.2", "法乙", "fr", 2),
]

# ESPN displayName -> openfootball 规范队名（人工核对；键取自 ESPN 真实返回，与译名表/队徽表键一致）
ESPN_MAP = {
    "eng.1": {   # 英超 2026-27（ESPN 真实队名）
        "AFC Bournemouth": "AFC Bournemouth",
        "Arsenal": "Arsenal FC",
        "Aston Villa": "Aston Villa FC",
        "Brentford": "Brentford FC",
        "Brighton & Hove Albion": "Brighton & Hove Albion FC",
        "Chelsea": "Chelsea FC",
        "Coventry City": "Coventry City FC",
        "Crystal Palace": "Crystal Palace FC",
        "Everton": "Everton FC",
        "Fulham": "Fulham FC",
        "Hull City": "Hull City AFC",
        "Ipswich Town": "Ipswich Town FC",
        "Leeds United": "Leeds United FC",
        "Liverpool": "Liverpool FC",
        "Manchester City": "Manchester City FC",
        "Manchester United": "Manchester United FC",
        "Newcastle United": "Newcastle United FC",
        "Nottingham Forest": "Nottingham Forest FC",
        "Sunderland": "Sunderland AFC",
        "Tottenham Hotspur": "Tottenham Hotspur FC",
    },
    "ger.1": {   # 德甲 2026-27
        "VfB Stuttgart": "VfB Stuttgart",
        "1. FC Union Berlin": "1. FC Union Berlin",
        "Eintracht Frankfurt": "Eintracht Frankfurt",
        "SC Paderborn 07": "SC Paderborn 07",
        "RB Leipzig": "RB Leipzig",
        "Borussia Mönchengladbach": "Borussia Mönchengladbach",
        "Borussia Dortmund": "Borussia Dortmund",
        "SC Freiburg": "SC Freiburg",
        "FC Augsburg": "FC Augsburg",
        "Bayern Munich": "FC Bayern München",
        "FC Cologne": "1. FC Köln",
        "TSG Hoffenheim": "TSG 1899 Hoffenheim",
        "Mainz": "1. FSV Mainz 05",
        "SV Elversberg": "SV 07 Elversberg",
        "Bayer Leverkusen": "Bayer 04 Leverkusen",
        "Hamburg SV": "Hamburger SV",
        "Werder Bremen": "SV Werder Bremen",
        "Schalke 04": "FC Schalke 04",
    },
    "esp.1": {   # 西甲 2026-27
        "Athletic Club": "Athletic Club",
        "Alavés": "Deportivo Alavés",
        "Getafe": "Getafe CF",
        "Sevilla": "Sevilla FC",
        "Rayo Vallecano": "Rayo Vallecano de Madrid",
        "Racing Santander": "Real Racing Club de Santander",
        "Villarreal": "Villarreal CF",
        "Espanyol": "RCD Espanyol de Barcelona",
        "Levante": "Levante UD",
        "Deportivo": "RC Deportivo La Coruña",
        "Elche": "Elche CF",
        "Atlético Madrid": "Club Atlético de Madrid",
        "Málaga": "Málaga CF",
        "Real Betis": "Real Betis Balompié",
        "Real Sociedad": "Real Sociedad de Fútbol",
        "Valencia": "Valencia CF",
        "Celta Vigo": "RC Celta de Vigo",
        "Real Madrid": "Real Madrid CF",
        "Barcelona": "FC Barcelona",
        "Osasuna": "CA Osasuna",
    },
    "ita.1": {   # 意甲 2026-27
        "AC Milan": "AC Milan",
        "AS Roma": "AS Roma",
        "Internazionale": "FC Internazionale Milano",
        "Monza": "AC Monza",
        "Udinese": "Udinese Calcio",
        "Como": "Como 1907",
        "Genoa": "Genoa CFC",
        "Napoli": "SSC Napoli",
        "Parma": "Parma Calcio 1913",
        "Cagliari": "Cagliari Calcio",
        "Frosinone": "Frosinone Calcio",
        "Juventus": "Juventus FC",
        "Venezia": "Venezia FC",
        "Lecce": "US Lecce",
        "Atalanta": "Atalanta BC",
        "Sassuolo": "US Sassuolo Calcio",
        "Torino": "Torino FC",
        "Bologna": "Bologna FC 1909",
        "Lazio": "SS Lazio",
        "Fiorentina": "ACF Fiorentina",
    },
    "fra.1": {   # 法甲 2026-27
        "AJ Auxerre": "AJ Auxerre",
        "Paris FC": "Paris FC",
        "Le Havre AC": "Le Havre AC",
        "Marseille": "Olympique de Marseille",
        "Strasbourg": "RC Strasbourg Alsace",
        "Lens": "Racing Club de Lens",
        "Le Mans": "Le Mans FC",
        "Brest": "Stade Brestois 29",
        "Nice": "OGC Nice",
        "Lorient": "FC Lorient",
        "Toulouse": "Toulouse FC",
        "Lyon": "Olympique Lyonnais",
        "Troyes": "ESTAC Troyes",
        "Angers": "Angers SCO",
        "Lille": "Lille OSC",
        "AS Monaco": "AS Monaco FC",
        "Stade Rennais": "Stade Rennais FC 1901",
        "Paris Saint-Germain": "Paris Saint-Germain FC",
    },
    "eng.2": {   # 英冠 2026-27
        "Wolverhampton Wanderers": "Wolverhampton Wanderers FC",
        "Blackburn Rovers": "Blackburn Rovers FC",
        "Bolton Wanderers": "Bolton Wanderers FC",
        "Preston North End": "Preston North End FC",
        "Bristol City": "Bristol City FC",
        "Millwall": "Millwall FC",
        "Charlton Athletic": "Charlton Athletic FC",
        "Derby County": "Derby County FC",
        "Middlesbrough": "Middlesbrough FC",
        "Lincoln City": "Lincoln City FC",
        "Norwich City": "Norwich City FC",
        "West Bromwich Albion": "West Bromwich Albion FC",
        "Portsmouth": "Portsmouth FC",
        "Queens Park Rangers": "Queens Park Rangers FC",
        "Stoke City": "Stoke City FC",
        "Swansea City": "Swansea City AFC",
        "Sheffield United": "Sheffield United FC",
        "Birmingham City": "Birmingham City FC",
        "Watford": "Watford FC",
        "Southampton": "Southampton FC",
        "Burnley": "Burnley FC",
        "West Ham United": "West Ham United FC",
        "Cardiff City": "Cardiff City FC",
        "Wrexham": "Wrexham AFC",
    },
    "ger.2": {   # 德乙 2026-27
        "VfL Bochum": "VfL Bochum",
        "1. FC Heidenheim 1846": "1. FC Heidenheim 1846",
        "VfL Osnabruck": "VfL Osnabrück",
        "1. FC Magdeburg": "1. FC Magdeburg",
        "Karlsruher SC": "Karlsruher SC",
        "Arminia Bielefeld": "Arminia Bielefeld",
        "SV Darmstadt 98": "SV Darmstadt 98",
        "Holstein Kiel": "Holstein Kiel",
        "VfL Wolfsburg": "VfL Wolfsburg",
        "1. FC Nürnberg": "1. FC Nürnberg",
        "Dynamo Dresden": "Dynamo Dresden",
        "Hannover 96": "Hannover 96",
        "SpVgg Greuther Fürth": "SpVgg Greuther Fürth",
        "Hertha Berlin": "Hertha BSC",
        "TSV Eintracht Braunschweig": "Eintracht Braunschweig",
        "Kaiserslautern": "1. FC Kaiserslautern",
        "Energie Cottbus": "FC Energie Cottbus",
        "St. Pauli": "FC St. Pauli",
    },
    "esp.2": {   # 西乙 2026-27
        "FC Andorra": "FC Andorra",
        "Real Oviedo": "Real Oviedo",
        "Real Valladolid": "Real Valladolid",
        "Albacete": "Albacete",
        "Sporting Gijón": "Sporting Gijón",
        "Real Sociedad II": "Real Sociedad B",
        "Castellón": "CD Castellón",
        "Ceuta": "AD Ceuta FC",
        "Cádiz": "Cádiz CF",
        "RC Celta Fortuna": "RC Celta de Vigo B",
        "Granada": "Granada CF",
        "Mallorca": "RCD Mallorca",
        "Eibar": "SD Eibar",
        "Tenerife": "CD Tenerife",
        "Burgos": "Burgos CF",
        "Córdoba": "Córdoba CF",
        "Girona": "Girona FC",
        "Leganés": "CD Leganés",
        "Las Palmas": "UD Las Palmas",
        "CD Sabadell": "CE Sabadell",
        "Almería": "UD Almería",
        "Eldense": "CD Eldense",
    },
    "ita.2": {   # 意乙 2026-27
        "Virtus Entella": "Virtus Entella",
        "US Avellino": "US Avellino",
        "Sampdoria": "Sampdoria",
        "Juve Stabia": "Juve Stabia",
        "Vicenza": "L.R. Vicenza Virtus",
        "Catanzaro": "US Catanzaro",
        "Carrarese": "Carrarese Calcio",
        "Mantova": "Mantova 1911 SSD",
        "Sudtirol": "FC Südtirol",
        "Benevento": "Benevento Calcio",
        "Modena": "Modena FC",
        "Empoli": "Empoli FC",
        "Cremonese": "US Cremonese",
        "Arezzo": "US Arezzo",
        "Hellas Verona": "Hellas Verona FC",
        "Ascoli": "Ascoli Calcio",
        "Pisa": "Pisa SC",
        "Padova": "Calcio Padova",
        "Cesena": "Cesena FC",
        "Palermo": "Palermo FC",
    },
    "fra.2": {   # 法乙 2026-27
        "AS Nancy Lorraine": "AS Nancy Lorraine",
        "Stade de Reims": "Stade de Reims",
        "Dijon FCO": "Dijon FCO",
        "Boulogne": "US Boulogne",
        "Clermont Foot": "Clermont Foot 63",
        "Dunkerque": "USL Dunkerque",
        "Grenoble": "Grenoble Foot 38",
        "Metz": "FC Metz",
        "Guingamp": "EA Guingamp",
        "Montpellier": "Montpellier HSC",
        "Nantes": "FC Nantes",
        "Red Star FC 93": "Red Star FC",
        "Pau": "Pau FC",
        "Annecy": "FC Annecy",
        "Rodez Aveyron": "Rodez AF",
        "Stade Laval": "Stade Lavallois",
        "Sochaux": "FC Sochaux",
        "Saint-Étienne": "AS Saint-Étienne",
    },
}


# ---- titan007 数据源（2026-27 主源，全部已完赛轮次）----------------
# 说明：titan007 赛果以静态 JS 文件暴露（页面主体是 JS 渲染，但赛果数据是静态文件）：
#   https://zq.titan007.com/jsData/matchResult/{season}/s{SclassID}[_{SubSclassID}].js
# 文件含 arrTeam=[队ID, 简体中文名, 繁体, 英文, '', 队徽, 0] 与
#   jh["R_N"]=[[赛果记录],...]；单条记录：
#   [matchId, SclassID, status, 'YYYY-MM-DD HH:MM', homeId, awayId, 'FT比分', 'HT比分', ...]
#   status==-1 或第 7 字段形如 'X-Y' 即已完赛。
# 队名经 cn_map（简体中文 -> 规范英文名）对齐；个别中文写法差异用 TITAN_CN_ALIAS 修正。
# 自 2026-09-15 起，2026-27 直接以 titan007 为准：取全部已完赛轮次（R_N 即官方轮次），
# 不再依赖 ESPN 主源（ESPN 仅作兜底，titan007 整联赛抓取失败时才用）。
# 历史赛季（2025-26 及更早）由各自独立 JSON 维护，本脚本只写 *.2026-27.json，不受影响。
# 任何抓取/解析失败都只告警、回退 ESPN，绝不中断主流程。
TITAN_SEASON = "2026-2027"
TITAN_URL = "https://zq.titan007.com/jsData/matchResult/{season}/s{SclassID}{sub}.js"
# 流水线联赛 -> (titan007 SclassID, SubSclassID)；SubSclassID=0 时文件无后缀。
# 下列 ID 全部由直抓页面 <title> 与 data 文件 arrLeague 核对，非站点导航（导航 ID 已过时）。
TITAN_LEAGUES = {
    "eng.1": (36, 0), "ger.1": (8, 0), "esp.1": (31, 0), "ita.1": (34, 2948), "fra.1": (11, 0),
    "eng.2": (37, 87), "ger.2": (9, 132), "esp.2": (33, 546), "ita.2": (40, 261), "fra.2": (12, 1778),
}
# titan007 简体中文写法 -> cn_map 采用的写法（用于对齐规范英文名）。键来自实测未匹配名。
TITAN_CN_ALIAS = {
    "曼彻斯特联": "曼联", "曼彻斯特城": "曼城", "托特纳姆热刺": "热刺",
    "云达不莱梅": "云达不来梅", "柏林联合": "柏林联",
    "巴伦西亚": "瓦伦西亚", "赫塔菲": "赫塔费",
    "弗洛西诺尼": "弗罗西诺内",
    "伯明翰": "伯明翰城", "南安普敦": "南安普顿", "卡迪夫城": "加的夫城",
    "布里斯托城": "布里斯托尔城", "查尔顿": "查尔顿竞技", "谢菲尔德联队": "谢菲尔德联",
    "奥斯纳布鲁克": "奥斯纳布吕克", "德累斯顿": "德累斯顿迪纳摩", "比勒菲尔德": "比勒费尔德",
    "荷尔斯泰因": "荷尔斯泰因基尔",
    "埃登斯": "埃登塞", "安道尔FC": "安道尔", "皇家奥维耶多": "奥维耶多",
    "凯勒雷斯": "卡拉雷塞", "卡坦萨罗": "卡坦扎罗", "史泰比亚": "斯塔比亚",
    "阿维利诺": "阿韦利诺", "阿雷佐": "阿雷索",
    "USL敦刻尔克": "敦刻尔克", "阿纳西": "阿讷西",
}


def parse_titan_file(path):
    """解析 titan007 matchResult JS 文件，返回已完赛列表
    [{round,date,home_cn,away_cn,ft}]。解析失败返回 []。"""
    try:
        s = open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return []
    id2cn = {}
    m = re.search(r'var arrTeam\s*=\s*(\[.*?\]);', s, re.S)
    if m:
        inner = m.group(1).strip()
        if inner.startswith('['):
            inner = inner[1:-1]
        for part in re.findall(r'\[[^\]]*\]', inner):
            cells = part[1:-1].split(',')
            if len(cells) >= 2:
                try:
                    id2cn[int(cells[0].strip())] = cells[1].strip().strip("'\"")
                except Exception:
                    pass
    out = []
    for rm in re.finditer(r'jh\["R_(\d+)"\]\s*=\s*\[(.*?)\];', s, re.S):
        rn = int(rm.group(1))
        for rec in re.findall(r'\[([^\]]*)\]', rm.group(2)):
            cells = [c.strip() for c in rec.split(',')]
            if len(cells) < 7:
                continue
            try:
                hid, aid = int(cells[4]), int(cells[5])
            except Exception:
                continue
            ft = cells[6].strip().strip("'\"")
            status = cells[2].strip().strip("'\"")
            if status != '-1' and not re.match(r'^\d+-\d+$', ft or ''):
                continue
            dt = cells[3].strip().strip("'\"").strip()[:10]
            out.append({"round": rn, "date": dt,
                        "home_cn": id2cn.get(hid, str(hid)),
                        "away_cn": id2cn.get(aid, str(aid)), "ft": ft})
    return out


def fetch_titan_season(code):
    """抓取并解析 titan007 某联赛整季已完赛（全部轮次），返回 recs 列表
    [{date, team1, team2, score:{ft:[h,a]}, round, _src}] 或 None（抓取失败/无数据）。
    2026-27 主源：titan007 的 R_N 即官方轮次，无需额外推导。best-effort，失败返回 None
    由调用方回退 ESPN。"""
    CN = {}
    for f in ("cn_map.json", "cn_map_champ.json"):
        p = os.path.join(WS, "assets", f)
        if os.path.exists(p):
            try:
                CN.update(json.load(open(p, encoding="utf-8")))
            except Exception:
                pass
    # 反向中文->规范名（限定本联赛 canonical 集合，规避跨联赛重名）
    rev = {}
    for c in ESPN_MAP.get(code, {}).values():
        cv = CN.get(c)
        if cv:
            rev.setdefault(cv, c)
    if not rev:
        print(f"  [titan007] {code} 无反向映射表，回退 ESPN")
        return None
    sc, sub = TITAN_LEAGUES[code]
    sub_s = ("_" + str(sub)) if sub else ""
    url = TITAN_URL.format(season=TITAN_SEASON, SclassID=sc, sub=sub_s)
    p = f"/tmp/titan_{code}_{sc}.js"
    ok = False
    for _ in range(3):
        try:
            subprocess.run(
                ["curl", "-sSL", "--retry", "1", "--max-time", "35", "-A",
                 "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
                 "-H", "Referer: https://zq.titan007.com/", "-o", p, url],
                check=True, capture_output=True, env=dict(os.environ))
        except Exception:
            pass
        # WAF 拦截会返回 HTML 错误页；忽略之
        try:
            head = open(p, encoding="utf-8", errors="replace").read(200)
        except Exception:
            head = ""
        if "<!DOCTYPE" in head or "<html" in head:
            try:
                os.remove(p)
            except Exception:
                pass
            head = ""
        if os.path.exists(p) and os.path.getsize(p) > 500 and head:
            ok = True
            break
        time.sleep(1)
    if not ok:
        print(f"  [titan007] {code} 抓取失败/被拦截，回退 ESPN")
        return None
    raw = parse_titan_file(p)
    if not raw:
        print(f"  [titan007] {code} 无已完赛数据，回退 ESPN")
        return None
    recs, unmapped = [], set()
    max_rn = 0
    for r in raw:
        h = rev.get(r["home_cn"]) or rev.get(TITAN_CN_ALIAS.get(r["home_cn"], ""))
        a = rev.get(r["away_cn"]) or rev.get(TITAN_CN_ALIAS.get(r["away_cn"], ""))
        if not h or not a:
            unmapped.add(r["home_cn"]); unmapped.add(r["away_cn"]); continue
        try:
            hs, as_ = (int(x) for x in r["ft"].split("-"))
        except Exception:
            continue
        max_rn = max(max_rn, r["round"])
        recs.append({"date": r["date"], "team1": h, "team2": a,
                     "score": {"ft": [hs, as_]}, "round": f"{r['round']}. Round",
                     "_src": "titan007"})
    if unmapped:
        print(f"  [titan007 warn] {code} 有未映射队名 {sorted(unmapped)}，相关场次跳过")
    if not recs:
        print(f"  [titan007] {code} 无可用场次，回退 ESPN")
        return None
    print(f"  [titan007] {code} 整季已完赛 {len(recs)} 场（R1..R{max_rn}），作为 2026-27 主源")
    return recs


def fetch_espn(code):
    """下载 ESPN 整季比分（按月分窗，规避单请求 100 条上限），返回 events 列表。

    2026-27 单联赛整季 380/462 场，远超 ESPN 单请求 100 条上限，故按自然月拆窗；
    每月赛程远小于 100，安全。失败或空响应返回 []（由调用方决定是否跳过该联赛）。
    """
    months = [(2026, 8, 31), (2026, 9, 30), (2026, 10, 31), (2026, 11, 30),
              (2026, 12, 31), (2027, 1, 31), (2027, 2, 28), (2027, 3, 31),
              (2027, 4, 30), (2027, 5, 31), (2027, 6, 30)]
    events = []
    for y, m, last in months:
        a = f"{y}{m:02d}01"
        b = f"{y}{m:02d}{last}"
        url = (f"https://site.api.espn.com/apis/site/v2/sports/soccer/{code}"
               f"/scoreboard?dates={a}-{b}")
        p = f"/tmp/espn_{code}_{y}{m:02d}.json"
        ok = False
        for _ in range(3):
            try:
                # 显式透传环境（含沙箱/企业代理变量），确保子进程 curl 走与顶层命令相同的出口
                subprocess.run(["curl", "-sSL", "--retry", "2", "--retry-delay", "1",
                                "--max-time", "40", "-A", "Mozilla/5.0", "-o", p, url],
                               check=True, capture_output=True, env=dict(os.environ))
            except Exception:
                pass
            if os.path.exists(p) and os.path.getsize(p) > 200:
                try:
                    d = json.load(open(p, encoding="utf-8"))
                except Exception:
                    d = None
                if d and isinstance(d.get("events"), list):
                    events.extend(d["events"])
                    ok = True
                    break
            time.sleep(1)
        if not ok:
            print(f"  [warn] {code} {y}-{m:02d} 抓取失败 / 无数据")
    return events


def parse_espn(events, mp):
    """把 ESPN events 解析成 recs；返回 (recs, unknown)。

    recs 元素结构 = {"date","team1","team2","score":{"ft":[h,a]}}，与旧 CSV 产物一致。
    unknown = 未出现在 mp 中的 ESPN displayName 集合（调用方据此决定是否跳过该联赛）。
    只取已完赛（detail=='FT' 或 state=='post'）且有整数比分的场次；同场去重。
    """
    seen = set()
    recs, unknown = [], set()
    for e in events:
        comp = (e.get("competitions") or [{}])[0]
        st = (e.get("status") or {}).get("type") or {}
        detail, state = st.get("detail", ""), st.get("state", "")
        if detail != "FT" and state != "post":
            continue
        comps = comp.get("competitors") or []
        if len(comps) != 2:
            continue
        home = away = None
        for c in comps:
            if c.get("homeAway") == "home":
                home = c
            elif c.get("homeAway") == "away":
                away = c
        if not home or not away:
            continue
        hn = (home.get("team") or {}).get("displayName", "")
        an = (away.get("team") or {}).get("displayName", "")
        hs, as_ = home.get("score"), away.get("score")
        if hn not in mp:
            unknown.add(hn)
        if an not in mp:
            unknown.add(an)
        if hn not in mp or an not in mp:
            continue
        try:
            h, a = int(hs), int(as_)
        except Exception:
            continue
        iso = str(e.get("date", ""))[:10]
        key = (iso, hn, an)
        if key in seen:
            continue
        seen.add(key)
        recs.append({"date": iso, "team1": mp[hn], "team2": mp[an],
                     "score": {"ft": [h, a]}})
    return recs, unknown


def _nkey(s, tbl=None):
    """队名归一化：去重音、去标点/空格，用于跨源对齐（Elche CF -> elchecf）

    tbl 给出「本工程名 -> 外部源名」的个别别名（不同源的注册全称写法不同）。
    """
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    k = re.sub(r"[^a-z0-9]", "", s.lower())
    return (tbl or OF_ALIAS).get(k, k)


def of_round_map(lg, div):
    """openfootball 2026-27 官方轮次表：{(主队key, 客队key): 轮次号}；源不存在返回 None。

    结果缓存在 assets/of_2627/ 下，避免每次跑流水线都打网络；缓存文件损坏会重新下载。
    """
    key = f"{lg}.{div}"
    os.makedirs(OF_DIR, exist_ok=True)
    miss_f = os.path.join(OF_DIR, "_missing.json")
    miss = {}
    if os.path.exists(miss_f):
        try:
            miss = json.load(open(miss_f, encoding="utf-8")) or {}
        except Exception:
            miss = {}
    dst = os.path.join(OF_DIR, f"{key}.json")
    have = os.path.exists(dst) and os.path.getsize(dst) > 500

    def _bail():
        """记下「官方源无此联赛」，7 天内不再重试（避免每天白等 4 次超时）"""
        miss[key] = date.today().isoformat()
        try:
            json.dump(miss, open(miss_f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        except Exception:
            pass

    if not have:
        # 7 天内已确认该联赛官方源不存在 -> 直接跳过，不发请求
        if miss.get(key):
            try:
                if (date.today() - date.fromisoformat(miss[key])).days < 7:
                    return None
            except Exception:
                pass
        ok = False
        for _ in range(2):
            try:
                subprocess.run(["curl", "-sSL", "--max-time", "25", "-o", dst,
                                f"{OF_BASE}/{key}.json"], check=True, capture_output=True)
                json.load(open(dst, encoding="utf-8"))   # 完整性校验
                ok = True
                break
            except Exception:
                try:
                    os.remove(dst)
                except Exception:
                    pass
        if not ok:
            _bail()
            return None
    if not (os.path.exists(dst) and os.path.getsize(dst) > 500):
        _bail()
        return None
    try:
        ms = json.load(open(dst, encoding="utf-8"))["matches"]
    except Exception:
        _bail()
        return None
    m = {}
    for x in ms:
        n = re.sub(r"\D", "", str(x.get("round", "")))
        if not n:
            continue
        m[(_nkey(x.get("team1")), _nkey(x.get("team2")))] = int(n)
    return m or None


def fd_round_map(lg, div):
    """fixturedownload 2026-27 官方轮次表：{(主队key, 客队key): 轮次号}。

    CSV 带官方 "Round Number" 列，是 openfootball 之外的第二顺位源（主要用于法乙）。
    未登记 slug 或下载失败返回 None。缓存同 openfootball，落在 assets/fd_2627/。
    """
    slug = FD_SLUG.get((lg, div))
    if not slug:
        return None
    os.makedirs(FD_DIR, exist_ok=True)
    dst = os.path.join(FD_DIR, f"{lg}.{div}.csv")
    if not (os.path.exists(dst) and os.path.getsize(dst) > 500):
        ok = False
        for _ in range(2):
            try:
                subprocess.run(["curl", "-sSL", "--max-time", "25", "-o", dst,
                                FD_BASE % slug], check=True, capture_output=True)
                head = open(dst, encoding="utf-8-sig", errors="replace").readline()
                if "Round Number" in head:
                    ok = True
                    break
            except Exception:
                pass
            try:
                os.remove(dst)
            except Exception:
                pass
        if not ok:
            return None
    try:
        rows = list(csv.DictReader(open(dst, encoding="utf-8-sig", errors="replace")))
    except Exception:
        return None
    m = {}
    for r in rows:
        n = re.sub(r"\D", "", str(r.get("Round Number", "")))
        if not n:
            continue
        m[(_nkey(r.get("Home Team"), FD_ALIAS),
           _nkey(r.get("Away Team"), FD_ALIAS))] = int(n)
    return m or None


def main():
    all_teams = {}          # (code,div) -> set(canonical)
    skipped_bad = []        # 因队名未映射被跳过的联赛（map 有 bug，需修复）
    # 2026-27 主源：titan007（全部已完赛轮次，R_N 即官方轮次）。
    # 不再依赖 ESPN 主源；ESPN 仅作兜底（titan007 抓取整联赛失败时才用）。
    # 历史赛季（2025-26 及更早）由各自独立 JSON 维护，本脚本只写 *.2026-27.json，不受影响。
    print("\n════════ 2026-27 主源：titan007（全部已完赛轮次）════════")
    for code, cn, lg, div in LEAGUES:
        recs = fetch_titan_season(code)      # 返回 recs 列表或 None
        if recs is not None:
            # ── titan007 主路径：轮次直接取官方 R_N，无需 openfootball/fixturedownload 推导
            skipped = 0
            round_src = "titan007"
            nround = len({r["round"] for r in recs})
            dates = sorted({r["date"] for r in recs if r["date"]})
            of_note = "titan007 官方轮次（R_N）"
        else:
            # ── ESPN 兜底分支（仅 titan007 整联赛抓取失败）──
            events = fetch_espn(code)
            if not events:
                print(f"[{cn} {code}] ✗ 整季抓取为空，跳过（保留旧数据）"); continue
            mp = ESPN_MAP[code]
            recs, unknown = parse_espn(events, mp)

            # 校验：ESPN 中出现的所有队名都必须已映射（map 不全 = 数据会错，必须修）
            if unknown:
                print(f"[{cn} {code}] ✗ 未映射 ESPN 队名 {sorted(unknown)} —— 跳过该联赛")
                skipped_bad.append(f"{cn} {code}: {sorted(unknown)}")
                continue
            if len(set(mp.values())) != len(mp):
                dup = [k for k, v in mp.items() if list(mp.values()).count(v) > 1]
                print(f"[{cn} {code}] ✗ 映射目标重复 {dup} —— 跳过该联赛")
                skipped_bad.append(f"{cn} {code}: 映射重复 {dup}")
                continue
            if not recs:
                print(f"[{cn} {code}] · 暂无已完赛（FT）场次，跳过（保留旧数据）"); continue

            # 只取 ESPN 真实存在的赛果（FT 且有比分）
            skipped = 0   # ESPN 侧无需「跳过无比分」计数，仅作占位保持日志一致

            # 轮次：ESPN 比分接口没有轮次字段，但绝不能「一个日期 = 一轮」——
            # 一轮联赛通常横跨周五~周一，按日期编号会把第二个周末的比赛标成「第 5 轮」。
            # 正确做法见 assign_rounds()：先按日期聚成「比赛窗口」，再按单轮容量切分。
            nteams = len({r["team1"] for r in recs} | {r["team2"] for r in recs})
            nround = assign_rounds(recs, max(1, nteams // 2))     # 无官方轮次时的兜底推导
            dates = sorted({r["date"] for r in recs if r["date"]})

            # 官方轮次覆盖：ESPN 无轮次字段，而「按日期推算」在补赛/提前进行时必然错乱。
            # 依次尝试 openfootball（官方 Matchday）-> fixturedownload（官方 Round Number），
            # 任一源能 100% 命中全部已赛场次就采信它；否则沿用推导轮次并说明原因。
            round_src, of_note = "derived", "按日期窗口推导"
            sources = [("openfootball", None, of_round_map(lg, div)),
                       ("fixturedownload", FD_ALIAS, fd_round_map(lg, div))]
            for src_name, tbl, src_map in sources:
                if not src_map:
                    continue
                # 先试算不落盘：命中不全时若逐个改写，会让官方轮次与推导轮次混在同一赛季里
                probe, miss = {}, []
                for r in recs:
                    n = src_map.get((_nkey(r["team1"], tbl), _nkey(r["team2"], tbl)))
                    if n:
                        probe[id(r)] = f"{n}. Round"
                    else:
                        miss.append(f"{r['team1']} vs {r['team2']}")
                if len(probe) != len(recs):
                    of_note = (f"{src_name} 仅命中 {len(probe)}/{len(recs)}，沿用推导轮次"
                               + (f"：{'; '.join(miss[:3])}" if miss else ""))
                    continue
                for r in recs:
                    r["round"] = probe[id(r)]
                round_src = "official"
                nround = len({r["round"] for r in recs})
                of_note = f"采信 {src_name} 官方轮次（{len(recs)}/{len(recs)} 命中）"
                break
            if round_src == "derived" and not sources[0][2] and not sources[1][2]:
                of_note = "两个官方源都无该联赛 2026-27 赛程，按日期窗口推导"

        out = {"name": f"{cn} {SEASON}", "roundSource": round_src, "matches": recs}
        dst = os.path.join(D, f"{lg}.{div}.2026-27.json")
        json.dump(out, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

        teams = {r["team1"] for r in recs} | {r["team2"] for r in recs}
        all_teams[(lg, div)] = teams
        print(f"[{cn} {code}] {lg}.{div}: 写入 {len(recs)} 场（跳过无比分 {skipped}），"
              f"球队 {len(teams)}，{len(dates)} 个比赛日 -> {nround} 个轮次"
              f" [{round_src}] {of_note}"
              f" -> {os.path.basename(dst)}")

    # 译名 / 队徽 覆盖检查
    print("\n=== 2026-27 新球队 译名/队徽 覆盖检查 ===")
    CN, CREST = {}, {}
    for f in ["cn_map.json", "cn_map_champ.json"]:
        p = os.path.join(WS, "assets", f)
        if os.path.exists(p):
            CN.update(json.load(open(p, encoding="utf-8")))
    for f in ["crests.json", "crests_champ.json"]:
        p = os.path.join(WS, "assets", f)
        if os.path.exists(p):
            CREST.update(json.load(open(p, encoding="utf-8")))
    need_cn, need_crest = [], []
    for (lg, div), teams in sorted(all_teams.items()):
        for t in sorted(teams):
            if t not in CN:
                need_cn.append((lg, div, t))
            if not CREST.get(t):
                need_crest.append((lg, div, t))
    print(f"  缺中文译名 {len(need_cn)} 支：")
    for lg, div, t in need_cn:
        print(f"     {lg}.{div}  {t}")
    print(f"  缺队徽 {len(need_crest)} 支：")
    for lg, div, t in need_crest:
        print(f"     {lg}.{div}  {t}")
    json.dump({"need_cn": need_cn, "need_crest": need_crest},
              open(os.path.join(D, "_need_2026_27.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)

    # 队名映射有缺口 = 脚本 bug，必须修；以非 0 退出让 refresh.sh 中止并告警
    if skipped_bad:
        print("\n[ERROR] 以下联赛因 ESPN 队名未映射被跳过，请补全 ESPN_MAP 后重跑：")
        for s in skipped_bad:
            print(f"   - {s}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# 轮次重算。ESPN 比分接口只有日期、没有轮次，而「一个日期 = 一轮」是错的：
# 一轮联赛通常横跨周五~周一（英冠 2026-27 首轮就拆在 08-14/15/16/17 四天），
# 按日期编号会让第二个周末的比赛显示成「第 5 轮」「第 6 轮」。
# 正确做法两步走：
#   1) 把日期聚成「比赛窗口」：相邻比赛日间隔 <= WINDOW_GAP 天视为同一窗口；
#   2) 窗口内按日期顺序累积，每满 per_round 场（= 队数/2）算一轮——
#      这样一周双赛（如节礼日 12-26 + 12-28）也能正确拆成两轮。
# ---------------------------------------------------------------------------
WINDOW_GAP = 3


def _days(iso):
    try:
        y, m, d = (int(x) for x in str(iso)[:10].split("-"))
        return date(y, m, d).toordinal()
    except Exception:
        return None


def assign_rounds(recs, per_round):
    """按比赛窗口 + 单轮容量重排轮次，写回每条记录的 round 字段，返回总轮数。"""
    dated = [r for r in recs if r.get("date")]
    if not dated:
        for r in recs:
            r["round"] = "1. Round"
        return 1
    # 1) 日期 -> 窗口号
    d2w, w, prev = {}, 0, None
    for d in sorted({r["date"] for r in dated}):
        cur = _days(d)
        if prev is None or cur is None or prev is None or (cur - prev) > WINDOW_GAP:
            w += 1
        d2w[d] = w
        prev = cur
    # 2) 窗口内按累积场次切轮
    byw = defaultdict(list)
    for r in dated:
        byw[d2w[r["date"]]].append(r)
    n = 0
    for wk in sorted(byw):
        grp = sorted(byw[wk], key=lambda r: (r["date"], r["team1"], r["team2"]))
        k = 0
        for r in grp:
            if k and k % per_round == 0:
                n += 1
            r["round"] = f"{n + 1}. Round"
            k += 1
        n += 1
    for r in recs:
        r.setdefault("round", f"{n}. Round")

    # 3) 兜底修复：同一支队在同一轮出现两次（补赛把两个轮次挤进同一个日期窗口时会发生），
    #    把后到的那场顺延到后面第一个「两队都空闲且该轮未满」的位置。
    #    对干净赛程这是空操作；对补赛场景它至少保证「每队每轮最多一场」这一硬约束。
    def _num(x):
        return int(re.sub(r"\D", "", str(x.get("round", ""))) or 1)

    used_by, cnt_by = defaultdict(set), Counter()
    for r in sorted(recs, key=lambda x: (_num(x), x.get("date") or "", x["team1"])):
        k = _num(r)
        while (used_by[k] & {r["team1"], r["team2"]}) or cnt_by[k] >= per_round:
            k += 1
        r["round"] = f"{k}. Round"
        used_by[k].add(r["team1"]); used_by[k].add(r["team2"]); cnt_by[k] += 1
    return max(cnt_by or [1])


def norm_date(d):
    """dd/mm/yyyy -> yyyy-mm-dd（ESPN 直接给 ISO，本函数保留以备其它源）"""
    d = (d or "").strip()
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", d)
    if not m:
        return d
    dd, mm, yy = m.group(1), m.group(2), m.group(3)
    if len(yy) == 2:
        yy = "20" + yy
    return f"{yy}-{int(mm):02d}-{int(dd):02d}"


if __name__ == "__main__":
    main()
