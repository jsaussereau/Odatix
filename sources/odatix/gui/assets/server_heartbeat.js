// ********************************************************************** //
//                                Odatix                                  //
// ********************************************************************** //
//
// Detect when the Odatix web server (GUI or Explorer) has stopped and warn
// the user with a modal popup. Only a refused connection means "stopped": a
// server busy with a long computation answers late, but it answers, and must
// not be reported as gone. Pure vanilla JS, self-contained: it injects
// its own overlay into <body> and polls the server with a lightweight
// heartbeat, so it works on every page of both apps without touching any
// Dash layout (the assets folder is shared by the GUI and the standalone
// Explorer, so this file is loaded by both).

(function () {
  "use strict";

  var POLL_INTERVAL_MS = 2000; // heartbeat period
  var FAIL_THRESHOLD = 3; // consecutive refused connections before declaring the server down
  // A heartbeat still unanswered after this long is given up and sent again.
  // It does NOT count as a failure: a slow answer means a busy server (a
  // Python callback holding the interpreter), not a stopped one.
  var REQUEST_TIMEOUT_MS = 30000;

  var failures = 0;
  var pending = false;
  var serverDown = false;
  var overlay = null;
  var messageEl = null;
  var buttonEl = null;

  function buildOverlay() {
    overlay = document.createElement("div");
    overlay.className = "overlay-odatix";
    overlay.id = "server-heartbeat-overlay";

    var popup = document.createElement("div");
    popup.className = "popup-odatix";

    var title = document.createElement("h3");
    title.textContent = "Server connection lost";

    messageEl = document.createElement("p");
    messageEl.style.color = "var(--theme-text-color)";
    messageEl.style.margin = "12px 0 24px";
    messageEl.textContent =
      "The Odatix server refuses connections: it was probably closed in the terminal. Restart it, then click Try again.";

    buttonEl = document.createElement("button");
    buttonEl.className = "color-button primary";
    buttonEl.textContent = "Try again";
    buttonEl.onclick = function () {
      window.location.reload();
    };

    popup.appendChild(title);
    popup.appendChild(messageEl);
    popup.appendChild(buttonEl);
    overlay.appendChild(popup);
    // Mount inside the #theme container so the theme CSS variables (defined on
    // .theme / .theme.<name>) cascade into the popup; fall back to <body>.
    (document.getElementById("theme") || document.body).appendChild(overlay);
  }

  function showOverlay() {
    if (!overlay) buildOverlay();
    overlay.classList.add("visible");
  }

  function setRecovered() {
    if (messageEl) {
      messageEl.textContent = "The server is back online. Reload the page to continue.";
    }
    if (buttonEl) {
      buttonEl.textContent = "Reload";
    }
  }

  function ping() {
    // One heartbeat at a time: piling them up behind a busy server would only
    // take the connections the page itself needs.
    if (pending) return;
    pending = true;
    var controller = new AbortController();
    var timedOut = false;
    var timer = setTimeout(function () {
      timedOut = true;
      controller.abort();
    }, REQUEST_TIMEOUT_MS);

    // HEAD on the current page: it is always served by the running server, so a
    // network error (connection refused) means the server is gone. Any HTTP
    // answer, even an error status, means it is still there.
    fetch(window.location.href, {
      method: "HEAD",
      cache: "no-store",
      signal: controller.signal,
    })
      .then(function () {
        clearTimeout(timer);
        pending = false;
        onSuccess();
      })
      .catch(function () {
        clearTimeout(timer);
        pending = false;
        if (timedOut) return; // busy, not stopped: neither a success nor a failure
        onFailure();
      });
  }

  function onFailure() {
    failures += 1;
    if (!serverDown && failures >= FAIL_THRESHOLD) {
      serverDown = true;
      showOverlay();
    }
  }

  function onSuccess() {
    failures = 0;
    if (serverDown) {
      // The server came back after being declared down: the page still holds a
      // stale Dash session, so invite (do not force) a reload.
      setRecovered();
    }
  }

  function start() {
    ping();
    setInterval(ping, POLL_INTERVAL_MS);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
