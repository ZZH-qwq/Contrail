from contrail.webapp import webapp_history


config = {
    "N_GPU": 8,
    "GMEM": 48,
}

webapp_history(hostname="Virgo", db_path="data/gpu_history_virgo.db", config=config)
