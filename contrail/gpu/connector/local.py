from loguru import logger

from gpu.GPU_logger import get_gpu_info
from gpu.framework import BaseDeviceConnector


class LocalDeviceConnector(BaseDeviceConnector):
    """本地设备连接器"""

    def connect(self):
        if not self._connected:
            logger.info(f"Connecting to local device {self.config.name}")
            self._connected = True

    def disconnect(self):
        self._connected = False

    def collect(self) -> list:
        return get_gpu_info()
