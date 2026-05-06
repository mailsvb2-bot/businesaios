(function () {
  const cfg = window.__ALERT_SUBSCRIPTIONS__ || {};
  const app = document.getElementById("alert-subscriptions-app");

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (typeof text === "string") node.textContent = text;
    return node;
  }

  function textInput(labelText, value, onChange) {
    const field = el("div", "as-field");
    const label = el("label", "", labelText);
    const input = document.createElement("input");
    input.value = value || "";
    input.addEventListener("input", function () { onChange(input.value); });
    field.appendChild(label);
    field.appendChild(input);
    return field;
  }

  function textArea(labelText, value, onChange) {
    const field = el("div", "as-field");
    const label = el("label", "", labelText);
    const input = document.createElement("textarea");
    input.rows = 3;
    input.value = Array.isArray(value) ? value.join(", ") : (value || "");
    input.addEventListener("input", function () { onChange(input.value); });
    field.appendChild(label);
    field.appendChild(input);
    return field;
  }

  function selectField(labelText, value, options, onChange) {
    const field = el("div", "as-field");
    const label = el("label", "", labelText);
    const select = document.createElement("select");
    options.forEach(function (item) {
      const opt = document.createElement("option");
      opt.value = item.key;
      opt.textContent = item.label;
      opt.selected = item.key === value;
      select.appendChild(opt);
    });
    select.addEventListener("change", function () { onChange(select.value); });
    field.appendChild(label);
    field.appendChild(select);
    return field;
  }

  function checkboxField(labelText, checked, onChange) {
    const wrap = el("div", "as-field");
    const row = el("div", "as-inline");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = !!checked;
    input.addEventListener("change", function () { onChange(input.checked); });
    row.appendChild(input);
    row.appendChild(el("label", "", labelText));
    wrap.appendChild(row);
    return wrap;
  }

  function removeButton(onClick) {
    const btn = el("button", "as-btn", "Remove");
    btn.addEventListener("click", onClick);
    return btn;
  }

  function subscriptionCard(state, item, index) {
    const card = el("section", "as-card");
    const grid = el("div", "as-grid");

    grid.appendChild(textInput("Recipient user id", item.recipient_user_id, function (v) {
      state.items[index].recipient_user_id = v;
    }));

    grid.appendChild(selectField("Channel", item.channel, state.channels, function (v) {
      state.items[index].channel = v;
    }));

    grid.appendChild(selectField("Min level", item.min_level, state.levels, function (v) {
      state.items[index].min_level = v;
    }));

    grid.appendChild(checkboxField("Enabled", item.enabled, function (v) {
      state.items[index].enabled = v;
    }));

    grid.appendChild(textArea("Code filters (comma separated)", item.code_filters, function (v) {
      state.items[index].code_filters = v;
    }));

    grid.appendChild(textArea("User scope (comma separated)", item.user_scope, function (v) {
      state.items[index].user_scope = v;
    }));

    card.appendChild(grid);

    const actions = el("div", "as-row-actions");
    actions.appendChild(removeButton(function () {
      state.items.splice(index, 1);
      render(app, state);
    }));
    card.appendChild(actions);

    return card;
  }

  function normalizedPayload(state) {
    return {
      items: state.items.map(function (item) {
        return {
          recipient_user_id: item.recipient_user_id || "",
          channel: item.channel || "telegram",
          min_level: item.min_level || "warn",
          enabled: !!item.enabled,
          code_filters: typeof item.code_filters === "string"
            ? item.code_filters.split(",").map(function (x) { return x.trim(); }).filter(Boolean)
            : (item.code_filters || []),
          user_scope: typeof item.user_scope === "string"
            ? item.user_scope.split(",").map(function (x) { return x.trim(); }).filter(Boolean)
            : (item.user_scope || [])
        };
      })
    };
  }

  function render(root, state) {
    root.innerHTML = "";
    const shell = el("div", "as-shell");
    shell.appendChild(el("h1", "as-title", "Alert subscriptions"));
    shell.appendChild(el("p", "as-subtitle", "Manage observability alert notifications for messaging policy."));

    const actions = el("div", "as-actions");
    const addBtn = el("button", "as-btn", "Add subscription");
    addBtn.addEventListener("click", function () {
      state.items.push({
        recipient_user_id: "",
        channel: "telegram",
        min_level: "warn",
        enabled: true,
        code_filters: [],
        user_scope: []
      });
      render(root, state);
    });

    const saveBtn = el("button", "as-btn", "Save");
    const status = el("div", "as-status");

    saveBtn.addEventListener("click", async function () {
      status.textContent = "Saving...";
      const res = await fetch(cfg.saveEndpoint, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(normalizedPayload(state))
      });
      const data = await res.json();
      status.textContent = data && data.saved_value ? "Saved" : "Save failed";
    });

    actions.appendChild(addBtn);
    actions.appendChild(saveBtn);
    shell.appendChild(actions);

    state.items.forEach(function (item, index) {
      shell.appendChild(subscriptionCard(state, item, index));
    });

    shell.appendChild(status);
    root.appendChild(shell);
  }

  async function boot() {
    const res = await fetch(cfg.modelEndpoint, { method: "GET" });
    const model = await res.json();
    const state = {
      items: model.items.slice(),
      channels: model.channels.slice(),
      levels: model.levels.slice()
    };
    render(app, state);
  }

  boot();
})();
