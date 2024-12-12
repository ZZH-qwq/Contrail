from loguru import logger
import pandas as pd
import sqlite3
import time
import datetime as dt

from pynvml import *
import psutil


def get_gpu_info():
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
            if err.value == NVML_ERROR_NOT_SUPPORTED:
                processes = []  # 某些设备可能不支持获取进程信息
            else:
                raise

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


def initialize_database(db_path="gpu_history.db"):
    logger.trace(f"Initializing database at {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

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
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpu_timestamp ON gpu_info (timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpu_index ON gpu_info (gpu_index)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_timestamp ON gpu_user_info (timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_gpu_index ON gpu_user_info (gpu_index)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpu_history_timestamp ON gpu_history (timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_gpu_history_gpu_index ON gpu_history (gpu_index)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_history_timestamp ON gpu_user_history (timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_history_gpu_index ON gpu_user_history (gpu_index)")

    conn.commit()
    conn.close()
    logger.trace("Initialize database completed")


def update_database(gpu_info, timestamp, db_path="gpu_history.db"):
    logger.trace(f"Updating database at {db_path} with timestamp {timestamp}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 启动事务
        conn.execute("BEGIN TRANSACTION")

        # 插入 GPU 信息
        for gpu in gpu_info:
            cursor.execute(
                """
                INSERT INTO gpu_info (gpu_index, name, gpu_utilization, memory_utilization, total_memory, used_memory, free_memory, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    gpu["gpu_index"],
                    gpu["name"],
                    gpu["gpu_utilization"],
                    gpu["memory_utilization"],
                    gpu["total_memory"],
                    gpu["used_memory"],
                    gpu["free_memory"],
                    timestamp,
                ),
            )

            # 插入 GPU 用户使用信息
            user_data = {}
            tot_processes = len(gpu["processes"])
            for proc in gpu["processes"]:
                if proc["user"] not in user_data:
                    user_data[proc["user"]] = {"used_memory": 0, "gpu_utilization": 0}
                user_data[proc["user"]]["used_memory"] += proc["used_memory"]
                user_data[proc["user"]]["gpu_utilization"] += gpu["gpu_utilization"] / tot_processes

            for user, data in user_data.items():
                cursor.execute(
                    """
                    INSERT INTO gpu_user_info (gpu_index, user, used_memory, gpu_utilization, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        gpu["gpu_index"],
                        user,
                        data["used_memory"],
                        data["gpu_utilization"],
                        timestamp,
                    ),
                )

        # 提交事务
        conn.commit()

    except Exception as e:
        logger.error(f"Error updating database: {e}")
        # 出现错误时回滚
        conn.rollback()

    finally:
        conn.close()
    logger.trace("Update database completed")


# 合并timestamp前period秒内的数据，提取平均值、最大值和最小值
def aggregate_data(timestamp, period_s=30, db_path="gpu_history.db", db_realtime_path="gpu_info.db"):
    logger.trace(f"Aggregating data at {timestamp} with period {period_s} seconds")
    conn = sqlite3.connect(db_realtime_path)
    cursor = conn.cursor()

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

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 插入 GPU 历史记录
    for _, row in result.iterrows():
        cursor.execute(
            """
            INSERT INTO gpu_history (gpu_index, gpu_utilization, gpu_utilization_max, gpu_utilization_min, used_memory, used_memory_max, used_memory_min, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["gpu_index"],
                row["gpu_utilization_avg"],
                row["gpu_utilization_max"],
                row["gpu_utilization_min"],
                row["used_memory_avg"],
                row["used_memory_max"],
                row["used_memory_min"],
                end_time,
            ),
        )

    conn.commit()
    conn.close()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 插入 GPU 用户使用历史记录
    for _, row in result_user.iterrows():
        cursor.execute(
            """
            INSERT INTO gpu_user_history (gpu_index, user, used_memory, used_memory_max, used_memory_min, gpu_utilization, gpu_utilization_max, gpu_utilization_min, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["gpu_index"],
                row["user"],
                row["used_memory_avg"],
                row["used_memory_max"],
                row["used_memory_min"],
                row["gpu_utilization_avg"],
                row["gpu_utilization_max"],
                row["gpu_utilization_min"],
                end_time,
            ),
        )

    # 提交事务
    conn.commit()
    conn.close()
    logger.trace("Aggregate data completed")


def remove_old_data(timestamp, period_s=3600, db_path="gpu_history.db"):
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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Monitor GPU usage of current device.")
    parser.add_argument("--name", help="The device name to monitor.", default="leo")
    args = parser.parse_args()

    logger.add("log/GPU_logger_{time:YYYY-MM-DD}.log", rotation="00:00", retention="7 days", level="TRACE")
    logger.info("Starting GPU logger")
    DB_PATH = f"data/gpu_history_{args.name}.db"
    DB_REALTIME_PATH = f"data/gpu_info_{args.name}.db"

    initialize_database(db_path=DB_PATH)
    initialize_database(db_path=DB_REALTIME_PATH)
    logger.info("Database initialized")
    timestamp_last = dt.datetime.now(tz=dt.timezone.utc)
    AGGR_PERIOD = 30  # 聚合周期：30 秒

    while True:
        try:
            gpu_info = get_gpu_info()
            curr_time = dt.datetime.now(tz=dt.timezone.utc)
            update_database(gpu_info, curr_time.strftime("%Y-%m-%d %H:%M:%S"), db_path=DB_REALTIME_PATH)
            if (curr_time - timestamp_last).seconds >= AGGR_PERIOD - 1:
                timestamp_last = curr_time
                aggregate_data(timestamp_last, period_s=AGGR_PERIOD, db_path=DB_PATH, db_realtime_path=DB_REALTIME_PATH)
                remove_old_data(timestamp_last, period_s=3600, db_path=DB_REALTIME_PATH)
            time.sleep(1)

        except KeyboardInterrupt:
            logger.info("Monitoring stopped")
            break
