import socket
import json
import time
from datetime import datetime
from pynvml import *

from GPU_logger import *


SENDER_ERR_TEMPLATE = EmailTemplate(
    subject="GPU Data Sender: Error",
    content="""
    [GPU Data Sender]
    Time: ${time}
    Hostname: ${hostname}
    
    Error: ${error}
    """,
)


# 发送 GPU 信息的函数
def send_gpu_info(
    args,
    fault_detector: GpuFaultDetector = None,
    sender: EmailSender = None,
):
    # 初始化 Socket
    server_ip = args.server_ip
    server_port = args.server_port
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, server_port))

    DB_PATH = f"data/gpu_history_{args.name}.db"
    DB_REALTIME_PATH = f"data/gpu_info_{args.name}.db"

    initialize_database(db_path=DB_PATH)
    initialize_database(db_path=DB_REALTIME_PATH)
    print("Database initialized.")
    AGGR_PERIOD = args.aggr_period

    def job_aggregate():
        timestamp = dt.datetime.now(tz=dt.timezone.utc)
        aggregate_data(
            timestamp,
            period_s=AGGR_PERIOD,
            db_path=DB_PATH,
            db_realtime_path=DB_REALTIME_PATH,
            fault_detector=fault_detector,
        )

    def job_clean():
        timestamp = dt.datetime.now(tz=dt.timezone.utc)
        remove_old_data(timestamp, period_s=3600, db_path=DB_REALTIME_PATH)

    schedule.every(AGGR_PERIOD).seconds.do(job_aggregate)
    schedule.every(3600).seconds.do(job_clean)

    try:
        while True:
            # 获取 GPU 信息
            gpu_info = get_gpu_info()
            curr_time = dt.datetime.now(tz=dt.timezone.utc)
            timestamp = datetime.now().isoformat()

            # 组装消息
            data = {
                "magic": 23333,
                "timestamp": timestamp,
                "gpu_info": gpu_info,
            }
            message = json.dumps(data)

            gpu_dfs = process_gpu_info(gpu_info)

            update_database(gpu_dfs, curr_time, DB_REALTIME_PATH)
            schedule.run_pending()

            # 发送数据
            client_socket.sendall(message.encode("utf-8"))

            # 间隔 1 秒发送一次
            time.sleep(1)
    except KeyboardInterrupt:
        print("发送端已停止")
    except Exception as e:
        print(f"发送端发生异常：{e}")

        if sender is not None:
            dyn_content = {"time": curr_time.strftime("%Y-%m-%d %H:%M:%S"), "hostname": args.name, "error": str(e)}
            SENDER_ERR_TEMPLATE(sender, **dyn_content)
    finally:
        client_socket.close()


# 主程序
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Send GPU information to the server.")
    parser.add_argument("--name", type=str, help="The name of the server.", default="virgo_local")
    parser.add_argument("--server_ip", type=str, required=True, help="The IP address of the server.")
    parser.add_argument("--server_port", type=int, required=True, help="The port of the server.")
    parser.add_argument("--ngpus", type=int, help="The number of GPUs to monitor.", default=8)
    parser.add_argument("--gmem", type=int, help="The total memory of the GPU in GB.", default=48)
    parser.add_argument("--aggr_period", type=int, help="The aggregation period in seconds.", default=30)
    parser.add_argument("--fault_detection", type=bool, help="Whether to enable fault detection.", default=False)

    args = parser.parse_args()

    fault_detector = None
    sender = None
    if args.fault_detection:
        SERVER_PASSPORT = getpass.getpass("Please input your email passport: ")
        sender = EmailSender(password=SERVER_PASSPORT)
        fault_detector = GpuFaultDetector(password=SERVER_PASSPORT, NGPU=args.ngpus, GMEM=args.gmem)

    send_gpu_info(args, fault_detector, sender)
