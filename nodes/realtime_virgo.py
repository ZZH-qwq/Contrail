from contrail.webapp import webapp_realtime


config = {
    "DURATION": 30,
    "N_GPU": 8,
    "GMEM": 48,
    "LIMIT": 1000,
}

webapp_realtime(hostname="Virgo", db_path="data/gpu_info_virgo.db", config=config)
