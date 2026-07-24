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
 * Highlight ${...} variables inside the workflow task "commands" textareas.
 *
 * A textarea cannot render colored text, so each command textarea is backed by
 * a mirror <div> that holds the same text with the variables wrapped in colored
 * spans. The textarea is made transparent (text + background) and sits on top,
 * so the user still types normally while seeing the colors of the mirror.
 *
 * Three colors, by where the ${name} resolves:
 *   - defined variable  : a variable card on the page (read live from the DOM)
 *   - parameter domain  : a physical domain of the workflow (window global,
 *                         pushed from Python via a clientside callback)
 *   - not found         : neither
 */

(function () {
  // Both ${name} (group 1) and bare $name (group 2, a shell-style identifier).
  var VAR_PATTERN = /\$\{([^}]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)/g;

  // Style properties the mirror must share with the textarea so the text wraps
  // at exactly the same place and the colors land under the real characters.
  var COPIED_STYLES = [
    "boxSizing", "width",
    "paddingTop", "paddingRight", "paddingBottom", "paddingLeft",
    "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth",
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

  function definedVariableNames() {
    // The variable cards' title inputs; read live so renaming a variable
    // recolors the commands without a save.
    var names = new Set();
    document.querySelectorAll('input[id*="variable-title"]').forEach(function (input) {
      var value = (input.value || "").trim();
      if (value) {
        names.add(value);
      }
    });
    return names;
  }

  function paramDomainNames() {
    var domains = window.__odatixWfParamDomains || [];
    var names = new Set();
    domains.forEach(function (domain) {
      var value = String(domain || "").trim();
      if (value) {
        names.add(value);
      }
    });
    return names;
  }

  // Class + hover description for each kind of ${...} token.
  var KINDS = {
    "wf-hl-var": "user defined variable",
    "wf-hl-domain": "parameter domain",
    "wf-hl-unknown":
      "not detected. This is fine if it is an environment variable, "
      + "otherwise define it as a variable below",
  };

  function classFor(name, variables, domains) {
    var key = name.trim();
    if (variables.has(key)) {
      return "wf-hl-var";
    }
    if (domains.has(key)) {
      return "wf-hl-domain";
    }
    return "wf-hl-unknown";
  }

  function buildHtml(text, variables, domains) {
    var html = "";
    var lastIndex = 0;
    var match;
    VAR_PATTERN.lastIndex = 0;
    while ((match = VAR_PATTERN.exec(text)) !== null) {
      html += escapeHtml(text.slice(lastIndex, match.index));
      var rawName = match[1] !== undefined ? match[1] : match[2];
      var cls = classFor(rawName, variables, domains);
      var name = rawName.trim();
      var tip = (name ? name + ": " : "") + KINDS[cls];
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

  function ensureMirror(textarea) {
    if (textarea.__wfHlMirror) {
      return textarea.__wfHlMirror;
    }
    var wrap = document.createElement("div");
    wrap.className = "wf-hl-wrap";

    var mirror = document.createElement("div");
    mirror.className = "wf-hl-mirror";
    mirror.setAttribute("aria-hidden", "true");

    // Move the textarea inside the wrapper, mirror behind it.
    textarea.parentNode.insertBefore(wrap, textarea);
    wrap.appendChild(mirror);
    wrap.appendChild(textarea);

    textarea.classList.add("wf-hl-input");
    textarea.__wfHlMirror = mirror;

    textarea.addEventListener("scroll", function () {
      mirror.scrollTop = textarea.scrollTop;
      mirror.scrollLeft = textarea.scrollLeft;
    });

    // Keep the mirror in step with a manual (resize handle) height change, which
    // fires no input event.
    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(function () {
        mirror.style.height = textarea.offsetHeight + "px";
      }).observe(textarea);
    }

    return mirror;
  }

  function refreshTextarea(textarea, variables, domains) {
    var mirror = ensureMirror(textarea);
    mirror.innerHTML = buildHtml(textarea.value || "", variables, domains);

    var computed = window.getComputedStyle(textarea);
    COPIED_STYLES.forEach(function (prop) {
      mirror.style[prop] = computed[prop];
    });
    // The textarea auto-resizes its height on input; match it on the next frame,
    // once that height has been applied.
    window.requestAnimationFrame(function () {
      mirror.style.height = textarea.offsetHeight + "px";
      mirror.scrollTop = textarea.scrollTop;
      mirror.scrollLeft = textarea.scrollLeft;
    });
  }

  function refreshAll() {
    var textareas = document.querySelectorAll("textarea.wf-command-textarea");
    if (!textareas.length) {
      return;
    }
    var variables = definedVariableNames();
    var domains = paramDomainNames();
    textareas.forEach(function (textarea) {
      refreshTextarea(textarea, variables, domains);
    });
  }

  // Typing in a command textarea, or renaming a variable, changes the colors.
  document.addEventListener("input", function (event) {
    var target = event.target;
    if (!target) {
      return;
    }
    if (target.classList && target.classList.contains("wf-command-textarea")) {
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
  observer.observe(document.body, { childList: true, subtree: true });

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
    if (!target || !target.classList || !target.classList.contains("wf-command-textarea")) {
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
    tip.classList.remove("wf-hl-var", "wf-hl-domain", "wf-hl-unknown");
    ["wf-hl-var", "wf-hl-domain", "wf-hl-unknown"].forEach(function (cls) {
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
