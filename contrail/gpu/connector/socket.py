import json
import socket
import struct
from typing import Optional
from loguru import logger

from contrail.gpu.framework import BaseDeviceConnector


class SocketDeviceConnector(BaseDeviceConnector):
    """网络设备连接器"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.socket = None
        self.client_socket = None

    def connect(self):
        if self._connected:
            return

        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.config.params["ip"], self.config.params["port"]))
        self.socket.listen(1)
        logger.info(f"[{self.config.name}] Listening on {self.config.params['ip']}:{self.config.params['port']}")

        try:
            self.client_socket, addr = self.socket.accept()
            logger.info(f"[{self.config.name}] Connected from {addr}")
            self._connected = True
        except Exception as e:
            logger.error(f"[{self.config.name}] Connection failed: {e}")
            self._connected = False
            self.handle_error(e)

    def disconnect(self):
        if not self._connected:
            return

        if self.socket:
            self.socket.close()
        if self.client_socket:
            self.client_socket.close()
        logger.info(f"[{self.config.name}] Disconnected")
        self.socket = None
        self.client_socket = None
        self._connected = False

    def _flush_socket(self):
        """清空 socket 缓冲区"""
        try:
            self.client_socket.setblocking(False)
            while True:
                leftover = self.client_socket.recv(4096)
                if not leftover:
                    break
        except BlockingIOError:
            pass
        finally:
            self.client_socket.setblocking(True)

    def collect(self) -> Optional[list]:
        """从网络设备收集数据"""
        if not self._connected:
            logger.warning(f"Not connected to {self.config.name}")
            return None

        try:
            # 读取4字节头部长度
            header_len_bytes = self.client_socket.recv(4)
            if not header_len_bytes:
                logger.warning(f"[{self.config.name}] Disconnected from network device {self.config.name}")
                self.disconnect()
                return None

            if len(header_len_bytes) < 4:
                logger.warning(f"[{self.config.name}] Incomplete header length received from network device.")
                self._flush_socket()
                return None
            header_len = struct.unpack("i", header_len_bytes)[0]

            # 读取header
            header_bytes = self.client_socket.recv(header_len)
            if len(header_bytes) < header_len:
                logger.warning(f"[{self.config.name}] Incomplete header received from network device.")
                logger.warning(header_bytes)
                logger.warning(f"{len(header_bytes)}, {header_len}")
                self._flush_socket()
                return None
            header = json.loads(header_bytes.decode("utf-8"))
            data_len = header["data_len"]

            # 读取数据体
            data_bytes = b""
            recv_len = 0
            tries = 0
            while recv_len < data_len and tries < self.config.retries:
                data_bytes += self.client_socket.recv(data_len - recv_len)
                recv_len = len(data_bytes)
                tries += 1

            if len(data_bytes) < data_len:
                logger.warning(f"[{self.config.name}] Incomplete data received from network device.")
                self._flush_socket()
                return None
            message = json.loads(data_bytes.decode("utf-8"))

            if "magic" not in message or message["magic"] != 23333:
                logger.warning(f"[{self.config.name}] Invalid data packet: {message}")
                return None

            return message["gpu_info"]

        except json.JSONDecodeError:
            logger.warning(f"[{self.config.name}] JSON decode error")
            self._flush_socket()
            return None
        except Exception as e:
            self.handle_error(e)
        return None
