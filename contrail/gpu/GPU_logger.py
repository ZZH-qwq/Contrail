import sqlite3
import time
import getpass
import schedule
import pandas as pd
import datetime as dt
from loguru import logger

from typing import List, Dict, Tuple, Optional

from pynvml import (
    nvmlInit,
    nvmlShutdown,
    nvmlDeviceGetCount,
    nvmlDeviceGetHandleByIndex,
    nvmlDeviceGetName,
    nvmlDeviceGetUtilizationRates,
    nvmlDeviceGetMemoryInfo,
    nvmlDeviceGetGraphicsRunningProcesses,
    nvmlDeviceGetComputeRunningProcesses,
    NVMLError,
)
import psutil

from contrail.utils.email_sender import EmailSender, EmailTemplate
from contrail.gpu.GPU_fault_detector import GpuFaultDetector


def get_gpu_info() -> List[Dict]:
    logger.trace("Getting GPU info")
    # 初始化 NVML
    nvmlInit()
    device_count = nvmlDeviceGetCount()
    gpu_info = []

    for i in range(device_count):
        # 获取 GPU 句柄
        handle = nvmlDeviceGetHandleByIndex(i)

        # 获取 GPU 名称
        gpu_name = nvmlDeviceGetName(handle)

        # 获取 GPU 使用率
        utilization = nvmlDeviceGetUtilizationRates(handle)
        gpu_utilization = utilization.gpu
        memory_utilization = utilization.memory

        # 获取显存信息
        memory_info = nvmlDeviceGetMemoryInfo(handle)
        total_memory = memory_info.total
        used_memory = memory_info.used
        free_memory = memory_info.free

        # 获取正在使用的进程信息
        try:
            processes = nvmlDeviceGetGraphicsRunningProcesses(handle) + nvmlDeviceGetComputeRunningProcesses(handle)
        except NVMLError as err:
            logger.error(f"Error getting processes for GPU {i}: {err}")
            processes = []

        process_info = []
        for p in processes:
            try:
                proc = psutil.Process(p.pid)
                username = proc.username()  # 获取用户
                cpu_usage = proc.cpu_percent()  # 获取 CPU 使用率
                process_info.append(
                    {
                        "pid": p.pid,
                        "user": username,
                        "used_memory": p.usedGpuMemory,
                        "cpu_usage": cpu_usage,
                        "name": proc.name(),
                    }
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # 处理进程终止或权限不足的情况
                process_info.append(
                    {
                        "pid": p.pid,
                        "user": "N/A",
                        "used_memory": p.usedGpuMemory,
                        "cpu_usage": "N/A",
                        "name": "Unknown",
                    }
                )

        # 保存 GPU 信息
        gpu_info.append(
            {
                "gpu_index": i,
                "name": gpu_name,
                "gpu_utilization": gpu_utilization,
                "memory_utilization": memory_utilization,
                "total_memory": total_memory,
                "used_memory": used_memory,
                "free_memory": free_memory,
                "processes": process_info,
            }
        )

    # 关闭 NVML
    nvmlShutdown()
    logger.trace("Get GPU info completed")
    return gpu_info


def process_gpu_info(gpu_info: List[Dict]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    将 gpu_info: List[Dict] 转换为 GPU 和进程的 dataframes

    Args:
        gpu_info (List[Dict]): GPU 信息

    Returns:
        Tuple[pd.DataFrame, pd.DataFrame]: GPU 和进程的 dataframes
    """

    logger.trace("Processing GPU info")
    gpu_info_df = pd.DataFrame(gpu_info)
    gpu_info_df = gpu_info_df.set_index("gpu_index")

    # GPU 使用率 和 内存使用率
    # gpu_utilization, memory_utilization, total_memory, used_memory, free_memory
    gpu_df = gpu_info_df[["gpu_utilization", "memory_utilization", "total_memory", "used_memory", "free_memory"]]

    # 进程信息 - 每个GPU的进程按用户分组
    processes = []
    for gpu in gpu_info:
        user_data = {}
        tot_processes = len(gpu["processes"])
        for proc in gpu["processes"]:
            if proc["user"] not in user_data:
                user_data[proc["user"]] = {"used_memory": 0, "gpu_utilization": 0}
            user_data[proc["user"]]["used_memory"] += proc["used_memory"]
            user_data[proc["user"]]["gpu_utilization"] += gpu["gpu_utilization"] / tot_processes

        for user, data in user_data.items():
            processes.append(
                {
                    "gpu_index": gpu["gpu_index"],
                    "user": user,
                    "used_memory": data["used_memory"],
                    "gpu_utilization": data["gpu_utilization"],
                }
            )

    if len(processes) == 0:
        processes_df = pd.DataFrame(columns=["gpu_index", "user", "used_memory", "gpu_utilization"])
    else:
        processes_df = pd.DataFrame(processes).set_index("gpu_index")

    return gpu_df, processes_df


def initialize_database(db_path="gpu_history.db", is_history=False) -> None:
    logger.trace(f"Initializing database at {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if not is_history:
        # 创建 GPU 信息表，允许多条记录
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gpu_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gpu_index INTEGER,
                name TEXT,
                gpu_utilization INTEGER,
                memory_utilization INTEGER,
                total_memory INTEGER,
                used_memory INTEGER,
                free_memory INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 创建 GPU 用户使用记录表，允许多条记录
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gpu_user_info (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gpu_index INTEGER,
                user TEXT,
                used_memory INTEGER,
                gpu_utilization INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    else:
        # 创建 GPU 历史记录 以更长间隔记录历史数据
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gpu_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gpu_index INTEGER,
                gpu_utilization INTEGER,
                gpu_utilization_max INTEGER,
                gpu_utilization_min INTEGER,
                used_memory INTEGER,
                used_memory_max INTEGER,
                used_memory_min INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # 创建 GPU 用户使用历史记录表，以更长间隔记录历史数据
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS gpu_user_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gpu_index INTEGER,
                user TEXT,
                used_memory INTEGER,
                used_memory_max INTEGER,
                used_memory_min INTEGER,
                gpu_utilization INTEGER,
                gpu_utilization_max INTEGER,
                gpu_utilization_min INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    # 添加索引
    if not is_history:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpu_timestamp ON gpu_info (timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpu_index ON gpu_info (gpu_index)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_timestamp ON gpu_user_info (timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_gpu_index ON gpu_user_info (gpu_index)")
    else:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpu_history_timestamp ON gpu_history (timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpu_history_gpu_index ON gpu_history (gpu_index)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_history_timestamp ON gpu_user_history (timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_history_gpu_index ON gpu_user_history (gpu_index)")

    # 使用 WAL 模式
    cursor.execute("PRAGMA journal_mode=WAL")

    conn.commit()
    conn.close()
    logger.trace("Initialize database completed")


def update_database(
    gpu_dfs: Tuple[pd.DataFrame, pd.DataFrame],
    timestamp: str,
    db_path: str = "gpu_info.db",
) -> None:
    """
    更新实时数据

    Args:
        gpu_dfs (Tuple[pd.DataFrame, pd.DataFrame]): GPU 和进程数据
        timestamp (str): 时间戳
        db_path (str, optional): 数据库路径. Defaults to "gpu_info.db".

    Returns:
        None
    """

    logger.trace(f"Updating database at {db_path} with timestamp {timestamp}")
    conn = sqlite3.connect(db_path)

    gpu_df, proc_df = gpu_dfs

    try:
        # 启动事务
        conn.execute("BEGIN TRANSACTION")

        # 插入 GPU 信息
        gpu_df["timestamp"] = timestamp
        gpu_df.to_sql("gpu_info", conn, if_exists="append", index=True)

        # 插入 GPU 用户使用信息
        proc_df["timestamp"] = timestamp
        proc_df.to_sql("gpu_user_info", conn, if_exists="append", index=True)

        # 提交事务
        conn.commit()

    except Exception as e:
        logger.error(f"Error updating database {db_path}: {e}")
        # 出现错误时回滚
        conn.rollback()

    finally:
        conn.close()
    logger.trace("Update database completed")


def aggregate_data(
    timestamp: dt.datetime,
    period_s: int = 30,
    db_path: str = "gpu_history.db",
    db_realtime_path: str = "gpu_info.db",
    fault_detector: Optional[GpuFaultDetector] = None,
) -> None:
    """
    合并timestamp前period秒内的数据，提取平均值、最大值和最小值，并将其插入到历史记录中

    Args:
        timestamp (dt.datetime): 时间戳
        period_s (int, optional): 聚合周期. Defaults to 30.
        db_path (str, optional): 数据库路径. Defaults to "gpu_history.db".
        db_realtime_path (str, optional): 实时数据数据库路径. Defaults to "gpu_info.db".
        fault_detector (Optional[GpuFaultDetector], optional): GPU 事件检测器. Defaults to None.

    Returns:
        None
    """
    logger.trace(f"Aggregating data at {timestamp} with period {period_s} seconds")
    conn = sqlite3.connect(db_realtime_path)

    # 查询时间范围
    start_time = (timestamp - pd.Timedelta(seconds=period_s)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")

    query = """
        SELECT gpu_index, gpu_utilization, used_memory
        FROM gpu_info
        WHERE timestamp BETWEEN ? AND ?
    """
    result = pd.read_sql_query(query, conn, params=(start_time, end_time))

    query_user = """
        SELECT gpu_index, user, used_memory, gpu_utilization
        FROM gpu_user_info
        WHERE timestamp BETWEEN ? AND ?
    """
    result_user = pd.read_sql_query(query_user, conn, params=(start_time, end_time))

    conn.close()

    # 计算平均值、第一四分位数和第三四分位数
    result = (
        result.groupby("gpu_index")
        .agg(
            gpu_utilization_avg=("gpu_utilization", "mean"),
            gpu_utilization_min=("gpu_utilization", lambda x: x.quantile(0.25)),
            gpu_utilization_max=("gpu_utilization", lambda x: x.quantile(0.75)),
            used_memory_avg=("used_memory", "mean"),
            used_memory_min=("used_memory", lambda x: x.quantile(0.25)),
            used_memory_max=("used_memory", lambda x: x.quantile(0.75)),
        )
        .reset_index()
    )

    result.rename(
        columns={
            "used_memory_avg": "used_memory",
            "gpu_utilization_avg": "gpu_utilization",
        },
        inplace=True,
    )
    result["timestamp"] = end_time

    # 计算平均值、第一四分位数和第三四分位数
    result_user = (
        result_user.groupby(["gpu_index", "user"])
        .agg(
            used_memory_avg=("used_memory", "mean"),
            used_memory_min=("used_memory", lambda x: x.quantile(0.25)),
            used_memory_max=("used_memory", lambda x: x.quantile(0.75)),
            gpu_utilization_avg=("gpu_utilization", "mean"),
            gpu_utilization_min=("gpu_utilization", lambda x: x.quantile(0.25)),
            gpu_utilization_max=("gpu_utilization", lambda x: x.quantile(0.75)),
        )
        .reset_index()
    )

    result_user.rename(
        columns={
            "used_memory_avg": "used_memory",
            "gpu_utilization_avg": "gpu_utilization",
        },
        inplace=True,
    )
    result_user["timestamp"] = end_time

    # 检测 GPU 故障
    if fault_detector:
        fault_detector.update(result)

    conn = sqlite3.connect(db_path)

    # 插入 GPU 历史记录
    result.to_sql("gpu_history", conn, if_exists="append", index=False)

    # 插入 GPU 用户使用历史记录
    result_user.to_sql("gpu_user_history", conn, if_exists="append", index=False)

    conn.commit()
    conn.close()

    logger.trace("Aggregate data completed")


def remove_old_data(
    timestamp: dt.datetime,
    period_s: int = 3600,
    db_path: str = "gpu_info.db",
) -> None:
    """
    删除 timestamp 前 period 秒的数据

    Args:
        timestamp (dt.datetime): 时间戳
        period_s (int, optional): 删除周期. Defaults to 3600.
        db_path (str, optional): 数据库路径. Defaults to "gpu_info.db".

    Returns:
        None
    """
    logger.trace(f"Removing old data before {timestamp - pd.Timedelta(seconds=period_s)}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 删除过期的 GPU 信息
    start_time = (timestamp - pd.Timedelta(seconds=period_s)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("DELETE FROM gpu_info WHERE timestamp < ?", (start_time,))

    # 删除过期的 GPU 用户使用信息
    cursor.execute("DELETE FROM gpu_user_info WHERE timestamp < ?", (start_time,))

    # 提交事务
    conn.commit()
    conn.close()

    # VAACUUM
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("VACUUM")
    conn.commit()

    conn.close()
    logger.trace("Remove old data completed")


ERROR_REPORT_TEMPLATE = EmailTemplate(
    subject="GPU Logger: Uncaught Exception",
    content="""
    [GPU Logger Alert]
    Time: ${time}
    Hostname: ${hostname}
    An uncaught exception occurred in the GPU logger.

    Error: ${error}
    """,
)


if __name__ == "__main__":
    import json

    gpu_info = get_gpu_info()
    message = json.dumps(gpu_info)
    print(message)
