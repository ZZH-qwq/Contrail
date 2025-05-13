import schedule
import time
from loguru import logger
from typing import Optional, Dict
from multiprocessing import Process
import signal
import sys
import select

from contrail.gpu.framework import DeviceConfig
from contrail.gpu.connector.local import LocalDeviceConnector
from contrail.gpu.connector.socket import SocketDeviceConnector
from contrail.gpu.connector.ssh import SSHDeviceConnector
from contrail.utils.email_sender import EmailSender, EmailTemplate


class DeviceManager:
    """总控端设备管理器"""

    def __init__(self, email_sender: Optional[EmailSender] = None):
        self.connected_devices: Dict[str, Dict] = {}  # 设备名称 -> {connector, process}
        self.scheduler = schedule.Scheduler()
        self.email_sender = email_sender
        self._config_path = "config/host_config.json"

    def add_device(self, config: DeviceConfig):
        """添加设备并初始化连接器"""
        if config.name in self.connected_devices:
            logger.warning(f"Device {config.name} already connected")
            return

        connector_map = {"local": LocalDeviceConnector, "socket": SocketDeviceConnector, "ssh": SSHDeviceConnector}

        connector = connector_map[config.type](config)
        self.connected_devices[config.name] = {"connector": connector, "process": None}  # 进程将在 monitor() 中初始化
        logger.info(f"Added device: {config.name} ({config.type})")

    def remove_device(self, name: str):
        """安全移除设备"""
        if name not in self.connected_devices:
            logger.warning(f"Device {name} not found")
            return

        device = self.connected_devices[name]
        process = device["process"]
        connector = device["connector"]

        # 断开连接
        if connector:
            connector.disconnect()
            logger.info(f"Disconnected {name}")

        # 终止进程
        if process and process.is_alive():
            logger.info(f"Terminating process for {name} (pid={process.pid})")
            process.terminate()
            process.join(timeout=3)
            if process.is_alive():
                logger.error(f"Failed to terminate process for {name}")
            else:
                logger.info(f"Process for {name} terminated")

        # 移除记录
        del self.connected_devices[name]
        logger.info(f"Removed device {name}")

    def create_process(self, name):
        """创建进程"""
        device = self.connected_devices[name]
        connector = device["connector"]

        # 终止旧进程
        if device["process"] and device["process"].is_alive():
            logger.info(f"Terminating old process for {name} (pid={device['process'].pid})")
            device["process"].terminate()
            device["process"].join(timeout=3)
            if device["process"].is_alive():
                logger.error(f"Failed to terminate old process for {name}, pid={device['process'].pid}")
            else:
                logger.info(f"Old process for {name} terminated")

        # 创建新进程
        p = Process(target=connector.run)
        p.daemon = True
        p.start()

        device["process"] = p
        logger.info(f"Started monitoring process for {name} (pid={p.pid})")

    def process_command(self, command: str):
        """处理命令"""
        if command == "reload":
            logger.info("Received reload command, reloading config...")
            try:
                device_added = self.load_config(self._config_path)
                for name in device_added:
                    self.create_process(name)
            except Exception as e:
                logger.error(f"Failed to reload config: {e}")
        elif command == "exit":
            logger.info("Received exit command, cleaning up and exiting...")
            sys.exit(0)
        elif command == "list":
            logger.info("Connected devices:")
            for name in self.connected_devices.keys():
                logger.info(f" - {name}")
        elif command.startswith("remove "):
            # 移除指定设备
            name = command.split(" ")[1]
            if name in self.connected_devices:
                self.remove_device(name)
            else:
                logger.warning(f"Device {name} not found")
        else:
            logger.warning(f"Unknown command: {command}")

    def monitor(self):
        """启动所有设备的监控进程，并监听 stdin 输入"""
        logger.info("Starting monitoring loop")

        # 初始化所有设备的监控进程
        for name in list(self.connected_devices.keys()):
            device = self.connected_devices[name]
            connector = device["connector"]

            p = Process(target=connector.run)
            p.daemon = True
            p.start()

            device["process"] = p
            logger.info(f"Started monitoring process for {name} (pid={p.pid})")

        try:
            while True:
                # 检查设备状态
                for name in list(self.connected_devices.keys()):
                    device = self.connected_devices.get(name)
                    if not device:
                        continue

                    process = device["process"]
                    if process and not process.is_alive():
                        logger.error(f"Process for {name} terminates unexpectedly")
                        # self.send_alert(f"Device {name} terminates unexpectedly")
                        self.remove_device(name)  # 自动清理异常设备

                # 检查 stdin 输入
                rlist, _, _ = select.select([sys.stdin], [], [], 2)
                if rlist:
                    cmd = sys.stdin.readline().strip()
                    if cmd:
                        self.process_command(cmd)
                # 如果没有输入，2秒后继续循环

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, cleaning up...")
        except Exception as e:
            logger.error(f"Monitoring error: {str(e)}")
        finally:
            # 清理所有设备
            for name in list(self.connected_devices.keys()):
                self.remove_device(name)
            logger.info("Monitoring stopped")

    def send_alert(self, message: str):
        """发送警报通知"""
        if self.email_sender:
            template = EmailTemplate(subject="GPU Monitor Alert", content=f"[设备异常告警]\n{message}")
            self.email_sender.send(template)

    def load_config(self, config_path: str = "config/host_config.json"):
        """加载配置文件"""
        import json

        self._config_path = config_path
        device_added = []

        with open(config_path, "r") as f:
            config = json.load(f)
            for _, conf in config["monitor"].items():
                if conf["name"] not in self.connected_devices:
                    self.add_device(DeviceConfig(**conf))
                    device_added.append(conf["name"])

        if not device_added:
            logger.info("No new devices added from config")
        else:
            logger.info(f"Loaded config from {config_path}, added devices: {device_added}")

        return device_added


# 使用示例
if __name__ == "__main__":
    # 初始化管理器
    manager = DeviceManager()

    # 加载配置
    manager.load_config()

    # 启动监控
    manager.monitor()
