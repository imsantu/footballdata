#!/bin/bash
# 足球数据站 · 自动更新
#   1. 从 ESPN 隐藏 API（site.api.espn.com）抓取 2026-27 最新赛果（免费、实时，
#      摆脱 openfootball / football-data.co.uk 结果录入滞后；build_2026_27.py 现以 ESPN 为主源）
#   2. 重算三份报告的数据（平局·五大 / 平局·次级 / 进球数）
#   3. 把数据块同步进静态站点（带备份 + 体检，历史赛季绝不改动）
#   4. git 提交并推送到 GitHub
# 由 GitHub Actions 每天 06:00（cron 定时）或手动 Run workflow 触发（脚本内含 0~3599s
# 随机错峰，仅定时任务生效，避免整点集中请求数据源）。

set -uo pipefail

# 路径改为「环境变量优先、本地路径兜底」：云端（GitHub Actions）通过 FD_* 注入仓库内
# 的 generator/ 目录；本机仍走 WorkBuddy 会话目录默认路径，行为与改造前完全一致。
SITE="${FD_SITE_DIR:-/Users/santu/footballdata/football-data-site}"
WS="${FD_GENERATOR_DIR:-/Users/santu/WorkBuddy AI/2026-09-02-02-18-19}"
# GOALS_WS = 进球数报告（football_big5_goals.html / football_mobile.html）所在目录。
#   本机：报告与脚本**不在同一目录**（脚本 09-02，报告 08-24）——历史事故：默认写成 $WS，
#         sync_site.py 找不到源报告 → 「[FAIL] 进球数统计: 源报告不存在」→ 整条流水线中止、
#         站点当天不更新（2026-09-22 两次）。
#   云端/同仓：FD_GENERATOR_DIR 已给出，报告与脚本同在 generator/，此时必须跟随 $WS，
#         否则会去找一个云端不存在的 macOS 路径。
#   判定顺序：FD_GOALS_WS 显式给出 → 用它；给了 FD_GENERATOR_DIR → 跟随 $WS；都没有 → 本机报告目录。
if [ -n "${FD_GOALS_WS:-}" ]; then
    GOALS_WS="$FD_GOALS_WS"
elif [ -n "${FD_GENERATOR_DIR:-}" ]; then
    GOALS_WS="$WS"
else
    GOALS_WS="/Users/santu/WorkBuddy AI/2026-08-24-11-07-48"
fi
AUTO="$SITE/tools"
PY="${FD_PY:-/usr/bin/python3}"
# 赛季唯一来源：generator/season.py（换季只改那一个文件）
SEASON="$("$PY" "$WS/season.py" 2>/dev/null || true)"
[ -n "$SEASON" ] || SEASON="(未知赛季)"

# 必须 export：sync_site.py 是独立进程，靠 FD_* 环境变量解析同一套路径
# （refresh.sh 自己算出的 WS/GOALS_WS 只用于拼本脚本内的命令，不会自动传给子进程）。
export FD_SITE_DIR="$SITE"
export FD_GENERATOR_DIR="$WS"
export FD_GOALS_WS="$GOALS_WS"
export FD_PY="$PY"

# ── 防重入 + 随机错峰 ──
# 运行锁：避免 catchup.sh 在下方随机等待期间误判「窗口错过」而重复拉起本任务
REFRESH_LOCK="$AUTO/.refresh.lock"
if [ -e "$REFRESH_LOCK" ]; then
    _pid=$(cat "$REFRESH_LOCK" 2>/dev/null)
    if [ -n "$_pid" ] && kill -0 "$_pid" 2>/dev/null; then
        echo "[SKIP] 已有 refresh 进程在运行 (pid $_pid)，退出"
        exit 0
    fi
    rm -f "$REFRESH_LOCK"
fi
echo $$ > "$REFRESH_LOCK"
trap 'rm -f "$REFRESH_LOCK"' EXIT
# 随机错峰：仅「自动定时（schedule / cron）」触发时才等待 0~3599 秒，
# 把实际抓取/同步错开到 06:00~07:00 之间，避免整点集中打数据源。
# 手动触发（workflow_dispatch）或本机直接运行 → 立即执行，不等待。
if [ "${GITHUB_EVENT_NAME:-}" = "schedule" ]; then
  echo "════════ 随机错峰等待（0~3599s，仅定时任务）════════"
  sleep $(( RANDOM % 3600 ))
else
  echo "════════ 跳过随机错峰等待（非定时触发，立即运行）════════"
fi

# 0) 路径护栏：站点必须位于 ~/footballdata，绝不允许落在桌面。
#    历史事故：站点曾放在 ~/Desktop/soccerdata，迁移后 launchd 仍指向旧路径，
#    导致桌面上被反复重建出 soccerdata 目录。这里主动兜底。
DESKTOP_DIR="${HOME:-/Users/santu}/Desktop"
case "$SITE" in
    "$DESKTOP_DIR"/*|"$DESKTOP_DIR")
        echo "[FAIL] 站点路径位于桌面（$SITE），已中止，避免在桌面产生任何内容"
        exit 1 ;;
esac
if [ -e "$DESKTOP_DIR/soccerdata" ]; then
    echo "[WARN] 检测到残留目录 $DESKTOP_DIR/soccerdata，疑似旧路径遗留，请确认后删除"
fi

mkdir -p "$AUTO/logs"
LOG="$AUTO/logs/$(date '+%Y-%m-%d_%H%M%S').log"
exec > >(tee -a "$LOG") 2>&1

notify() {  # notify "标题" "正文" ["error|notice"]（云端无 osascript，降级为 GHA 注解 + 日志）
    local lvl="${3:-notice}"
    echo "::${lvl} title=$1::$2" >&2 || true
    command -v osascript >/dev/null 2>&1 && osascript -e "display notification \"$2\" with title \"$1\"" >/dev/null 2>&1 || true
}

step() {
    local name="$1"; shift
    echo
    echo "──────── $name ────────"
    "$@"
    local rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "[FAIL] $name（退出码 $rc）"
        echo "=== 本次更新中止，站点未做任何改动 ==="
        echo "日志：$LOG"
        notify "足球数据更新失败" "$name 失败，详见日志" "error"
        exit 1
    fi
    echo "[OK] $name"
}

echo "════════ 足球数据自动更新 $(date '+%F %T') ════════"

# 0) 清掉 football-data 的 /tmp 缓存。
#    build_2026_27.py 的 fetch() 已经自清，这里再兜一层底，防止将来脚本被回滚。
rm -f /tmp/fd_*_2627.csv

# 1) 抓取并重建 2026-27（五大联赛 + 五大次级联赛）
step "抓取 $SEASON 最新赛果" "$PY" "$WS/build_2026_27.py"

# 1b) 站点已不再展示「数据源更新时间」，mark_fetch_stamp.py 步骤已移除（其写入的
#     srcUpdated 现在无人读取，保留 mark_fetch_stamp.py 脚本本身以备将来复用）。

# 1c) 2026-27 赛程表（fixtures）：各联赛全季赛程，含未开赛场次与开球时间。
#     与步骤 1 完全同源 —— titan007 那份 jsData/matchResult 文件本来就是全季赛程
#     （已完赛 + 未开赛），build_2026_27.py 只取已完赛，这里换个过滤条件把未开赛
#     也留下。因此**直接复用步骤 1 刚抓的 /tmp 缓存**，几乎零额外网络开销。
#     全量覆盖天然处理赛程调整 / 补赛；单联赛失败时保留旧数据 + 告警，不拖垮主线。
step "抓取 $SEASON 赛程表" "$PY" "$SITE/generator/build_fixtures.py"

# 2) 平局统计 · 五大联赛
step "分析：平局·五大联赛"  "$PY" "$WS/analyze_all.py"
step "出报告：平局·五大联赛" "$PY" "$WS/build_big5.py"

# 3) 平局统计 · 次级联赛
step "分析：平局·次级联赛"  "$PY" "$WS/analyze_champ.py"
step "出报告：平局·次级联赛" "$PY" "$WS/build_champ.py"

# 4) 进球数统计（该页是增量打补丁式更新 2026-27 的进球分布）
step "更新：进球数统计 $SEASON" "$PY" "$WS/update_seq23_2627.py"

# 5) 同步数据块到站点（第一遍：含抽取+体检+enrich，随后由 sync_site.py 直传内存对象给
#    拆分器写出按季 chunk + 队徽外置 PNG；历史赛季 chunk 已冻结于 git，日常只动 2026-27）
step "同步数据到站点" "$PY" "$AUTO/sync_site.py"

# 5b) 进球数统计 · 次级联赛（新功能：英冠/西乙/德乙/法乙/意乙）
#     由已上线的 draws-champ 分块（同源、覆盖完整）重建种子 HTML，再交 sync_site.py 拆 chunk。
#     ⚠️ 顺序很重要：它读的是**站点里刚落盘的** draws-champ 分块，所以必须排在 5) 之后。
#        若放在 5) 之前，读到的是昨天那版分块，会让「次级联赛进球数」比「次级联赛平局」滞后一天。
#     该脚本随仓库走（$SITE/generator/），不在 $WS；云端模式下 FD_GENERATOR_DIR 就是
#     $SITE/generator，两种模式此路径都成立。
step "更新：进球数·次级联赛" "$PY" "$SITE/generator/build_champ_goals.py"

# 5c) 再同步一遍，把刚重建的 goals-champ 种子拆成 chunk。
#     此时其余三组会判定「无变化」直接跳过（幂等），额外代价很小。
step "同步数据到站点（补：进球数·次级联赛）" "$PY" "$AUTO/sync_site.py"

# 6) 提交并推送（带锁重试；git add 失败视为锁冲突必须重试，绝不再静默 SKIP）
SUMMARY="$(grep -m1 '^SUMMARY|' "$LOG" | sed 's/^SUMMARY|//')"
echo
echo "──────── git 提交与推送 ────────"
cd "$SITE" || { echo "[FAIL] 站点目录不存在"; exit 1; }

if [ ! -d .git ]; then
    echo "[SKIP] 站点尚未 git init，跳过提交"
else
    # 静态资源引用闸门（**非阻断**）：shell / 页面引用的 assets/img/** 必须真实存在且已被 git 跟踪。
    # 为什么需要：渲染快照门禁只覆盖「用例里那几十个容器 + 那几个赛季」，抓不到**队徽映射**
    # 这类全量字符串表的变化。2026-09-26 的真实事故就是这样溜过去的 —— 生成器把源图格式
    # 从 png 换成 jpeg 时**另存了一份新文件**（既有的 png 变孤儿），shell 立刻改指新文件，
    # 而新文件默认未被 git 跟踪 → 提交时极易漏掉、线上 404 / 错图。
    # 不阻断的理由：这是「资源完整性」问题，不该拖垮当天的数据更新；但必须打注解让人看见。
    if ! "$PY" "$AUTO/check_asset_refs.py" > /tmp/fd_asset_refs.log 2>&1; then
        echo "[WARN] 静态资源引用检查未通过："
        sed -n '1,25p' /tmp/fd_asset_refs.log
        notify "资源引用有问题" "$(grep -c '^   ' /tmp/fd_asset_refs.log) 处 assets/img 引用缺失或未被 git 跟踪（详见日志）" warning
    fi

    pushed=0
    for attempt in 1 2 3; do
        # 刷新「本页更新时间」为本机当前时间（与 pre-commit 钩子 bump_meta.py 双重保险；
        # 钩子未被安装时这里兜底，保证任何一次同步提交都会让页脚「本页更新」前进）
        "$PY" "$AUTO/bump_meta.py" || true
        # 外壳文件（site.js / CSS / 页面 HTML / 逻辑 JS）有改动时自动把 sw.js 的 CACHE +1。
        # 漏 +1 是「明明上线了却看不到变化」的经典原因（cache-first，不报错、只是不生效）。
        # 基线 hash 存在 sw.js 自身，所以云端每次全新 checkout 也能正确比对。
        # 幂等：无变化不动版本号；失败不阻断数据同步（下面会把 sw.js 一起提交）。
        "$PY" "$AUTO/bump_sw.py" || true
        # 清掉可能的 stale 写锁（WorkBuddy 后台 git 沙箱会反复重建 .git/index.lock，
        # 曾导致整个推送被 git 静默跳过、数据更新卡在本地不上线）
        rm -f .git/index.lock
        # 仅当生成器位于仓库内（云端/同仓模式：WS 以 SITE 开头）才回写随运行演化的
        # 种子 HTML（football_big5_goals.html / football_mobile.html）；本机模式生成器
        # 在仓库外（WorkBuddy 会话目录），跳过以免 git add 报错。
        case "$WS" in
            "$SITE"*) git add generator/football_big5_goals.html generator/football_mobile.html generator/football_champ_goals.html 2>/dev/null || true ;;
        esac
        if ! git add 'assets/js/meta.js' \
                     'assets/js/data/draws-big5' 'assets/js/data/draws-champ' 'assets/js/data/goals' 'assets/js/data/goals-champ' \
                     'assets/js/data/fixtures' \
                     'assets/img/crests' 'assets/img/leaguelogos' \
                     'sw.js'; then
            echo "[WARN] git add 失败（第 $attempt 次，疑似锁冲突），清锁后重试"
            rm -f .git/index.lock; sleep 3; continue
        fi
        if git diff --cached --quiet; then
            echo "[SKIP] 没有需要提交的改动"
            pushed=1; break
        fi
        MSG="chore(data): 同步 $SEASON 赛果 $(date '+%F') [skip ci]"
        [ -n "$SUMMARY" ] && MSG="$(printf '%s\n\n%s' "$MSG" "$SUMMARY")"
        if git commit -q -F - <<< "$MSG"; then
            echo "[OK] 已提交：$(git log -1 --format='%h %s')"
            if git remote get-url origin >/dev/null 2>&1; then
                if git push origin HEAD 2>&1; then
                    echo "[OK] 已推送到 origin"
                    notify "足球数据已更新" "${SUMMARY:-数据已同步}"
                    pushed=1; break
                else
                    echo "[WARN] git push 失败（第 $attempt 次），清锁后重试"
                    rm -f .git/index.lock; sleep 3
                fi
            else
                echo "[SKIP] 未配置 origin 远程仓库，仅提交到本地"
                pushed=1; break
            fi
        else
            echo "[WARN] git commit 失败（第 $attempt 次），清锁后重试"
            rm -f .git/index.lock; sleep 3
        fi
    done
    if [ "$pushed" -ne 1 ]; then
        echo "[FAIL] git 提交/推送在重试后仍然失败，站点数据已本地更新但未上线"
        echo "日志：$LOG"
        notify "足球数据推送失败" "本地数据已更新但推送失败，需检查 SSH/仓库/锁冲突" "error"
        exit 1
    fi
fi

echo
# 记录本次成功时间戳，供「错过窗口补跑」机制判断
# 只有整条流水线成功到达此处（前面任意步骤失败都会 exit 1）才写，失败则留空让补跑重试
date +%s > "$AUTO/.lastrun"
echo "[OK] 已记录成功时间戳 → $AUTO/.lastrun"

echo "════════ 完成 $(date '+%F %T') ════════"
echo "日志：$LOG"
