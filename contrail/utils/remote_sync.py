import os
import glob
import subprocess
from datetime import datetime
import schedule
import time
from loguru import logger

# 配置日志记录
logger.add("log/remote_rsync_{time:YYYY-MM-DD}.log", rotation="00:00", retention="7 days", level="TRACE")


def remote_incremental_backup(source, targets, destination, remote_user, remote_host, remote_port):
    """
    使用 rsync 实现跨服务器增量备份。

    Args:
        source (str): 源文件或目录路径。
        targets (str): 目标文件或目录名称。
        destination (str): 目标目录路径。
        remote_user (str): 远程服务器用户名。
        remote_host (str): 远程服务器主机名或 IP 地址。
        remote_port (int): 远程服务器端口。
    """
    # 检查源路径是否存在
    if not os.path.exists(source):
        logger.error(f"Source path does not exist: {source}")
        return

    # 构建远程目标目录
    remote_destination = f"{remote_user}@{remote_host}:{destination}"

    target_list = glob.glob(os.path.join(source, targets))

    # 构建 rsync 命令
    rsync_command = [
        "rsync",
        "-avz",  # 递归、详细、压缩
        "--progress",  # 显示进度
        "-e",
        f"ssh -p {remote_port}",  # 指定 SSH 端口
        *target_list,
        remote_destination,
    ]

    try:
        # 执行 rsync 命令
        logger.info(f"Start incremental backup task across servers: {datetime.now()}")
        result = subprocess.run(rsync_command, capture_output=True, text=True)

        # 输出 rsync 结果
        if result.returncode == 0:
            logger.info(f"Incremental backup across servers succeeded: {result.stdout}")
        else:
            logger.error(f"Incremental backup across servers failed: {result.stderr}")
    except Exception as e:
        logger.error(f"An error occurred during incremental backup across servers: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Incremental backup files across servers.")
    parser.add_argument("--source", type=str, help="The source file or directory path.", default="data")
    parser.add_argument("--targets", type=str, help="The target file or directory path.", default="gpu_history_*")
    parser.add_argument("--destination", type=str, help="The destination directory path.", required=True)
    parser.add_argument("--remote_user", type=str, help="The username of the remote server.", required=True)
    parser.add_argument("--host", type=str, help="The hostname or IP address of the remote server.", required=True)
    parser.add_argument("--port", type=int, help="The port of the remote server.", default=22)
    args = parser.parse_args()

    # 定义备份任务
    def backup_task():
        remote_incremental_backup(args.source, args.targets, args.destination, args.remote_user, args.host, args.port)

    backup_task()

    # 每隔 2 小时执行一次备份任务
    schedule.every(2).hours.do(backup_task)

    # 主循环，保持脚本运行
    logger.info("Incremental backup task has started. Press Ctrl+C to stop.")
    while True:
        try:
            schedule.run_pending()
            time.sleep(2)  # 避免 CPU 占用过高

        except KeyboardInterrupt:
            logger.info("Backup task stopped.")
            break
        except Exception as e:
            logger.exception(f"An unexpected error occurred: {e}")
            break
