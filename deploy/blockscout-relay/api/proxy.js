const UPSTREAM_ORIGIN = "https://api.blockscout.com";
const PUBLIC_CONFIG_PATH = "/api/json/config";
const FORWARDED_RESPONSE_HEADERS = [
  "content-type",
  "retry-after",
  "x-ratelimit-limit",
  "x-ratelimit-remaining",
  "x-ratelimit-reset",
  "x-credits-used",
  "x-credits-remaining",
];

function requestedPath(req) {
  const value = req.query.path;
  if (Array.isArray(value)) {
    return value.join("/");
  }
  return typeof value === "string" ? value : "";
}

function buildUpstreamUrl(req) {
  const path = `/${requestedPath(req).replace(/^\/+/, "")}`;
  const url = new URL(path, UPSTREAM_ORIGIN);
  for (const [name, value] of Object.entries(req.query)) {
    if (name === "path") continue;
    for (const item of Array.isArray(value) ? value : [value]) {
      if (item !== undefined) url.searchParams.append(name, String(item));
    }
  }
  return url;
}

function validAuthorization(value) {
  return typeof value === "string" && /^Bearer proapi_[A-Za-z0-9_-]{20,}$/.test(value);
}

export default async function handler(req, res) {
  const upstreamUrl = buildUpstreamUrl(req);
  const isPublicConfig = upstreamUrl.pathname === PUBLIC_CONFIG_PATH;
  const authorization = req.headers.authorization;

  if (!isPublicConfig && !validAuthorization(authorization)) {
    return res.status(401).json({ error: "A valid Blockscout Pro bearer key is required." });
  }

  if (!["GET", "POST"].includes(req.method)) {
    res.setHeader("allow", "GET, POST");
    return res.status(405).json({ error: "Method not allowed." });
  }

  const headers = {
    accept: "application/json",
    "user-agent": "trust-receipt-blockscout-relay/1.0",
  };
  if (authorization) headers.authorization = authorization;
  if (req.headers["content-type"]) headers["content-type"] = req.headers["content-type"];

  try {
    const upstream = await fetch(upstreamUrl, {
      method: req.method,
      headers,
      body: req.method === "POST" ? JSON.stringify(req.body ?? {}) : undefined,
      redirect: "manual",
    });
    for (const name of FORWARDED_RESPONSE_HEADERS) {
      const value = upstream.headers.get(name);
      if (value) res.setHeader(name, value);
    }
    const payload = Buffer.from(await upstream.arrayBuffer());
    return res.status(upstream.status).send(payload);
  } catch {
    return res.status(502).json({ error: "Blockscout upstream request failed." });
  }
}
