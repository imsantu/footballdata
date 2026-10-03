# titan007 中转 —— 腾讯云函数 SCF 版（境内出口，可达性最高）
#
# 部署：腾讯云 → 云函数 SCF → 新建函数（Python 3.9，事件函数）→ 粘贴本文件
#       触发器 → 函数 URL（公开访问，无需备案）
# 用法：https://<函数URL>?url=<百分号编码的原始URL>
# 配到 GitHub Secret `FD_TITAN_PROXY`：https://<函数URL>?url={url}
#
# 为什么境内出口最稳：titan007（zq.titan007.com → 61.143.225.63，中国广东电信）
# 已确认对 Azure 云 IP 段静默丢包；而境内出口与本机同网（本机直连建连仅 16ms）。

import urllib.parse
import urllib.request

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)


def main_handler(event, context):
    qs = event.get("queryString") or {}
    if isinstance(qs, str):
        qs = urllib.parse.parse_qs(qs)
    val = qs.get("url")
    target = (val[0] if isinstance(val, list) else val) or ""
    if not target:
        return {"statusCode": 400, "body": "missing ?url="}

    host = urllib.parse.urlparse(target).hostname or ""
    # 只放行 titan007，避免被当成公开开放代理
    if not host.endswith("titan007.com"):
        return {"statusCode": 403, "body": "host not allowed"}

    req = urllib.request.Request(
        target,
        headers={
            "User-Agent": UA,
            "Referer": "https://zq.titan007.com/",
            "Accept-Encoding": "identity",  # 让上游不压缩，避免二次解码问题
        },
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read()
        ctype = r.headers.get("content-type", "text/plain; charset=utf-8")
        status = r.status

    return {
        "statusCode": status,
        "headers": {"content-type": ctype},
        "isBase64Encoded": False,
        "body": body.decode("utf-8", "replace"),
    }
