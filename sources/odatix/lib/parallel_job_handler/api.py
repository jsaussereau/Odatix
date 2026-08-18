# ********************************************************************** #
#                                Odatix                                  #
# ********************************************************************** #
#
# Copyright (C) 2022 Jonathan Saussereau
#
# This file is part of Odatix.
# Odatix is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Odatix is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Odatix. If not, see <https://www.gnu.org/licenses/>.
#

"""FastAPI REST + WebSocket API for controlling ParallelJobHandler.

This module is intentionally imported lazily (see ParallelJobHandler.run_api)
so that Odatix can be used without FastAPI/uvicorn installed.

Every request must carry a session token (see auth.py): enqueuing a job runs
a command line on this machine, so an unauthenticated API is a remote shell.
Tokens come in two scopes -- ``read`` may only look, ``control`` may act. Read
requests are the GETs; everything else acts.

Protocol overview
-----------------
REST endpoints expose command-style operations and snapshots.
WebSocket /ws pushes periodic snapshots and accepts command messages.
The WebSocket carries the same Authorization header as the REST calls, and is
refused before the handshake is accepted when it does not.

WebSocket client->server messages (JSON):
- {"type": "snapshot"}  -> server replies with a snapshot immediately
- {"type": "command", "name": "select|pause|start|kill|open|theme_next|shutdown", "job_id": 0}
- {"type": "logs", "name": "scroll|home|end", "job_id": 0, "delta": -3}
- {"type": "set", "logs_height": 60}

Server->client messages (JSON):
- {"type": "snapshot", "data": <handler.snapshot()>}
- {"type": "error", "message": "..."}

"""

import asyncio
import importlib
import time
from typing import Any, Dict, Optional, Set

from odatix.lib.parallel_job_handler.auth import (
    AUTH_HEADER,
    SCOPE_CONTROL,
    SCOPE_READ,
    ApiAuth,
    is_loopback_host,
    scope_satisfies,
)
from odatix.lib.parallel_job_handler.serialization import payload_to_job
from odatix.lib.parallel_job_handler.transport import TRANSPORT_UNIX
from odatix.lib.parallel_job_handler import diagnostics
import odatix.lib.hard_settings as hard_settings

#: A request slower than this made every other client of the session wait for
#: it, and is written to the session diagnostics (see the ``measure``
#: middleware). Callers time out at one second, so this is already too slow.
SLOW_REQUEST_S = 0.5


def _null_uvicorn_log_config() -> Dict[str, Any]:
    # Uvicorn config accepts standard logging.dictConfig dictionaries.
    # NullHandler prevents any output to the terminal.
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "null": {"class": "logging.NullHandler"},
        },
        "loggers": {
            "uvicorn": {"handlers": ["null"], "level": "CRITICAL", "propagate": False},
            "uvicorn.error": {"handlers": ["null"], "level": "CRITICAL", "propagate": False},
            "uvicorn.access": {"handlers": ["null"], "level": "CRITICAL", "propagate": False},
        },
        "root": {"handlers": ["null"], "level": "CRITICAL"},
    }


def _require_fastapi():
    try:
        fastapi = importlib.import_module("fastapi")
        responses = importlib.import_module("fastapi.responses")
        FastAPI = fastapi.FastAPI
        WebSocket = fastapi.WebSocket
        WebSocketDisconnect = fastapi.WebSocketDisconnect
        JSONResponse = responses.JSONResponse
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "FastAPI is not installed. Install with: pip install fastapi uvicorn"
        ) from e

    return FastAPI, WebSocket, WebSocketDisconnect, JSONResponse


def create_parallel_job_app(
    handler,
    *,
    auth,
    tick_interval: float = 0.1,
    ws_push_interval: float = 0.25,
    start_headless_on_startup: bool = True,
    shutdown_callback=None,
):
    """Build the session app.

    Args:
        auth (ApiAuth): the session's tokens and accepted Host values. Required:
            an app without it would let anyone reaching the socket or port run
            commands as the user owning the session.
    """
    if not isinstance(auth, ApiAuth):
        raise ValueError("create_parallel_job_app() requires an ApiAuth instance")

    FastAPI, WebSocket, WebSocketDisconnect, JSONResponse = _require_fastapi()

    app = FastAPI(title="Odatix ParallelJob API")
    app.state.auth = auth

    @app.middleware("http")
    async def measure(request, call_next):
        # The event loop is shared by every client of the session -- the
        # monitor, the GUI, and the exploration driver polling for its jobs.
        # A request that takes seconds is one that made all the others wait,
        # and it is what a session "going unresponsive" looks like from here.
        started = time.time()
        try:
            return await call_next(request)
        finally:
            elapsed = time.time() - started
            if elapsed >= SLOW_REQUEST_S:
                diagnostics.log(
                    "slow request",
                    seconds=elapsed,
                    method=request.method,
                    path=str(request.url.path),
                    jobs=len(getattr(handler, "job_list", ())),
                )

    @app.middleware("http")
    async def authenticate(request, call_next):
        # GETs only read; anything else acts on the session, and acting is
        # what a read-only token must not be able to do.
        required = SCOPE_READ if request.method.upper() in ("GET", "HEAD") else SCOPE_CONTROL
        status, message = auth.authorize(request.headers, required_scope=required)
        if status:
            return JSONResponse(status_code=status, content={"ok": False, "error": message})
        return await call_next(request)

    # Avoid referencing FastAPI WebSocket class in type expressions (lazy import)
    connections: Set[Any] = set()
    broadcast_task: Optional[asyncio.Task] = None

    async def safe_send(ws: Any, payload: Dict[str, Any]):
        try:
            await ws.send_json(payload)
            return True
        except Exception:
            return False

    async def broadcaster():
        loop = asyncio.get_event_loop()
        while True:
            await asyncio.sleep(float(ws_push_interval))
            if not connections:
                continue
            # Keep periodic broadcasts lightweight (no logs), and off the event
            # loop: snapshot() takes the handler lock, which the scheduler
            # holds for the whole of a tick. Taken inline, one slow tick froze
            # every other client of the session with it.
            data = await loop.run_in_executor(None, lambda: handler.snapshot(logs_job_id=-1))
            payload = {"type": "snapshot", "data": data}
            dead: Set[Any] = set()
            for ws in list(connections):
                ok = await safe_send(ws, payload)
                if not ok:
                    dead.add(ws)
            for ws in dead:
                connections.discard(ws)

    @app.on_event("startup")
    async def on_startup():
        nonlocal broadcast_task
        if start_headless_on_startup:
            handler.start_headless(tick_interval=tick_interval)
        broadcast_task = asyncio.create_task(broadcaster())

    @app.on_event("shutdown")
    async def on_shutdown():
        nonlocal broadcast_task
        if broadcast_task is not None:
            broadcast_task.cancel()
            broadcast_task = None
        if start_headless_on_startup:
            handler.stop_headless()
        else:
            handler.terminate_all_jobs()

    @app.get("/status")
    def get_status(
        logs_job_id: Optional[int] = None,
        logs_offset: Optional[int] = None,
        logs_limit: Optional[int] = None,
    ):
        # Keep /status lightweight by default (no logs).
        if logs_job_id is None:
            logs_job_id = -1
        return handler.snapshot(logs_job_id=logs_job_id, logs_offset=logs_offset, logs_limit=logs_limit)

    @app.get("/jobs")
    def list_jobs():
        snap = handler.snapshot(logs_job_id=-1)  # keep logs null
        snap["logs"] = None
        return snap

    @app.get("/jobs/{job_id}")
    def get_job(job_id: int, logs_offset: Optional[int] = None, logs_limit: Optional[int] = None):
        return handler.snapshot(logs_job_id=job_id, logs_offset=logs_offset, logs_limit=logs_limit)

    def _ok(message: str, **extra):
        payload = {"ok": True, "message": message}
        payload.update(extra)
        return payload

    @app.post("/jobs/{job_id}/pause")
    def pause_job(job_id: int):
        handler.enqueue_command("pause", job_id=job_id)
        return _ok("pause requested", job_id=job_id)

    @app.post("/jobs/{job_id}/start")
    def start_job(job_id: int):
        handler.enqueue_command("start", job_id=job_id)
        return _ok("start/resume requested", job_id=job_id)

    @app.post("/jobs/{job_id}/kill")
    def kill_job(job_id: int):
        handler.enqueue_command("kill", job_id=job_id)
        return _ok("kill/cancel requested", job_id=job_id)

    @app.post("/jobs/{job_id}/open")
    def open_job(job_id: int):
        handler.enqueue_command("open", job_id=job_id)
        return _ok("open requested", job_id=job_id)

    @app.post("/jobs/enqueue")
    def enqueue_jobs(payload: Dict[str, Any]):
        if not isinstance(payload, dict):
            raise ValueError("payload must be a JSON object")

        # Configuring the session and adding jobs to it are two different
        # things: a caller that only wants its jobs run sends no options, and
        # what the session was told before it stands (see enqueue_parallel_jobs).
        # How a job reports its progress is the job's own business and travels
        # with it, so nothing global is set here.
        options = payload.get("options")
        if isinstance(options, dict):
            handler.configure_runtime(
                nb_jobs=options.get("nb_jobs"),
                process_group=options.get("process_group"),
                auto_exit=options.get("auto_exit"),
                log_size_limit=options.get("log_size_limit"),
                format_yaml=options.get("format_yaml"),
            )

        jobs_data = payload.get("jobs")
        if not isinstance(jobs_data, list):
            raise ValueError("'jobs' must be a list")

        added = 0
        for item in jobs_data:
            if not isinstance(item, dict):
                raise ValueError("each job entry must be a JSON object")
            job = payload_to_job(item, default_log_size_limit=getattr(handler, "log_size_limit", 200))
            handler.add_job(job)
            added += 1

        return _ok("jobs enqueued", added=added, total_jobs=len(handler.job_list))

    @app.post("/config")
    def set_config(
        nb_jobs: Optional[int] = None,
        process_group: Optional[bool] = None,
        auto_exit: Optional[bool] = None,
        log_size_limit: Optional[int] = None,
    ):
        """Update runtime scheduling options on the fly (e.g. max parallel jobs).

        Parameters are passed as query args; any omitted value is left unchanged.
        Changing nb_jobs immediately fills or frees running slots.
        """
        handler.configure_runtime(
            nb_jobs=nb_jobs,
            process_group=process_group,
            auto_exit=auto_exit,
            log_size_limit=log_size_limit,
        )
        return _ok("config updated", nb_jobs=int(handler.nb_jobs))

    @app.post("/shutdown")
    async def shutdown():
        if start_headless_on_startup:
            handler.enqueue_command("shutdown")
        else:
            handler.terminate_all_jobs()
            handler.request_shutdown()
        if callable(shutdown_callback):
            shutdown_callback()
        return _ok("shutdown requested")

    @app.websocket("/ws")
    async def ws_endpoint(ws: Any):
        # Authenticate before accepting: a rejected handshake never reaches
        # application code, and a browser page cannot read the token file.
        status, message = auth.authorize(ws.headers, required_scope=SCOPE_READ)
        if status:
            await ws.close(code=1008, reason=message)
            return

        ws_scope = auth.scope_for_token(auth.token_from_header(ws.headers.get(AUTH_HEADER)))

        await ws.accept()
        connections.add(ws)

        # Send initial state
        await ws.send_json({"type": "snapshot", "data": handler.snapshot(logs_job_id=-1)})

        try:
            while True:
                msg = await ws.receive_json()
                if not isinstance(msg, dict):
                    continue

                msg_type = msg.get("type")

                if msg_type == "snapshot":
                    await ws.send_json({"type": "snapshot", "data": handler.snapshot(logs_job_id=-1)})
                    continue

                if msg_type == "command":
                    if not scope_satisfies(ws_scope, SCOPE_CONTROL):
                        await ws.send_json({"type": "error", "message": "This token is read-only"})
                        continue

                    name = msg.get("name")
                    job_id = msg.get("job_id")
                    if name in ("pause", "start", "kill", "open"):
                        if job_id is None:
                            await ws.send_json({"type": "error", "message": "job_id is required"})
                            continue
                        handler.enqueue_command(name, job_id=int(job_id))
                    else:
                        await ws.send_json({"type": "error", "message": f"unknown command: {name}"})
                        continue

                    await ws.send_json({"type": "snapshot", "data": handler.snapshot(logs_job_id=-1)})
                    continue

        except WebSocketDisconnect:
            connections.discard(ws)
        except Exception as e:
            connections.discard(ws)
            try:
                await ws.close()
            except Exception:
                pass

    # Basic exception wrapper for REST (keeps errors JSON)
    @app.exception_handler(Exception)
    async def all_exception_handler(_, exc: Exception):
        return JSONResponse(status_code=500, content={"ok": False, "error": str(exc)})

    return app


def create_uvicorn_server(
    handler,
    *,
    auth=None,
    transport: str = "tcp",
    host: str = hard_settings.daemon_default_host,
    port: int = hard_settings.daemon_default_port,
    socket_path: Optional[str] = None,
    allow_remote_bind: bool = False,
    log_level: str = "info",
    start_headless_on_startup: bool = True,
    quiet: bool = False,
    shutdown_callback=None,
):
    """Build the uvicorn server for a session.

    Args:
        auth (ApiAuth): the session tokens. Generated when omitted, in which
            case read them back from ``server.odatix_auth`` -- a caller that
            never reads them has built a session nothing can talk to.
        transport (str): "unix" to listen on ``socket_path``, "tcp" otherwise.
        allow_remote_bind (bool): required to bind a TCP address other than
            loopback. Listening on a routable address puts the session in
            reach of the whole network, so it is never done by accident.
    """
    try:
        uvicorn = importlib.import_module("uvicorn")
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("uvicorn is not installed. Install with: pip install uvicorn") from e

    transport = str(transport or "tcp")
    if transport == TRANSPORT_UNIX and not socket_path:
        raise ValueError("transport 'unix' requires a socket path")

    if transport != TRANSPORT_UNIX and not is_loopback_host(host) and not allow_remote_bind:
        raise ValueError(
            "Refusing to bind {} : this exposes the session to the network. "
            "Pass allow_remote_bind=True (odatix daemon --expose) if that is "
            "really what you want, and prefer an SSH tunnel.".format(host)
        )

    if auth is None:
        auth = ApiAuth.generate(bound_host=host)

    app = create_parallel_job_app(
        handler,
        auth=auth,
        start_headless_on_startup=start_headless_on_startup,
        shutdown_callback=shutdown_callback,
    )

    log_config = None
    access_log = True
    if quiet:
        # Force silence: no access logs, and all uvicorn loggers routed to NullHandler.
        access_log = False
        log_level = "critical"
        log_config = _null_uvicorn_log_config()

    config_kwargs = {
        "log_level": str(log_level),
        "access_log": bool(access_log),
        "log_config": log_config,
    }
    if transport == TRANSPORT_UNIX:
        config_kwargs["uds"] = str(socket_path)
    else:
        config_kwargs["host"] = str(host)
        config_kwargs["port"] = int(port)

    config = uvicorn.Config(app, **config_kwargs)
    server = uvicorn.Server(config)
    server.odatix_auth = auth
    return server


def run_parallel_job_api(
    handler,
    *,
    auth=None,
    transport: str = "tcp",
    host: str = hard_settings.daemon_default_host,
    port: int = hard_settings.daemon_default_port,
    socket_path: Optional[str] = None,
    allow_remote_bind: bool = False,
    log_level: str = "info",
    start_headless_on_startup: bool = True,
):
    server = create_uvicorn_server(
        handler,
        auth=auth,
        transport=transport,
        host=host,
        port=port,
        socket_path=socket_path,
        allow_remote_bind=allow_remote_bind,
        log_level=log_level,
        start_headless_on_startup=start_headless_on_startup,
    )
    return server.run()
