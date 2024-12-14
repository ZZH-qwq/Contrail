from realtime import webapp_realtime


config = {
    "DURATION": 30,
    "N_GPU": 8,
    "GMEM": 48,
    "LIMIT": 1000,
}

webapp_realtime(hostname="Leo", db_path="data/gpu_info_leo.db", config=config)
