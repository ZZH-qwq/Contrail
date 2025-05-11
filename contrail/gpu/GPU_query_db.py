from loguru import logger
import os
import sqlite3
import pandas as pd
import datetime as dt
import streamlit as st

from typing import Optional, Tuple, Dict


if os.getenv("ENABLE_NAME_DICT", "0") == "1":
    from utils.name_dict import dict_username


@st.cache_data
def query_latest_gpu_info(db_path: str, query_tm: Optional[str] = None) -> pd.DataFrame:
    """
    查询最新的 GPU 状态信息（包括 GPU 使用率、内存使用情况等）。

    Args:
        db_path (str): SQLite 数据库路径。
        query_tm (Optional[str]): 查询时间 token

    Returns:
        pd.DataFrame: 最新的 GPU 状态信息。
    """
    logger.trace(f"Querying latest GPU info from {db_path}")
    conn = sqlite3.connect(db_path)

    # 查询最新的 GPU 信息
    query = """
        SELECT *
        FROM gpu_info
        WHERE timestamp = (
            SELECT MAX(timestamp)
            FROM gpu_info
        )
    """
    data = pd.read_sql_query(query, conn)
    conn.close()
    logger.trace("Query latest GPU info completed")

    # 将时间戳转换为 datetime 类型
    data["timestamp"] = (
        pd.to_datetime(data["timestamp"])
        .dt.tz_localize("UTC")
        .dt.tz_convert("Asia/Shanghai")
        .dt.strftime("%Y-%m-%d %H:%M:%S")
    )

    return data


@st.cache_data
def query_min_max_timestamp(db_path: str, query_tm: Optional[str] = None) -> Tuple[dt.datetime, dt.datetime]:
    """
    查询最早和最晚的 GPU 数据记录时间。

    Args:
        db_path (str): SQLite 数据库路径。
        query_tm (Optional[str]): 查询时间 token

    Returns:
        min_timestamp (datetime): 最早的 GPU 数据记录时间。
        max_timestamp (datetime): 最晚的 GPU 数据记录时间。
    """
    logger.trace(f"Querying min and max timestamp from {db_path}")
    conn = sqlite3.connect(db_path)

    # 查询最早和最晚的 GPU 数据记录时间
    query = """
        SELECT 
            MIN(timestamp) AS min_timestamp,
            MAX(timestamp) AS max_timestamp
        FROM gpu_history
    """
    data = pd.read_sql_query(query, conn)
    conn.close()
    logger.trace("Query min and max timestamp completed")

    if data.empty:
        return None, None

    min_timestamp = pd.to_datetime(data["min_timestamp"].iloc[0]).tz_localize("UTC").tz_convert("Asia/Shanghai")
    max_timestamp = pd.to_datetime(data["max_timestamp"].iloc[0]).tz_localize("UTC").tz_convert("Asia/Shanghai")

    return min_timestamp, max_timestamp


@st.cache_data
def query_gpu_realtime_usage(start_time: str, end_time: str, db_path: str) -> pd.DataFrame:
    """
    查询指定时间范围内的 GPU 使用情况。

    Args:
        start_time (str): 起始时间，格式为 "YYYY-MM-DD HH:MM:SS"。
        end_time (str): 终止时间，格式为 "YYYY-MM-DD HH:MM:SS"。
        db_path (str): SQLite 数据库路径。

    Returns:
        gpu_utilization_df: 每台 GPU 在每个时刻的使用率变化。
    """
    logger.trace(f"Querying GPU realtime usage from {start_time} to {end_time} in {db_path}")
    conn = sqlite3.connect(db_path)

    # 查询 GPU 信息
    query = """
        SELECT gpu_index, gpu_utilization, timestamp
        FROM gpu_info
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp
    """
    data = pd.read_sql_query(query, conn, params=(start_time, end_time))
    conn.close()
    logger.trace("Query GPU realtime usage completed")

    # 将时间戳转换为 datetime 类型
    data["timestamp"] = pd.to_datetime(data["timestamp"]).dt.tz_localize("UTC").dt.tz_convert("Asia/Shanghai")

    return data


@st.cache_data
def query_gpu_memory_realtime_usage(start_time: str, end_time: str, db_path: str) -> pd.DataFrame:
    """
    查询指定时间范围内的 GPU 内存使用情况。

    Args:
        start_time (str): 起始时间，格式为 "YYYY-MM-DD HH:MM:SS"。
        end_time (str): 终止时间，格式为 "YYYY-MM-DD HH:MM:SS"。
        db_path (str): SQLite 数据库路径。

    Returns:
        pd.DataFrame: GPU 内存使用情况。
    """
    logger.trace(f"Querying GPU memory realtime usage from {start_time} to {end_time} in {db_path}")
    conn = sqlite3.connect(db_path)

    # 查询 GPU 信息
    query = """
        SELECT gpu_index, used_memory, timestamp
        FROM gpu_info
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp
    """
    data = pd.read_sql_query(query, conn, params=(start_time, end_time))
    conn.close()
    logger.trace("Query GPU memory realtime usage completed")

    # 将时间戳转换为 datetime 类型
    data["timestamp"] = pd.to_datetime(data["timestamp"]).dt.tz_localize("UTC").dt.tz_convert("Asia/Shanghai")

    return data


@st.cache_data
def query_user_gpu_realtime_usage(start_time: str, end_time: str, db_path: str) -> pd.DataFrame:
    """
    查询指定时间范围内的用户 GPU 使用情况。

    Args:
        start_time (str): 起始时间，格式为 "YYYY-MM-DD HH:MM:SS"。
        end_time (str): 终止时间，格式为 "YYYY-MM-DD HH:MM:SS"。
        db_path (str): SQLite 数据库路径。

    Returns:
        pd.DataFrame: 用户 GPU 使用情况。
    """
    logger.trace(f"Querying user GPU realtime usage from {start_time} to {end_time} in {db_path}")
    conn = sqlite3.connect(db_path)

    # 查询用户 GPU 使用情况
    query = """
        SELECT gpu_index, user, gpu_utilization, timestamp
        FROM gpu_user_info
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp
    """
    data = pd.read_sql_query(query, conn, params=(start_time, end_time))
    conn.close()
    logger.trace("Query user GPU realtime usage completed")

    # 将时间戳转换为 datetime 类型
    data["timestamp"] = pd.to_datetime(data["timestamp"]).dt.tz_localize("UTC").dt.tz_convert("Asia/Shanghai")

    return data


@st.cache_data
def query_user_gpu_memory_realtime_usage(start_time: str, end_time: str, db_path: str) -> pd.DataFrame:
    """
    查询指定时间范围内的用户 GPU 内存使用情况。

    Args:
        start_time (str): 起始时间，格式为 "YYYY-MM-DD HH:MM:SS"。
        end_time (str): 终止时间，格式为 "YYYY-MM-DD HH:MM:SS"。
        db_path (str): SQLite 数据库路径。

    Returns:
        pd.DataFrame: 用户 GPU 内存使用情况。
    """
    logger.trace(f"Querying user GPU memory realtime usage from {start_time} to {end_time} in {db_path}")
    conn = sqlite3.connect(db_path)

    # 查询用户 GPU 使用情况
    query = """
        SELECT gpu_index, user, used_memory, timestamp
        FROM gpu_user_info
        WHERE timestamp BETWEEN ? AND ?
        ORDER BY timestamp
    """
    data = pd.read_sql_query(query, conn, params=(start_time, end_time))
    conn.close()
    logger.trace("Query user GPU memory realtime usage completed")

    # 将时间戳转换为 datetime 类型
    data["timestamp"] = pd.to_datetime(data["timestamp"]).dt.tz_localize("UTC").dt.tz_convert("Asia/Shanghai")

    return data


def get_period_sample_interval(start_time: dt.datetime, end_time: dt.datetime) -> int:
    """
    获取指定时间段的采样间隔。

    Args:
        start_time (dt.datetime): 起始时间。
        end_time (dt.datetime): 终止时间。

    Returns:
        int: 采样间隔。
    """
    # 根据时间段计算采样间隔
    period_seconds = (end_time - start_time).total_seconds()

    if period_seconds <= 3600:  # 小于 1 小时，采样间隔为 10 秒
        interval = 30
    elif period_seconds <= 86400:  # 1 小时到 1 天，采样间隔为 1 * (小时数//8 + 1) 分钟
        interval = 60 * (period_seconds // 28800 + 1)
    elif period_seconds <= 7 * 86400:  # 1 天到 7 天，采样间隔为 5 * 天数 分钟
        interval = 300 * (period_seconds // 86400)
    else:  # 超过 7 天，采样间隔为 1 小时
        interval = 3600

    return interval


@st.cache_data
def query_gpu_history_usage(
    start_time: dt.datetime,
    end_time: dt.datetime,
    db_path: str,
    latest_tm: Optional[str] = None,
) -> pd.DataFrame:
    """
    查询指定时间范围内的 GPU 使用情况，并进行间隔采样以减小数据量。

    Args:
        start_time (dt.datetime): 起始时间。
        end_time (dt.datetime): 终止时间。
        db_path (str): SQLite 数据库路径。
        latest_tm (Optional[str]): 查询时间 token

    Returns:
        pd.DataFrame: GPU 使用情况。
    """
    logger.trace(f"Querying GPU history usage from {start_time} to {end_time} in {db_path}")
    conn = sqlite3.connect(db_path)

    # 根据时间段计算采样间隔
    interval = get_period_sample_interval(start_time, end_time)

    # SQL 查询
    query = f"""
        WITH AlignedData AS (
            SELECT
                gpu_index,
                -- 将时间戳对齐到采样间隔
                DATETIME(FLOOR(UNIXEPOCH(timestamp) / {interval}) * {interval}, 'unixepoch') AS aligned_timestamp,
                AVG(gpu_utilization) AS gpu_utilization,
                MIN(gpu_utilization_min) AS gpu_utilization_min,
                MAX(gpu_utilization_max) AS gpu_utilization_max,
                AVG(used_memory) AS used_memory,
                MIN(used_memory_min) AS used_memory_min,
                MAX(used_memory_max) AS used_memory_max
            FROM gpu_history
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY gpu_index, aligned_timestamp
        )
        SELECT *
        FROM AlignedData
        ORDER BY aligned_timestamp
    """
    data = pd.read_sql_query(query, conn, params=(start_time, end_time))

    conn.close()
    logger.trace("Query GPU history usage completed")

    # 将时间戳转换为 datetime 类型
    data["timestamp"] = pd.to_datetime(data["aligned_timestamp"]).dt.tz_localize("UTC").dt.tz_convert("Asia/Shanghai")

    # 将显存相关字段转换为 GB
    data["used_memory"] = data["used_memory"] / 0x40000000
    data["used_memory_max"] = data["used_memory_max"] / 0x40000000
    data["used_memory_min"] = data["used_memory_min"] / 0x40000000

    return data


@st.cache_data
def query_gpu_history_average_usage(
    start_time: dt.datetime,
    end_time: dt.datetime,
    db_path: str,
    latest_tm: Optional[str] = None,
) -> pd.DataFrame:
    """
    查询指定时间范围内的 GPU 平均使用情况。

    Args:
        start_time (dt.datetime): 起始时间。
        end_time (dt.datetime): 终止时间。
        db_path (str): SQLite 数据库路径。
        latest_tm (Optional[str]): 查询时间 token

    Returns:
        pd.DataFrame: GPU 平均使用情况。
    """
    logger.trace(f"Querying GPU history average usage from {start_time} to {end_time} in {db_path}")
    conn = sqlite3.connect(db_path)

    # 查询 GPU 信息
    query = """
        SELECT 
            gpu_index,
            AVG(gpu_utilization) AS avg_gpu_utilization,
            AVG(used_memory) AS avg_used_memory
        FROM gpu_history
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY gpu_index
    """
    data = pd.read_sql_query(query, conn, params=(start_time, end_time))
    conn.close()
    logger.trace("Query GPU history average usage completed")

    # 将显存相关字段转换为 GB
    data["avg_used_memory"] = data["avg_used_memory"] / 0x40000000

    return data


@st.cache_data
def query_gpu_user_history_usage(
    start_time: dt.datetime,
    end_time: dt.datetime,
    db_path: str,
    latest_tm: Optional[str] = None,
) -> Tuple[Dict[str, Dict[int, pd.DataFrame]], pd.DatetimeIndex]:
    """
    查询指定时间范围内的用户 GPU 使用情况，并进行间隔采样以减小数据量。

    Args:
        start_time (dt.datetime): 起始时间。
        end_time (dt.datetime): 终止时间。
        db_path (str): SQLite 数据库路径。
        latest_tm (Optional[str]): 查询时间 token

    Returns:
        Tuple[dict, pd.DatetimeIndex]: 用户 GPU 使用情况。
    """
    logger.trace(f"Querying GPU user history usage from {start_time} to {end_time} in {db_path}")
    conn = sqlite3.connect(db_path)

    # 根据时间段计算采样间隔
    interval = get_period_sample_interval(start_time, end_time)

    # SQL 查询
    query = f"""
        WITH AlignedData AS (
            SELECT
                user,
                gpu_index,
                -- 将时间戳对齐到采样间隔
                DATETIME(FLOOR(UNIXEPOCH(timestamp) / {interval}) * {interval}, 'unixepoch') AS aligned_timestamp,
                AVG(gpu_utilization) AS gpu_utilization,
                AVG(used_memory) AS used_memory
            FROM gpu_user_history
            WHERE timestamp BETWEEN ? AND ?
            GROUP BY user, gpu_index, aligned_timestamp
        )
        SELECT *
        FROM AlignedData
        ORDER BY aligned_timestamp
    """
    data = pd.read_sql_query(query, conn, params=(start_time, end_time))
    conn.close()
    logger.trace("Query GPU user history usage completed")

    if data.empty:
        return {}, pd.DatetimeIndex([])

    # 将时间戳转换为 datetime 类型
    data["timestamp"] = pd.to_datetime(data["aligned_timestamp"]).dt.tz_localize("UTC").dt.tz_convert("Asia/Shanghai")
    max_time = data["timestamp"].max()
    min_time = data["timestamp"].min()

    # 将显存相关字段转换为 GB
    data["used_memory"] = data["used_memory"] / 0x40000000

    # 按照'user'和'gpu_index'进行分组
    grouped = data.groupby(["user", "gpu_index"])

    user_gpu_history = {}
    for (user, gpu_index), group in grouped:
        end_time = group["timestamp"].max()

        full_time_range = pd.date_range(
            start=min_time - pd.Timedelta(seconds=interval) if min_time > start_time else min_time,
            end=end_time + pd.Timedelta(seconds=interval) if end_time < max_time else end_time,
            freq=f"{interval}s",
        )
        group = group.set_index("timestamp").reindex(full_time_range, fill_value=0).reset_index()
        group.rename(columns={"index": "timestamp"}, inplace=True)

        if user not in user_gpu_history:
            user_gpu_history[user] = {}
        user_gpu_history[user][gpu_index] = group

    return user_gpu_history, pd.date_range(start=min_time, end=max_time, freq=f"{interval}s")


@st.cache_data
def query_gpu_user_history_total_usage(
    start_time: dt.datetime,
    end_time: dt.datetime,
    db_path: str,
    latest_tm: Optional[str] = None,
) -> pd.DataFrame:
    """
    查询指定时间范围内的用户 GPU 总用量。

    Args:
        start_time (dt.datetime): 起始时间。
        end_time (dt.datetime): 终止时间。
        db_path (str): SQLite 数据库路径。
        latest_tm (Optional[str]): 查询时间 token

    Returns:
        pd.DataFrame: 用户 GPU 总用量。
    """
    logger.trace(f"Querying GPU user history total usage from {start_time} to {end_time} in {db_path}")
    conn = sqlite3.connect(db_path)

    # 先查询总的历史记录数量作为总时间
    query = """
        SELECT COUNT(*) AS total_count
        FROM gpu_history
        WHERE timestamp BETWEEN ? AND ?
    """

    total_count = pd.read_sql_query(query, conn, params=(start_time, end_time))
    total_count = total_count["total_count"].iloc[0]

    # 查询用户 GPU 总用量
    query = """
        SELECT 
            user,
            SUM(gpu_utilization) AS 平均GPU用量,
            SUM(used_memory) AS 平均显存用量
        FROM gpu_user_history
        WHERE timestamp BETWEEN ? AND ?
        GROUP BY user
    """
    data = pd.read_sql_query(query, conn, params=(start_time, end_time))
    conn.close()
    logger.trace("Query GPU user history total usage completed")

    # 计算总用量
    data["平均GPU用量"] = (data["平均GPU用量"] / total_count).round(1)
    data["平均显存用量"] = (data["平均显存用量"] / 0x40000000 / total_count).round(1)

    return data
