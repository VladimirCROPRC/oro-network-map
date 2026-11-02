const ADMIN_EMAILS = new Set([
  "felix.tibrea@proconect.ro",
  "dorin.vlaic@proconect.ro",
  "serban.mincic@proconect.ro",
  "vladimir.carlan@proconect.ro",
]);

const json = (data, status = 200) =>
  Response.json(data, {
    status,
    headers: { "Cache-Control": "no-store" },
  });

async function identityFromAccess(ctx) {
  const identity = await ctx.access?.getIdentity();
  const email = String(identity?.email || "").trim().toLowerCase();
  return email.endsWith("@proconect.ro") ? email : "";
}

function clean(value, maxLength = 200) {
  return String(value ?? "").trim().slice(0, maxLength);
}

async function handleApi(request, env, ctx, url) {
  const email = await identityFromAccess(ctx);
  if (!email) return json({ error: "Autentificare necesară" }, 401);
  const isAdmin = ADMIN_EMAILS.has(email);

  if (url.pathname === "/api/session" && request.method === "GET") {
    return json({ email, isAdmin });
  }

  if (url.pathname === "/api/activity" && request.method === "POST") {
    let input;
    try {
      input = await request.json();
    } catch {
      return json({ error: "Date invalide" }, 400);
    }
    const elementId = clean(input.elementId);
    const elementName = clean(input.elementName);
    const layerId = clean(input.layerId, 120);
    const layerName = clean(input.layerName, 120);
    if (!elementId && !elementName) return json({ error: "Element lipsă" }, 400);
    await env.DB.prepare(
      `INSERT INTO activity_logs
       (email, event_type, layer_id, layer_name, element_id, element_name)
       VALUES (?, 'view', ?, ?, ?, ?)`,
    )
      .bind(email, layerId, layerName, elementId, elementName)
      .run();
    return json({ ok: true }, 201);
  }

  if (url.pathname === "/api/activity" && request.method === "GET") {
    if (!isAdmin) return json({ error: "Acces administrator necesar" }, 403);
    const days = Math.min(90, Math.max(1, Number(url.searchParams.get("days")) || 7));
    const limit = Math.min(2000, Math.max(1, Number(url.searchParams.get("limit")) || 500));
    const emailFilter = clean(url.searchParams.get("email"), 254).toLowerCase();
    const statement = emailFilter
      ? env.DB.prepare(
          `SELECT id, viewed_at, email, layer_id, layer_name, element_id, element_name
           FROM activity_logs
           WHERE viewed_at >= datetime('now', ?) AND email = ?
           ORDER BY viewed_at DESC LIMIT ?`,
        ).bind(`-${days} days`, emailFilter, limit)
      : env.DB.prepare(
          `SELECT id, viewed_at, email, layer_id, layer_name, element_id, element_name
           FROM activity_logs
           WHERE viewed_at >= datetime('now', ?)
           ORDER BY viewed_at DESC LIMIT ?`,
        ).bind(`-${days} days`, limit);
    const result = await statement.all();
    return json({ days, rows: result.results || [] });
  }

  return json({ error: "Endpoint inexistent" }, 404);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname.startsWith("/api/")) {
      try {
        return await handleApi(request, env, ctx, url);
      } catch (error) {
        console.error("Activity API failed", error);
        return json({ error: "Serviciul de logare nu este disponibil" }, 500);
      }
    }
    return fetch(request);
  },

  async scheduled(_controller, env) {
    await env.DB.prepare(
      "DELETE FROM activity_logs WHERE viewed_at < datetime('now', '-90 days')",
    ).run();
  },
};
