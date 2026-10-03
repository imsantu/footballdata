// titan007 中转 —— Cloudflare Worker 版
//
// 部署：dash.cloudflare.com → Workers & Pages → Create → Worker → 粘贴本文件 → Deploy
// 用法：https://<你的worker>.workers.dev/?url=<百分号编码的原始URL>
// 配到 GitHub Secret `FD_TITAN_PROXY`：https://<你的worker>.workers.dev/?url={url}
//
// ⚠️ CF 出口同为云厂商 IP，**可达性未经实测**（titan007 已确认对 Azure IP 段静默丢包）。
//    部署后务必先验证：curl 一次拿到的应是 200 + `var jh=` 开头的内容。
// ⚠️ 只放行 titan007 域名，避免被当成公开开放代理而遭滥用/限流。

const UA =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36";

export default {
  async fetch(request) {
    const target = new URL(request.url).searchParams.get("url");
    if (!target) {
      return new Response("missing ?url=", { status: 400 });
    }
    let host = "";
    try {
      host = new URL(target).hostname;
    } catch (e) {
      return new Response("bad url", { status: 400 });
    }
    if (!/(^|\.)titan007\.com$/i.test(host)) {
      return new Response("host not allowed", { status: 403 });
    }

    const upstream = await fetch(target, {
      headers: {
        "User-Agent": UA,
        Referer: "https://zq.titan007.com/",
        "Accept-Encoding": "identity", // 不要求压缩，避免二次解码
      },
    });

    return new Response(upstream.body, {
      status: upstream.status,
      headers: {
        "content-type":
          upstream.headers.get("content-type") || "text/plain; charset=utf-8",
        "cache-control": "no-store",
      },
    });
  },
};
