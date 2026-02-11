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

Protocol overview
-----------------
REST endpoints expose command-style operations and snapshots.
WebSocket /ws pushes periodic snapshots and accepts command messages.

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
from typing import Any, Dict, Optional, Set


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
  tick_interval: float = 0.1,
  ws_push_interval: float = 0.25,
  start_headless_on_startup: bool = True,
):
  FastAPI, WebSocket, WebSocketDisconnect, JSONResponse = _require_fastapi()

  app = FastAPI(title="Odatix ParallelJob API")

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
    while True:
      await asyncio.sleep(float(ws_push_interval))
      # Keep periodic broadcasts lightweight (no logs).
      data = handler.snapshot(logs_job_id=-1)
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
  async def get_status(
    logs_job_id: Optional[int] = None,
    logs_offset: Optional[int] = None,
    logs_limit: Optional[int] = None,
  ):
    # Keep /status lightweight by default (no logs).
    if logs_job_id is None:
      logs_job_id = -1
    return handler.snapshot(logs_job_id=logs_job_id, logs_offset=logs_offset, logs_limit=logs_limit)

  @app.get("/jobs")
  async def list_jobs():
    snap = handler.snapshot(logs_job_id=-1)  # keep logs null
    snap["logs"] = None
    return snap

  @app.get("/jobs/{job_id}")
  async def get_job(job_id: int, logs_offset: Optional[int] = None, logs_limit: Optional[int] = None):
    return handler.snapshot(logs_job_id=job_id, logs_offset=logs_offset, logs_limit=logs_limit)

  def _ok(message: str, **extra):
    payload = {"ok": True, "message": message}
    payload.update(extra)
    return payload

  @app.post("/jobs/{job_id}/pause")
  async def pause_job(job_id: int):
    handler.enqueue_command("pause", job_id=job_id)
    return _ok("pause requested", job_id=job_id)

  @app.post("/jobs/{job_id}/start")
  async def start_job(job_id: int):
    handler.enqueue_command("start", job_id=job_id)
    return _ok("start/resume requested", job_id=job_id)

  @app.post("/jobs/{job_id}/kill")
  async def kill_job(job_id: int):
    handler.enqueue_command("kill", job_id=job_id)
    return _ok("kill/cancel requested", job_id=job_id)

  @app.post("/jobs/{job_id}/open")
  async def open_job(job_id: int):
    handler.enqueue_command("open", job_id=job_id)
    return _ok("open requested", job_id=job_id)

  @app.post("/shutdown")
  async def shutdown():
    if start_headless_on_startup:
      handler.enqueue_command("shutdown")
    else:
      handler.terminate_all_jobs()
      handler.request_shutdown()
    return _ok("shutdown requested")

  @app.websocket("/ws")
  async def ws_endpoint(ws: Any):
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
  host: str = "0.0.0.0",
  port: int = 8000,
  log_level: str = "info",
  start_headless_on_startup: bool = True,
  quiet: bool = False,
):
  try:
    uvicorn = importlib.import_module("uvicorn")
  except ImportError as e:  # pragma: no cover
    raise RuntimeError("uvicorn is not installed. Install with: pip install uvicorn") from e

  app = create_parallel_job_app(
    handler,
    start_headless_on_startup=start_headless_on_startup,
  )

  log_config = None
  access_log = True
  if quiet:
    # Force silence: no access logs, and all uvicorn loggers routed to NullHandler.
    access_log = False
    log_level = "critical"
    log_config = _null_uvicorn_log_config()

  config = uvicorn.Config(
    app,
    host=str(host),
    port=int(port),
    log_level=str(log_level),
    access_log=bool(access_log),
    log_config=log_config,
  )
  return uvicorn.Server(config)


def run_parallel_job_api(
  handler,
  *,
  host: str = "0.0.0.0",
  port: int = 8000,
  log_level: str = "info",
  start_headless_on_startup: bool = True,
):
  server = create_uvicorn_server(
    handler,
    host=host,
    port=port,
    log_level=log_level,
    start_headless_on_startup=start_headless_on_startup,
  )
  return server.run()
