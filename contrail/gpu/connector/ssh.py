import json
import re
import time
import socket
import paramiko
from typing import Optional
from loguru import logger

from contrail.gpu.framework import BaseDeviceConnector


class SSHDeviceConnector(BaseDeviceConnector):
    """SSH设备连接器"""

    # 常用 prompt 模式：末尾为 $ 或 #，或包含括号环境名 (env)
    PROMPT_RE = re.compile(r"(^.*[#$]\s*$)|(^.*\([^)]+\)\s*.*[#$]\s*$)")
    # 过滤 ANSI 转义序列
    ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client: Optional[paramiko.SSHClient] = None
        self.channel: Optional[paramiko.Channel] = None
        self._recv_buffer = ""  # 未解析的字符缓冲

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
                key_filename=self.config.params.get("key_file"),
                timeout=10,
                look_for_keys=False,
                allow_agent=False,
            )
            self.channel = self.client.invoke_shell()
            self.channel.settimeout(1.0)

            init_cmd = self.config.params.get("init_cmd")
            if init_cmd:
                # 发送 init_cmd 并短暂清理回显
                self._send_and_clean(init_cmd, drain_time=2.0)

            self._connected = True
            logger.info(f"[{self.config.name}] SSH persistent shell connected")
        except Exception as e:
            logger.exception(f"[{self.config.name}] SSH connect failed: {e}")
            self.handle_error(e)
            self._connected = False

    def disconnect(self):
        if self.channel:
            try:
                self.channel.close()
            except Exception:
                pass
            self.channel = None
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
        self._connected = False

    def _send_and_clean(self, cmd: str, drain_time: float = 0.05):
        """
        发送命令并在 drain_time 内读取到达的数据以丢弃回显 / prompt。
        **注意**：不会将读取内容保存到任何缓冲区。
        """
        if not self.channel:
            raise RuntimeError("No persistent shell channel")

        if not cmd.endswith("\n"):
            cmd_to_send = cmd + "\n"
        else:
            cmd_to_send = cmd

        self.channel.send(cmd_to_send)

        end = time.time() + drain_time
        while time.time() < end:
            try:
                if self.channel.recv_ready():
                    # 读取并丢弃
                    _ = self.channel.recv(65536)
                else:
                    time.sleep(0.01)
            except socket.timeout:
                break
            except Exception:
                break

    def _read_lines_until_json(self, cmd: str, timeout: float) -> Optional[list]:
        """
        从 channel 读取并按行解析 JSON 输出
        """
        deadline = time.time() + timeout
        self._recv_buffer = ""

        while time.time() < deadline:
            # 读取所有可用数据
            try:
                while self.channel.recv_ready():
                    data = self.channel.recv(65536).decode(errors="ignore")
                    if data:
                        self._recv_buffer += data
            except socket.timeout:
                logger.warning(f"[{self.config.name}] channel read timeout")
                pass
            except Exception as e:
                logger.exception(f"[{self.config.name}] channel read error: {e}")
                return None

            # 如果有完整行则处理
            if "\n" in self._recv_buffer:
                lines = self._recv_buffer.splitlines()
                # 如果最后一行不是以换行结束，则保留为不完整行
                if not self._recv_buffer.endswith("\n"):
                    incomplete = lines.pop()
                else:
                    incomplete = ""

                for ln in lines:
                    s = ln.strip()
                    s = self.ANSI_ESCAPE_RE.sub("", s)
                    if not s:
                        continue
                    # 过滤命令回显
                    if s == cmd.strip():
                        continue
                    # 过滤 prompt
                    if self.PROMPT_RE.match(s):
                        continue

                    # 尝试解析 JSON
                    try:
                        obj = json.loads(s)
                    except Exception:
                        logger.warning(f"[{self.config.name}] non-json line ignored: {s:200} (len={len(s)})")
                        continue

                    if isinstance(obj, list):
                        return obj
                    else:
                        logger.warning(f"[{self.config.name}] json is not a list, ignored: {s[:200]} (len={len(s)})")
                        continue

                # 更新缓冲保留不完整部分
                self._recv_buffer = incomplete

            # 等待一小段时间继续读取
            time.sleep(0.02)

        # 超时未读到 JSON
        logger.warning(f"[{self.config.name}] read timeout, no JSON parsed")
        return None

    def collect(self) -> Optional[list]:
        """
        发送命令并等待按行 JSON 输出
        """
        if not self._connected or not self.channel:
            logger.warning(f"[{self.config.name}] not connected")
            return None

        cmd = self.config.params.get("command")

        try:
            # 发送命令并短暂清理回显
            self._send_and_clean(cmd, drain_time=float(self.config.params.get("drain_time", 0.02)))
        except Exception as e:
            logger.exception(f"[{self.config.name}] send failed: {e}")
            self.handle_error(e)
            self.disconnect()
            return None

        read_timeout = float(self.config.params.get("read_timeout", 5.0))
        result = self._read_lines_until_json(cmd=cmd, timeout=read_timeout)
        return result
