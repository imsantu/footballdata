#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pre-commit 钩子：每次提交都把「本页更新时间」刷新为当前时间。

设计：
  * 只改 assets/js/meta.js 里的 generated 字段；顺手删掉残留的 srcUpdated 键
    （站点已不再展示「数据源更新时间」，避免旧数据被保留）。
  * 所有页面页脚统一读 window.SITE_META（见 goals-app.js / draws-*.js / more.html），
    因此「本页更新」会随任意一次提交（含纯代码修复）前进，几页时间永远一致。
  * 解析用 json.JSONDecoder.raw_decode，避免被 meta 字符串里的特殊字符干扰。
  * 任何异常都吞掉并 exit 0 —— 钩子绝不允许阻断提交。
"""
import json
import os
import sys
import time


def main():
    try:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        meta = os.path.join(root, "assets/js/meta.js")
        if not os.path.exists(meta):
            return 0
        text = open(meta, encoding="utf-8").read()
        marker = "window.SITE_META = "
        i = text.find(marker)
        if i < 0:
            return 0
        i += len(marker)
        obj, _ = json.JSONDecoder().raw_decode(text[i:])
        # 顺手清掉残留的 srcUpdated 键（站点已不再展示数据源更新时间）
        obj.pop("srcUpdated", None)
        # generated = 最近一次部署/提交时间
        obj["generated"] = time.strftime("%Y-%m-%d %H:%M")
        new = marker + json.dumps(obj, ensure_ascii=False) + ";\n"
        open(meta, "w", encoding="utf-8").write(new)
        print("[bump_meta] 本页更新时间 ->", obj["generated"])
    except Exception as e:
        sys.stderr.write("bump_meta 跳过：%s\n" % e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
