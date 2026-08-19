/*
 * Client-side task list for the monitor page.
 *
 * The monitor used to render its task list in Python: one Dash component per
 * job, and a handful of callbacks that re-sent the whole snapshot to the server
 * every second and patched ~10 properties per job back. On a session with a few
 * thousand jobs that is tens of thousands of property updates per second, plus
 * a DOM holding every row whether or not it is on screen.
 *
 * Here instead:
 *   - the browser keeps the job model and merges the deltas the daemon sends
 *     (see ParallelJobHandler.snapshot and `?since=`), so a tick carries only
 *     the jobs that actually moved;
 *   - only the rows inside the scroll viewport exist in the DOM (virtualized
 *     list), so the DOM cost is bounded by the panel height, not by job count;
 *   - filtering, sorting, selection and the KPI figures are computed here, on
 *     data the page already holds, with no round trip at all;
 *   - clicks are delegated on the container, so no per-row Dash component and
 *     no arrays of N click counts travelling on every click.
 *
 * The row markup itself is NOT written here: it is serialized from the Dash
 * component tree in pages/monitor.py (`monitor_task_template`) and handed over
 * through the `monitor-row-template` store, so the icons and class names have a
 * single definition.
 */
(function () {
  "use strict";

  var CONTAINER_ID = "monitor-container";
  var SCROLLER_SELECTOR = ".monitor-list-scroll";

  // Rows above and below the viewport, so a fast scroll does not show gaps.
  var OVERSCAN = 6;
  // Fallback pitch, used only until the first row has been measured.
  var DEFAULT_PITCH = 42;

  // Poll cadence. A session with thousands of jobs gains nothing from a 1 s
  // round trip that a 2 s one does not give it, and each tick still costs a
  // request to the daemon.
  var FAST_INTERVAL_MS = 1000;
  var SLOW_INTERVAL_MS = 2000;
  var SLOW_INTERVAL_THRESHOLD = 500;

  var state = {
    container: null,
    scroller: null,
    template: null,
    jobs: new Map(),          // id -> job payload
    epoch: null,
    order: [],                // visible job ids, in display order
    orderDirty: true,
    filter: null,
    sort: null,
    reverse: null,
    selected: null,
    rendered: new Map(),      // id -> {el, refs, last}
    pitch: DEFAULT_PITCH,
    frame: null,
    buckets: null,
    priority: null,
    counts: null,
    nonce: 0,
  };

  /* ------------------------------------------------------------------ utils */

  function setProps(id, props) {
    var ds = window.dash_clientside;
    if (ds && typeof ds.set_props === "function") {
      try {
        ds.set_props(id, props);
      } catch (e) {
        /* the store is not on this page (yet): nothing to update */
      }
    }
  }

  function noUpdate() {
    var ds = window.dash_clientside;
    return ds ? ds.no_update : undefined;
  }

  function statusOf(job) {
    return String((job && job.status) || "").toLowerCase().trim();
  }

  function progressOf(job) {
    var value = Number(job && job.progress);
    if (!isFinite(value)) return 0;
    return Math.max(0, Math.min(100, Math.round(value)));
  }

  function elapsedSeconds(job) {
    var parts = String((job && job.elapsed_time) || "").split(":");
    if (parts.length !== 3) return 0;
    var total = Number(parts[0]) * 3600 + Number(parts[1]) * 60 + Number(parts[2]);
    return isFinite(total) ? Math.max(0, total) : 0;
  }

  // The status buckets and their sort priority come from the daemon
  // (odatix.lib.parallel_job_handler.job_status), so counting here and counting
  // there cannot drift apart.
  function matchesFilter(status, filterValue) {
    if (!filterValue || filterValue === "all") return true;
    var bucket = state.buckets && state.buckets[filterValue];
    return bucket ? bucket.indexOf(status) !== -1 : true;
  }

  /* ------------------------------------------------------- model + ordering */

  function mergeSnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return false;

    var handler = snapshot.handler || {};
    state.buckets = handler.status_buckets || state.buckets;
    state.priority = handler.status_sort_priority || state.priority;
    state.counts = handler.counts || state.counts;
    state.handler = handler;

    var jobs = Array.isArray(snapshot.jobs) ? snapshot.jobs : [];

    // A full snapshot, or one from another daemon, replaces the model outright:
    // a delta is only meaningful against the revisions it was computed from.
    if (snapshot.full || snapshot.epoch !== state.epoch) {
      state.epoch = snapshot.epoch;
      state.jobs = new Map();
      for (var i = 0; i < jobs.length; i++) {
        state.jobs.set(jobs[i].id, jobs[i]);
      }
      state.orderDirty = true;
      return true;
    }

    if (jobs.length === 0) return false;

    for (var j = 0; j < jobs.length; j++) {
      var job = jobs[j];
      var previous = state.jobs.get(job.id);
      // Only a new job, or one changing status, can change what is visible or
      // in which order. A progress tick on an already-visible job does not.
      if (!previous || statusOf(previous) !== statusOf(job)) {
        state.orderDirty = true;
      }
      state.jobs.set(job.id, job);
    }
    return true;
  }

  function sortComparator(sortValue) {
    var priority = state.priority || {};
    return function (leftId, rightId) {
      var left = state.jobs.get(leftId) || {};
      var right = state.jobs.get(rightId) || {};
      var delta = 0;

      if (sortValue === "name") {
        delta = String(left.display_name || "").toLowerCase()
          .localeCompare(String(right.display_name || "").toLowerCase());
      } else if (sortValue === "status") {
        var leftRank = priority[statusOf(left)];
        var rightRank = priority[statusOf(right)];
        delta = (leftRank === undefined ? 99 : leftRank) - (rightRank === undefined ? 99 : rightRank);
        if (delta === 0) {
          delta = String(left.display_name || "").toLowerCase()
            .localeCompare(String(right.display_name || "").toLowerCase());
        }
      } else if (sortValue === "progress") {
        delta = progressOf(right) - progressOf(left);
      } else if (sortValue === "runtime") {
        delta = elapsedSeconds(right) - elapsedSeconds(left);
      }

      // Ties always fall back to the job id, so the order is total and a row
      // never swaps places with another for no visible reason.
      return delta !== 0 ? delta : leftId - rightId;
    };
  }

  function rebuildOrder() {
    var order = [];
    state.jobs.forEach(function (job, id) {
      if (matchesFilter(statusOf(job), state.filter)) order.push(id);
    });

    // "progress" and "runtime" rank on values that move on every tick, so their
    // order has to be recomputed even when no job changed status.
    order.sort(sortComparator(state.sort));
    if (state.reverse) order.reverse();

    state.order = order;
    state.orderDirty = false;
  }

  /* ----------------------------------------------------------------- layout */

  function readPitch() {
    var probe = state.rendered.values().next();
    if (!probe.done) {
      var height = probe.value.el.offsetHeight;
      if (height > 0) {
        var styles = window.getComputedStyle(state.container);
        var gap = parseFloat(styles.rowGap || styles.gap || "0") || 0;
        state.pitch = height + gap;
      }
    }
    return state.pitch;
  }

  function visibleRange() {
    var total = state.order.length;
    if (total === 0 || !state.scroller) return { first: 0, last: 0 };

    var pitch = state.pitch || DEFAULT_PITCH;
    var containerRect = state.container.getBoundingClientRect();
    var scrollerRect = state.scroller.getBoundingClientRect();

    // How much of the list has scrolled past the top of the viewport. Measured
    // rather than derived from scrollTop, so the scroller's own padding and any
    // header above the list are accounted for without hardcoding them.
    var scrolledPast = scrollerRect.top - containerRect.top;

    var first = Math.floor(scrolledPast / pitch) - OVERSCAN;
    var count = Math.ceil(scrollerRect.height / pitch) + 1 + 2 * OVERSCAN;

    first = Math.max(0, Math.min(first, Math.max(0, total - 1)));
    return { first: first, last: Math.min(total, first + count) };
  }

  /* ------------------------------------------------------------------- rows */

  function createRow(jobId) {
    var holder = document.createElement("div");
    holder.innerHTML = state.template;
    var el = holder.firstElementChild;
    if (!el) return null;

    el.setAttribute("data-job-id", String(jobId));
    el.classList.add("virtual-row");

    var refs = {
      row: el.querySelector('[data-role="row"]'),
      name: el.querySelector('[data-role="name"]'),
      bar: el.querySelector('[data-role="bar"]'),
      progress: el.querySelector('[data-role="progress"]'),
      runtime: el.querySelector('[data-role="runtime"]'),
      status: el.querySelector('[data-role="status"]'),
      start: el.querySelector('[data-wrap="start"]'),
      pause: el.querySelector('[data-wrap="pause"]'),
      stop: el.querySelector('[data-wrap="stop"]'),
    };

    state.container.appendChild(el);
    return { el: el, refs: refs, last: {} };
  }

  function updateRow(entry, job, index, selectedId) {
    var refs = entry.refs;
    var last = entry.last;

    var top = index * (state.pitch || DEFAULT_PITCH);
    if (last.top !== top) {
      entry.el.style.transform = "translateY(" + top + "px)";
      last.top = top;
    }

    var status = statusOf(job);
    if (last.status !== status) {
      if (refs.row) refs.row.className = "monitor-task " + status;
      if (refs.status) {
        refs.status.className = "monitor-task-status " + status;
        refs.status.textContent = String(job.status || "unknown");
      }
      // Which actions apply is a function of the status alone.
      if (refs.start) refs.start.style.display = (status === "queued" || status === "paused") ? "block" : "none";
      if (refs.pause) refs.pause.style.display = (status === "running" || status === "starting") ? "block" : "none";
      if (refs.stop) {
        refs.stop.style.display =
          (status === "queued" || status === "paused" || status === "running" || status === "starting")
            ? "block" : "none";
      }
      last.status = status;
    }

    var name = String(job.display_name || ("job" + job.id));
    if (last.name !== name) {
      if (refs.name) refs.name.textContent = name;
      last.name = name;
    }

    var progress = progressOf(job);
    if (last.progress !== progress) {
      if (refs.bar) refs.bar.style.width = progress + "%";
      if (refs.progress) refs.progress.textContent = progress + " %";
      last.progress = progress;
    }

    var runtime = String(job.elapsed_time || "--:--:--");
    if (last.runtime !== runtime) {
      if (refs.runtime) refs.runtime.textContent = runtime;
      last.runtime = runtime;
    }

    var selected = job.id === selectedId;
    if (last.selected !== selected) {
      entry.el.classList.toggle("selected", selected);
      last.selected = selected;
    }
  }

  function draw() {
    state.frame = null;
    if (!state.container || !state.template) return;

    if (state.orderDirty) rebuildOrder();

    var total = state.order.length;
    state.container.style.height = (total * (state.pitch || DEFAULT_PITCH)) + "px";

    var range = visibleRange();
    var needed = new Set();
    for (var i = range.first; i < range.last; i++) needed.add(state.order[i]);

    // Recycle: drop the rows that scrolled out of the window.
    state.rendered.forEach(function (entry, jobId) {
      if (!needed.has(jobId)) {
        entry.el.remove();
        state.rendered.delete(jobId);
      }
    });

    for (var index = range.first; index < range.last; index++) {
      var jobId = state.order[index];
      var job = state.jobs.get(jobId);
      if (!job) continue;

      var entry = state.rendered.get(jobId);
      if (!entry) {
        entry = createRow(jobId);
        if (!entry) continue;
        state.rendered.set(jobId, entry);
      }
      updateRow(entry, job, index, state.selected);
    }

    // The first rows just landed: measure the real pitch and lay out again with
    // it, instead of guessing a row height in JavaScript that the CSS owns.
    if (state.pitch === DEFAULT_PITCH && state.rendered.size > 0) {
      var measured = readPitch();
      if (measured !== DEFAULT_PITCH) schedule();
    }
  }

  function schedule() {
    if (state.frame !== null) return;
    state.frame = window.requestAnimationFrame(draw);
  }

  /* --------------------------------------------------------------- attaching */

  function onScroll() {
    schedule();
  }

  function onClick(event) {
    var row = event.target.closest("[data-job-id]");
    if (!row || !state.container.contains(row)) return;

    var jobId = parseInt(row.getAttribute("data-job-id"), 10);
    if (isNaN(jobId)) return;

    // An action button: run the action, without also selecting the row.
    var button = event.target.closest("button");
    var wrap = button && button.closest("[data-wrap]");
    if (button && wrap) {
      event.stopPropagation();
      state.nonce += 1;
      setProps("monitor-task-command", {
        data: {
          action: wrap.getAttribute("data-wrap"),
          job_id: jobId,
          // Two identical actions in a row must still look like two writes.
          nonce: state.nonce,
        },
      });
      return;
    }

    setProps("monitor-selected-job", { data: jobId });
  }

  function ensureAttached() {
    var container = document.getElementById(CONTAINER_ID);
    if (!container) {
      state.container = null;
      state.scroller = null;
      return false;
    }
    if (state.container === container) return true;

    // Dash re-created the node (page navigation): rebind and start from an
    // empty pool. The model itself survives, so nothing has to be refetched.
    state.container = container;
    state.scroller = container.closest(SCROLLER_SELECTOR) || container.parentElement;
    state.rendered = new Map();
    state.pitch = DEFAULT_PITCH;
    container.innerHTML = "";
    container.classList.add("virtual");

    if (state.scroller) {
      state.scroller.addEventListener("scroll", onScroll, { passive: true });
    }
    container.addEventListener("click", onClick);
    return true;
  }

  /* ------------------------------------------------------- tab visibility */

  function reportVisibility() {
    if (!document.getElementById(CONTAINER_ID)) return;
    setProps("monitor-visibility", { data: !document.hidden });
  }

  document.addEventListener("visibilitychange", reportVisibility);

  /* ------------------------------------------------- clientside callbacks */

  window.dash_clientside = window.dash_clientside || {};
  window.dash_clientside.odatixMonitor = {
    render: function (snapshot, filterValue, sortValue, sortReverse, selectedJob, template) {
      if (template && template !== state.template) {
        state.template = template;
        // The markup changed under us: every pooled row is stale.
        state.rendered.forEach(function (entry) { entry.el.remove(); });
        state.rendered = new Map();
      }
      if (!ensureAttached()) return noUpdate();

      if (filterValue !== state.filter) {
        state.filter = filterValue;
        state.orderDirty = true;
      }
      if (sortValue !== state.sort) {
        state.sort = sortValue;
        state.orderDirty = true;
      }
      var reverse = !!sortReverse;
      if (reverse !== state.reverse) {
        state.reverse = reverse;
        state.orderDirty = true;
      }
      state.selected = (selectedJob === null || selectedJob === undefined)
        ? null : Number(selectedJob);

      mergeSnapshot(snapshot);

      // These two rank on values that move every tick, so their order has to be
      // recomputed on every snapshot, not only when a job changed status.
      if (state.sort === "progress" || state.sort === "runtime") state.orderDirty = true;

      schedule();
      return noUpdate();
    },

    kpis: function (snapshot) {
      var handler = snapshot && snapshot.handler;
      var counts = (handler && handler.counts) || null;
      if (!counts) return noUpdate();

      var overall = Number(handler.overall_progress) || 0;
      return [
        String(counts.total || 0),
        String(counts.running || 0),
        String(counts.queued || 0),
        String(counts.done || 0),
        String(counts.failed || 0),
        { width: overall + "%" },
        overall + "%",
      ];
    },

    nbJobs: function (snapshot) {
      var handler = snapshot && snapshot.handler;
      if (!handler || handler.nb_jobs === null || handler.nb_jobs === undefined) return noUpdate();
      return String(Math.max(1, parseInt(handler.nb_jobs, 10) || 1));
    },

    logTitle: function (selectedJob, snapshot) {
      if (selectedJob === null || selectedJob === undefined) {
        return ["No task selected", "", "monitor-log-title-status"];
      }
      var jobId = Number(selectedJob);
      var job = state.jobs.get(jobId);
      if (!job) return ["job" + jobId, "", "monitor-log-title-status"];

      var status = statusOf(job);
      return [
        String(job.display_name || ("job" + jobId)),
        status,
        "monitor-log-title-status " + status,
      ];
    },

    initSelection: function (snapshot, selectedJob) {
      // Pick a default only while nothing is selected: on page load, and after
      // a session switch cleared the selection. Afterwards selection is
      // user-driven.
      if (selectedJob !== null && selectedJob !== undefined) return noUpdate();
      var handler = snapshot && snapshot.handler;
      if (!handler) return noUpdate();

      var index = handler.selected_job_index;
      if (index === null || index === undefined || index < 0) index = handler.first_job_id;
      if (index === null || index === undefined) return noUpdate();
      return Number(index);
    },

    finishedSummary: function (snapshot) {
      // The completion dialog is built in Python (it has components in it), so
      // it cannot move here -- but it must not be woken on every tick either.
      // This gate writes its store only once nothing is running or queued, and
      // then only when the figures change, so the round trip happens once.
      var handler = snapshot && snapshot.handler;
      var counts = (handler && handler.counts) || null;
      if (!counts || !counts.total) return noUpdate();
      if (counts.running > 0 || counts.queued > 0) return noUpdate();

      return {
        total: counts.total,
        done: counts.done,
        failed: counts.failed,
        longest_elapsed: handler.longest_elapsed || 0,
      };
    },

    refreshRate: function (snapshot, visible) {
      var handler = snapshot && snapshot.handler;
      var total = (handler && handler.counts && handler.counts.total) || 0;
      var interval = total >= SLOW_INTERVAL_THRESHOLD ? SLOW_INTERVAL_MS : FAST_INTERVAL_MS;
      // A hidden tab shows nothing: polling it only costs the daemon requests.
      return [interval, visible === false];
    },
  };
})();
