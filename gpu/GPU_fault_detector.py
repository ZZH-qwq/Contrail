import pandas as pd
import numpy as np
from loguru import logger

from abc import abstractmethod
from typing import Optional, List, Tuple

import sys

sys.path.append(".")
from email_sender import EmailSender, EmailTemplate, BasicEvent


class GpuUsageManager:
    def __init__(
        self,
        NGPU: int = 8,
        GMEM: int = 48,
        history_length: int = 20,
    ):
        self.NGPU = NGPU
        self.GMEM = GMEM
        self.HISTORY_LENGTH = history_length  # 10 minutes history length
        self.util_history = np.zeros((NGPU, self.HISTORY_LENGTH))
        self.mem_history = np.zeros((NGPU, self.HISTORY_LENGTH))
        self.gpu_utils = np.zeros(NGPU)
        self.gpu_mems = np.zeros(NGPU)

    def update_usage(self, gpu_df: pd.DataFrame) -> None:
        """
        更新 GPU 使用情况数据并计算平均值
        """
        gpu_utils = gpu_df["gpu_utilization"].values
        gpu_mems = gpu_df["used_memory"].values / 0x40000000 / self.GMEM

        # 更新历史记录
        self.util_history = np.roll(self.util_history, shift=1, axis=1)
        self.mem_history = np.roll(self.mem_history, shift=1, axis=1)

        self.util_history[:, 0] = gpu_utils
        self.mem_history[:, 0] = gpu_mems

        # 计算 GPU 使用情况的平均值
        self.gpu_utils = np.mean(self.util_history, axis=1)
        self.gpu_mems = np.mean(self.mem_history, axis=1)

    def query_usage(self, gpu_idx: List[int]) -> Tuple[List[float], List[float]]:
        """
        查询出现问题的 GPU 使用情况
        """
        return self.gpu_utils[gpu_idx], self.gpu_mems[gpu_idx]


class GpuFaultEvent(BasicEvent):
    def __init__(
        self,
        mail_subject: str,
        mail_content: str,
        gpu_usage_manager: GpuUsageManager,
        config_file: str = "email_config.json",
        password: Optional[str] = None,
    ):
        self.gpu_usage_manager = gpu_usage_manager
        self.fault_idxs = []
        self.fault_utils = []
        self.fault_mems = []

        self.mail_subject = mail_subject
        self.mail_content = mail_content

        self.sender = EmailSender(config_file, password)
        self.template = EmailTemplate(subject=self.mail_subject, content=self.mail_content)

        get_dyn_content = lambda: {
            "time": self.event_start.strftime("%Y-%m-%d %H:%M:%S"),
            "util": self.fault_utils,
            "mem": self.fault_mems,
            "gpu_index": self.fault_idxs,
        }

        self.active_action = lambda: self.template(
            self.sender,
            **get_dyn_content(),
        )

        super().__init__(init_status=False, active_action=self.active_action)

    def update(self) -> None:
        # 判断是否触发事件
        self.fault_idxs = self._check_fault_gpus()
        self.fault_utils, self.fault_mems = self.gpu_usage_manager.query_usage(self.fault_idxs)

        is_fault = len(self.fault_idxs) > 0
        super().update(is_fault)

    @abstractmethod
    def _check_fault_gpus(self) -> List[int]:
        return []


class GpuOverloadFaultEvent(GpuFaultEvent):
    def __init__(
        self,
        gpu_usage_manager: GpuUsageManager,
        config_file: str = "email_config.json",
        password: Optional[str] = None,
    ):
        mail_subject = "GPU Fault Detection: High Utilization and Low Memory Usage"
        mail_content = """
        [Fault Detection Alert]
        Time: ${time}
        GPU Utilization: ${util}%
        Memory Usage: ${mem}%

        Please check the GPU ${gpu_index} immediately.
        """

        super().__init__(mail_subject, mail_content, gpu_usage_manager, config_file, password)

    def _check_fault_gpus(self) -> List[int]:
        """检测 GPU 是否过载"""

        falut_gpus = []

        for i in range(self.gpu_usage_manager.NGPU):
            if self.gpu_usage_manager.gpu_utils[i] > 90 and self.gpu_usage_manager.gpu_mems[i] < 0.2:
                falut_gpus.append(i)

        if len(falut_gpus) > 0:
            logger.warning(f"Detected GPU overload faults: {falut_gpus}")

        return falut_gpus


class GpuUnderutilizedFaultEvent(GpuFaultEvent):
    def __init__(
        self,
        gpu_usage_manager: GpuUsageManager,
        config_file: str = "email_config.json",
        password: Optional[str] = None,
    ):
        mail_subject = "GPU Fault Detection: Low Utilization and High Memory Usage"
        mail_content = """
        [Fault Detection Alert]
        Time: ${time}
        GPU Utilization: ${util}%
        Memory Usage: ${mem}%

        Please check the GPU ${gpu_index} immediately.
        """

        super().__init__(mail_subject, mail_content, gpu_usage_manager, config_file, password)

    def _check_fault_gpus(self) -> List[int]:
        """检测 GPU 是否异常低负载"""

        falut_gpus = []

        for i in range(self.gpu_usage_manager.NGPU):
            if self.gpu_usage_manager.gpu_utils[i] < 10 and self.gpu_usage_manager.gpu_mems[i] > 0.9:
                falut_gpus.append(i)

        if len(falut_gpus) > 0:
            logger.warning(f"Detected GPU underutilized faults: {falut_gpus}")

        return falut_gpus


class GpuFaultDetector:
    def __init__(
        self,
        config_file: str = "email_config.json",
        password: Optional[str] = None,
        NGPU: int = 8,
    ):
        self.gpu_usage_manager = GpuUsageManager(NGPU)

        self.events = [
            GpuOverloadFaultEvent(self.gpu_usage_manager, config_file, password),
            GpuUnderutilizedFaultEvent(self.gpu_usage_manager, config_file, password),
        ]

    def update(self, gpu_df: pd.DataFrame) -> None:
        self.gpu_usage_manager.update_usage(gpu_df)

        for event in self.events:
            event.update()
