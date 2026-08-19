// Log pane writer for the monitor page.
//
// The log is never held in a dcc.Store: a store is uploaded back to the server
// as State/Input on every callback that reads it, so an accumulating log would
// make each poll tick cost the size of the whole log so far. Instead the server
// sends one chunk of already-formatted HTML per tick (`monitor-log-chunk`,
// built by _log_chunk in pages/monitor.py) and this splices it in place.
//
// Only new lines travel, and only downwards; the browser keeps the scrollback
// as plain DOM. assets/monitor_log_autoscroll.js watches the same node with a
// MutationObserver, so appends keep the pane pinned to the bottom exactly as
// a Dash-rendered log did.
(function () {
  var lastNonce = null;
  // The markup currently displayed, kept so a re-mount (client-side routing
  // rebuilds the <pre>) can be restored without asking the server to resend a
  // log it has already sent. It lives in JS memory only -- never in a store,
  // which is the whole point.
  var markupCache = "";
  var attachedTo = null;

  window.dash_clientside = window.dash_clientside || {};
  window.dash_clientside.odatixMonitor = window.dash_clientside.odatixMonitor || {};

  window.dash_clientside.odatixMonitor.appendLog = function (chunk) {
    var target = document.getElementById("monitor-log");
    if (!target) return window.dash_clientside.no_update;

    if (target !== attachedTo) {
      attachedTo = target;
      target.innerHTML = markupCache;
    }

    if (!chunk) return window.dash_clientside.no_update;

    // Dash re-fires a clientside callback whenever the page is re-mounted, and
    // both _poll_status and _fetch_full_log_on_selection write this store; the
    // nonce is what makes replaying the same chunk a no-op instead of a
    // duplicated block of lines.
    if (chunk.nonce === lastNonce) return window.dash_clientside.no_update;
    lastNonce = chunk.nonce;

    var markup = typeof chunk.html === "string" ? chunk.html : "";
    if (chunk.mode === "replace") {
      markupCache = markup;
      target.innerHTML = markup;
    } else if (markup) {
      markupCache += markup;
      target.insertAdjacentHTML("beforeend", markup);
    }
    return chunk.nonce;
  };
})();
