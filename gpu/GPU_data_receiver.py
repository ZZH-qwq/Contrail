from loguru import logger
import socket
import json

from GPU_logger import *


# 接收 GPU 信息的函数
def receive_gpu_info(server_ip, server_port, device="virgo"):
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
    # print("Database initialized.")
    logger.info("Database initialized.")
    timestamp_last = dt.datetime.now(tz=dt.timezone.utc)
    AGGR_PERIOD = 30  # 聚合周期：30 秒

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
                            # print("错误的数据包：", message)
                            continue

                        gpu_info = message["gpu_info"]
                        curr_time = dt.datetime.strptime(message["timestamp"], "%Y-%m-%dT%H:%M:%S.%f").replace(
                            tzinfo=dt.timezone(dt.timedelta(hours=8))
                        )
                        curr_time = curr_time - dt.timedelta(hours=8)  # Convert from UTC+8 to UTC+0
                        update_database(gpu_info, curr_time.strftime("%Y-%m-%d %H:%M:%S"), db_path=DB_REALTIME_PATH)
                        if (curr_time - timestamp_last).seconds >= AGGR_PERIOD - 1:
                            timestamp_last = curr_time
                            aggregate_data(
                                timestamp_last, period_s=AGGR_PERIOD, db_path=DB_PATH, db_realtime_path=DB_REALTIME_PATH
                            )
                            remove_old_data(timestamp_last, period_s=3600, db_path=DB_REALTIME_PATH)
                        time.sleep(1)

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to decode JSON: {buffer.decode('utf-8')}")
                        # 检测是否是不完整数据包
                        if data[-1] != ord("}"):
                            continue
                        else:
                            # print("数据包解析失败：", buffer.decode("utf-8"))
                            logger.error(f"Failed to decode JSON: {buffer.decode('utf-8')}")
                            buffer = b""
                    except Exception as e:
                        logger.error(f"An unexpected error occurred: {e}")
                        buffer = b""

    except KeyboardInterrupt:
        logger.info("Server stopped")
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
    args = parser.parse_args()

    logger.add("log/GPU_data_receiver_{time:YYYY-MM-DD}.log", rotation="00:00", retention="7 days", level="TRACE")
    logger.info("Starting GPU data receiver")

    receive_gpu_info(args.ip, args.port, args.name)
