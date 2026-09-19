# 自动更新工具

每周一、周四 09:03 由 launchd 调用 `refresh.sh`，把 2026-27 赛季的最新赛果同步到站点并推送 GitHub。

## 手动跑一次

```bash
/bin/bash /Users/santu/soccerdata/football-data-site/tools/refresh.sh
```

日志落在 `tools/logs/YYYY-MM-DD_HHMMSS.log`。旧数据文件的本地快照 `tools/backups/` 已按用户要求关闭，线上数据即唯一真相（回滚走 git 历史 / GitHub）。

## 流程

| # | 动作 | 脚本 |
|---|---|---|
| 1 | 抓 football-data.co.uk 的 2026-27 CSV（10 个联赛） | `build_2026_27.py` |
| 2 | 轮次对齐：优先 openfootball 官方 Matchday，其次 fixturedownload，都无则按日期窗口推导 | 同上 |
| 3 | 五大联赛平局分析 → `report_all.json` → `football_big5_draws.html` | `analyze_all.py` / `build_big5.py` |
| 4 | 次级联赛平局分析 → `report_champ.json` → `football_champ_draws.html` | `analyze_champ.py` / `build_champ.py` |
| 5 | 进球数页 2026-27 进球分布增量打补丁 | `update_seq23_2627.py` |
| 6 | 抽出三份 HTML 的数据块 → 校验 → 直传拆分器写成 `assets/js/data/<group>/<league>/<season>.js`（无单体中间文件） | `sync_site.py` |
| 7 | `git commit` + `git push origin HEAD` | `refresh.sh` |

数据源脚本位于 `~/WorkBuddy AI/2026-09-02-02-18-19/`，本目录只放编排与同步脚本。

## 安全措施

`sync_site.py` 在写入前做体检，任一条不通过就整批中止、一个字节都不写：

1. 新旧顶层键集合必须一致
2. 联赛数量、赛季键集合必须一致
3. **历史赛季（非 2026-27）的场次必须一字不变**
4. **2026-27 的场次只能增加、不能减少**

另外，站点的外壳（`site.js` / `site.css` / 各页 JS 与 CSS / 字体）完全不在更新范围内。

## 已知坑（已在脚本里修掉）

- `www.football-data.co.uk` 会整站返回 503，去掉 `www.` 的域名正常 —— `build_2026_27.py` 已改为「非 www → www」多镜像重试，并对返回内容做 HTML 兜底校验（503 返回的是 489 字节 HTML 错误页）。
- `build_2026_27.py` 的 `fetch()` 原本命中 `/tmp` 缓存就不再联网 —— 定时任务会永远拿到第一次的旧赛果，已改为强制重新下载。

## 定时任务

`~/Library/LaunchAgents/com.santu.football-data-refresh.plist`

```bash
launchctl list | grep football-data        # 查看是否已加载
launchctl kickstart -k gui/$UID/com.santu.football-data-refresh   # 立即跑一次
launchctl bootout gui/$UID/com.santu.football-data-refresh        # 卸载
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.santu.football-data-refresh.plist  # 重新加载
```

> 注意：单独的 `refresh` 任务在 Mac 合盖休眠到 09:03 时**不会**补跑；但本机另有一支 `com.santu.football-data-catchup` 任务（每 5 分钟 + 开机即跑，随系统唤醒恢复），会在唤醒后自动检测错过的周一/周四窗口并补跑 `refresh.sh`，**无需手动 kickstart**。

```bash
launchctl list | grep football-data   # 应同时看到 refresh 与 catchup 两个任务
```
