/**********************************************************************\
*                                Odatix                                *
************************************************************************
*
* Copyright (C) 2022 Jonathan Saussereau
*
* This file is part of Odatix.
* Odatix is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* Odatix is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with Odatix. If not, see <https://www.gnu.org/licenses/>.
*
*/

/*
 * Highlight ${...} variables inside command fields: the workflow task
 * "commands" textareas, the architecture "generate command" input, and the two
 * templates of a parameter domain's configuration rules.
 *
 * An input/textarea cannot render colored text, so each command field is backed
 * by a mirror <div> that holds the same text with the variables wrapped in
 * colored spans. The field is made transparent (text + background) and sits on
 * top, so the user still types normally while seeing the colors of the mirror.
 *
 * Four colors, by where the ${name} resolves:
 *   - defined variable  : a variable of the instance, either a variable card on
 *                         the page (read live from the DOM) or a window global
 *                         pushed from Python via a clientside callback
 *   - parameter domain  : a physical domain of the instance (window global,
 *                         pushed from Python via a clientside callback)
 *   - built-in variable : one Odatix substitutes itself ($work_path,
 *                         ${rtl_dir}, ...), declared by the page (see
 *                         odatix.gui.builtin_variables) with its description,
 *                         which the hover tooltip shows
 *   - not found         : none of them
 */

(function () {
  // Both ${name} (group 1) and bare $name (group 2, a shell-style identifier).
  var VAR_PATTERN = /\$\{([^}]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)/g;

  // Every highlighted field carries this class, textarea (multi-line) or input
  // (single-line) alike.
  var FIELD_CLASS = "odatix-command-field";
  var FIELD_SELECTOR = "textarea." + FIELD_CLASS + ", input." + FIELD_CLASS;

  function isField(element) {
    return !!(element && element.classList && element.classList.contains(FIELD_CLASS));
  }

  // Style properties the mirror must share with the textarea so the text wraps
  // at exactly the same place and the colors land under the real characters.
  var COPIED_STYLES = [
    "boxSizing", "width",
    "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth",
    // Without them the colors land next to the characters they belong to, by
    // exactly the padding of the field.
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
    "fontFamily", "fontSize", "fontWeight", "fontStyle",
    "lineHeight", "letterSpacing", "wordSpacing", "textTransform", "textIndent",
  ];

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function nameSet(values) {
    var names = new Set();
    (values || []).forEach(function (value) {
      var name = String(value || "").trim();
      if (name) {
        names.add(name);
      }
    });
    return names;
  }

  // The element a page declares its built-in variables in, if any.
  function builtinElement() {
    return document.querySelector("[data-odatix-hl-builtins]");
  }

  // The window globals hold what the last page pushing them left there: a page
  // saying it pushes none of its own must not inherit them.
  function usesGlobals() {
    var element = builtinElement();
    return !(element && element.hasAttribute("data-odatix-hl-no-globals"));
  }

  // A page holding several independent sets of variables (the configuration
  // editor, one rules panel per parameter domain) marks each of them with
  // data-odatix-hl-scope: a field inside one only sees the variables declared
  // in it, and none of the window globals.
  function scopeRoot(field) {
    return (field && field.closest && field.closest("[data-odatix-hl-scope]")) || null;
  }

  function definedVariableNames(root) {
    // The variable cards' title inputs; read live so renaming a variable
    // recolors the commands without a save. Pages without variable cards (the
    // architecture editor) push their variable names from Python instead.
    var names = nameSet(!root && usesGlobals() ? window.__odatixHlVariables : []);
    (root || document).querySelectorAll('input[id*="variable-title"]').forEach(function (input) {
      var value = (input.value || "").trim();
      if (value) {
        names.add(value);
      }
    });
    return names;
  }

  function paramDomainNames(root) {
    return nameSet(!root && usesGlobals() ? window.__odatixHlParamDomains : []);
  }

  // {name: description} of the variables Odatix substitutes itself, declared by
  // the page in a hidden element (see odatix.gui.builtin_variables).
  function builtinVariables() {
    var element = builtinElement();
    if (!element) {
      return {};
    }
    try {
      return JSON.parse(element.getAttribute("data-odatix-hl-builtins")) || {};
    } catch (error) {
      return {};
    }
  }

  // Class + hover description for each kind of ${...} token. A built-in one
  // describes itself, so it has no entry here.
  var KINDS = {
    "wf-hl-var": "user defined variable",
    "wf-hl-domain": "parameter domain",
    "wf-hl-unknown":
      "not detected. This is fine if it is an environment variable, "
      + "otherwise define it as a variable below",
  };

  var TOKEN_CLASSES = [
    "wf-hl-var", "wf-hl-domain", "wf-hl-builtin", "wf-hl-unknown",
    "wf-hl-wildcard", "wf-hl-target", "wf-hl-comment",
  ];

  /*
   * Selector fields (.odatix-selector-field) hold something else than
   * a command: one "selector -> configuration" per line, the selector being a
   * name, a pattern, a regular expression or a condition on $name and $value
   * (see odatix.workspace.selectors). They are highlighted by what a selector is
   * made of -- the values it reads, the wildcards it matches with, and the
   * configuration it points at -- rather than by where a ${...} resolves.
   */
  var SELECTOR_FIELD_CLASS = "odatix-selector-field";

  // What a selector may read, and what it means. Anything else written with a
  // dollar sign is nothing, and is shown as such.
  var SELECTOR_VALUES = {
    name: "name of the configuration being run, as a number when it is one",
    value: "what that configuration substitutes, when it is a single number",
  };

  var SELECTOR_KINDS = {
    "wf-hl-wildcard": "matches any part of a name",
    "wf-hl-target": "the configuration substituted for the ones this selector matches",
    "wf-hl-comment": "comment: this line selects nothing",
  };

  function isSelectorField(field) {
    return !!(field && field.classList && field.classList.contains(SELECTOR_FIELD_CLASS));
  }

  function token(text, cls, tip) {
    return '<span class="wf-hl-token ' + cls + '" data-wf-hl-tip="' + escapeHtml(tip) + '">'
      + escapeHtml(text) + "</span>";
  }

  // The selector half of a line: its values, its wildcards, and the rest as it
  // is written.
  function buildSelectorHtml(text) {
    var html = "";
    // A selector reading a value is a condition, where "*" multiplies and does
    // not stand for anything: only a pattern has wildcards.
    var pattern = /\$/.test(text)
      ? /\$\{([^}]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)/g
      : /[*?]|\[[^\]]*\]/g;
    var lastIndex = 0;
    var match;
    while ((match = pattern.exec(text)) !== null) {
      html += escapeHtml(text.slice(lastIndex, match.index));
      var rawName = match[1] !== undefined ? match[1] : match[2];
      if (rawName === undefined) {
        html += token(match[0], "wf-hl-wildcard", SELECTOR_KINDS["wf-hl-wildcard"]);
      } else {
        var name = rawName.trim();
        var known = Object.prototype.hasOwnProperty.call(SELECTOR_VALUES, name);
        html += token(
          match[0],
          known ? "wf-hl-builtin" : "wf-hl-unknown",
          known
            ? name + ": " + SELECTOR_VALUES[name]
            : name + ": a selector only reads $name and $value"
        );
      }
      lastIndex = match.index + match[0].length;
    }
    return html + escapeHtml(text.slice(lastIndex));
  }

  function buildSelectorsHtml(text) {
    var lines = String(text).split("\n");
    var html = lines.map(function (line) {
      if (!line.trim()) {
        return escapeHtml(line);
      }
      if (line.trim().charAt(0) === "#") {
        return token(line, "wf-hl-comment", SELECTOR_KINDS["wf-hl-comment"]);
      }
      // Both separators the field accepts, the arrow first: a selector may hold
      // a colon of its own, an arrow it never does.
      var at = line.indexOf("->");
      var width = 2;
      if (at === -1) {
        at = line.lastIndexOf(":");
        width = 1;
      }
      if (at === -1) {
        return buildSelectorHtml(line);
      }
      return buildSelectorHtml(line.slice(0, at))
        + escapeHtml(line.slice(at, at + width))
        + token(line.slice(at + width), "wf-hl-target", SELECTOR_KINDS["wf-hl-target"]);
    }).join("\n");
    if (html.endsWith("\n")) {
      html += "\u200b";
    }
    return html;
  }

  function classFor(name, variables, domains, builtins) {
    var key = name.trim();
    if (variables.has(key)) {
      return "wf-hl-var";
    }
    if (domains.has(key)) {
      return "wf-hl-domain";
    }
    if (Object.prototype.hasOwnProperty.call(builtins, key)) {
      return "wf-hl-builtin";
    }
    return "wf-hl-unknown";
  }

  function buildHtml(text, variables, domains, builtins, unknownTip) {
    var html = "";
    var lastIndex = 0;
    var match;
    VAR_PATTERN.lastIndex = 0;
    while ((match = VAR_PATTERN.exec(text)) !== null) {
      html += escapeHtml(text.slice(lastIndex, match.index));
      var rawName = match[1] !== undefined ? match[1] : match[2];
      var cls = classFor(rawName, variables, domains, builtins);
      var name = rawName.trim();
      var tip = (name ? name + ": " : "")
        + (cls === "wf-hl-builtin"
            ? builtins[name]
            : (cls === "wf-hl-unknown" && unknownTip ? unknownTip : KINDS[cls]));
      html +=
        '<span class="wf-hl-token ' + cls + '" data-wf-hl-tip="' + escapeHtml(tip) + '">'
        + escapeHtml(match[0])
        + "</span>";
      lastIndex = match.index + match[0].length;
    }
    html += escapeHtml(text.slice(lastIndex));
    // A trailing newline is not rendered by the browser: add a zero-width space
    // so the mirror keeps the same height as the textarea on the last line.
    if (html.endsWith("\n")) {
      html += "​";
    }
    return html;
  }

  function isSingleLine(field) {
    return field.tagName === "INPUT";
  }

  function ensureMirror(textarea) {
    if (textarea.__wfHlMirror) {
      return textarea.__wfHlMirror;
    }
    var wrap = document.createElement("div");
    wrap.className = isSingleLine(textarea) ? "wf-hl-wrap wf-hl-wrap-single" : "wf-hl-wrap";

    var mirror = document.createElement("div");
    // A single-line field never wraps and scrolls horizontally instead.
    mirror.className = isSingleLine(textarea) ? "wf-hl-mirror wf-hl-mirror-single" : "wf-hl-mirror";
    mirror.setAttribute("aria-hidden", "true");

    // Move the textarea inside the wrapper, mirror behind it.
    textarea.parentNode.insertBefore(wrap, textarea);
    wrap.appendChild(mirror);
    wrap.appendChild(textarea);

    textarea.classList.add("wf-hl-input");
    textarea.__wfHlMirror = mirror;

    function syncScroll() {
      mirror.scrollTop = textarea.scrollTop;
      mirror.scrollLeft = textarea.scrollLeft;
    }

    textarea.addEventListener("scroll", syncScroll);
    // A single-line input scrolls itself as the caret moves, without firing a
    // scroll event in every browser: follow the caret on these events too.
    ["input", "keyup", "click", "select", "focus", "blur"].forEach(function (name) {
      textarea.addEventListener(name, function () {
        window.requestAnimationFrame(syncScroll);
      });
    });

    // The mirror takes its height from the wrapper, whose height is the one of
    // the textarea itself: no measurement to keep in step with a resize (the
    // handle, or the auto-resize on input), only the scroll position.
    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(syncScroll).observe(textarea);
    }

    return mirror;
  }

  function refreshTextarea(textarea, variables, domains, builtins, unknownTip) {
    var mirror = ensureMirror(textarea);
    var text = textarea.value || "";
    // An empty field would show nothing at all: the mirror covers the real one,
    // whose native placeholder is hidden with the rest of its text. Draw it
    // here instead, dimmed but with its ${...} highlighted like any other --
    // a placeholder that is what Odatix would use (the templates a parameter
    // domain of a single variable leaves unwritten) is worth reading.
    var shown = text || textarea.getAttribute("placeholder") || "";
    var html = isSelectorField(textarea)
      ? buildSelectorsHtml(shown)
      : buildHtml(shown, variables, domains, builtins, unknownTip);
    mirror.innerHTML = text ? html : '<span class="wf-hl-placeholder">' + html + "</span>";

    var computed = window.getComputedStyle(textarea);
    COPIED_STYLES.forEach(function (prop) {
      mirror.style[prop] = computed[prop];
    });
    // The textarea auto-resizes its height on input; the mirror follows it
    // through the wrapper, but its scroll position only settles a frame later.
    window.requestAnimationFrame(function () {
      mirror.scrollTop = textarea.scrollTop;
      mirror.scrollLeft = textarea.scrollLeft;
    });
  }

  function refreshAll() {
    var textareas = document.querySelectorAll(FIELD_SELECTOR);
    if (!textareas.length) {
      return;
    }
    var builtins = builtinVariables();
    // The unscoped names are shared by every field of the page; a scope is
    // read once and reused by the fields belonging to it.
    var byRoot = new Map();
    textareas.forEach(function (textarea) {
      var root = scopeRoot(textarea);
      if (!byRoot.has(root)) {
        byRoot.set(root, [
          definedVariableNames(root),
          paramDomainNames(root),
          root ? root.getAttribute("data-odatix-hl-unknown") : null,
        ]);
      }
      var names = byRoot.get(root);
      refreshTextarea(textarea, names[0], names[1], builtins, names[2]);
    });
  }

  // Typing in a command textarea, or renaming a variable, changes the colors.
  document.addEventListener("input", function (event) {
    var target = event.target;
    if (!target) {
      return;
    }
    if (isField(target)) {
      refreshAll();
    } else if (target.id && String(target.id).indexOf("variable-title") !== -1) {
      refreshAll();
    }
  });

  // Cards are added/removed and values set programmatically by Dash (no input
  // event): re-highlight whenever the DOM changes, coalesced to one pass.
  var scheduled = false;
  var observer = new MutationObserver(function (records) {
    if (scheduled) {
      return;
    }
    // Ignore the mutations caused by our own mirror rewrites, or refreshing
    // (which rewrites the mirrors) would retrigger this observer forever.
    var relevant = records.some(function (record) {
      var node = record.target;
      while (node && node !== document.body) {
        if (node.classList && node.classList.contains("wf-hl-mirror")) {
          return false;
        }
        node = node.parentNode;
      }
      return true;
    });
    if (!relevant) {
      return;
    }
    scheduled = true;
    window.requestAnimationFrame(function () {
      scheduled = false;
      refreshAll();
    });
  });
  // A placeholder is an attribute, and Dash rewrites it as the variables of a
  // domain change: it has to be watched too, or the mirror would keep drawing
  // the previous one.
  observer.observe(document.body, {
    childList: true, subtree: true, attributes: true, attributeFilter: ["placeholder"],
  });

  // Fired by the clientside callback when the parameter domains change.
  document.addEventListener("odatix:refresh-var-highlight", refreshAll);

  window.addEventListener("DOMContentLoaded", refreshAll);

  /*
   * Hover tooltip. The mirror (and its tokens) sits under the transparent
   * textarea with pointer-events: none, so a CSS :hover on the tokens never
   * fires. Instead we hit-test the mouse against each token's client rects
   * (the mirror is laid out exactly over the textarea) and show a floating
   * tooltip, keeping the textarea fully editable.
   */
  var tooltip = null;

  function getTooltip() {
    if (!tooltip) {
      tooltip = document.createElement("div");
      tooltip.className = "wf-hl-tooltip";
      (document.querySelector(".theme") || document.body).appendChild(tooltip);
    }
    return tooltip;
  }

  function hideTooltip() {
    if (tooltip) {
      tooltip.classList.remove("visible");
    }
  }

  function tokenAtPoint(textarea, x, y) {
    var mirror = textarea.__wfHlMirror;
    if (!mirror) {
      return null;
    }
    var tokens = mirror.querySelectorAll(".wf-hl-token");
    for (var i = 0; i < tokens.length; i++) {
      var rects = tokens[i].getClientRects();
      for (var r = 0; r < rects.length; r++) {
        var rect = rects[r];
        if (x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom) {
          return { token: tokens[i], rect: rect };
        }
      }
    }
    return null;
  }

  document.addEventListener("mousemove", function (event) {
    var target = event.target;
    if (!isField(target)) {
      hideTooltip();
      return;
    }
    var hit = tokenAtPoint(target, event.clientX, event.clientY);
    if (!hit) {
      hideTooltip();
      return;
    }
    var tip = getTooltip();
    tip.textContent = hit.token.getAttribute("data-wf-hl-tip") || "";
    // Match the tooltip color to the token kind.
    TOKEN_CLASSES.forEach(function (cls) {
      tip.classList.remove(cls);
    });
    TOKEN_CLASSES.forEach(function (cls) {
      if (hit.token.classList.contains(cls)) {
        tip.classList.add(cls);
      }
    });
    tip.classList.add("visible");
    // Center above the token; keep it within the viewport.
    var tipRect = tip.getBoundingClientRect();
    var left = hit.rect.left + hit.rect.width / 2 - tipRect.width / 2;
    left = Math.max(6, Math.min(left, window.innerWidth - tipRect.width - 6));
    var top = hit.rect.top - tipRect.height - 8;
    if (top < 6) {
      top = hit.rect.bottom + 8;
    }
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  });

  document.addEventListener("mouseleave", hideTooltip, true);
  window.addEventListener("scroll", hideTooltip, true);
})();

window.dash_clientside.odatix_highlight = window.dash_clientside.odatix_highlight || {};

window.dash_clientside.odatix_highlight.push_names = function(domains, variables) {
    // `variables` is absent for the pages that declare no variable of their own
    // (workflow and simulation editors read theirs live from the variable cards).
    window.__odatixHlParamDomains = domains || [];
    window.__odatixHlVariables = variables || [];
    document.dispatchEvent(new CustomEvent("odatix:refresh-var-highlight"));
    return "";
};
