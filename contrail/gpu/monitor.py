import schedule
import time
from loguru import logger
from typing import Optional, Dict
from multiprocessing import Process
import signal
import sys

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

    def monitor(self):
        """启动所有设备的监控进程"""
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

                time.sleep(2)

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, cleaning up...")
            for name in list(self.connected_devices.keys()):
                self.remove_device(name)
        except Exception as e:
            logger.error(f"Monitoring error: {str(e)}")
        finally:
            logger.info("Monitoring stopped")

    def send_alert(self, message: str):
        """发送警报通知"""
        if self.email_sender:
            template = EmailTemplate(subject="GPU Monitor Alert", content=f"[设备异常告警]\n{message}")
            self.email_sender.send(template)


# 使用示例
if __name__ == "__main__":
    # 设备配置
    local_config = DeviceConfig(
        name="leo",
        type="local",
        params={},
    )

    socket_config = DeviceConfig(
        name="virgo",
        type="socket",
        params={"ip": "0.0.0.0", "port": 3334},
        poll_interval=0.1,
    )

    ssh_config = DeviceConfig(
        name="libra",
        type="ssh",
        params={
            "host": "10.80.0.1",
            "port": 22,
            "user": "admin",
            "key_file": "/home/admin/.ssh/id_rsa",
            "command": (
                "source /opt/miniconda3/etc/profile.d/conda.sh && "
                "conda activate contrail && "
                "export PYTHONPATH=/home/admin/others/Contrail:$PYTHONPATH && "
                "python -m contrail.gpu.GPU_logger"
            ),
        },
        poll_interval=0.5,
    )

    # 初始化管理器
    manager = DeviceManager()
    manager.add_device(local_config)
    manager.add_device(socket_config)
    manager.add_device(ssh_config)

    # 启动监控
    manager.monitor()
