import pandas as pd
from datetime import datetime
import sqlite3
import sys
import os

from contrail.utils.config import query_ai4s_username


def extract_and_save_to_db(file_path, db_path, table_name, if_exists="replace"):
    """
    从 Excel 文件中提取指定信息，并保存到 SQLite 数据库。

    参数：
    - file_path: Excel 文件路径。
    - db_path: SQLite 数据库路径。
    - table_name: 保存到数据库的表名。
    - if_exists: 如果表存在的处理方式（默认覆盖）。
    """
    # 读取 Excel 文件
    df = pd.read_excel(file_path)

    # 筛选备注为“实际扣费”的行
    filtered_df = df[df["备注"] == "实际扣费"]

    # 提取所需列
    result = filtered_df[["扣费时间", "任务名称", "资源使用人员", "消费金额"]].copy()

    # 将 "资源使用人员" "--" 替换为 "pfs"
    # result["资源使用人员"] = result["资源使用人员"].replace("--", "pfs")

    # 替换人员名称
    result["资源使用人员"] = result["资源使用人员"].apply(lambda x: query_ai4s_username(x))

    # 将“扣费时间”转换为 SQLite DATETIME 格式
    # result["扣费时间"] = pd.to_datetime(result["扣费时间"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    # 连接到 SQLite 数据库
    conn = sqlite3.connect(db_path)

    # 将结果保存到数据库
    result.to_sql(table_name, conn, if_exists=if_exists, index=False)

    # 为表添加索引（提高查询效率）
    cursor = conn.cursor()
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_time ON {table_name} (扣费时间);")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_user ON {table_name} (资源使用人员);")

    # 关闭数据库连接
    conn.commit()
    conn.close()


def query_min_max_date(db_path, table_name):
    """
    查询最早和最晚的扣费日期。

    参数：
    - db_path: SQLite 数据库路径。
    - table_name: 表名。

    返回：
    - 最早和最晚的扣费日期。
    """
    conn = sqlite3.connect(db_path)
    query = f"""
        SELECT 
            MIN(扣费时间) AS 最早日期,
            MAX(扣费时间) AS 最晚日期
        FROM {table_name}
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    min_date = datetime.strptime(df["最早日期"].iloc[0], "%Y-%m-%d %H:%M:%S")
    max_date = datetime.strptime(df["最晚日期"].iloc[0], "%Y-%m-%d %H:%M:%S")
    return min_date, max_date


def query_total_cost_by_date_range(db_path, table_name, start_date, end_date):
    """
    按日期范围查询总扣费金额。

    参数：
    - db_path: SQLite 数据库路径。
    - table_name: 表名。
    - start_date: 起始日期（格式：YYYY-MM-DD）。
    - end_date: 结束日期（格式：YYYY-MM-DD）。

    返回：
    - 总扣费金额。
    """
    conn = sqlite3.connect(db_path)
    query = f"""
        SELECT 
            ROUND(SUM(消费金额)) AS 总消费金额
        FROM {table_name}
        WHERE 扣费时间 BETWEEN ? AND ?
    """
    df = pd.read_sql_query(query, conn, params=(start_date + " 00:00:00", end_date + " 23:59:59"))
    total_cost = df["总消费金额"].iloc[0]
    conn.close()
    return total_cost


def query_cost_by_date_range(db_path, table_name, start_date, end_date):
    """
    按日期范围查询总扣费情况。

    参数：
    - db_path: SQLite 数据库路径。
    - table_name: 表名。
    - start_date: 起始日期（格式：YYYY-MM-DD）。
    - end_date: 结束日期（格式：YYYY-MM-DD）。

    返回：
    - 总扣费金额和按人员的统计 DataFrame。
    """
    conn = sqlite3.connect(db_path)
    query = f"""
        SELECT 
            资源使用人员,
            COUNT(任务名称) AS 任务数量,
            ROUND(SUM(消费金额)) AS 总消费金额
        FROM {table_name}
        WHERE 扣费时间 BETWEEN ? AND ?
        GROUP BY 资源使用人员
        ORDER BY 总消费金额 DESC
    """
    df = pd.read_sql_query(query, conn, params=(start_date + " 00:00:00", end_date + " 23:59:59"))
    conn.close()
    return df


def query_cost_by_day_or_month(db_path, table_name, start_date, end_date, group_by="day"):
    """
    按天或按月统计每位用户的扣费情况。

    参数：
    - db_path: SQLite 数据库路径。
    - table_name: 表名。
    - start_date: 起始日期（格式：YYYY-MM-DD）。
    - end_date: 结束日期（格式：YYYY-MM-DD）。
    - group_by: 统计方式（day 或 month）。

    返回：
    - 按天或按月的统计 DataFrame。
    """
    conn = sqlite3.connect(db_path)
    if group_by == "day":
        query = f"""
            SELECT 
                strftime('%Y-%m-%d', 扣费时间) AS 日期,
                资源使用人员,
                COUNT(任务名称) AS 任务数量,
                ROUND(SUM(消费金额)) AS 总消费金额
            FROM {table_name}
            WHERE 扣费时间 BETWEEN ? AND ?
            GROUP BY 日期, 资源使用人员
            ORDER BY 日期
        """
    elif group_by == "month":
        query = f"""
            SELECT 
                strftime('%Y-%m', 扣费时间) AS 月份,
                资源使用人员,
                COUNT(任务名称) AS 任务数量,
                ROUND(SUM(消费金额)) AS 总消费金额
            FROM {table_name}
            WHERE 扣费时间 BETWEEN ? AND ?
            GROUP BY 月份, 资源使用人员
            ORDER BY 月份, 资源使用人员
        """
    else:
        raise ValueError("group_by 参数必须为 'day' 或 'month'。")

    df = pd.read_sql_query(query, conn, params=(start_date + " 00:00:00", end_date + " 23:59:59"))

    conn.close()
    return df


def generate_data(db_path, table_name, count=1000):
    import random
    import datetime

    users = ["Alice", "Bob", "Charlie", "David", "Eve"]
    weights = [0.1, 0.2, 0.3, 0.25, 0.15]
    tasks = ["Task A", "Task B", "Task C", "Task D", "Task E"]

    # 随机生成count个时间 YYYY-MM-DD HH:MM:SS
    start_date = datetime.datetime(2020, 1, 1)
    end_date = datetime.datetime(2024, 1, 1)
    periods = int((end_date - start_date).total_seconds())
    timestamps = [start_date + datetime.timedelta(seconds=random.randint(0, periods)) for _ in range(count)]

    # 随机生成count个用户、任务和金额
    data = {
        "扣费时间": timestamps,
        "任务名称": [random.choice(tasks) for _ in range(count)],
        "资源使用人员": [random.choice(users) for _ in range(count)],
        "资源使用人员": [random.choices(users, weights=weights, k=1)[0] for _ in range(count)],
        "消费金额": [random.uniform(1, 100) for _ in range(count)],
    }

    # 保存到 sqlite
    conn = sqlite3.connect(db_path)
    df = pd.DataFrame(data)
    df.to_sql(table_name, conn, if_exists="replace", index=False)

    cursor = conn.cursor()
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_time ON {table_name} (扣费时间);")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_user ON {table_name} (资源使用人员);")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    extract_and_save_to_db("DeductRecords_2024_11_22_235723.xlsx", "data/fee.db", "fee_data")
