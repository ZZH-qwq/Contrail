from history import webapp_history


config = {
    "N_GPU": 8,
    "GMEM": 48,
}

webapp_history(hostname="Leo", db_path="data/gpu_history_leo.db", config=config)
