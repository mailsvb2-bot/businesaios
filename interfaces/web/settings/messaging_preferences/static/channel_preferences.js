(function () {
  const cfg = window.__MESSAGING_PREFS__ || {};
  const app = document.getElementById("messaging-preferences-app");
  function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (typeof text === "string") node.textContent = text; return node; }
  function checkboxItem(item, state) {
    const row = el("div", "mp-item");
    const check = document.createElement("input");
    check.type = "checkbox"; check.checked = !!item.enabled; check.dataset.channel = item.key;
    check.addEventListener("change", function () {
      if (check.checked) { if (!state.enabled.includes(item.key)) state.enabled.push(item.key); }
      else { state.enabled = state.enabled.filter(function (x) { return x !== item.key; }); if (state.primary === item.key) state.primary = state.enabled[0] || "telegram"; }
      render(app, state);
    });
    const meta = el("div"); meta.appendChild(el("span", "mp-item-label", item.label)); meta.appendChild(el("div", "mp-item-desc", item.description));
    const tags = el("div", "mp-tags"); if (item.primary) tags.appendChild(el("span", "mp-tag mp-tag-primary", "Primary")); if (item.verified) tags.appendChild(el("span", "mp-tag mp-tag-verified", "Verified"));
    row.appendChild(check); row.appendChild(meta); row.appendChild(tags); return row;
  }
  function primarySection(state) { const box = el("div", "mp-primary-row"); box.appendChild(el("div", "mp-group-title", "Primary channel")); const select = document.createElement("select"); select.className = "mp-primary-select"; state.enabled.forEach(function (key) { const option = document.createElement("option"); option.value = key; option.textContent = key; option.selected = key === state.primary; select.appendChild(option); }); select.addEventListener("change", function () { state.primary = select.value; }); box.appendChild(select); return box; }
  function groupSection(group, state) { const box = el("section", "mp-group"); box.appendChild(el("div", "mp-group-title", group.title)); group.items.forEach(function (item) { box.appendChild(checkboxItem(item, state)); }); return box; }
  function saveBar(state) { const wrap = el("div"); const actions = el("div", "mp-actions"); const save = el("button", "mp-btn mp-btn-primary", "Save"); const status = el("div", "mp-status"); save.addEventListener("click", async function () { status.textContent = "Saving..."; const payload = { primary: state.primary, enabled: state.enabled, verified: state.verified || [] }; const res = await fetch(cfg.saveEndpoint, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(payload) }); const data = await res.json(); status.textContent = data && data.saved_value ? "Saved" : "Save failed"; }); actions.appendChild(save); wrap.appendChild(actions); wrap.appendChild(status); return wrap; }
  function render(root, state) { root.innerHTML = ""; const shell = el("div", "mp-shell"); const header = el("div", "mp-header"); header.appendChild(el("h1", "mp-title", "Messaging preferences")); header.appendChild(el("p", "mp-subtitle", "Choose several channels and set one primary channel.")); shell.appendChild(header); shell.appendChild(primarySection(state)); state.groups.forEach(function (group) { shell.appendChild(groupSection(group, state)); }); shell.appendChild(saveBar(state)); root.appendChild(shell); }
  async function boot() { const res = await fetch(cfg.modelEndpoint, { method: "GET" }); const model = await res.json(); const state = { primary: model.primary, enabled: model.enabled.slice(), verified: model.verified.slice(), groups: model.groups }; render(app, state); }
  boot();
})();
