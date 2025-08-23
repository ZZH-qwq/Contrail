import json
import os
import pandas as pd
from dataclasses import dataclass
from functools import cache


@dataclass
class EnabledFeature:
    ai4s: bool = False
    user_info: bool = False
    name_dict: bool = False
    history_only: bool = False


@dataclass
class PageConfig:
    hostname: str
    gpu_type: str
    realtime_db_path: str = None
    history_db_path: str = None
    config: dict = None

    def __post_init__(self):
        if not self.realtime_db_path:
            self.realtime_db_path = f"data/gpu_info_{self.hostname.lower()}.db"
        if not self.history_db_path:
            self.history_db_path = f"data/gpu_history_{self.hostname.lower()}.db"
        if not self.config:
            raise ValueError("Config must be provided.")


def load_config(config_path: str = "config/host_config.json") -> dict:
    """
    Load the configuration file.
    """
    with open(config_path, "r") as f:
        config = json.load(f)
    return config


_config = load_config()
webapp_config = _config.get("webapp", {})
enabled_features = EnabledFeature(**webapp_config.get("features", {}))
devices_config = webapp_config.get("devices", {})

ai4s_users = None
server_users = None


if enabled_features.name_dict:
    if "assets" in webapp_config and "name_dict_files" in webapp_config["assets"]:
        server_file = webapp_config["assets"]["name_dict_files"].get("server", "")
        if server_file and os.path.exists(server_file):
            server_users = pd.read_csv(server_file)
        else:
            raise FileNotFoundError(f"Server name dictionary file '{server_file}' not found.")

        if enabled_features.ai4s:
            ai4s_file = webapp_config["assets"]["name_dict_files"].get("ai4s", "")
            if ai4s_file and os.path.exists(ai4s_file):
                ai4s_users = pd.read_csv(ai4s_file)
            else:
                raise FileNotFoundError(f"AI4S name dictionary file '{ai4s_file}' not found.")
    else:
        raise ValueError("Name dictionary files must be specified in the configuration.")


@cache
def query_ai4s_username(username: str) -> str:
    """
    Query the real name of an AI4S user.
    """
    if ai4s_users is not None:
        match = ai4s_users[ai4s_users["AI4S用户名"] == username]
        if not match.empty:
            return match["姓名"].values[0]
    return username


@cache
def query_server_username(db_path: str, username: str) -> str:
    """
    Query the real name of a server user based on the database path.
    """
    col_name = db_path.split("_")[-1].split(".")[0].capitalize()
    if server_users is not None:
        match = server_users[server_users[col_name] == username]
        if not match.empty:
            return match["姓名"].values[0]
    return username


__all__ = [
    "EnabledFeature",
    "PageConfig",
    "webapp_config",
    "enabled_features",
    "devices_config",
    "ai4s_users",
    "server_users",
    "query_ai4s_username",
    "query_server_username",
]
