import { getAssetFromKV } from "@cloudflare/kv-asset-handler";
import manifestJSON from "__STATIC_CONTENT_MANIFEST";

const assetManifest = JSON.parse(manifestJSON);
const PROJECT_NAME = "SaaS Revenue Retention";

const CORS = {
  "Content-Type": "application/json",
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization"
};

const TOOLS = [
  { name: "get_kpis", description: "Get all current KPI values for " + PROJECT_NAME, inputSchema: { type: "object", properties: {}, required: [] } },
  { name: "get_insights", description: "Get business insights ranked by severity (HIGH/MEDIUM/LOW)", inputSchema: { type: "object", properties: { severity: { type: "string", enum: ["HIGH", "MEDIUM", "LOW", "ALL"], default: "ALL" } }, required: [] } },
  { name: "get_anomalies", description: "Get detected anomalies and unusual business patterns", inputSchema: { type: "object", properties: {}, required: [] } },
  { name: "get_recommendations", description: "Get prioritized action recommendations (save list)", inputSchema: { type: "object", properties: {}, required: [] } },
  { name: "get_forecast", description: "Get the latest forecast data and predictions", inputSchema: { type: "object", properties: {}, required: [] } },
  { name: "get_summary", description: "Get pipeline run summary and data freshness info", inputSchema: { type: "object", properties: {}, required: [] } }
];

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const method = request.method;

    if (method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }
    if (method === "POST" && url.pathname === "/api") {
      return handleForecast(request, env, ctx, url);
    }
    if (url.pathname === "/mcp" || url.pathname.startsWith("/mcp/")) {
      return handleMCP(request, env, ctx, url);
    }
    return serveAsset(request, env, ctx);
  }
};

async function serveAsset(request, env, ctx) {
  const reqUrl = new URL(request.url);
  try {
    return await getAssetFromKV(
      { request, waitUntil: ctx.waitUntil.bind(ctx) },
      {
        ASSET_NAMESPACE: env.__STATIC_CONTENT,
        ASSET_MANIFEST: assetManifest,
        mapRequestToAsset: (req) => {
          const u = new URL(req.url);
          if (!u.pathname.includes(".")) {
            u.pathname = "/index.html";
            return new Request(u.toString(), req);
          }
          return req;
        }
      }
    );
  } catch (err) {
    if (reqUrl.pathname.includes(".")) {
      return new Response("Not found", { status: 404 });
    }
    try {
      const fallback = new Request(new URL("/index.html", request.url).toString(), request);
      const res = await getAssetFromKV(
        { request: fallback, waitUntil: ctx.waitUntil.bind(ctx) },
        { ASSET_NAMESPACE: env.__STATIC_CONTENT, ASSET_MANIFEST: assetManifest }
      );
      return new Response(res.body, { status: 200, headers: res.headers });
    } catch (e) {
      return new Response("Not found", { status: 404 });
    }
  }
}

async function fetchJSON(path, request, env, ctx, url) {
  try {
    const res = await serveAsset(new Request(url.origin + path, { method: "GET", headers: request.headers }), env, ctx);
    if (!res.ok) return null;
    const type = res.headers.get("content-type") || "";
    if (type.indexOf("json") === -1) return null;
    return await res.json();
  } catch (e) {
    return null;
  }
}

async function handleForecast(request, env, ctx, url) {
  try {
    const body = await request.json().catch(() => ({}));
    const inputVal = Number(body.input);
    if (body.input === undefined || body.input === null || body.input === "" || isNaN(inputVal)) {
      return json({ error: "Invalid input value. Must be a number." }, 400);
    }

    let lookup = null;
    const raw = env.FORECAST_LOOKUP ?? null;
    if (raw) {
      try { lookup = JSON.parse(raw); } catch (e) {
        return json({ error: "FORECAST_LOOKUP secret is not valid JSON." }, 500);
      }
    } else {
      // Fallback: build the lookup from the deployed forecast data file.
      const fc = await fetchJSON("/data/monitor/forecast.json", request, env, ctx, url);
      if (fc && Array.isArray(fc.monthly)) {
        lookup = {};
        fc.monthly.forEach((m) => {
          lookup[m.month_index] = { value: m.mrr_base, range_low: m.mrr_worst, range_high: m.mrr_best };
        });
      }
    }
    if (!lookup) {
      return json({ error: "Forecast data not configured. Run: wrangler secret put FORECAST_LOOKUP (or redeploy with output/monitor/forecast.json)." }, 503);
    }
    const keys = Object.keys(lookup).map(Number).filter((n) => !isNaN(n)).sort((a, b) => a - b);
    if (keys.length === 0) {
      return json({ error: "Forecast lookup table is empty." }, 503);
    }
    const nearest = keys.reduce((a, b) => (Math.abs(b - inputVal) < Math.abs(a - inputVal) ? b : a));
    const result = lookup[nearest];
    const value = result !== null && typeof result === "object" ? (result.value ?? null) : result;
    return json({
      prediction: value,
      confidence: result && typeof result === "object" ? (result.confidence ?? null) : null,
      range_low: result && typeof result === "object" ? (result.range_low ?? null) : null,
      range_high: result && typeof result === "object" ? (result.range_high ?? null) : null,
      input_received: inputVal,
      nearest_key: nearest
    }, 200);
  } catch (e) {
    return json({ error: "Forecast error: " + e.message }, 500);
  }
}

async function runTool(tool, params, request, env, ctx, url) {
  const get = (path) => fetchJSON(path, request, env, ctx, url);
  switch (tool) {
    case "get_kpis": {
      const data = await get("/data/understand/kpis.json");
      return data ? { status: 200, payload: { tool, result: data } } : { status: 503, payload: { error: "KPI data not available. Run pipeline first." } };
    }
    case "get_insights": {
      const data = await get("/data/decide/insights.json");
      if (!data) return { status: 503, payload: { error: "Insights not available. Run pipeline first." } };
      const severity = String((params && params.severity) || "ALL").toUpperCase();
      const filtered = severity === "ALL" || !Array.isArray(data) ? data : data.filter((i) => String(i.severity).toUpperCase() === severity);
      return { status: 200, payload: { tool, result: filtered, filter: severity } };
    }
    case "get_anomalies": {
      const data = await get("/data/understand/anomalies.json");
      return data ? { status: 200, payload: { tool, result: data } } : { status: 503, payload: { error: "Anomaly data not available. Run pipeline first." } };
    }
    case "get_recommendations": {
      const data = await get("/data/decide/recommendations.json");
      return data ? { status: 200, payload: { tool, result: data } } : { status: 503, payload: { error: "Recommendations not available. Run pipeline first." } };
    }
    case "get_forecast": {
      const data = await get("/data/monitor/forecast.json");
      return data ? { status: 200, payload: { tool, result: data } } : { status: 503, payload: { error: "Forecast data not available. Run pipeline first." } };
    }
    case "get_summary": {
      const runLog = await get("/data/meta/run_log.json");
      const summary = await get("/data/meta/summary.json");
      return { status: 200, payload: { tool, result: { run_log: runLog, summary } } };
    }
    default:
      return { status: 400, payload: { error: 'Unknown tool: "' + tool + '". Call GET /mcp for available tools.' } };
  }
}

// Read-only MCP endpoint. GET /mcp = manifest. POST /mcp = {tool, params} or JSON-RPC 2.0 (initialize, tools/list, tools/call).
async function handleMCP(request, env, ctx, url) {
  const method = request.method;
  if (method === "GET" && url.pathname === "/mcp") {
    return json({
      name: PROJECT_NAME + " Analytics MCP",
      description: "Read-only business analytics tools for " + PROJECT_NAME,
      version: "1.0.0",
      tools: TOOLS
    }, 200);
  }
  if (method === "POST" && url.pathname === "/mcp") {
    try {
      const body = await request.json().catch(() => ({}));

      if (body && body.jsonrpc === "2.0") {
        const id = body.id ?? null;
        const rpc = (result) => json({ jsonrpc: "2.0", id, result }, 200);
        const rpcErr = (code, message) => json({ jsonrpc: "2.0", id, error: { code, message } }, 200);
        if (body.method === "initialize") {
          return rpc({ protocolVersion: "2024-11-05", capabilities: { tools: {} }, serverInfo: { name: PROJECT_NAME + " Analytics MCP", version: "1.0.0" } });
        }
        if (typeof body.method === "string" && body.method.indexOf("notifications/") === 0) {
          return new Response(null, { status: 202, headers: CORS });
        }
        if (body.method === "tools/list") return rpc({ tools: TOOLS });
        if (body.method === "ping") return rpc({});
        if (body.method === "tools/call") {
          const p = body.params || {};
          const out = await runTool(p.name, p.arguments || {}, request, env, ctx, url);
          return rpc({ content: [{ type: "text", text: JSON.stringify(out.payload) }], isError: out.status >= 400 });
        }
        return rpcErr(-32601, "Method not found: " + body.method);
      }

      const tool = body.tool ?? body.name ?? "";
      const params = body.params ?? body.arguments ?? {};
      const out = await runTool(tool, params, request, env, ctx, url);
      return json(out.payload, out.status);
    } catch (e) {
      return json({ error: "MCP error: " + e.message }, 500);
    }
  }
  return json({ error: "MCP: use GET /mcp for manifest, POST /mcp to call tools." }, 405);
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), { status, headers: CORS });
}
