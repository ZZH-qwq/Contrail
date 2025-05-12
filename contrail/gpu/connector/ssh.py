import json
import paramiko
from typing import Optional
from loguru import logger

from gpu.framework import BaseDeviceConnector


class SSHDeviceConnector(BaseDeviceConnector):
    """SSH设备连接器"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = None
        self.channel = None

    def connect(self):
        if self._connected:
            return

        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.config.params["host"],
                port=self.config.params.get("port", 22),
                username=self.config.params["user"],
                key_filename=self.config.params["key_file"],
                timeout=10,
            )
            self.channel = self.client.invoke_shell()

            # 初始化命令
            if "init_cmd" in self.config.params:
                stdin, stdout, stderr = self.client.exec_command(self.config.params["init_cmd"])
                output = stdout.read().decode()
                err = stderr.read().decode()
                logger.info(output)
                logger.warning(err)

            self._connected = True
            logger.info(f"SSH connected to {self.config.name}")

        except Exception as e:
            logger.error(f"[{self.config.name}] SSH connection failed")
            self.handle_error(e)

    def disconnect(self):
        if not self._connected:
            return

        if self.client:
            self.client.close()
        self._connected = False

    def collect(self) -> Optional[list]:
        try:
            stdin, stdout, stderr = self.client.exec_command(self.config.params["command"])
            output = stdout.read().decode()
            err = stderr.read().decode()
            if len(err):
                logger.warning(err)
            return json.loads(output)
        except Exception as e:
            logger.error(f"[{self.config.name}] Command execution failed")
            self.handle_error(e)
            return None
