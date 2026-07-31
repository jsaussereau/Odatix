(function () {
  // The <pre id="monitor-log"> is the node Dash rewrites, but it has
  // overflow:visible: the actual scroll box is its .monitor-log-scroll wrapper.
  // Watch the former, scroll the latter.
  var PIN_THRESHOLD_PX = 12;

  function isAtBottom(el) {
    if (!el) return true;
    return el.scrollTop + el.clientHeight >= el.scrollHeight - PIN_THRESHOLD_PX;
  }

  function scrollToBottom(el) {
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }

  function attach(scroller, content) {
    // "Pinned" means new lines follow the bottom, like a terminal. Scrolling
    // up unpins; coming back to the bottom (mouse, wheel or End) re-pins.
    var pinned = true;

    var onScroll = function () {
      pinned = isAtBottom(scroller);
    };
    scroller.addEventListener("scroll", onScroll, { passive: true });

    var observer = new MutationObserver(function () {
      if (!pinned) return;
      // Defer so the new lines are laid out before we measure scrollHeight.
      window.requestAnimationFrame(function () {
        scrollToBottom(scroller);
      });
    });
    observer.observe(content, { childList: true, subtree: true, characterData: true });

    window.requestAnimationFrame(function () {
      scrollToBottom(scroller);
    });

    window.__odatixMonitorLogEl = content;
    window.__odatixMonitorLogCleanup = function () {
      try {
        scroller.removeEventListener("scroll", onScroll);
      } catch (e) {}
      try {
        observer.disconnect();
      } catch (e) {}
    };
  }

  function ensureAttached() {
    var content = document.getElementById("monitor-log");
    if (!content) return;
    if (window.__odatixMonitorLogEl === content) return;

    var scroller = content.closest(".monitor-log-scroll") || content.parentElement;
    if (!scroller) return;

    // Dash may replace DOM nodes; detach old listeners first.
    if (typeof window.__odatixMonitorLogCleanup === "function") {
      try {
        window.__odatixMonitorLogCleanup();
      } catch (e) {}
    }

    attach(scroller, content);
  }

  // Poll for the element because pages are client-side routed.
  setInterval(ensureAttached, 500);
  if (document.readyState === "complete" || document.readyState === "interactive") {
    ensureAttached();
  } else {
    document.addEventListener("DOMContentLoaded", ensureAttached);
  }
})();
