import abc
import time
import json
import schedule
import datetime as dt
from dataclasses import dataclass
from typing import Dict, Any, Optional
from loguru import logger
from pynvml import *

# 复用原有模块的功能
from contrail.gpu.GPU_logger import *


@dataclass
class DeviceConfig:
    name: str
    type: str  # local/socket/ssh
    params: Dict[str, Any]
    db_path: str = "data"
    retries: int = 3
    poll_interval: float = 1.0
    aggregate_period: int = 30
    clean_period: int = 3600

    def __post_init__(self):
        self._validate_params()

    def _validate_params(self):
        required = {
            "local": [],
            "socket": ["ip", "port"],
            "ssh": ["host", "user", "key_file", "command"],
        }
        if self.type not in required:
            raise ValueError(f"Unsupported device type: {self.type}")

        missing = [k for k in required[self.type] if k not in self.params]
        if missing:
            raise ValueError(f"Missing params for {self.name}({self.type}): {missing}")


class BaseDeviceConnector(abc.ABC):
    """设备连接器基类"""

    def __init__(self, config: DeviceConfig):
        self.config = config
        self._connected = False
        self._last_seen = None
        self._error_count = 0
        self.realtime_db_path = f"{self.config.db_path}/gpu_info_{self.config.name}.db"
        self.history_db_path = f"{self.config.db_path}/gpu_history_{self.config.name}.db"
        self.scheduler = None

        # 初始化数据库
        self._init_db()

    def _init_db(self):
        """初始化数据库"""
        initialize_database(self.realtime_db_path, is_history=False)
        initialize_database(self.history_db_path, is_history=True)
        logger.info(f"[{self.config.name}] Database initialized")

    @abc.abstractmethod
    def connect(self):
        """建立连接"""
        pass

    @abc.abstractmethod
    def disconnect(self):
        """断开连接"""
        pass

    @property
    def is_healthy(self) -> bool:
        """连接健康状态"""
        return self._error_count < self.config.retries

    @abc.abstractmethod
    def collect(self) -> Optional[list]:
        """获取原始数据"""
        pass

    def process(self):
        """处理并存储数据"""
        try:
            raw_data = self.collect()
            if not raw_data:
                return

            gpu_dfs = process_gpu_info(raw_data)
            # timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            curr_time = dt.datetime.now(tz=dt.timezone.utc)
            timestamp = curr_time.strftime("%Y-%m-%d %H:%M:%S")
            update_database(gpu_dfs, timestamp, self.realtime_db_path)

            # 测试阶段使用 print 代替数据库更新
            # print(f"Updating database for {self.config.name} at {timestamp}: {gpu_dfs}")

            self._last_seen = time.time()

        except Exception as e:
            logger.error(f"[{self.config.name}] Data processing failed")
            self.handle_error(e)

    def aggregate(self):
        """聚合数据"""
        timestamp = dt.datetime.now(tz=dt.timezone.utc)
        aggregate_data(
            timestamp,
            period_s=self.config.aggregate_period,
            db_path=self.history_db_path,
            db_realtime_path=self.realtime_db_path,
            fault_detector=None,
        )

    def clean(self):
        """清理旧数据"""
        timestamp = dt.datetime.now(tz=dt.timezone.utc)
        remove_old_data(
            timestamp,
            period_s=self.config.clean_period,
            db_path=self.realtime_db_path,
        )

    def run(self):
        self.connect()
        self._last_seen = time.time()

        self.scheduler = schedule.Scheduler()
        self.scheduler.every(self.config.aggregate_period).seconds.do(self.aggregate)
        self.scheduler.every(self.config.clean_period).seconds.do(self.clean)
        logger.info(f"[{self.config.name}] Starting data collection")

        while self._connected:
            self.process()
            self.scheduler.run_pending()

            time.sleep(self.config.poll_interval)

    def handle_error(self, error: Exception):
        """错误处理"""
        logger.error(f"[{self.config.name}] Unexpected error: {error}")
        self._error_count += 1
        if self._error_count >= self.config.retries:
            self.disconnect()
            logger.error(f"[{self.config.name}] Disconnected due to persistent errors")
