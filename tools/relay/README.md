# titan007 中转（relay）

## 为什么需要

GitHub Actions runner 的出口 IP 属于 **Azure 数据中心**，而 titan007
（`zq.titan007.com` → CNAME `info-cn.nowodds.com` → **`61.143.225.63`**，中国广东电信）
对**云厂商 IP 段**做了**静默丢包（DROP）**：

| 视角 | 结果 |
|---|---|
| GitHub runner | `curl` **HTTP 000**，每次跑满 35 秒超时 |
| 本机直连（不走代理） | **HTTP 200**，建连 **16ms** |
| check-host 境外节点（德/港/日/俄/**美**） | **全部 200**（0.67~3.03s） |
| `r.jina.ai`（非 Azure 云出口） | **连得上**（422 仅因它拒绝 `application/javascript`） |

**铁证**：`refresh.sh` 有 20 次 titan007 抓取（`build_2026_27.py` 10 + `build_fixtures.py` 10），
每次 `curl --max-time 35`（`--max-time` 是进程总上限、重试也含在内）→ 20 × 35 = **700s**，
加其余步骤 ≈ **848s**，与「运行每日更新」步骤实测 **14m08s** 逐秒吻合。
⇒ 若是快速拒绝（403/重置），20 次只需几秒；**848s 只能由「每次都跑满超时」解释**。

⚠️ 这不是地域封锁（美国节点也能通），而是**封云厂商 IP 段**——反爬的常规做法。

## 配置方式（GitHub Secret）

1. 仓库 Settings → Secrets and variables → Actions → **New repository secret**
2. Name：`FD_TITAN_PROXY`
3. Value：中转模板，例如 `https://<你的域名>/?url={url}`

- `{url}` → 替换成**百分号编码**后的原始 URL；`{raw}` → 未编码的原 URL
- 多个中转用**逗号**分隔，直连失败后**按顺序**依次尝试
- **未配置 = 只试直连**（与改造前逐字节一致）⇒ 可随时开启/关闭

## 方案 A：Cloudflare Worker（免费，建议先试）

⚠️ **可达性未验证**——CF 出口同为云厂商 IP，理论上可能也被丢包。部署后**必须先验证**。

1. 打开 <https://dash.cloudflare.com/> → Workers & Pages → Create → Worker
2. 把 `cloudflare-worker.js` 整体粘贴进去 → Deploy
3. 得到 `https://<name>.<account>.workers.dev`
4. Secret 值：`https://<name>.<account>.workers.dev/?url={url}`

## 方案 B：腾讯云函数 SCF（境内出口，可达性最高）

境内出口与 titan007 同网（本机直连 16ms 已证），**确定性最高**。

1. 腾讯云 → 云函数 SCF → 新建函数（**Python 3.9**，事件函数）
2. 粘贴 `tencent-scf.py`
3. 触发器 → **函数 URL**（公开访问，无需备案域名）
4. Secret 值：`https://<函数URL>?url={url}`

## 验证（部署后必做）

在**本地终端**执行一次（`<PROXY>` 换成实际前缀）：

```bash
curl -sS -o /tmp/_relay.js -w "http=%{http_code} size=%{size_download}\n" \
  "<PROXY>?url=https%3A%2F%2Fzq.titan007.com%2FjsData%2FmatchResult%2F2026-2027%2Fs36.js"
head -c 120 /tmp/_relay.js
```

期望：`http=200`，内容以 `var jh=` 或 `var arrTeam=` 开头。

⚠️ **不要连续重复请求**：titan007 对同一 URL 的密集请求会临时限流，表现为
`HTTP/2 PROTOCOL_ERROR` 或 `Empty reply from server`（**快速失败**，不是超时）。
本机在 2026-10-03 诊断期间就因密集请求触发过一次，属临时现象。

## 相关

- 失败诊断能力：`generator/build_2026_27.py` 的 `titan_curl` 会输出
  `HTTP <码>` / `%{errormsg}`（如 `Connection timed out after 35001 milliseconds`）+ `IP`
- 兜底数据源：ESPN 逐日枚举（已实测 100% 覆盖 titan007 的 590 场），
  即使中转也失效，站点仍能出数据
