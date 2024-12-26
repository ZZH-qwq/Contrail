from datetime import datetime
from GPU_email_sender import EmailSender
import sqlite3
import pandas as pd
from loguru import logger

class FaultDetectionEvent(EmailSender):
    def __init__(self, config_file="email_config.json", passport=None):
        super().__init__(config_file, passport)
        # 用于记录每个 GPU 每种故障状态
        self.gpu_fault_status = {
            "high_utilization_low_memory": {},
            "low_utilization_high_memory": {}
        }

    def monitor(self, timestamp_last, gpu_index, db_realtime_path):
        """
        监控 GPU 使用情况，并在出现问题时发送邮件，确保每个问题只会发一次邮件
        :param timestamp_last: 上次检查的时间戳
        :param gpu_index: GPU 索引
        :param db_realtime_path: 数据库路径
        """
        gpu_utilization, memory_usage = self.calculate_average_usage(timestamp_last, gpu_index, db_realtime_path)

        if gpu_utilization is not None and memory_usage is not None:
            # 高 GPU 使用率并且低内存使用率
            if gpu_utilization > 90 and memory_usage < 0.2:
                if not self.gpu_fault_status["high_utilization_low_memory"].get(gpu_index, False):
                    logger.warning(f"GPU {gpu_index} is under high load but low memory usage (GPU Utilization: {gpu_utilization}%, Memory Usage: {memory_usage * 100}%).")
                    subject = "GPU Fault Detection: High Utilization and Low Memory Usage"
                    body = f"""
                    [Fault Detection Alert]
                    Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    GPU Utilization: {gpu_utilization}% (Critical)
                    Memory Usage: {memory_usage * 100}% (Critical)
                    
                    Please check the GPU {gpu_index} immediately.
                    """
                    self.send_email(subject, body)
                    self.gpu_fault_status["high_utilization_low_memory"][gpu_index] = True  # 将该 GPU 状态标记为故障

            # 低 GPU 使用率并且高内存使用率
            if gpu_utilization < 10 and memory_usage > 0.9:
                if not self.gpu_fault_status["low_utilization_high_memory"].get(gpu_index, False):
                    logger.warning(f"GPU {gpu_index} is under low load but high memory usage (GPU Utilization: {gpu_utilization}%, Memory Usage: {memory_usage * 100}%).")
                    subject = "GPU Fault Detection: Low Utilization and High Memory Usage"
                    body = f"""
                    [Fault Detection Alert]
                    Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                    GPU Utilization: {gpu_utilization}% (Critical)
                    Memory Usage: {memory_usage * 100}% (Critical)
                    
                    Please check the GPU {gpu_index} immediately.
                    """
                    self.send_email(subject, body)
                    self.gpu_fault_status["low_utilization_high_memory"][gpu_index] = True  # 将该 GPU 状态标记为故障

            # 如果 GPU 使用情况恢复正常，且当前 GPU 处于故障状态
            if gpu_utilization < 90 or memory_usage > 0.2:
                if self.gpu_fault_status["high_utilization_low_memory"].get(gpu_index, False):
                    # 解除高使用率低内存故障状态
                    logger.info(f"GPU {gpu_index} high utilization issue resolved (GPU Utilization: {gpu_utilization}%, Memory Usage: {memory_usage * 100}%).")
                    self.gpu_fault_status["high_utilization_low_memory"][gpu_index] = False  # 恢复为正常

            if gpu_utilization > 10 or memory_usage < 0.9:
                if self.gpu_fault_status["low_utilization_high_memory"].get(gpu_index, False):
                    # 解除低使用率高内存故障状态
                    logger.info(f"GPU {gpu_index} low utilization issue resolved (GPU Utilization: {gpu_utilization}%, Memory Usage: {memory_usage * 100}%).")
                    self.gpu_fault_status["low_utilization_high_memory"][gpu_index] = False  # 恢复为正常

    def calculate_average_usage(self, timestamp, gpu_index, dp_realtime_path):
        """
        计算指定时间段内的 GPU 使用率和内存使用率
        :param timestamp: 当前时间戳
        :param gpu_index: GPU 索引
        :param dp_realtime_path: 数据库路径
        :return: 平均 GPU 使用率, 平均内存使用率
        """
        try:
            conn = sqlite3.connect(dp_realtime_path)
            cursor = conn.cursor()

            start_time = (timestamp - pd.Timedelta(seconds=600)).strftime("%Y-%m-%d %H:%M:%S")
            end_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")

            query = f"""
                SELECT gpu_utilization, used_memory, total_memory
                FROM gpu_info
                WHERE gpu_index = ? AND timestamp BETWEEN ? AND ?
            """
            result = pd.read_sql_query(query, conn, params=(gpu_index, start_time, end_time))

            conn.close()

            if len(result) == 0:
                return None, None

            avg_gpu_utilization = result["gpu_utilization"].mean()
            avg_memory_usage = result["used_memory"].mean() / result["total_memory"].mean()

            return avg_gpu_utilization, avg_memory_usage
        except Exception as e:
            logger.error(f"Error while fetching GPU usage data: {e}")
            return None, None
