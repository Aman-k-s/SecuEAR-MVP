// Shared helpers for all SecuEAR frontend pages. Plain JS, no framework/build step.

const API_BASE = ""; // same-origin: FastAPI serves these pages, so relative paths work.

function renderNav(activePage) {
  const links = [
    { href: "enroll.html", label: "Enroll" },
    { href: "pay.html", label: "Pay (Kiosk)" },
    { href: "recharge.html", label: "Recharge" },
    { href: "audit.html", label: "Audit Log" },
  ];
  const nav = document.createElement("header");
  nav.className = "topbar";
  nav.innerHTML = `
    <div class="brand">Secu<span class="dot">EAR</span></div>
    <nav class="tabs">
      ${links
        .map(
          (l) =>
            `<a href="${l.href}" class="${l.href === activePage ? "active" : ""}">${l.label}</a>`
        )
        .join("")}
    </nav>
  `;
  document.body.prepend(nav);
}

async function postForm(path, formData) {
  const res = await fetch(API_BASE + path, { method: "POST", body: formData });
  const isJson = (res.headers.get("content-type") || "").includes("application/json");
  const body = isJson ? await res.json() : { detail: await res.text() };
  if (!res.ok) {
    const message = body.detail || `Request failed (HTTP ${res.status})`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return body;
}

async function getJSON(path) {
  const res = await fetch(API_BASE + path);
  const body = await res.json();
  if (!res.ok) throw new Error(body.detail || `Request failed (HTTP ${res.status})`);
  return body;
}

function fmtScore(score) {
  return typeof score === "number" ? score.toFixed(4) : "—";
}

function fmtMoney(n) {
  return typeof n === "number" ? `₹${n.toFixed(2)}` : "—";
}

function fmtTime(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function genTxnRef(prefix = "txn") {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
}
