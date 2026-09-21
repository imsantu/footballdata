#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_goals_perspective.py — 统一 goals 数据里 seq23Matches[*].score 的「视角」。

单体 goals-data.js 已废弃（不再落盘），本模块的 normalize / check_conservation
被 sync_site.py 直接作用于「抽取后的内存对象」；下方 main() 作为手动修复入口，
默认读取进球数源报告（与 sync_site 同一份数据源）。

背景
----
goals 数据里每支球队的 seq23Matches[*].score 存在两种视角：
  * 主客视角（绝大多数队）：score = "主队进球-客队进球"
  * 球队视角（德甲的 VfL Bochum / SpVgg Greuther Fürth 等孤例）：score = "自己进球-对手进球"

两种视角在「主场」时读数一致，只在「客场」时相反，所以肉眼很难发现。
上层若按其中一种口径累加得失球，客场场次就会整体颠倒，导致全队 / 全联赛数据失真。

判定方法（不需要任何队名硬编码）
--------------------------------
同一场比赛会被主客两队各记一次。取某队「客场」(ha == 'A') 的场次，
与其对手在同一日期的记录比对：
  * 两条 score 完全相同            -> 该队是主客视角
  * 两条 score 互为翻转            -> 该队是球队视角
主场场次无法区分（两种视角读数相同），因此只用客场场次判定。

修复
----
把判定为「球队视角」的队，其**所有**场次的 score 翻转，统一成主客视角。
（主场场次翻转后仍然正确，因为主队视角下 "自己-对手" == "主队-客队"。）

校验
----
修复后每个联赛每赛季必须满足「总进球守恒」：sum(所有队进球) == sum(所有队失球)。
"""

import json
import os
import re
import sys

# 手动修复入口默认读取进球数源报告（与 sync_site.py 同一份数据源；单体 goals-data.js 已废弃）
GOALS_SRC = os.environ.get("FD_GOALS_HTML", os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "generator", "football_big5_goals.html"))


def flip_score(s):
    """'2-1' -> '1-2'；非标准比分原样返回"""
    if not isinstance(s, str):
        return s
    parts = s.split('-')
    if len(parts) != 2:
        return s
    return '%s-%s' % (parts[1], parts[0])


def is_team_perspective(team, by_name):
    """只用客场(ha == 'A')场次判定该队 score 是否为「球队视角」。"""
    same = flip = 0
    for m in (team.get('seq23Matches') or []):
        if m.get('ha') != 'A':
            continue
        opp = by_name.get(m.get('opponent'))
        if not opp:
            continue
        om = next((x for x in (opp.get('seq23Matches') or [])
                   if x.get('date') == m.get('date')), None)
        if not om:
            continue
        a, b = str(m.get('score')), str(om.get('score'))
        if a == b:
            same += 1
        elif b == flip_score(a):
            flip += 1
    # 客场场次里「翻转」占多数 -> 球队视角
    return flip > same


def normalize(data):
    """把所有队的 score 统一成主客视角，返回 (修复的队数, 明细列表)"""
    fixed = []
    for lg in data.get('leagues', []):
        for season in (lg.get('order') or []):
            sc = (lg.get('scopes') or {}).get(season)
            if not sc or not sc.get('teams'):
                continue
            by_name = {t['name']: t for t in sc['teams']}
            for t in sc['teams']:
                if not is_team_perspective(t, by_name):
                    continue
                n = 0
                for m in (t.get('seq23Matches') or []):
                    # 只翻转客场：主场时「球队视角」与「主客视角」读数本就相同，
                    # 翻转反而会把正确的主队比分改成错的。
                    if m.get('ha') != 'A':
                        continue
                    new = flip_score(m.get('score'))
                    if new != m.get('score'):
                        m['score'] = new
                        n += 1
                fixed.append((lg.get('code'), season, t.get('cn', t.get('name')), n))
    return fixed


def check_conservation(data):
    """总进球守恒：每个联赛每赛季 sum(进球) 必须 == sum(失球)。返回违规列表。"""
    bad = []
    for lg in data.get('leagues', []):
        for season in (lg.get('order') or []):
            sc = (lg.get('scopes') or {}).get(season)
            if not sc or not sc.get('teams'):
                continue
            gf = ga = 0
            for t in sc['teams']:
                for m in (t.get('seq23Matches') or []):
                    sp = str(m.get('score') or '').split('-')
                    if len(sp) != 2:
                        continue
                    a, b = int(sp[0]), int(sp[1])
                    if m.get('ha') == 'H':
                        gf += a; ga += b
                    else:
                        gf += b; ga += a
            if gf != ga:
                bad.append((lg.get('code'), season, gf, ga, gf - ga))
    return bad


def main():
    path = os.path.abspath(GOALS_SRC)
    if not os.path.exists(path):
        print('源文件不存在: %s' % path, file=sys.stderr)
        return 1
    raw = open(path, encoding='utf-8').read()

    marker = 'window.DATA = '
    i = raw.find(marker)
    if i < 0:
        print('未在 %s 中找到 %r' % (path, marker), file=sys.stderr)
        return 1
    data, _ = json.JSONDecoder().raw_decode(raw[i + len(marker):])

    before = check_conservation(data)
    print('修复前 不守恒赛季: %d' % len(before))
    for x in before:
        print('   ❌ %s %s  sumGf=%d sumGa=%d diff=%d' % x)

    fixed = normalize(data)
    print('\n统一视角，修复了 %d 个队:' % len(fixed))
    for x in fixed:
        print('   %s %s  %s  (翻转 %d 场)' % x)

    after = check_conservation(data)
    print('\n修复后 不守恒赛季: %d' % len(after))
    for x in after:
        print('   ❌ %s %s  sumGf=%d sumGa=%d diff=%d' % x)

    if after:
        print('\n仍未守恒，放弃写回。', file=sys.stderr)
        return 1

    # 备份
    bak = path + '.bak.perspective'
    with open(bak, 'w', encoding='utf-8') as f:
        f.write(raw)
    print('\n已备份原文件 -> %s' % bak)

    with open(path, 'w', encoding='utf-8') as f:
        f.write('window.DATA = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';')
    print('已写入 %s' % path)
    return 0


if __name__ == '__main__':
    sys.exit(main())
