// Cekar page script: dialogs and small helpers.
// Every feature degrades to plain links and forms when this script does not run.
(function () {
  "use strict";
  var DIALOG_HEADER = { "X-Cekar-Dialog": "1" };
  var overlay = document.getElementById("overlay");

  /* ---------- dialogs ---------- */
  function closeOverlay() { if (overlay) { overlay.innerHTML = ""; } }

  function show(html) {
    overlay.innerHTML = html;
    var first = overlay.querySelector("input:not([type=hidden]), select, textarea");
    if (first && !overlay.querySelector(".chooser, .confirm")) { first.focus(); }
  }

  function openDialog(href) {
    fetch(href, { headers: DIALOG_HEADER, credentials: "same-origin" })
      .then(function (r) { return r.text(); })
      .then(show)
      .catch(function () { window.location.href = href; });
  }

  function submitDialog(form, submitter) {
    var data = new URLSearchParams(new FormData(form));
    if (submitter && submitter.name) { data.append(submitter.name, submitter.value); }
    var action = (submitter && submitter.getAttribute("formaction")) || form.getAttribute("action") || window.location.href;
    fetch(action, {
      method: (form.getAttribute("method") || "get").toUpperCase(),
      body: data, redirect: "manual", credentials: "same-origin",
      headers: Object.assign({ "Content-Type": "application/x-www-form-urlencoded" }, DIALOG_HEADER)
    }).then(function (r) {
      if (r.type === "opaqueredirect" || (r.status >= 300 && r.status < 400)) {
        window.location.reload();
        return null;
      }
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
    if (scrim && event.target === scrim) { closeOverlay(); return; }
    var opener = event.target.closest("a[data-dialog]");
    if (opener && !event.ctrlKey && !event.metaKey && !event.shiftKey && overlay) {
      event.preventDefault();
      openDialog(opener.href);
    }
    var pop = document.querySelector("details.customise[open]");
    if (pop && !pop.contains(event.target)) { pop.removeAttribute("open"); }
  });

  document.addEventListener("keydown", function (event) {
    if (event.key !== "Escape") { return; }
    closeOverlay();
    var pop = document.querySelector("details.customise[open]");
    if (pop) { pop.removeAttribute("open"); }
  });

  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (overlay && overlay.contains(form)) {
      event.preventDefault();
      submitDialog(form, event.submitter);
    }
  });

  /* ---------- toast ---------- */
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
})();
