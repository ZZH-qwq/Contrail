from __future__ import annotations

import datetime as dt
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import tornado.web

from contrail.utils.config import PageConfig, devices_config, query_server_username


BYTES_PER_GIB = 1024**3
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _memory_gb(value: Any) -> float:
    return round(float(value or 0) / BYTES_PER_GIB, 2)


def _format_timestamp(timestamp: Any) -> str | None:
    if timestamp is None:
        return None
    if isinstance(timestamp, dt.datetime):
        parsed = timestamp
    else:
        parsed = dt.datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _connect_readonly(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(f"Realtime database not found: {db_path}")
    uri = f"file:{path.resolve()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _latest_gpu_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT gpu_index, gpu_utilization, total_memory, used_memory, timestamp
        FROM gpu_info
        WHERE timestamp = (SELECT MAX(timestamp) FROM gpu_info)
        ORDER BY gpu_index
        """
    ).fetchall()


def _latest_user_rows(conn: sqlite3.Connection, timestamp: Any) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT gpu_index, user, used_memory
        FROM gpu_user_info
        WHERE timestamp = ?
        ORDER BY gpu_index, user
        """,
        (timestamp,),
    ).fetchall()


def build_server_status(config: PageConfig) -> dict[str, Any]:
    conn = _connect_readonly(config.realtime_db_path)
    try:
        gpu_rows = _latest_gpu_rows(conn)
        if not gpu_rows:
            return {
                "gpu_type": config.gpu_type,
                "gpu_count": config.config.get("N_GPU", 0),
                "memory_total_gb": config.config.get("GMEM", 0),
                "overall_usage_pct": 0,
                "gpus": [],
            }

        timestamp = gpu_rows[0]["timestamp"]
        users_by_gpu: dict[int, list[dict[str, Any]]] = {}
        for row in _latest_user_rows(conn, timestamp):
            gpu_index = int(row["gpu_index"])
            users_by_gpu.setdefault(gpu_index, []).append(
                {
                    "name": query_server_username(config.realtime_db_path, row["user"]),
                    "memory_used_gb": _memory_gb(row["used_memory"]),
                }
            )
    finally:
        conn.close()

    gpus = [
        {
            "index": int(row["gpu_index"]),
            "utilization_pct": int(row["gpu_utilization"] or 0),
            "memory_used_gb": _memory_gb(row["used_memory"]),
            "users": users_by_gpu.get(int(row["gpu_index"]), []),
        }
        for row in gpu_rows
    ]
    total_memory = max((row["total_memory"] or 0 for row in gpu_rows), default=0)
    memory_total_gb = _memory_gb(total_memory) or config.config.get("GMEM", 0)
    avg_utilization = sum(gpu["utilization_pct"] for gpu in gpus) / len(gpus)

    return {
        "gpu_type": config.gpu_type,
        "gpu_count": len(gpus),
        "memory_total_gb": memory_total_gb,
        "overall_usage_pct": round(avg_utilization),
        "gpus": gpus,
        "_updated_at": _format_timestamp(timestamp),
    }


def build_status_dict(configs: Mapping[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    status_configs = devices_config if configs is None else configs
    servers: dict[str, dict[str, Any]] = {}
    updated_at: str | None = None

    for name, raw_config in status_configs.items():
        config = PageConfig(**raw_config)
        try:
            server_status = build_server_status(config)
        except (OSError, sqlite3.Error) as exc:
            # Keep one unavailable realtime DB from breaking the whole endpoint.
            server_status = {
                "gpu_type": config.gpu_type,
                "gpu_count": config.config.get("N_GPU", 0),
                "memory_total_gb": config.config.get("GMEM", 0),
                "overall_usage_pct": 0,
                "gpus": [],
                "error": str(exc),
            }
        server_updated_at = server_status.pop("_updated_at", None)
        if server_updated_at and (updated_at is None or server_updated_at > updated_at):
            updated_at = server_updated_at
        servers[name.lower()] = server_status

    return {"updated_at": updated_at, "servers": servers}


class GpuStatusHandler(tornado.web.RequestHandler):
    def get(self) -> None:
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.finish(json.dumps(build_status_dict(), ensure_ascii=False))


def install_gpu_status_route() -> None:
    from streamlit import config as st_config
    from streamlit.web.server import Server
    from streamlit.web.server.server_util import make_url_path_regex

    if getattr(Server, "_contrail_gpu_status_route", False):
        return

    create_app_original = Server._create_app

    def _create_app_patched(self: Any) -> Any:
        app = create_app_original(self)
        base = st_config.get_option("server.baseUrlPath")
        route = tornado.web.URLSpec(make_url_path_regex(base, "gpu-status"), GpuStatusHandler)
        app.default_router.rules.insert(0, route)
        return app

    Server._create_app = _create_app_patched
    Server._contrail_gpu_status_route = True
