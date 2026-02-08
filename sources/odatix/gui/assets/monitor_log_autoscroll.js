(function () {
  function isAtBottom(el, thresholdPx) {
    if (!el) return true;
    var threshold = typeof thresholdPx === "number" ? thresholdPx : 8;
    return el.scrollTop + el.clientHeight >= el.scrollHeight - threshold;
  }

  function scrollToBottom(el) {
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }

  function attachToLogElement(el) {
    if (!el) return;

    // Track whether the user is "pinned" at bottom.
    // If pinned, new content auto-scrolls; if user scrolls up, it stops.
    if (window.odatixMonitorLogPinnedToBottom == null) {
      window.odatixMonitorLogPinnedToBottom = true;
    }

    var onScroll = function () {
      window.odatixMonitorLogPinnedToBottom = isAtBottom(el, 12);
    };

    el.addEventListener("scroll", onScroll, { passive: true });

    var observer = new MutationObserver(function () {
      // If user was at bottom before update, keep them at bottom.
      if (window.odatixMonitorLogPinnedToBottom) {
        // Defer to ensure layout is updated.
        window.requestAnimationFrame(function () {
          scrollToBottom(el);
        });
      }
    });

    observer.observe(el, {
      childList: true,
      subtree: true,
      characterData: true,
    });

    // Initial behavior: if pinned, go bottom.
    window.requestAnimationFrame(function () {
      if (window.odatixMonitorLogPinnedToBottom) {
        scrollToBottom(el);
      }
    });

    // Keep references so we can re-attach if Dash replaces the node.
    window.__odatixMonitorLogEl = el;
    window.__odatixMonitorLogCleanup = function () {
      try {
        el.removeEventListener("scroll", onScroll);
      } catch (e) {}
      try {
        observer.disconnect();
      } catch (e) {}
    };
  }

  function ensureAttached() {
    var el = document.getElementById("monitor-log");
    if (!el) return;

    if (window.__odatixMonitorLogEl === el) return;

    // Dash may replace DOM nodes; detach old listeners.
    if (typeof window.__odatixMonitorLogCleanup === "function") {
      try {
        window.__odatixMonitorLogCleanup();
      } catch (e) {}
    }

    attachToLogElement(el);
  }

  // Poll for the element because pages are client-side routed.
  setInterval(ensureAttached, 500);
  if (document.readyState === "complete" || document.readyState === "interactive") {
    ensureAttached();
  } else {
    document.addEventListener("DOMContentLoaded", ensureAttached);
  }
})();
