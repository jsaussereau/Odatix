// ********************************************************************** //
//                                Odatix                                  //
// ********************************************************************** //
//
// File browser of the path fields (ui.path_input). The browser of the user
// may run on another machine than the GUI, and a path field holds a path of
// the server: the listing is asked to the server (gui/file_browser.py), one
// directory at a time, and never goes out of the workspace.
//
// A click on a ".odx-path-browse" button opens the modal on the directory of
// the field's value. The selection is written back with
// dash_clientside.set_props, so the callbacks of the field run as if it had
// been typed. Pure vanilla JS: the modal is injected into <body> on first use.

(function () {
  "use strict";

  var LIST_URL = "/_odatix/fs/list";
  var CODE_EXT = ["v", "sv", "vh", "svh", "vhd", "vhdl", "scala", "py", "tcl", "sdc", "xdc", "c", "cpp", "h", "hpp", "sh", "mk"];

  var el = {};          // elements of the modal
  var state = null;     // the session of the open modal

  function icon(name, size) {
    var span = document.createElement("span");
    span.className = "odx-icon";
    span.setAttribute("data-icon", name);
    span.style.width = span.style.height = (size || 18) + "px";
    return span;
  }

  function make(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function build() {
    el.overlay = make("div", "odx-fb-overlay");
    el.overlay.setAttribute("role", "dialog");
    el.overlay.setAttribute("aria-modal", "true");
    var dialog = make("div", "odx-fb-dialog");
    el.overlay.appendChild(dialog);

    var head = make("div", "odx-fb-head");
    el.title = make("h3", "odx-fb-title");
    var close = make("button", "odx-fb-close");
    close.type = "button";
    close.title = "Close (Esc)";
    close.appendChild(icon("cross", 16));
    close.addEventListener("click", hide);
    head.appendChild(el.title);
    head.appendChild(close);

    var bar = make("div", "odx-fb-bar");
    el.crumbs = make("nav", "odx-fb-crumbs");
    el.filter = make("input", "odx-fb-filter");
    el.filter.type = "search";
    el.filter.placeholder = "Filter";
    el.filter.spellcheck = false;
    el.filter.addEventListener("input", function () { state.cursor = -1; render(); });
    el.hidden = make("label", "odx-fb-hidden");
    el.hiddenBox = make("input");
    el.hiddenBox.type = "checkbox";
    el.hiddenBox.addEventListener("change", function () {
      state.showHidden = el.hiddenBox.checked;
      load(state.path);
      el.filter.focus();
    });
    el.hidden.appendChild(el.hiddenBox);
    el.hidden.appendChild(document.createTextNode("Hidden"));
    bar.appendChild(el.crumbs);
    bar.appendChild(el.filter);
    bar.appendChild(el.hidden);

    el.list = make("div", "odx-fb-list");
    el.list.setAttribute("role", "listbox");
    el.note = make("div", "odx-fb-note");

    var foot = make("div", "odx-fb-foot");
    el.result = make("code", "odx-fb-result");
    var buttons = make("div", "odx-fb-buttons");
    var cancel = make("button", "odx-fb-button", "Cancel");
    cancel.type = "button";
    cancel.addEventListener("click", hide);
    el.select = make("button", "odx-fb-button primary", "Select");
    el.select.type = "button";
    el.select.addEventListener("click", confirm);
    buttons.appendChild(cancel);
    buttons.appendChild(el.select);
    foot.appendChild(el.result);
    foot.appendChild(buttons);

    dialog.appendChild(head);
    dialog.appendChild(bar);
    dialog.appendChild(el.list);
    dialog.appendChild(el.note);
    dialog.appendChild(foot);

    el.overlay.addEventListener("mousedown", function (e) {
      if (e.target === el.overlay) hide();
    });
    el.overlay.addEventListener("keydown", onKey);
    // Inside the themed container: the theme's variables are set on it.
    (document.getElementById("theme") || document.body).appendChild(el.overlay);
  }

  // --- paths ------------------------------------------------------------- //

  function join(dir, name) {
    return dir ? dir + "/" + name : name;
  }

  function parentOf(path) {
    var i = path.lastIndexOf("/");
    return i < 0 ? "" : path.slice(0, i);
  }

  // `target` (relative to the workspace) as written relative to `base`.
  function relativeTo(target, base) {
    if (!base) return target || ".";
    var t = target ? target.split("/") : [];
    var b = base.split("/");
    var i = 0;
    while (i < t.length && i < b.length && t[i] === b[i]) i++;
    var parts = [];
    for (var j = i; j < b.length; j++) parts.push("..");
    parts = parts.concat(t.slice(i));
    return parts.length ? parts.join("/") : ".";
  }

  function extensionOf(name) {
    var i = name.lastIndexOf(".");
    return i <= 0 ? "" : name.slice(i + 1).toLowerCase();
  }

  // --- data -------------------------------------------------------------- //

  function query(params) {
    var parts = [];
    for (var key in params) {
      parts.push(encodeURIComponent(key) + "=" + encodeURIComponent(params[key]));
    }
    return LIST_URL + "?" + parts.join("&");
  }

  function fetchListing(params) {
    var session = state;
    session.loading = true;
    el.list.classList.add("loading");
    return fetch(query(params), { credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (session !== state) return;
        session.loading = false;
        el.list.classList.remove("loading");
        if (data.error) {
          session.error = data.error;
          render();
          return;
        }
        session.error = "";
        session.path = data.path;
        session.root = data.root;
        session.rootName = data.root_name;
        session.entries = data.entries;
        session.hiddenCount = data.hidden;
        session.truncated = data.truncated;
        if (data.base !== undefined && params.open) session.base = data.base;
        session.cursor = -1;
        el.filter.value = "";
        var select = params.select !== undefined ? params.select : data.selected;
        if (select) {
          var visible = visibleEntries();
          for (var i = 0; i < visible.length; i++) {
            if (visible[i].name === select) { session.cursor = i; break; }
          }
        }
        render();
        scrollToCursor();
      })
      .catch(function () {
        if (session !== state) return;
        session.loading = false;
        el.list.classList.remove("loading");
        session.error = "The server did not answer.";
        render();
      });
  }

  function load(path, select) {
    var params = { path: path, hidden: state.showHidden ? "1" : "0" };
    if (select !== undefined) params.select = select;
    return fetchListing(params);
  }

  // --- rendering --------------------------------------------------------- //

  function selectable(entry) {
    if (!entry) return false;
    if (entry.parent) return false;
    if (state.mode === "dir") return entry.dir;
    if (entry.dir) return false;
    return !state.extensions.length || state.extensions.indexOf(extensionOf(entry.name)) >= 0;
  }

  function visibleEntries() {
    var filter = (el.filter.value || "").toLowerCase();
    var list = [];
    if (state.path && !filter) list.push({ name: "..", dir: true, parent: true });
    (state.entries || []).forEach(function (entry) {
      if (!filter || entry.name.toLowerCase().indexOf(filter) >= 0) list.push(entry);
    });
    return list;
  }

  function formatSize(size) {
    if (size === null || size === undefined) return "";
    var units = ["B", "kB", "MB", "GB"];
    var i = 0;
    while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
    return (i === 0 ? size : size.toFixed(size < 10 ? 1 : 0)) + " " + units[i];
  }

  function formatDate(seconds) {
    var date = new Date(seconds * 1000);
    var now = new Date();
    if (date.toDateString() === now.toDateString()) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    return date.toLocaleDateString([], { year: "numeric", month: "short", day: "numeric" });
  }

  function entryIcon(entry) {
    if (entry.parent) return icon("parent");
    if (entry.dir) return icon("folder");
    return icon(CODE_EXT.indexOf(extensionOf(entry.name)) >= 0 ? "file_code" : "file");
  }

  function renderCrumbs() {
    el.crumbs.textContent = "";
    var home = make("button", "odx-fb-crumb root");
    home.type = "button";
    home.title = "Workspace root (" + state.root + ")";
    home.appendChild(icon("home", 16));
    home.appendChild(make("span", "", state.rootName || "Workspace"));
    home.addEventListener("click", function () { load(""); el.filter.focus(); });
    el.crumbs.appendChild(home);
    var parts = state.path ? state.path.split("/") : [];
    parts.forEach(function (part, i) {
      el.crumbs.appendChild(make("span", "odx-fb-sep", "/"));
      var target = parts.slice(0, i + 1).join("/");
      var crumb = make("button", "odx-fb-crumb" + (i === parts.length - 1 ? " current" : ""), part);
      crumb.type = "button";
      crumb.addEventListener("click", function () { load(target); el.filter.focus(); });
      el.crumbs.appendChild(crumb);
    });
    el.crumbs.scrollLeft = el.crumbs.scrollWidth;
  }

  function render() {
    renderCrumbs();
    el.list.textContent = "";
    if (state.error) {
      el.list.appendChild(make("div", "odx-fb-empty error", state.error));
    } else {
      var visible = visibleEntries();
      if (!visible.length) {
        el.list.appendChild(make("div", "odx-fb-empty",
          el.filter.value ? "Nothing matches “" + el.filter.value + "”." : "This folder is empty."));
      }
      visible.forEach(function (entry, i) {
        var row = make("div", "odx-fb-row");
        row.setAttribute("role", "option");
        if (entry.dir) row.classList.add("dir");
        if (entry.parent) row.classList.add("parent");
        if (!entry.dir && !selectable(entry)) row.classList.add("muted");
        if (i === state.cursor) {
          row.classList.add("active");
          row.setAttribute("aria-selected", "true");
        }
        row.appendChild(entryIcon(entry));
        row.appendChild(make("span", "odx-fb-name", entry.parent ? "Parent folder" : entry.name));
        row.appendChild(make("span", "odx-fb-size", entry.parent ? "" : formatSize(entry.size)));
        row.appendChild(make("span", "odx-fb-date", entry.parent || !entry.mtime ? "" : formatDate(entry.mtime)));
        // The double click is read from the click itself: the first click
        // redraws the list, so no "dblclick" would ever reach a row.
        row.addEventListener("click", function (e) {
          if (e.detail >= 2) { activate(entry); return; }
          state.cursor = i;
          render();
          el.filter.focus();
        });
        el.list.appendChild(row);
      });
    }

    var notes = [];
    if (state.truncated) notes.push(state.truncated + " more entries not shown: use the filter.");
    if (state.hiddenCount && !state.showHidden) {
      notes.push(state.hiddenCount + " hidden " + (state.hiddenCount > 1 ? "entries" : "entry"));
    }
    if (state.extensions.length && state.mode === "file") {
      notes.push("Selectable: " + state.extensions.map(function (e) { return "." + e; }).join(", "));
    }
    el.note.textContent = notes.join(" · ");
    el.note.style.display = notes.length ? "" : "none";

    var chosen = chosenPath();
    el.result.textContent = chosen === null ? "Nothing selected" : output(chosen);
    el.result.classList.toggle("empty", chosen === null);
    el.select.disabled = chosen === null;
    el.select.textContent = state.mode === "dir" && !selectable(currentEntry()) ? "Select this folder" : "Select";
  }

  function scrollToCursor() {
    var row = el.list.querySelector(".odx-fb-row.active");
    if (row) row.scrollIntoView({ block: "nearest" });
  }

  function currentEntry() {
    return state.cursor >= 0 ? visibleEntries()[state.cursor] : null;
  }

  // The workspace path the "Select" button would write, null when none.
  function chosenPath() {
    var entry = currentEntry();
    if (selectable(entry)) return join(state.path, entry.name);
    if (state.mode === "dir") return state.path;
    return null;
  }

  // A workspace path as the field writes it.
  function output(path) {
    if (state.absolute) return state.root + (path ? "/" + path : "");
    return relativeTo(path, state.base);
  }

  // --- actions ----------------------------------------------------------- //

  function activate(entry) {
    if (!entry) return;
    if (entry.parent) {
      var from = state.path.split("/").pop();
      load(parentOf(state.path), from);
    } else if (entry.dir) {
      load(join(state.path, entry.name));
    } else if (selectable(entry)) {
      state.cursor = visibleEntries().indexOf(entry);
      confirm();
    }
    el.filter.focus();
  }

  function onKey(e) {
    if (!state) return;
    var visible = visibleEntries();
    if (e.key === "Escape") {
      e.preventDefault();
      if (el.filter.value) { el.filter.value = ""; render(); } else hide();
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!visible.length) return;
      var step = e.key === "ArrowDown" ? 1 : -1;
      state.cursor = state.cursor < 0 ? (step > 0 ? 0 : visible.length - 1)
        : Math.max(0, Math.min(visible.length - 1, state.cursor + step));
      render();
      scrollToCursor();
    } else if (e.key === "Enter") {
      e.preventDefault();
      var entry = currentEntry();
      if (!entry && visible.length === 1) entry = visible[0];
      if ((e.ctrlKey || e.metaKey) && chosenPath() !== null) confirm();
      else if (entry) activate(entry);
      else if (state.mode === "dir" && !el.filter.value) confirm();
    } else if (e.key === "Backspace" && document.activeElement === el.filter && !el.filter.value && state.path) {
      e.preventDefault();
      activate({ parent: true });
    } else if (e.key === "Tab") {
      // The focus stays in the modal.
      var focusable = el.overlay.querySelectorAll("button:not([disabled]), input");
      var first = focusable[0], last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  }

  function dashId(node) {
    var id = node.id;
    if (id && id.charAt(0) === "{") {
      try { return JSON.parse(id); } catch (err) { return id; }
    }
    return id;
  }

  function confirm() {
    var chosen = chosenPath();
    if (chosen === null) return;
    var value = output(chosen);
    var field = state.field;
    if (state.append) {
      var lines = (field.value || "").split("\n").filter(function (l) { return l.trim() !== ""; });
      if (lines.indexOf(value) < 0) lines.push(value);
      value = lines.join("\n");
    }
    var setProps = window.dash_clientside && window.dash_clientside.set_props;
    if (setProps && field.id) {
      setProps(dashId(field), { value: value });
    }
    hide();
    field.focus();
  }

  function hide() {
    if (!el.overlay) return;
    el.overlay.classList.remove("visible");
    state = null;
  }

  function open(button) {
    var wrapper = button.closest(".odx-path-input");
    var field = wrapper && wrapper.querySelector("input, textarea");
    if (!field) return;
    if (!el.overlay) build();
    else if (!document.body.contains(el.overlay)) {
      (document.getElementById("theme") || document.body).appendChild(el.overlay);
    }

    var base = button.getAttribute("data-base") || "";
    var baseInputId = button.getAttribute("data-base-input");
    if (baseInputId) {
      var baseInput = document.getElementById(baseInputId);
      if (baseInput && baseInput.value.trim()) base = baseInput.value.trim();
    }
    var append = button.getAttribute("data-append") === "1";
    var value = append ? "" : (field.value || "").trim();
    if (append) {
      // Open where the last listed file is.
      var lines = (field.value || "").split("\n").filter(function (l) { return l.trim() && l.indexOf("*") < 0; });
      if (lines.length) value = lines[lines.length - 1].trim();
    }
    var extensions = (button.getAttribute("data-extensions") || "").split(",")
      .map(function (e) { return e.trim().replace(/^\./, "").toLowerCase(); })
      .filter(function (e) { return e; });

    state = {
      field: field,
      mode: button.getAttribute("data-mode") === "dir" ? "dir" : "file",
      extensions: extensions,
      base: base,
      append: append,
      absolute: value.charAt(0) === "/",
      showHidden: false,
      path: "",
      entries: [],
      cursor: -1,
      error: "",
    };
    el.hiddenBox.checked = false;
    el.filter.value = "";
    el.title.textContent = state.mode === "dir" ? "Select a folder" : (append ? "Add a file" : "Select a file");
    el.list.textContent = "";
    el.overlay.classList.add("visible");
    el.filter.focus();
    requestAnimationFrame(function () { if (state) el.filter.focus(); });
    fetchListing({ open: "1", base: base, value: value, hidden: "0" });
  }

  document.addEventListener("click", function (e) {
    var button = e.target.closest && e.target.closest(".odx-path-browse");
    if (!button || button.disabled) return;
    e.preventDefault();
    open(button);
  });
})();
