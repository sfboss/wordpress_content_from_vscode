/* WordPress Content Factory — web UI */

const state = {
  sites: [],
  tasks: [],
  tools: [],
  selectedKey: null,
  siteDetail: null,
  readiness: null,
  docFilter: "needs", // needs | blocked | almost | ready | all
  pendingConfirm: null,
  eventSource: null,
  running: false,
  refreshReadyAfterJob: false,
};

const $ = (sel, el = document) => el.querySelector(sel);
const $$ = (sel, el = document) => [...el.querySelectorAll(sel)];

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const detail = data?.detail || data?.error || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

function setConsoleStatus(status) {
  const badge = $("#job-status");
  badge.className = `badge ${status}`;
  badge.textContent = status;
}

function appendConsole(text) {
  const out = $("#console-out");
  out.textContent += text;
  out.scrollTop = out.scrollHeight;
}

function clearConsole() {
  $("#console-out").textContent = "";
  $("#job-label").textContent = "";
  setConsoleStatus("idle");
}

function openModal(id) {
  $(id).classList.remove("hidden");
}

function closeModals() {
  $$(".modal").forEach((m) => m.classList.add("hidden"));
}

function siteByKey(key) {
  return state.sites.find((s) => s.key === key);
}

function renderSiteList() {
  const list = $("#site-list");
  if (!state.sites.length) {
    list.innerHTML = `<div class="muted" style="padding:8px">No sites with site.yaml yet.</div>`;
    return;
  }
  list.innerHTML = state.sites
    .map((s) => {
      const tone = s.tone || (s.has_credentials ? "yellow" : "red");
      const cred = s.has_credentials
        ? `<span class="chip green">credentials</span>`
        : `<span class="chip red">no .env</span>`;
      return `
      <button type="button" class="site-card tone-${escapeAttr(tone)} ${state.selectedKey === s.key ? "active" : ""}" data-site="${escapeAttr(s.key)}" role="listitem">
        <div class="site-name"><span class="tone-dot ${escapeAttr(tone)}" title="${escapeAttr(tone)}"></span>${escapeHtml(s.name)}</div>
        <div class="site-url">${escapeHtml(s.url)}</div>
        <div class="site-stats">
          <span class="chip">${s.counts?.posts || 0} posts</span>
          <span class="chip">${s.counts?.pages || 0} pages</span>
          <span class="chip ${escapeAttr(tone)}">${escapeHtml(tone)}</span>
          ${cred}
        </div>
      </button>`;
    })
    .join("");

  $$(".site-card", list).forEach((btn) => {
    btn.addEventListener("click", () => selectSite(btn.dataset.site));
  });
}

function actionButtonHtml(action, extraClass = "") {
  const cls = action.primary ? "btn btn-primary btn-sm" : `btn btn-ghost btn-sm ${extraClass}`;
  const payload = encodeURIComponent(JSON.stringify(action));
  return `<button type="button" class="fix-action ${cls}" data-action="${payload}">${escapeHtml(action.label)}</button>`;
}

function bindFixActions(root) {
  $$(".fix-action", root).forEach((btn) => {
    btn.addEventListener("click", () => {
      let action;
      try {
        action = JSON.parse(decodeURIComponent(btn.dataset.action));
      } catch {
        return;
      }
      runFixAction(action);
    });
  });
}

function runFixAction(action) {
  if (!action) return;
  if (action.open_content) {
    openContentPath(action.open_content);
  }
  if (action.task_id) {
    const task = state.tasks.find((t) => t.id === action.task_id);
    if (!task) {
      appendConsole(`Unknown task for fix action: ${action.task_id}\n`);
      return;
    }
    state.refreshReadyAfterJob = true;
    requestRun(task, {
      confirm: !!action.confirm,
      open_report: !!action.open_report,
      target: action.target || undefined,
      tool: action.tool || undefined,
    });
    return;
  }
  if (action.tool) {
    // Direct tool without catalog id
    const synthetic = {
      id: "tool-run-selected",
      label: action.label || action.tool,
      scope: "site",
      command: "tool",
      tool: action.tool,
      confirm: !!action.confirm,
      open_report: !!action.open_report,
      mutating: !!action.confirm,
    };
    state.refreshReadyAfterJob = true;
    requestRun(synthetic, {
      tool: action.tool,
      confirm: !!action.confirm,
      open_report: !!action.open_report,
      target: action.target,
    });
  }
}

async function openContentPath(rel) {
  if (!state.selectedKey || !rel) return;
  // Switch to content tab and load file (or folder focus)
  $$(".tab").forEach((t) => t.classList.remove("active"));
  $$(".tab-panel").forEach((p) => p.classList.remove("active"));
  $(`.tab[data-tab="content"]`)?.classList.add("active");
  $("#tab-content")?.classList.add("active");

  let path = rel.replace(/^\/+/, "");
  if (!path.startsWith("content/") && !path.includes("/")) {
    path = path;
  }
  // Folder only — show tree, no file body
  if (!path.includes(".") || path.endsWith("/")) {
    $("#preview-path").textContent = path;
    $("#preview-body").textContent = `Folder: ${path}\n\nPick a file in the tree, or add Markdown under this path.`;
    return;
  }
  // Ensure path is under site content
  if (!path.startsWith("content/") && !path.startsWith("websites/")) {
    // publish readiness keys are already content/...
  }
  try {
    await loadFilePreview(path.startsWith("content/") ? path : path);
    // highlight in tree if present
    $$(".tree-file").forEach((b) => {
      b.classList.toggle("active", b.dataset.path === path || b.dataset.path?.endsWith(path));
    });
  } catch (err) {
    $("#preview-path").textContent = path;
    $("#preview-body").textContent = `Could not open ${path}: ${err.message}`;
  }
}

function kpiFixActions(kpi) {
  // Map KPI deficits to concrete fix actions
  if (kpi.tone === "green") return [];
  const map = {
    posts: [
      { label: "Open posts", open_content: "content/posts", primary: true },
      { label: "Inventory", task_id: "tool-content-inventory", open_report: true },
    ],
    pages: [
      { label: "Open pages", open_content: "content/pages", primary: true },
      { label: "Inventory", task_id: "tool-content-inventory", open_report: true },
    ],
    categories: [{ label: "Open categories", open_content: "content/categories", primary: true }],
    ready_docs: [
      { label: "Publish readiness", task_id: "tool-publish-readiness", open_report: true, primary: true },
      { label: "SEO audit", task_id: "tool-seo-audit", open_report: true },
      { label: "Featured images", task_id: "tool-featured-image-fixer", confirm: true, open_report: true },
    ],
    credentials: [{ label: "Test connection", task_id: "doctor", primary: true }],
  };
  return map[kpi.id] || [];
}

function renderReadyBoard() {
  const board = $("#ready-board");
  if (!board) return;
  const r = state.readiness;
  if (!r) {
    board.innerHTML = `<div class="ready-loading muted">Loading readiness assessment…</div>`;
    return;
  }

  const sum = r.summary || {};
  const overall = r.overall || "blocked";
  const kpis = r.kpis || [];
  const todos = r.todos || [];
  const openTodos = todos.filter((t) => t.severity !== "green" || t.id === "drafts-ready" || t.id === "sync-path");
  const fixTodos = todos.filter((t) => t.severity === "red" || t.severity === "yellow");

  const next = (r.next_actions || [])
    .map((a) => actionButtonHtml(a, a.confirm ? "btn-warn" : "btn-fix"))
    .join("");

  const kpiHtml = kpis
    .map((k) => {
      const fixes = kpiFixActions(k);
      const fixBtns =
        k.tone === "green"
          ? `<span class="chip green">on target</span>`
          : fixes.map((a) => actionButtonHtml(a, k.tone === "red" ? "btn-warn" : "btn-fix")).join("");
      return `<article class="kpi-card ${escapeAttr(k.tone)}">
        <div class="kpi-top"><span>${escapeHtml(k.label)}</span><span class="tone-dot ${escapeAttr(k.tone)}"></span></div>
        <div class="kpi-value">${escapeHtml(k.actual)}</div>
        <div class="kpi-target">target ${escapeHtml(k.target)} · ${escapeHtml(k.pct)}%</div>
        <div class="track"><div class="fill" style="width:${Math.min(100, k.pct)}%"></div></div>
        <div class="kpi-actions">${fixBtns}</div>
      </article>`;
    })
    .join("");

  const todoHtml = fixTodos.length
    ? fixTodos
        .map((t) => {
          const items = (t.items || [])
            .slice(0, 8)
            .map(
              (item) =>
                `<li><button type="button" class="open-doc" data-path="${escapeAttr(item)}" title="${escapeAttr(item)}">${escapeHtml(item.split("/").pop())}</button></li>`
            )
            .join("");
          const more =
            (t.item_count || 0) > 8
              ? `<li><span class="chip">+${t.item_count - 8} more</span></li>`
              : "";
          const actions = (t.actions || [])
            .map((a) =>
              actionButtonHtml(
                a,
                a.primary ? "" : t.severity === "red" ? "btn-warn" : "btn-fix"
              )
            )
            .join("");
          return `<article class="todo-card ${escapeAttr(t.severity)}">
            <header>
              <div>
                <h3><span class="tone-dot ${escapeAttr(t.severity)}"></span>${escapeHtml(t.title)}</h3>
                <p class="todo-detail">${escapeHtml(t.detail)}</p>
              </div>
              <span class="chip ${escapeAttr(t.severity)}">${escapeHtml(t.severity)} · ${escapeHtml(t.category)}</span>
            </header>
            ${items ? `<ul class="todo-items">${items}${more}</ul>` : ""}
            <div class="todo-actions">${actions}</div>
          </article>`;
        })
        .join("")
    : `<article class="todo-card green">
        <header><div>
          <h3><span class="tone-dot green"></span>No open deficits</h3>
          <p class="todo-detail">Volume, quality, and publish checks are clear. Lint → plan → push when you want live updates.</p>
        </div><span class="chip green">ready path</span></header>
        <div class="todo-actions">
          ${actionButtonHtml({ label: "Lint", task_id: "lint" })}
          ${actionButtonHtml({ label: "Plan", task_id: "plan", primary: true })}
          ${actionButtonHtml({ label: "Push", task_id: "push", confirm: true })}
        </div>
      </article>`;

  const greenTodos = todos.filter((t) => t.severity === "green");
  const greenHtml = greenTodos
    .map(
      (t) => `<article class="todo-card green">
        <header>
          <div>
            <h3><span class="tone-dot green"></span>${escapeHtml(t.title)}</h3>
            <p class="todo-detail">${escapeHtml(t.detail)}</p>
          </div>
        </header>
        <div class="todo-actions">${(t.actions || []).map((a) => actionButtonHtml(a, "btn-fix")).join("")}</div>
      </article>`
    )
    .join("");

  board.innerHTML = `
    <div class="ready-toolbar">
      <button type="button" class="btn btn-ghost btn-sm" id="btn-refresh-ready">↻ Re-assess</button>
      <button type="button" class="btn btn-ghost btn-sm" id="btn-run-dashboard">Open site dashboard report</button>
      <button type="button" class="btn btn-ghost btn-sm" id="btn-run-publish-ready">Publish readiness report</button>
      <span class="muted" style="font-size:12px">Goal: move every red/yellow item to green → <strong>Ready</strong></span>
    </div>

    <section class="ready-hero ${escapeAttr(overall)}">
      <div class="ready-score">
        <div class="score-num">${escapeHtml(r.score)}</div>
        <div class="score-label">${escapeHtml(r.label || overall)}</div>
      </div>
      <div class="ready-hero-body">
        <h2>Fix queue → Ready</h2>
        <p class="muted">Hyper-focused on deficits vs targets. Each action runs the same VS Code / CLI task that clears that gap.</p>
        <div class="ready-stats">
          <span class="chip red">${sum.red_todos || 0} red</span>
          <span class="chip yellow">${sum.yellow_todos || 0} yellow</span>
          <span class="chip green">${sum.docs_ready || 0} docs ready</span>
          <span class="chip yellow">${sum.docs_almost || 0} almost</span>
          <span class="chip red">${sum.docs_blocked || 0} blocked</span>
          <span class="chip">${sum.drafts_ready_to_publish || 0} drafts ready to publish</span>
        </div>
        <div class="next-actions">${next || `<span class="muted">No automated next step</span>`}</div>
      </div>
    </section>

    <div class="kpi-strip">${kpiHtml}</div>

    <div class="todo-section-head">
      <div>
        <h2>TODOs to clear</h2>
        <p class="muted">${fixTodos.length} deficit item(s) — red first, then yellow. Buttons resolve or diagnose.</p>
      </div>
    </div>
    <div class="todo-list">${todoHtml}</div>

    ${
      greenHtml
        ? `<div class="todo-section-head mt"><div><h2>On track</h2><p class="muted">Green checks and optional next steps.</p></div></div>
           <div class="todo-list">${greenHtml}</div>`
        : ""
    }

    <div class="todo-section-head mt">
      <div>
        <h2>Documents</h2>
        <p class="muted">Per-file readiness from the publish checklist (blockers &amp; warnings).</p>
      </div>
      <div class="filter-pills" id="doc-filter">
        <button type="button" data-filter="needs" class="${state.docFilter === "needs" ? "active" : ""}">Needs work</button>
        <button type="button" data-filter="blocked" class="${state.docFilter === "blocked" ? "active" : ""}">Blocked</button>
        <button type="button" data-filter="almost" class="${state.docFilter === "almost" ? "active" : ""}">Almost</button>
        <button type="button" data-filter="ready" class="${state.docFilter === "ready" ? "active" : ""}">Ready</button>
        <button type="button" data-filter="all" class="${state.docFilter === "all" ? "active" : ""}">All</button>
      </div>
    </div>
    <div class="doc-ready-wrap">
      <table class="doc-ready-table">
        <thead>
          <tr>
            <th>Document</th>
            <th>State</th>
            <th>SEO</th>
            <th>Issues</th>
            <th>Fix</th>
          </tr>
        </thead>
        <tbody id="doc-ready-rows"></tbody>
      </table>
    </div>
  `;

  renderDocReadyRows();
  bindFixActions(board);

  $("#btn-refresh-ready")?.addEventListener("click", () => loadReadiness(state.selectedKey, true));
  $("#btn-run-dashboard")?.addEventListener("click", () => {
    const task = state.tasks.find((t) => t.id === "tool-site-dashboard");
    if (task) {
      state.refreshReadyAfterJob = true;
      requestRun(task, { open_report: true });
    }
  });
  $("#btn-run-publish-ready")?.addEventListener("click", () => {
    const task = state.tasks.find((t) => t.id === "tool-publish-readiness");
    if (task) {
      state.refreshReadyAfterJob = true;
      requestRun(task, { open_report: true });
    }
  });

  $$("#doc-filter button").forEach((btn) => {
    btn.addEventListener("click", () => {
      state.docFilter = btn.dataset.filter;
      $$("#doc-filter button").forEach((b) => b.classList.toggle("active", b === btn));
      renderDocReadyRows();
    });
  });

  $$(".open-doc", board).forEach((btn) => {
    btn.addEventListener("click", () => openContentPath(btn.dataset.path));
  });
}

function renderDocReadyRows() {
  const tbody = $("#doc-ready-rows");
  if (!tbody || !state.readiness) return;
  let docs = state.readiness.documents || [];
  const f = state.docFilter;
  if (f === "needs") docs = docs.filter((d) => d.readiness === "blocked" || d.readiness === "almost");
  else if (f === "blocked" || f === "almost" || f === "ready") docs = docs.filter((d) => d.readiness === f);

  if (!docs.length) {
    tbody.innerHTML = `<tr><td colspan="5" class="muted">No documents in this filter.</td></tr>`;
    return;
  }

  tbody.innerHTML = docs
    .map((d) => {
      const issues = [...(d.blockers || []).slice(0, 2), ...(d.warnings || []).slice(0, 2)]
        .map((i) => `<div class="muted" style="font-size:11px">• ${escapeHtml(i)}</div>`)
        .join("");
      const fixes = [];
      const allIssues = `${(d.blockers || []).join(" ")} ${(d.warnings || []).join(" ")}`.toLowerCase();
      if (allIssues.includes("featured")) {
        fixes.push({
          label: "Featured img",
          task_id: "tool-featured-image-fixer",
          confirm: true,
          open_report: true,
          target: `websites/${state.selectedKey}/${d.document}`,
        });
      }
      if (allIssues.includes("seo") || (d.seo_score != null && d.seo_score < 70)) {
        fixes.push({
          label: "SEO",
          task_id: "tool-seo-audit",
          open_report: true,
          target: `websites/${state.selectedKey}/${d.document}`,
        });
      }
      if (allIssues.includes("internal")) {
        fixes.push({
          label: "Internal links",
          task_id: "tool-internal-linker",
          target: `websites/${state.selectedKey}/${d.document}`,
        });
      }
      if (allIssues.includes("external") || allIssues.includes("authority")) {
        fixes.push({
          label: "External links",
          task_id: "tool-external-linker",
          target: `websites/${state.selectedKey}/${d.document}`,
        });
      }
      fixes.push({ label: "Open", open_content: d.document, primary: !fixes.length });
      fixes.push({
        label: "Overlap",
        task_id: "tool-content-overlap-target",
        open_report: true,
        target: `websites/${state.selectedKey}/${d.document}`,
      });

      return `<tr>
        <td>
          <div style="font-weight:600">${escapeHtml(d.title || d.document)}</div>
          <div class="mono muted" style="font-size:11px">${escapeHtml(d.document)}</div>
        </td>
        <td><span class="chip ${escapeAttr(d.tone)}">${escapeHtml(d.readiness)}</span>
          <div class="muted" style="font-size:11px;margin-top:4px">${escapeHtml(d.status)} · ${escapeHtml(d.words || 0)}w</div>
        </td>
        <td>${d.seo_score != null ? escapeHtml(d.seo_score) : "—"}</td>
        <td>${issues || `<span class="muted">—</span>`}</td>
        <td><div class="doc-actions">${fixes.map((a) => actionButtonHtml(a, "btn-sm")).join("")}</div></td>
      </tr>`;
    })
    .join("");

  bindFixActions(tbody);
  $$(".open-doc", tbody).forEach((btn) => {
    btn.addEventListener("click", () => openContentPath(btn.dataset.path));
  });
}

async function loadReadiness(key, force) {
  if (!key) return;
  const board = $("#ready-board");
  if (board && (force || !state.readiness || state.readiness.site !== key)) {
    board.innerHTML = `<div class="ready-loading muted">Assessing site readiness (content + publish checklist)…</div>`;
  }
  try {
    const data = await api(`/api/sites/${encodeURIComponent(key)}/readiness`);
    state.readiness = data;
    // Update sidebar tone from real assessment
    const site = siteByKey(key);
    if (site) {
      site.tone = data.overall === "ready" ? "green" : data.overall === "almost" ? "yellow" : "red";
      renderSiteList();
    }
    renderReadyBoard();
    // Topbar badge
    updateTopbarReady(data);
  } catch (err) {
    if (board) {
      board.innerHTML = `<div class="todo-card red"><h3>Readiness failed</h3><p class="todo-detail">${escapeHtml(err.message)}</p>
        <div class="todo-actions"><button type="button" class="btn btn-primary btn-sm" id="btn-retry-ready">Retry</button></div></div>`;
      $("#btn-retry-ready")?.addEventListener("click", () => loadReadiness(key, true));
    }
  }
}

function updateTopbarReady(data) {
  const meta = $("#topbar-meta");
  if (!meta || !data) return;
  const site = siteByKey(state.selectedKey);
  const tone = data.overall === "ready" ? "green" : data.overall === "almost" ? "yellow" : "red";
  meta.innerHTML = `
    <span class="chip ${tone}"><span class="tone-dot ${tone}"></span>${escapeHtml(data.label)} · ${escapeHtml(data.score)}</span>
    <span class="chip">${escapeHtml(site?.url || "")}</span>
    ${
      site?.has_credentials
        ? `<span class="chip green">credentials</span>`
        : `<span class="chip red">add .env</span>`
    }
    <span class="chip red">${data.summary?.red_todos || 0} red</span>
    <span class="chip yellow">${data.summary?.yellow_todos || 0} yellow</span>
  `;
}

function escapeHtml(str) {
  return String(str ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function escapeAttr(str) {
  return escapeHtml(str).replace(/'/g, "&#39;");
}

function tasksInGroup(group) {
  return state.tasks.filter((t) => t.group === group);
}

function renderActionCard(task) {
  const mutating = task.mutating ? "mutating" : "";
  const badge = task.mutating
    ? `<span class="chip warn">writes</span>`
    : `<span class="chip">safe</span>`;
  return `
    <article class="action-card ${mutating}" data-task="${escapeAttr(task.id)}">
      <h3>${escapeHtml(task.label)}</h3>
      <p>${escapeHtml(task.description || "")}</p>
      <div class="card-foot">
        ${badge}
        <button type="button" class="btn btn-primary run-task" data-task="${escapeAttr(task.id)}">Run</button>
      </div>
    </article>`;
}

function renderWorkflow() {
  const syncIds = ["doctor", "lint", "plan", "push", "pull", "verify"];
  const multiIds = ["plan-all", "push-all"];
  const sync = syncIds.map((id) => state.tasks.find((t) => t.id === id)).filter(Boolean);
  const multi = multiIds.map((id) => state.tasks.find((t) => t.id === id)).filter(Boolean);
  $("#sync-actions").innerHTML = sync.map(renderActionCard).join("");
  $("#multi-actions").innerHTML = multi.map(renderActionCard).join("");
  bindRunButtons($("#tab-workflow"));
}

function renderTools() {
  const toolTasks = state.tasks.filter((t) => t.group === "tools" && t.id !== "tools-list");
  $("#tool-actions").innerHTML = toolTasks.map(renderActionCard).join("");

  const toolSelect = $("#tool-select");
  const tools = state.tools.length
    ? state.tools
    : toolTasks.filter((t) => t.tool).map((t) => ({ name: t.tool, title: t.label }));
  const names = [...new Set(tools.map((t) => t.name || t.tool).filter(Boolean))];
  toolSelect.innerHTML = names
    .map((n) => {
      const meta = tools.find((t) => (t.name || t.tool) === n);
      const title = meta?.title || n;
      return `<option value="${escapeAttr(n)}">${escapeHtml(title)}</option>`;
    })
    .join("");

  bindRunButtons($("#tab-tools"));
}

function bindRunButtons(root) {
  $$(".run-task", root).forEach((btn) => {
    btn.addEventListener("click", () => {
      const task = state.tasks.find((t) => t.id === btn.dataset.task);
      if (task) requestRun(task);
    });
  });
}

function fillTargetSelect(detail) {
  const sel = $("#target-select");
  const opts = [`<option value="">Whole site</option>`];
  for (const group of detail.content_tree || []) {
    for (const f of group.files || []) {
      if (!f.path.endsWith(".md") && !f.path.endsWith(".markdown")) continue;
      opts.push(
        `<option value="${escapeAttr(f.path)}">${escapeHtml(group.collection)} / ${escapeHtml(f.name)}</option>`
      );
    }
  }
  sel.innerHTML = opts.join("");
}

function renderContentTree(detail) {
  const tree = $("#content-tree");
  if (!detail.content_tree?.length) {
    tree.innerHTML = `<div class="muted" style="padding:8px">No content folders.</div>`;
    return;
  }
  tree.innerHTML = detail.content_tree
    .map((g) => {
      const files =
        g.files?.length
          ? g.files
              .map(
                (f) =>
                  `<button type="button" class="tree-file" data-path="${escapeAttr(f.path)}">${escapeHtml(f.name)}</button>`
              )
              .join("")
          : `<div class="muted" style="padding:6px 8px;font-size:12px">empty</div>`;
      return `<details class="tree-group" open>
        <summary>${escapeHtml(g.collection)} (${g.count})</summary>
        ${files}
      </details>`;
    })
    .join("");

  $$(".tree-file", tree).forEach((btn) => {
    btn.addEventListener("click", async () => {
      $$(".tree-file", tree).forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      await loadFilePreview(btn.dataset.path);
    });
  });
}

async function loadFilePreview(relPath) {
  if (!state.selectedKey) return;
  $("#preview-path").textContent = relPath;
  $("#preview-body").textContent = "Loading…";
  try {
    const data = await api(
      `/api/sites/${encodeURIComponent(state.selectedKey)}/file?path=${encodeURIComponent(relPath)}`
    );
    $("#preview-body").textContent = data.content;
  } catch (err) {
    $("#preview-body").textContent = `Error: ${err.message}`;
  }
}

async function loadReports() {
  if (!state.selectedKey) return;
  const list = $("#reports-list");
  list.innerHTML = `<div class="muted">Loading…</div>`;
  try {
    const data = await api(`/api/sites/${encodeURIComponent(state.selectedKey)}/reports`);
    if (!data.reports?.length) {
      list.innerHTML = `<div class="muted">No reports yet. Run doctor, lint, plan, push, or a tool.</div>`;
      return;
    }
    list.innerHTML = data.reports
      .map((r) => {
        const open =
          r.kind === "html"
            ? `<a href="${escapeAttr(r.path)}" target="_blank" rel="noopener">Open HTML</a>`
            : `<a href="${escapeAttr(r.path)}" target="_blank" rel="noopener">Open JSON</a>`;
        return `<div class="report-row">
          <div>
            <div class="mono">${escapeHtml(r.name)}</div>
            <div class="muted" style="font-size:12px">${escapeHtml(r.mtime)} · ${r.size} bytes</div>
          </div>
          ${open}
        </div>`;
      })
      .join("");
  } catch (err) {
    list.innerHTML = `<div class="muted">Error: ${escapeHtml(err.message)}</div>`;
  }
}

async function selectSite(key) {
  state.selectedKey = key;
  state.readiness = null;
  state.docFilter = "needs";
  renderSiteList();
  $("#empty-state").classList.add("hidden");
  $("#site-workspace").classList.remove("hidden");

  // Default to Ready tab for fix-focused workflow
  $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === "ready"));
  $$(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === "tab-ready"));

  const site = siteByKey(key);
  $("#page-title").textContent = site?.name || key;
  $("#page-sub").innerHTML = `Project folder <code>websites/${escapeHtml(key)}</code> · get to <strong>Ready</strong> by clearing red/yellow deficits`;
  $("#topbar-meta").innerHTML = `
    <span class="chip">${escapeHtml(site?.url || "")}</span>
    <span class="chip">status: ${escapeHtml(site?.default_status || "draft")}</span>
    ${
      site?.has_credentials
        ? `<span class="chip green">credentials</span>`
        : `<span class="chip red">add .env</span>`
    }
  `;

  try {
    const detail = await api(`/api/sites/${encodeURIComponent(key)}`);
    state.siteDetail = detail;
    fillTargetSelect(detail);
    renderContentTree(detail);
    await Promise.all([loadReports(), loadReadiness(key, true)]);
  } catch (err) {
    appendConsole(`ERROR loading site: ${err.message}\n`);
  }
}

function requestRun(task, extra = {}) {
  const needsSite =
    task.scope === "site" ||
    (task.command === "tool" && !task.all_sites) ||
    task.command === "tool-chain";

  if (needsSite && !task.all_sites && !state.selectedKey && !extra.site) {
    alert("Select a website first.");
    return;
  }

  if (task.needs_domains) {
    openModal("#modal-new-site");
    return;
  }

  const payload = {
    task_id: task.id,
    site: extra.site || state.selectedKey || null,
    force: !!extra.force,
    open_report: extra.open_report ?? task.open_report ?? false,
  };

  if (extra.tool) payload.tool = extra.tool;
  if (extra.target) payload.target = extra.target;
  if (extra.domains) payload.domains = extra.domains;

  if (task.needs_target && !payload.target) {
    const target = $("#target-select")?.value;
    if (!target) {
      alert("Choose a content file in the Tools target selector (or use a Ready-board row action).");
      return;
    }
    payload.target = `websites/${state.selectedKey}/${target}`;
  }

  if (task.needs_tool || task.id === "tool-run-selected") {
    payload.tool = payload.tool || extra.tool || $("#tool-select")?.value;
    if (!payload.tool) {
      alert("Choose a tool.");
      return;
    }
    if (!payload.target) {
      const target = $("#target-select")?.value;
      if (target) {
        payload.target = `websites/${state.selectedKey}/${target}`;
      } else if (task.needs_target) {
        alert("Choose a content file target.");
        return;
      }
    }
  }

  // Already confirmed from modal
  if (extra.confirm === true) {
    payload.confirm = true;
    runTask(payload, task.label);
    return;
  }

  if (task.confirm || task.mutating || extra.confirm) {
    state.pendingConfirm = { task, payload };
    $("#confirm-title").textContent = task.label;
    $("#confirm-body").textContent =
      (task.description || task.label) +
      (task.mutating || extra.confirm
        ? " This may change local Markdown, remote WordPress content, or the environment."
        : "");
    openModal("#modal-confirm");
    return;
  }

  runTask(payload, task.label);
}

async function runTask(payload, label) {
  if (state.running) {
    if (!confirm("A job is already running. Start another anyway?")) return;
  }
  closeModals();
  $("#console-pane").classList.remove("collapsed");
  $("#job-label").textContent = label || payload.task_id;
  appendConsole(`\n—— ${label || payload.task_id} ——\n`);
  setConsoleStatus("running");
  state.running = true;

  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }

  try {
    const job = await api("/api/run", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    const es = new EventSource(job.stream_url);
    state.eventSource = es;
    es.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      if (msg.type === "line") {
        appendConsole(msg.text);
      } else if (msg.type === "done") {
        setConsoleStatus(msg.status || (msg.exit_code === 0 ? "succeeded" : "failed"));
        state.running = false;
        es.close();
        state.eventSource = null;
        afterJobFinished();
      }
    };
    es.onerror = () => {
      // EventSource retries; if job finished, status endpoint will settle
      api(job.status_url)
        .then((st) => {
          if (st.status === "succeeded" || st.status === "failed") {
            setConsoleStatus(st.status);
            state.running = false;
            es.close();
            state.eventSource = null;
            afterJobFinished();
          }
        })
        .catch(() => {});
    };
  } catch (err) {
    appendConsole(`ERROR ${err.message}\n`);
    setConsoleStatus("failed");
    state.running = false;
  }
}

async function afterJobFinished() {
  const key = state.selectedKey;
  const reassess = state.refreshReadyAfterJob;
  state.refreshReadyAfterJob = false;
  try {
    await refreshSites();
    if (key) {
      // Refresh detail + readiness without full tab reset thrash
      const detail = await api(`/api/sites/${encodeURIComponent(key)}`);
      state.siteDetail = detail;
      fillTargetSelect(detail);
      renderContentTree(detail);
      await loadReports();
      if (reassess || true) {
        await loadReadiness(key, true);
      }
    }
  } catch (err) {
    appendConsole(`Post-job refresh: ${err.message}\n`);
  }
}

async function refreshSites() {
  const data = await api("/api/sites");
  state.sites = data.sites || [];
  renderSiteList();
  return state.sites;
}

async function createSites() {
  const raw = $("#new-site-domains").value.trim();
  if (!raw) {
    alert("Enter at least one domain.");
    return;
  }
  const domains = raw.split(/[\s,]+/).filter(Boolean);
  $("#btn-create-sites").disabled = true;
  try {
    const result = await api("/api/sites", {
      method: "POST",
      body: JSON.stringify({ domains }),
    });
    appendConsole((result.stdout || "") + (result.stderr || ""));
    setConsoleStatus(result.ok ? "succeeded" : "failed");
    state.sites = result.sites || [];
    renderSiteList();
    closeModals();
    $("#new-site-domains").value = "";
    if (domains[0]) {
      const key = domains[0].toLowerCase().replace(/^https?:\/\//, "").replace(/\/$/, "");
      if (state.sites.some((s) => s.key === key)) selectSite(key);
    }
  } catch (err) {
    alert(err.message);
  } finally {
    $("#btn-create-sites").disabled = false;
  }
}

function bindTabs() {
  $$(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      $$(".tab").forEach((t) => t.classList.remove("active"));
      $$(".tab-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      $(`#tab-${tab.dataset.tab}`).classList.add("active");
      if (tab.dataset.tab === "reports") loadReports();
      if (tab.dataset.tab === "ready" && state.selectedKey) loadReadiness(state.selectedKey, false);
    });
  });
}

function bindGlobal() {
  $("#btn-refresh-sites").addEventListener("click", () => refreshSites());
  $("#btn-new-site").addEventListener("click", () => openModal("#modal-new-site"));
  $("#btn-new-site-empty").addEventListener("click", () => openModal("#modal-new-site"));
  $("#btn-create-sites").addEventListener("click", createSites);
  $("#btn-confirm-run").addEventListener("click", () => {
    if (!state.pendingConfirm) return;
    const { task, payload } = state.pendingConfirm;
    state.pendingConfirm = null;
    runTask({ ...payload, confirm: true }, task.label);
  });
  $$("[data-close-modal]").forEach((b) => b.addEventListener("click", closeModals));
  $$(".modal").forEach((m) => {
    m.addEventListener("click", (e) => {
      if (e.target === m) closeModals();
    });
  });

  $("#btn-plan-all").addEventListener("click", () => {
    const task = state.tasks.find((t) => t.id === "plan-all");
    if (task) requestRun(task);
  });
  $("#btn-push-all").addEventListener("click", () => {
    const task = state.tasks.find((t) => t.id === "push-all");
    if (task) requestRun(task);
  });
  $("#btn-tools-list").addEventListener("click", () => {
    const task = state.tasks.find((t) => t.id === "tools-list");
    if (task) requestRun(task);
  });
  $("#btn-setup").addEventListener("click", () => {
    const task = state.tasks.find((t) => t.id === "setup-python");
    if (task) requestRun(task);
  });
  $("#btn-tests").addEventListener("click", () => {
    const task = state.tasks.find((t) => t.id === "core-tests");
    if (task) requestRun(task);
  });
  $("#btn-refresh-reports").addEventListener("click", loadReports);
  $("#btn-clear-console").addEventListener("click", clearConsole);
  $("#btn-toggle-console").addEventListener("click", () => {
    $("#console-pane").classList.toggle("collapsed");
  });

  $("#new-site-domains").addEventListener("keydown", (e) => {
    if (e.key === "Enter") createSites();
  });
}

async function boot() {
  bindTabs();
  bindGlobal();
  try {
    const [tasks, tools, sites] = await Promise.all([
      api("/api/tasks"),
      api("/api/tools"),
      api("/api/sites"),
    ]);
    state.tasks = tasks.tasks || [];
    state.tools = tools.tools || [];
    state.sites = sites.sites || [];
    renderSiteList();
    renderWorkflow();
    renderTools();
    if (state.sites.length === 1) {
      selectSite(state.sites[0].key);
    }
  } catch (err) {
    appendConsole(`Failed to load UI data: ${err.message}\n`);
    setConsoleStatus("failed");
  }
}

boot();
