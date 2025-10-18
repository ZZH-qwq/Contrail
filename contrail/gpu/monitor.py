import schedule
import os
import json
from loguru import logger
from typing import Optional, Dict
from multiprocessing import Process
from dataclasses import dataclass
import shlex
import sys
import select

from contrail.gpu.framework import DeviceConfig
from contrail.gpu.connector.local import LocalDeviceConnector
from contrail.gpu.connector.socket import SocketDeviceConnector
from contrail.gpu.connector.ssh import SSHDeviceConnector
from contrail.utils.email_sender import EmailSender, EmailTemplate


@dataclass
class ManagerConfig:
    reload_interval: int = 0  # 0 表示不自动重载
    db_path: str = "data"
    log_path: str = "log"


class DeviceManager:
    """总控端设备管理器"""

    def __init__(self, email_sender: Optional[EmailSender] = None):
        self.connected_devices: Dict[str, Dict] = {}  # 设备名称 -> {connector, process}
        self.email_sender = email_sender
        self._config_path = "config/host_config.json"
        self.config = ManagerConfig()
        self.reload_scheduler = None

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

    def process_command(self, command_str: str):
        """处理命令"""
        parts = shlex.split(command_str)
        command = parts[0]
        if command == "reload":
            logger.info("Received reload command, reloading config...")
            try:
                if len(parts) > 1:
                    config_path = os.path.expanduser(parts[1])
                    if os.path.exists(config_path):
                        logger.info(f"Reloading config from {config_path}...")
                        device_added = self.load_config(config_path)
                    else:
                        logger.warning(f"Config file {config_path} does not exist")
                        device_added = []
                else:
                    device_added = self.load_devices()

                for name in device_added:
                    self.create_process(name)
            except Exception as e:
                logger.error(f"Failed to reload config: {e}")
        elif command == "exit":
            logger.info("Received exit command, cleaning up and exiting...")
            for name in list(self.connected_devices.keys()):
                self.remove_device(name)
            sys.exit(0)
        elif command == "list":
            logger.info("Connected devices:")
            for name in self.connected_devices.keys():
                logger.info(f" - {name}")
        elif command == "remove" and len(parts) == 2:
            # 移除指定设备
            name = parts[1]
            if name in self.connected_devices:
                self.remove_device(name)
            else:
                logger.warning(f"Device {name} not found")
        else:
            logger.warning(f"Unknown command: {command_str}")

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

                if self.reload_scheduler:
                    schedule.run_pending()

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
            # TODO: implement email sending
            pass

    def load_config(self, config_path: str = "config/host_config.json"):
        self._config_path = config_path

        with open(self._config_path, "r") as f:
            config = json.load(f)
            if "config" in config["monitor"]:
                new_config = ManagerConfig(**config["monitor"]["config"])
                logger.info(f"Loaded manager config: {new_config}")

                if new_config != self.config:
                    self.config = new_config
                    logger.warning(f"Manager config updated: pre-existing devices will not be affected")

                    if self.reload_scheduler:
                        schedule.clear(self.reload_scheduler)

                    if self.config.reload_interval > 0:
                        self.reload_scheduler = schedule.every(self.config.reload_interval).seconds.do(self.reload_job)
                        logger.info(f"Set up device reload every {self.config.reload_interval} seconds")
                    else:
                        self.reload_scheduler = None
                        logger.info("Auto reload disabled")

            else:
                logger.warning("No manager config found in config file, using defaults")

        return self.load_devices()

    def load_devices(self, log=True):
        """加载配置文件"""
        device_added = []

        with open(self._config_path, "r") as f:
            config = json.load(f)
            config["monitor"].pop("config", None)

            for _, conf in config["monitor"].items():
                conf = {"db_path": self.config.db_path} | conf
                if conf["name"] not in self.connected_devices:
                    self.add_device(DeviceConfig(**conf))
                    device_added.append(conf["name"])

        if device_added:
            logger.info(f"Loaded config from {self._config_path}, added devices: {device_added}")
        elif log:
            logger.info("No new devices added from config")
        else:
            logger.trace("No new devices added from config")

        return device_added

    def reload_job(self):
        """自动重载设备并创建进程"""
        logger.trace("Auto reloading devices...")
        device_added = self.load_devices(log=False)
        for name in device_added:
            self.create_process(name)


# 使用示例
if __name__ == "__main__":
    # 初始化管理器
    manager = DeviceManager()

    # 加载配置
    manager.load_config()

    # 启动监控
    manager.monitor()
