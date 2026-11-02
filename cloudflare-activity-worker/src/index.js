const OWNER_EMAIL = "felix.tibrea@proconect.ro";

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
  const admin = await env.DB.prepare(
    "SELECT email, can_manage_admins FROM activity_admins WHERE email = ?",
  ).bind(email).first();
  const isAdmin = Boolean(admin);
  const canManageAdmins = Boolean(admin?.can_manage_admins);

  if (url.pathname === "/api/session" && request.method === "GET") {
    return json({ email, isAdmin, canManageAdmins });
  }

  if (url.pathname === "/api/admins" && request.method === "GET") {
    if (!canManageAdmins) return json({ error: "Acces administrator principal necesar" }, 403);
    const result = await env.DB.prepare(
      "SELECT email, can_manage_admins, created_at, created_by FROM activity_admins ORDER BY email",
    ).all();
    return json({ owner: OWNER_EMAIL, rows: result.results || [] });
  }

  if (url.pathname === "/api/admins" && request.method === "POST") {
    if (!canManageAdmins) return json({ error: "Acces administrator principal necesar" }, 403);
    let input;
    try {
      input = await request.json();
    } catch {
      return json({ error: "Date invalide" }, 400);
    }
    const newEmail = clean(input.email, 254).toLowerCase();
    if (!/^[^\s@]+@proconect\.ro$/.test(newEmail)) {
      return json({ error: "Este permisă numai o adresă @proconect.ro" }, 400);
    }
    await env.DB.prepare(
      "INSERT OR IGNORE INTO activity_admins (email, can_manage_admins, created_by) VALUES (?, 0, ?)",
    ).bind(newEmail, email).run();
    return json({ ok: true }, 201);
  }

  if (url.pathname === "/api/admins" && request.method === "DELETE") {
    if (!canManageAdmins) return json({ error: "Acces administrator principal necesar" }, 403);
    const target = clean(url.searchParams.get("email"), 254).toLowerCase();
    if (!target) return json({ error: "Adresa lipsește" }, 400);
    if (target === OWNER_EMAIL) return json({ error: "Administratorul principal nu poate fi șters" }, 400);
    await env.DB.prepare("DELETE FROM activity_admins WHERE email = ?").bind(target).run();
    return json({ ok: true });
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
