// Cekar page script: dialogs, snackbar, live updates, the add field, drag reorder.
// Every feature degrades to plain links and forms when this script does not run:
// the pages are server-rendered and every action is a normal form post.
(function () {
  "use strict";
  var DIALOG_HEADER = { "X-Cekar-Dialog": "1" };
  var FORM_HEADER = { "Content-Type": "application/x-www-form-urlencoded" };
  var POLL_MS = 4000;
  var SNACKBAR_MS = 10000;
  var overlay = document.getElementById("overlay");

  function fail(error) {
    console.error(error);
    toast(error.message || String(error));
  }

  function formBody(form, submitter) {
    var data = new URLSearchParams(new FormData(form));
    if (submitter && submitter.name) { data.append(submitter.name, submitter.value); }
    return data;
  }

  /* ---------- dialogs ---------- */
  function closeOverlay() { if (overlay) { overlay.innerHTML = ""; } }

  function show(html) {
    overlay.innerHTML = html;
    var first = overlay.querySelector("input:not([type=hidden]), select, textarea");
    if (first && !overlay.querySelector(".chooser, .confirm")) { first.focus(); }
    overlay.querySelectorAll("form[data-expense]").forEach(initExpenseForm);
    initTripForms(overlay);
  }

  function openDialog(href) {
    fetch(href, { headers: DIALOG_HEADER, credentials: "same-origin" })
      .then(function (r) { return r.text(); })
      .then(show)
      .catch(function () { window.location.href = href; });
  }

  function submitDialog(form, submitter) {
    var action = (submitter && submitter.getAttribute("formaction")) || form.getAttribute("action") || window.location.href;
    fetch(action, {
      method: (form.getAttribute("method") || "get").toUpperCase(),
      body: formBody(form, submitter), credentials: "same-origin",
      headers: Object.assign({}, FORM_HEADER, DIALOG_HEADER)
    }).then(function (r) {
      if (r.redirected) { window.location.href = r.url; return null; }
      if (!r.ok && r.status !== 422) { form.submit(); return null; }
      return r.text().then(show);
    }).catch(function () { form.submit(); });
  }

  document.addEventListener("click", function (event) {
    var confirmer = event.target.closest("[data-confirm]");
    if (confirmer && !window.confirm(confirmer.getAttribute("data-confirm"))) {
      event.preventDefault();
      return;
    }
    var closer = event.target.closest("[data-close]");
    if (closer && overlay && overlay.contains(closer)) {
      event.preventDefault();
      closeOverlay();
      return;
    }
    var scrim = event.target.closest("[data-scrim]");
    if (scrim && event.target === scrim && overlay && overlay.contains(scrim)) { closeOverlay(); return; }
    var snackClose = event.target.closest("[data-snack-close]");
    if (snackClose) {
      event.preventDefault();
      hideSnackbar();
      return;
    }
    var opener = event.target.closest("a[data-dialog]");
    if (opener && !event.ctrlKey && !event.metaKey && !event.shiftKey && overlay) {
      event.preventDefault();
      openDialog(opener.href);
      return;
    }
    var suggestion = event.target.closest(".suggest button[data-name]");
    if (suggestion) {
      pickSuggestion(suggestion);
      return;
    }
    document.querySelectorAll("details.user-wrap[open]").forEach(function (menu) {
      if (!menu.contains(event.target)) { menu.removeAttribute("open"); }
    });
  });

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") {
      closeOverlay();
      document.querySelectorAll("details.user-wrap[open]").forEach(function (menu) { menu.removeAttribute("open"); });
      clearSuggestions();
      return;
    }
    var input = event.target.closest && event.target.closest("form[data-add] input[name=name]");
    if (input) { suggestionKeys(event, input); }
  });

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (form.matches("form[data-add]")) {
      event.preventDefault();
      addItem(form);
    } else if (form.matches("form[data-ajax]")) {
      event.preventDefault();
      postAndRefresh(form);
    } else if (overlay && overlay.contains(form)) {
      event.preventDefault();
      submitDialog(form, event.submitter);
    }
  });

  /* ---------- toast (a background action failed) ---------- */
  function toast(message) {
    var old = document.querySelector(".toast");
    if (old) { old.remove(); }
    var node = document.createElement("div");
    node.className = "toast";
    node.setAttribute("role", "status");
    node.textContent = message;
    document.body.appendChild(node);
    setTimeout(function () { node.remove(); }, 3000);
  }

  /* ---------- delete snackbar (design D17) ---------- */
  function hideSnackbar() {
    var bar = document.getElementById("snackbar");
    if (bar) { bar.remove(); }
  }

  (function () {
    var bar = document.getElementById("snackbar");
    if (!bar) { return; }
    // Drop ?undo=... so a reload does not show the message again.
    history.replaceState(null, "", bar.getAttribute("data-return"));
    setTimeout(hideSnackbar, SNACKBAR_MS);
  })();

  /* ---------- live regions: poll a version, swap a fragment (design D9) ---------- */
  function region() { return document.querySelector("[data-live]"); }

  function refreshLive(highlight) {
    var live = region();
    if (!live) { return Promise.resolve(); }
    refreshChips().catch(function (error) { console.error("chips refresh failed", error); });
    var open = Array.prototype.map.call(live.querySelectorAll("details[open]"), function (d) { return d.id; });
    var fragment = live.getAttribute("data-fragment-url") + (highlight ? "?hl=" + encodeURIComponent(highlight) : "");
    return fetch(fragment, { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.text();
    }).then(function (html) {
      live.outerHTML = html;
      open.forEach(function (id) {
        var details = id && document.getElementById(id);
        if (details) { details.open = true; }
      });
    });
  }

  // The list switcher (chips) is polled like the items, with its own version.
  function chipsRegion() { return document.querySelector("[data-live-chips]"); }

  function refreshChips() {
    var chips = chipsRegion();
    if (!chips) { return Promise.resolve(); }
    return fetch(chips.getAttribute("data-fragment-url"), { credentials: "same-origin" }).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return r.text();
    }).then(function (html) { chips.outerHTML = html; });
  }

  function pollChips() {
    var chips = chipsRegion();
    if (document.hidden || !chips) { return; }
    fetch(chips.getAttribute("data-version-url"), { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) { throw new Error("HTTP " + r.status); }
        return r.text();
      })
      .then(function (version) {
        if (version.trim() !== chips.getAttribute("data-version")) { return refreshChips(); }
      })
      .catch(function (error) { console.error("chips poll failed", error); });
  }

  function poll() {
    pollChips();
    var live = region();
    if (document.hidden || !live) { return; }
    fetch(live.getAttribute("data-version-url"), { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) { throw new Error("HTTP " + r.status); }
        return r.text();
      })
      .then(function (version) {
        if (version.trim() !== live.getAttribute("data-version")) { return refreshLive(); }
      })
      .catch(function (error) { console.error("poll failed", error); });
  }

  if (region() || chipsRegion()) {
    setInterval(poll, POLL_MS);
    document.addEventListener("visibilitychange", function () { if (!document.hidden) { poll(); } });
  }

  // A small form (check box, ...) posted in the background; then the region is refreshed.
  function postAndRefresh(form) {
    fetch(form.getAttribute("action"), {
      method: "POST", body: formBody(form), credentials: "same-origin", headers: FORM_HEADER
    }).then(function (r) {
      if (!r.ok) { throw new Error("HTTP " + r.status); }
      return refreshLive();
    }).catch(function (error) { fail(error); });
  }

  /* ---------- add field: suggestions, quantity, "for" toggle ---------- */
  var suggestTimer = null;

  function clearSuggestions() {
    var box = document.getElementById("suggest");
    if (box) { box.innerHTML = ""; }
  }

  function loadSuggestions(form, input) {
    var query = input.value.trim();
    if (!query) { clearSuggestions(); return; }
    fetch(form.getAttribute("data-suggest-url") + "?q=" + encodeURIComponent(query), { credentials: "same-origin" })
      .then(function (r) {
        if (!r.ok) { throw new Error("HTTP " + r.status); }
        return r.text();
      })
      .then(function (html) {
        if (input.value.trim() === query) { document.getElementById("suggest").innerHTML = html; }
      })
      .catch(function (error) { console.error("suggestions failed", error); });
  }

  document.addEventListener("input", function (event) {
    var input = event.target;
    if (input.matches && input.matches("form[data-add] input[name=name]")) {
      clearTimeout(suggestTimer);
      suggestTimer = setTimeout(function () { loadSuggestions(input.form, input); }, 150);
    } else if (input.matches && input.matches("form[data-expense] [name^=exact_], form[data-expense] [name=amount]")) {
      updateLeft(input.form);
    }
  });

  document.addEventListener("focusout", function (event) {
    if (event.target.matches && event.target.matches("form[data-add] input[name=name]")) {
      setTimeout(clearSuggestions, 200);
    }
  });

  function pickSuggestion(button) {
    var form = document.querySelector("form[data-add]");
    form.elements.name.value = button.getAttribute("data-name");
    clearSuggestions();
    form.requestSubmit();
  }

  function suggestionKeys(event, input) {
    var buttons = Array.prototype.slice.call(document.querySelectorAll("#suggest button[data-name]"));
    if (!buttons.length) { return; }
    var current = buttons.findIndex(function (b) { return b.classList.contains("hl"); });
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      var step = event.key === "ArrowDown" ? 1 : -1;
      var next = (current + step + buttons.length + (current < 0 && step < 0 ? 1 : 0)) % buttons.length;
      buttons.forEach(function (b, i) { b.classList.toggle("hl", i === next); });
    } else if (event.key === "Enter" && current >= 0) {
      event.preventDefault();
      pickSuggestion(buttons[current]);
    }
  }

  function addItem(form) {
    if (!form.elements.name.value.trim()) { return; }
    fetch(form.getAttribute("action"), {
      method: "POST", body: formBody(form), credentials: "same-origin", headers: FORM_HEADER
    }).then(function (r) {
      if (!r.redirected) { form.submit(); return null; } // the server shows the error
      form.elements.name.value = "";
      form.elements.quantity.value = "";
      if (form.elements.for_whom) {
        form.elements.for_whom.selectedIndex = 0;
        form.elements.for_whom.dispatchEvent(new Event("change"));
      }
      clearSuggestions();
      form.elements.name.focus();
      return refreshLive(new URL(r.url).searchParams.get("hl"));
    }).catch(function (error) { fail(error); });
  }

  // With two members or fewer the "for" select becomes a button that cycles
  // through "shared" and each member; with more it stays a small picker.
  function initForToggle() {
    var select = document.querySelector("form[data-add] select[data-cycle]");
    if (!select) { return; }
    var sprite = document.body.getAttribute("data-sprite");
    var button = document.createElement("button");
    button.type = "button";
    button.className = "for-toggle";
    button.setAttribute("aria-label", select.getAttribute("aria-label"));
    function draw() {
      var person = select.selectedIndex > 0;
      var icon = person ? "account" : "account-multiple";
      button.classList.toggle("on", person);
      button.innerHTML = '<svg class="mdi" width="18" height="18" aria-hidden="true"><use href="' + sprite + "#" + icon + '"/></svg><span></span>';
      button.lastChild.textContent = select.options[select.selectedIndex].text;
    }
    button.addEventListener("click", function () {
      select.selectedIndex = (select.selectedIndex + 1) % select.options.length;
      draw();
    });
    select.addEventListener("change", draw);
    select.hidden = true;
    select.parentNode.insertBefore(button, select);
    draw();
  }
  initForToggle();

  /* ---------- drag to reorder the unchecked items ---------- */
  document.addEventListener("pointerdown", function (event) {
    var handle = event.target.closest(".handle");
    if (!handle) { return; }
    var row = handle.closest(".row");
    var list = row.parentNode;
    event.preventDefault();
    row.classList.add("dragging");
    handle.setPointerCapture(event.pointerId);

    function move(ev) {
      var others = Array.prototype.filter.call(list.children, function (c) { return c !== row; });
      var next = others.find(function (c) {
        var box = c.getBoundingClientRect();
        return ev.clientY < box.top + box.height / 2;
      });
      list.insertBefore(row, next || null);
    }
    function up() {
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", up);
      handle.removeEventListener("pointercancel", up);
      row.classList.remove("dragging");
      var ids = new URLSearchParams();
      list.querySelectorAll("[data-item]").forEach(function (r) { ids.append("ids", r.getAttribute("data-item")); });
      fetch(list.getAttribute("data-reorder-url"), {
        method: "POST", body: ids, credentials: "same-origin", headers: FORM_HEADER
      }).then(function (r) {
        if (!r.ok) { throw new Error("HTTP " + r.status); }
      }).catch(function (error) { fail(error); });
    }
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", up);
    handle.addEventListener("pointercancel", up);
  });

  /* ---------- expense form: "For <person>" follows the payer; exact amounts add up ---------- */
  function parseCents(text) {
    var match = /^(\d+)(?:[.,](\d{1,2}))?$/.exec(text.trim());
    return match ? parseInt(match[1], 10) * 100 + parseInt(((match[2] || "") + "00").slice(0, 2), 10) : null;
  }

  function euros(cents) { return "€" + (cents / 100).toFixed(2); }

  function updateLeft(form) {
    var line = form.querySelector(".left-line");
    var submit = form.querySelector("button[type=submit]:not([formaction])");
    if (!line || !submit) { return; }
    var exact = form.querySelector("input[name=split][value=exact]").checked;
    var total = parseCents(form.elements.amount.value);
    var sum = 0;
    form.querySelectorAll("[name^=exact_]").forEach(function (f) { sum += parseCents(f.value || "0") || 0; });
    var left = total === null ? null : total - sum;
    line.className = "left-line " + (left === 0 ? "ok" : "bad");
    line.innerHTML = "<span></span><b></b>";
    line.firstChild.textContent = left === 0 ? line.getAttribute("data-ok") : line.getAttribute(left !== null && left < 0 ? "data-over" : "data-left");
    line.lastChild.textContent = left === null ? "–" : euros(Math.abs(left));
    submit.disabled = exact && left !== 0;
  }

  function syncForPerson(form) {
    var payer = form.elements.payer.value;
    var label = form.querySelector("[data-for-label]");
    if (label) {
      var members = JSON.parse(form.getAttribute("data-members"));
      var other = members.filter(function (m) { return m[0] !== payer; })[0];
      label.textContent = form.getAttribute("data-for-template").replace("{name}", other ? other[1] : "");
    }
    var pick = form.elements.for_user;
    if (pick) {
      Array.prototype.forEach.call(pick.options, function (o) { o.hidden = o.value === payer; o.disabled = o.value === payer; });
      if (pick.value === payer) {
        var first = Array.prototype.filter.call(pick.options, function (o) { return !o.disabled; })[0];
        if (first) { pick.value = first.value; }
      }
    }
  }

  function initExpenseForm(form) {
    syncForPerson(form);
    updateLeft(form);
  }

  document.addEventListener("change", function (event) {
    var form = event.target.form;
    if (!form || !form.matches("form[data-expense]")) { return; }
    if (event.target.name === "payer") { syncForPerson(form); }
    if (event.target.name === "split") { updateLeft(form); }
  });
  document.querySelectorAll("form[data-expense]").forEach(initExpenseForm);

  /* ---------- Done shopping: preview of the expenses that will be recorded ---------- */
  function initTripForm(form) {
    var data = JSON.parse(form.getAttribute("data-trip"));
    var box = form.querySelector("#trip-preview");
    var submit = form.querySelector("button[type=submit]");
    var sprite = document.body.getAttribute("data-sprite");
    function icon(name) {
      return '<svg class="mdi" width="20" height="20" aria-hidden="true"><use href="' + sprite + "#" + name + '"/></svg>';
    }
    function row(iconName, title, label, cents) {
      var el = document.createElement("div");
      el.className = "mini-row";
      el.innerHTML = icon(iconName) + '<span class="t"></span><span class="a"></span>';
      el.querySelector(".t").textContent = title;
      var small = document.createElement("small");
      small.textContent = label;
      el.querySelector(".t").appendChild(small);
      el.querySelector(".a").textContent = euros(cents);
      return el;
    }
    function draw() {
      var total = parseCents(form.elements.total.value);
      var payer = form.elements.payer.value;
      var sum = 0;
      var byPerson = {};
      data.priced.forEach(function (item) {
        var cents = parseCents((form.elements["price_" + item.id] || { value: "" }).value);
        if (cents) { sum += cents; (byPerson[item.for] = byPerson[item.for] || []).push({ item: item, cents: cents }); }
      });
      box.innerHTML = "";
      if (total === null) { submit.disabled = false; return; }
      if (sum > total) {
        var alert = document.createElement("div");
        alert.className = "alert error";
        alert.setAttribute("role", "alert");
        alert.textContent = data.exceed.replace("{prices}", euros(sum)).replace("{total}", euros(total));
        box.appendChild(alert);
        submit.disabled = true;
        return;
      }
      submit.disabled = false;
      var list = document.createElement("div");
      list.className = "mini-list";
      data.members.forEach(function (id) {
        var owned = byPerson[id];
        if (!owned) { return; }
        var cents = owned.reduce(function (a, o) { return a + o.cents; }, 0);
        var names = owned.map(function (o) { return o.item.name; }).join(", ");
        var mine = id === payer;
        list.appendChild(row(mine ? "account" : "arrow-right", data.list + ": " + names,
          mine ? data.personal : data.forTemplate.replace("{name}", owned[0].item.forName), cents));
      });
      if (total - sum > 0) { list.appendChild(row("account-multiple", data.list, data.equal, total - sum)); }
      box.appendChild(list);
    }
    form.addEventListener("input", draw);
    form.addEventListener("change", draw);
    draw();
  }

  function initTripForms(root) {
    root.querySelectorAll("form[data-trip]").forEach(initTripForm);
  }
  initTripForms(document);

  /* ---------- switches in Settings save on change ---------- */
  document.addEventListener("change", function (event) {
    if (event.target.matches && event.target.matches("[data-autosubmit]") && event.target.form) {
      event.target.form.submit();
    }
  });
})();
