import socket
import json
from loguru import logger

import sys

sys.path.append(".")
from GPU_logger import *


CONN_LOST_TEMPLATE = EmailTemplate(
    subject="GPU Data Receiver: Connection Lost",
    content="""
    [GPU Data Receiver]
    Time: ${time}
    Hostname: ${hostname}
    
    Connection from ${client_ip} lost.
    """,
)


# 接收 GPU 信息的函数
def receive_gpu_info(
    args,
    fault_detector: GpuFaultDetector = None,
    sender: EmailSender = None,
):
    server_ip = args.ip
    server_port = args.port
    device = args.name
    AGGR_PERIOD = args.aggr_period

    logger.info(f"Starting server at {server_ip}:{server_port}")
    # 初始化 Socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((server_ip, server_port))
    server_socket.listen(1)
    logger.trace("Server initialized")

    logger.info(f"Server started, listening at {server_ip}:{server_port}")

    DB_PATH = f"data/gpu_history_{device}.db"
    DB_REALTIME_PATH = f"data/gpu_info_{device}.db"

    initialize_database(db_path=DB_PATH)
    initialize_database(db_path=DB_REALTIME_PATH)
    logger.info("Database initialized.")
    curr_time = dt.datetime.now(tz=dt.timezone.utc)
    AGGR_PERIOD = 30  # 聚合周期：30 秒

    def job_aggregate():
        timestamp = curr_time
        aggregate_data(
            timestamp,
            period_s=AGGR_PERIOD,
            db_path=DB_PATH,
            db_realtime_path=DB_REALTIME_PATH,
            fault_detector=fault_detector,
        )

    def job_clean():
        timestamp = curr_time
        remove_old_data(timestamp, period_s=3600, db_path=DB_REALTIME_PATH)

    schedule.every(AGGR_PERIOD).seconds.do(job_aggregate)
    schedule.every(3600).seconds.do(job_clean)
    n_uncaught = 0

    try:
        while True:
            # 接受连接
            client_socket, client_address = server_socket.accept()
            logger.info(f"Connection from {client_address}")

            with client_socket:
                buffer = b""
                while True:
                    # 接收数据
                    data = client_socket.recv(4096)
                    if not data:
                        break
                    buffer += data

                    try:
                        # 尝试解析 JSON 数据
                        message = json.loads(buffer.decode("utf-8"))
                        buffer = b""  # 清空缓冲区

                        if "magic" not in message or message["magic"] != 23333:
                            logger.warning(f"Invalid data packet: {message}")
                            continue

                        gpu_info = message["gpu_info"]
                        curr_time = dt.datetime.fromisoformat(message["timestamp"]).astimezone(dt.timezone.utc)

                        gpu_dfs = process_gpu_info(gpu_info)

                        update_database(gpu_dfs, curr_time.strftime("%Y-%m-%d %H:%M:%S"), db_path=DB_REALTIME_PATH)
                        schedule.run_pending()

                        time.sleep(0.1)

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode JSON: {buffer.decode('utf-8')}")
                        # 检测是否是不完整数据包
                        if data[-1] != ord("}"):
                            continue
                        else:
                            logger.error(f"Failed to decode JSON: {buffer.decode('utf-8')}")
                            buffer = b""
                    except Exception as e:
                        logger.exception(f"An unexpected error occurred: {e}")
                        buffer = b""

                        if sender is not None:
                            dyn_content = {
                                "time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "hostname": args.name,
                                "error": str(e),
                            }
                            ERROR_REPORT_TEMPLATE(sender, **dyn_content)

                        time.sleep(1)
                        n_uncaught += 1
                        if n_uncaught >= 5:
                            logger.error("Too many uncaught exceptions. Exiting.")
                            break

                # 断开连接
                logger.info(f"Connection from {client_address} closed")
                if sender is not None:
                    dyn_content = {
                        "time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "hostname": args.name,
                        "client_ip": client_address[0],
                    }
                    CONN_LOST_TEMPLATE(sender, **dyn_content)

    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        if sender is not None:
            dyn_content = {
                "time": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "hostname": args.name,
                "error": str(e),
            }
            ERROR_REPORT_TEMPLATE(sender, **dyn_content)
    finally:
        server_socket.close()
        logger.trace("Server socket closed")


# 主程序
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Receive GPU information from the client.")
    parser.add_argument("--ip", type=str, help="The IP address of the server.", default="0.0.0.0")
    parser.add_argument("--port", type=int, help="The port of the server.", default=3334)
    parser.add_argument("--name", type=str, help="The device name.", default="virgo")
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

    logger.add(
        f"log/GPU_data_receiver_{args.name}_{{time:YYYY-MM-DD}}.log",
        rotation="00:00",
        retention="7 days",
        level="TRACE",
    )
    logger.info("Starting GPU data receiver")

    receive_gpu_info(args, fault_detector, sender)
