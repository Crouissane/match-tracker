"use strict";

/* ============ State ============ */
const state = { teams: [], matches: [], standings: [], teamFilter: "", teamSearch: "" };
const $ = (sel) => document.querySelector(sel);

/* ============ API ============ */
async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (res.status === 204) return null;
  let body = null;
  try { body = await res.json(); } catch { /* empty body */ }
  if (!res.ok) throw new Error(errorMessage(body, res.status));
  return body;
}

function errorMessage(body, status) {
  const detail = body && body.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((d) => {
        const field = (d.loc || []).filter((p) => p !== "body").join(".").replace(/_/g, " ");
        return field ? `${capitalize(field)}: ${d.msg}` : d.msg;
      })
      .join(" · ");
  }
  return `Request failed (${status})`;
}

async function loadAll() {
  try {
    const [teams, matches, standings] = await Promise.all([
      api("/teams"), api("/matches"), api("/standings"),
    ]);
    Object.assign(state, { teams, matches, standings });
    $("#offline").hidden = true;
    render();
  } catch (err) {
    console.error(err);
    document.querySelectorAll(".view").forEach((v) => (v.hidden = true));
    $("#offline").hidden = false;
  }
}

/* ============ Helpers ============ */
const capitalize = (s) => s.charAt(0).toUpperCase() + s.slice(1);

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function hue(str) {
  // FNV-1a hash, spread around the colour wheel with the golden angle
  let h = 2166136261;
  for (const ch of str) { h ^= ch.codePointAt(0); h = Math.imul(h, 16777619); }
  return Math.round(((h >>> 0) * 137.508) % 360);
}

function initials(name) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

function crest(team, size = "") {
  if (!team) return `<span class="crest ${size}" style="--h:0">?</span>`;
  return `<span class="crest ${size}" style="--h:${hue(team.name + team.country)}" aria-hidden="true">${esc(initials(team.name))}</span>`;
}

const teamById = (id) => state.teams.find((t) => t.id === id);

/** Per-team stats & form, computed from matches (ordered by id = order recorded). */
function teamRecords() {
  const rec = {};
  for (const t of state.teams) rec[t.id] = { p: 0, w: 0, d: 0, l: 0, pts: 0, form: [] };
  const sorted = [...state.matches].sort((a, b) => a.id - b.id);
  for (const m of sorted) {
    const h = rec[m.home_team_id], a = rec[m.away_team_id];
    if (!h || !a) continue;
    h.p++; a.p++;
    if (m.home_score > m.away_score) { h.w++; h.pts += 3; a.l++; h.form.push("W"); a.form.push("L"); }
    else if (m.home_score < m.away_score) { a.w++; a.pts += 3; h.l++; h.form.push("L"); a.form.push("W"); }
    else { h.d++; a.d++; h.pts++; a.pts++; h.form.push("D"); a.form.push("D"); }
  }
  return rec;
}

/* ============ Toasts ============ */
function toast(message, type = "success") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  $("#toasts").appendChild(el);
  setTimeout(() => {
    el.classList.add("leaving");
    el.addEventListener("animationend", () => el.remove(), { once: true });
    setTimeout(() => el.remove(), 400);
  }, type === "error" ? 4500 : 2800);
}

/* ============ Routing ============ */
const VIEWS = ["table", "matches", "teams"];

function currentView() {
  const v = location.hash.replace("#", "");
  return VIEWS.includes(v) ? v : "table";
}

function showView() {
  const view = currentView();
  document.querySelectorAll(".view").forEach((el) => (el.hidden = el.dataset.view !== view));
  document.querySelectorAll(".tab").forEach((el) => {
    const active = el.dataset.view === view;
    el.classList.toggle("active", active);
    el.setAttribute("aria-selected", active);
  });
}

/* ============ Render ============ */
function render() {
  showView();
  const records = teamRecords();
  renderTable(records);
  renderMatchForm();
  renderMatches();
  renderTeams(records);
}

function renderTable(records) {
  const tbody = $("#standings tbody");
  const rows = state.standings;
  $("#standings-empty").hidden = rows.length > 0;
  $("#standings").hidden = rows.length === 0;

  tbody.innerHTML = rows.map((row, i) => {
    const team = teamById(row.team_id) || { name: row.team, country: "" };
    const form = (records[row.team_id]?.form || []).slice(-5);
    const formCells = Array.from({ length: 5 }, (_, k) => {
      const r = form[k - (5 - form.length)];
      return r ? `<span class="${r}" title="${{ W: "Win", D: "Draw", L: "Loss" }[r]}">${r}</span>` : `<span class="none"></span>`;
    }).join("");
    const gd = row.goal_difference;
    const gdClass = gd > 0 ? "gd-pos" : gd < 0 ? "gd-neg" : "";
    const leading = i === 0 && row.played > 0;
    return `
      <tr class="${leading ? "is-first" : ""}">
        <td class="col-pos"><span class="pos">${i + 1}</span></td>
        <td class="col-team">
          <div class="team-cell">${crest(team)}
            <div>${esc(team.name)}<span class="country">${esc(team.country)}</span></div>
          </div>
        </td>
        <td>${row.played}</td>
        <td>${row.wins}</td>
        <td>${row.draws}</td>
        <td>${row.losses}</td>
        <td class="hide-sm">${row.goals_for}</td>
        <td class="hide-sm">${row.goals_against}</td>
        <td class="${gdClass}">${gd > 0 ? "+" : ""}${gd}</td>
        <td class="col-pts">${row.points}</td>
        <td class="col-form hide-md"><div class="form">${formCells}</div></td>
      </tr>`;
  }).join("");

  // Leader card
  const leaderEl = $("#leader");
  const top = rows[0];
  if (top && top.played > 0) {
    const team = teamById(top.team_id) || { name: top.team, country: "" };
    leaderEl.innerHTML = `
      ${crest(team, "lg")}
      <div><div class="label">League leader</div><div class="name">${esc(team.name)}</div></div>
      <div class="pts">${top.points}<small>PTS</small></div>`;
    leaderEl.hidden = false;
  } else {
    leaderEl.hidden = true;
  }

  // Stats
  const goals = state.matches.reduce((s, m) => s + m.home_score + m.away_score, 0);
  const avg = state.matches.length ? (goals / state.matches.length).toFixed(2) : "0.00";
  $("#stats").innerHTML = [
    ["Teams", state.teams.length],
    ["Matches", state.matches.length],
    ["Goals", goals],
    ["Goals / match", avg],
  ].map(([k, v]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`).join("");
}

function teamOptions(selected, placeholder) {
  const sorted = [...state.teams].sort((a, b) => a.name.localeCompare(b.name));
  return `<option value="">${placeholder}</option>` + sorted.map((t) =>
    `<option value="${t.id}" ${String(t.id) === String(selected) ? "selected" : ""}>${esc(t.name)} (${esc(t.country)})</option>`
  ).join("");
}

function renderMatchForm() {
  const home = $("#home-team"), away = $("#away-team");
  const hv = home.value, av = away.value;
  home.innerHTML = teamOptions(hv, "Select home team");
  away.innerHTML = teamOptions(av, "Select away team");
  const disabled = state.teams.length < 2;
  $("#match-form").querySelector("button[type=submit]").disabled = disabled;
  $("#match-form").title = disabled ? "Add at least two teams first" : "";
}

function renderMatches() {
  const filter = $("#match-filter");
  filter.innerHTML = teamOptions(state.teamFilter, "All teams");
  if (state.teamFilter && !teamById(Number(state.teamFilter))) state.teamFilter = "";

  const id = Number(state.teamFilter);
  const list = [...state.matches]
    .filter((m) => !id || m.home_team_id === id || m.away_team_id === id)
    .sort((a, b) => b.id - a.id);

  $("#match-count").textContent = list.length;
  $("#matches-empty").hidden = list.length > 0;
  $("#matches-empty-text").textContent = state.teamFilter
    ? "This team hasn’t played any matches yet."
    : state.teams.length < 2
      ? "Add at least two teams, then record your first result."
      : "Pick two teams above and enter the final score.";

  $("#match-list").innerHTML = list.map((m) => {
    const h = teamById(m.home_team_id), a = teamById(m.away_team_id);
    const hw = m.home_score > m.away_score, aw = m.away_score > m.home_score;
    return `
      <article class="card match">
        <div class="side home ${aw ? "loser" : ""}">${crest(h)}<span class="tname">${esc(h?.name ?? "Unknown")}</span></div>
        <div class="score" aria-label="${m.home_score} to ${m.away_score}">
          <b class="${hw ? "win" : ""}">${m.home_score}</b><i>–</i><b class="${aw ? "win" : ""}">${m.away_score}</b>
        </div>
        <div class="side away ${hw ? "loser" : ""}">${crest(a)}<span class="tname">${esc(a?.name ?? "Unknown")}</span></div>
        <div class="meta">Match ${m.id} · Full time</div>
      </article>`;
  }).join("");
}

const ICON_EDIT = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg>`;
const ICON_TRASH = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/></svg>`;

function renderTeams(records) {
  const q = state.teamSearch.trim().toLowerCase();
  const list = [...state.teams]
    .filter((t) => !q || t.name.toLowerCase().includes(q) || t.country.toLowerCase().includes(q))
    .sort((a, b) => a.name.localeCompare(b.name));

  $("#team-count").textContent = state.teams.length;
  $("#teams-empty").hidden = list.length > 0;
  $("#teams-empty-title").textContent = q ? "No matching teams" : "No teams yet";
  $("#teams-empty-text").textContent = q ? `Nothing matches “${state.teamSearch}”.` : "Use the form above to add your first team.";

  $("#team-grid").innerHTML = list.map((t) => {
    const r = records[t.id] || { p: 0, w: 0, d: 0, l: 0, pts: 0 };
    const locked = r.p > 0;
    return `
      <article class="card team-card">
        <div class="top">
          ${crest(t, "lg")}
          <div class="info">
            <div class="name" title="${esc(t.name)}">${esc(t.name)}</div>
            <div class="country">${esc(t.country)}</div>
          </div>
          <div class="actions">
            <button class="icon-btn" data-edit="${t.id}" title="Edit team" aria-label="Edit ${esc(t.name)}">${ICON_EDIT}</button>
            <button class="icon-btn danger" data-delete="${t.id}" title="${locked ? "Has played matches — can’t be deleted" : "Delete team"}" aria-label="Delete ${esc(t.name)}">${ICON_TRASH}</button>
          </div>
        </div>
        <div class="record">
          <div><b>${r.w}</b><span>W</span></div>
          <div><b>${r.d}</b><span>D</span></div>
          <div><b>${r.l}</b><span>L</span></div>
          <div class="pts"><b>${r.pts}</b><span>PTS</span></div>
        </div>
      </article>`;
  }).join("");
}

/* ============ Actions ============ */
async function withBusy(button, fn) {
  button.disabled = true;
  try { await fn(); } finally { button.disabled = false; }
}

$("#team-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const name = $("#team-name"), country = $("#team-country");
  name.classList.toggle("invalid", !name.value.trim());
  country.classList.toggle("invalid", !country.value.trim());
  if (!name.value.trim() || !country.value.trim()) return toast("Please fill in both the name and country.", "error");

  withBusy(e.submitter || e.target.querySelector("button"), async () => {
    try {
      const team = await api("/teams", {
        method: "POST",
        body: JSON.stringify({ name: name.value.trim(), country: country.value.trim() }),
      });
      e.target.reset();
      name.focus();
      toast(`${team.name} added`);
      await loadAll();
    } catch (err) { toast(err.message, "error"); }
  });
});

$("#match-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const home = $("#home-team"), away = $("#away-team");
  const hs = Number($("#home-score").value), as = Number($("#away-score").value);
  home.classList.toggle("invalid", !home.value);
  away.classList.toggle("invalid", !away.value);
  if (!home.value || !away.value) return toast("Choose both a home and an away team.", "error");
  if (home.value === away.value) {
    away.classList.add("invalid");
    return toast("A team cannot play against itself.", "error");
  }
  if (!Number.isInteger(hs) || !Number.isInteger(as) || hs < 0 || as < 0) {
    return toast("Scores must be whole numbers, 0 or more.", "error");
  }

  withBusy(e.submitter || e.target.querySelector("button[type=submit]"), async () => {
    try {
      await api("/matches", {
        method: "POST",
        body: JSON.stringify({
          home_team_id: Number(home.value), away_team_id: Number(away.value),
          home_score: hs, away_score: as,
        }),
      });
      const h = teamById(Number(home.value)), a = teamById(Number(away.value));
      toast(`Result saved: ${h.name} ${hs}–${as} ${a.name}`);
      home.value = ""; away.value = "";
      $("#home-score").value = 0; $("#away-score").value = 0;
      await loadAll();
    } catch (err) { toast(err.message, "error"); }
  });
});

// Score steppers
document.querySelectorAll(".stepper").forEach((stepper) => {
  const input = document.getElementById(stepper.dataset.target);
  stepper.addEventListener("click", (e) => {
    const btn = e.target.closest(".step");
    if (!btn) return;
    input.value = Math.max(0, (parseInt(input.value, 10) || 0) + Number(btn.dataset.delta));
  });
  input.addEventListener("focus", () => input.select());
  input.addEventListener("blur", () => { input.value = Math.max(0, parseInt(input.value, 10) || 0); });
});

["#home-team", "#away-team", "#team-name", "#team-country"].forEach((sel) =>
  $(sel).addEventListener("input", (e) => e.target.classList.remove("invalid"))
);

$("#match-filter").addEventListener("change", (e) => { state.teamFilter = e.target.value; renderMatches(); });
$("#team-search").addEventListener("input", (e) => { state.teamSearch = e.target.value; renderTeams(teamRecords()); });

// Edit / delete
let editingId = null;
const editDialog = $("#edit-dialog");

$("#team-grid").addEventListener("click", async (e) => {
  const editBtn = e.target.closest("[data-edit]");
  const delBtn = e.target.closest("[data-delete]");
  if (editBtn) {
    const team = teamById(Number(editBtn.dataset.edit));
    editingId = team.id;
    $("#edit-name").value = team.name;
    $("#edit-country").value = team.country;
    editDialog.showModal();
    $("#edit-name").focus();
  } else if (delBtn) {
    const team = teamById(Number(delBtn.dataset.delete));
    const ok = await confirmDialog(`Delete ${team.name}?`, "This permanently removes the team. This can’t be undone.");
    if (!ok) return;
    try {
      await api(`/teams/${team.id}`, { method: "DELETE" });
      toast(`${team.name} deleted`);
      await loadAll();
    } catch (err) { toast(err.message, "error"); }
  }
});

editDialog.querySelector("[data-close]").addEventListener("click", () => editDialog.close());

$("#edit-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("#edit-name").value.trim(), country = $("#edit-country").value.trim();
  if (!name || !country) return toast("Please fill in both the name and country.", "error");
  try {
    await api(`/teams/${editingId}`, { method: "PUT", body: JSON.stringify({ name, country }) });
    editDialog.close();
    toast("Team updated");
    await loadAll();
  } catch (err) { toast(err.message, "error"); }
});

function confirmDialog(title, text) {
  const dlg = $("#confirm-dialog");
  $("#confirm-title").textContent = title;
  $("#confirm-text").textContent = text;
  dlg.returnValue = "";
  dlg.showModal();
  return new Promise((resolve) => {
    dlg.addEventListener("close", () => resolve(dlg.returnValue === "ok"), { once: true });
  });
}

$("#retry").addEventListener("click", loadAll);
window.addEventListener("hashchange", showView);

loadAll();
