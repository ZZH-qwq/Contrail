import argparse
import importlib
import sys


def run_gpu_logger():
    """执行 GPU 日志记录模块"""
    import json
    from contrail.gpu.GPU_logger import get_gpu_info

    gpu_info = get_gpu_info()
    message = json.dumps(gpu_info)
    print(message)


def run_gpu_sender():
    """执行 GPU 数据发送模块"""
    import json
    from contrail.gpu.GPU_data_sender import GpuSenderConfig, send_gpu_info

    # 读取 config/sender_config.json
    with open("config/sender_config.json", "r") as f:
        config = json.load(f)

        sender_config = GpuSenderConfig(**config)

    # 发送 GPU 信息
    # TODO: 这里需要传入 fault_detector 和 sender
    send_gpu_info(sender_config)


def run_monitor():
    """执行监控模块"""
    import json
    from loguru import logger
    from contrail.gpu.monitor import DeviceManager

    manager = DeviceManager()

    # 加载配置
    manager.load_config()

    # 启动监控
    manager.monitor()


def main():
    parser = argparse.ArgumentParser(prog="contrail")
    subparsers = parser.add_subparsers(dest="command")

    # log 命令
    subparsers.add_parser("log", help="Run GPU logger")

    # sender 命令
    subparsers.add_parser("sender", help="Run GPU data sender")

    # monitor 命令
    subparsers.add_parser("monitor", help="Start GPU monitoring")

    args = parser.parse_args()

    if args.command == "log":
        run_gpu_logger()
    elif args.command == "monitor":
        run_monitor()
    elif args.command == "sender":
        run_gpu_sender()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
