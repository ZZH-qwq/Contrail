import json
import os
import pandas as pd
import datetime as dt
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from contrail.gpu.GPU_query_db import query_latest_gpu_info


@st.cache_data
def load_config(config_path: str = "config/host_config.json") -> dict:
    """
    Load the configuration file.
    """
    with open(config_path, "r") as f:
        config = json.load(f)
    return config["webapp"]


def load_ai4s_result(file="data/ai4s_data.json"):
    """
    Load the AI4S result file.
    """
    if not os.path.exists(file):
        st.error(f"文件 {file} 不存在。")
        return None

    with open(file, "r") as f:
        try:
            result = json.load(f)
        except Exception as e:
            st.error(e)
            return None

    return result


class HomePage:
    def __init__(self, pages, configs, features):
        self.pages = pages
        self.configs = configs
        self.features = features
        self.__name__ = "homepage"

    def __call__(self):
        webapp_homepage(self.pages, self.configs, self.features)


def device_status(device, timestamp: str, features: dict):
    name = device.hostname
    db_path = device.realtime_db_path
    gpu = device.gpu_type
    n_gpu = device.config["N_GPU"]
    gmem = device.config["GMEM"]

    if features.history_only:
        st.subheader(name)
        st.caption(f"{n_gpu} × {gpu} {gmem}G")
        return None

    try:
        gpu_current_df = query_latest_gpu_info(db_path, timestamp)
        if not gpu_current_df.empty:
            current_timestamp = gpu_current_df["timestamp"].max()
    except Exception as e:
        st.error(e)

    mean_util = gpu_current_df["gpu_utilization"].mean()

    st.subheader(name)
    st.progress(mean_util / 100)
    st.caption(
        f'<p><span style="float: left;">{n_gpu} × {gpu} {gmem}G</span><span style="float: right; font-weight: 600;">{mean_util:.0f}%</span></p>',
        unsafe_allow_html=True,
    )

    return current_timestamp


def device_card_pc(device, features, pages):
    cont1, cont2 = st.columns([3, 2], vertical_alignment="center")

    with cont1:
        current_timestamp = device_status(device, dt.datetime.now().strftime("%Y-%m-%d %H:%M"), features)

    if not features.history_only:
        cont2.page_link(pages[device.hostname][0], label="实时状态", use_container_width=True)
        cont2.page_link(pages[device.hostname][1], label="历史信息", use_container_width=True)
    else:
        cont2.page_link(pages[device.hostname][0], label="历史信息", use_container_width=True)

    return current_timestamp


def device_card_mobile(device, features, pages):
    current_timestamp = device_status(device, dt.datetime.now().strftime("%Y-%m-%d %H:%M"), features)

    if not features.history_only:
        col1, col2 = st.columns(2)
        col1.page_link(pages[device.hostname][0], label="实时状态", use_container_width=True)
        col2.page_link(pages[device.hostname][1], label="历史信息", use_container_width=True)
    else:
        st.page_link(pages[device.hostname][0], label="历史信息", use_container_width=True)

    return current_timestamp


def webapp_homepage(pages, configs, features):
    """
    首页
    """

    st.html(
        """<style>
        /* 主页 - 设备标题 */
        .stColumn:has(a[data-testid="stPageLink-NavLink"]) h3 {
            margin-top: -2px;
            padding-top: 0px;
            padding-bottom: 0px;
        }
        /* 主页 - 进度条 */
        .stProgress {
            margin-top: 0px;
            margin-bottom: -6px;
        }
        /* 主页 - 标注 */
        .stColumn div[data-testid="stCaptionContainer"] > p {
            margin-bottom: 10px;
        }
        /* 主页 - 设备操作按钮 */
        .stColumn a[data-testid="stPageLink-NavLink"] {
            background-color: #aaa2;
            justify-content: center;
            transision: background-color 0.5s;
        }
        .stColumn a[data-testid="stPageLink-NavLink"]:hover {
            background-color: #aaa1;
        }
        /* column 修改 */
        @media (max-width: 640px) {
            .stColumn .stColunm,
            .st-emotion-cache-1eoatk1 {
                min-width: calc(50% - 1rem) !important;
            }
        }
        </style>"""
    )

    st.title("Contrail")

    col1, col2, col3 = st.columns([4, 11, 1], vertical_alignment="center")

    col1.checkbox("自动刷新", key="ai4s_autorefresh", value=True)

    with col3:
        if st.session_state["ai4s_autorefresh"]:
            st_autorefresh(interval=60000, key="ai4s_task_monitor")

    st.subheader("服务器列表")

    not_pc = not st.session_state.get("is_session_pc", True)
    device_card = device_card_mobile if not_pc else device_card_pc

    configs_list = list(configs.values())
    times = []

    n_cols = 2
    for i in range(0, len(configs_list), n_cols):
        cols = st.columns(n_cols, border=True)
        for j, col in enumerate(cols):
            if i + j >= len(configs_list):
                break
            with col:
                timestamp = device_card(configs_list[i + j], features, pages)
                times.append(timestamp)

    if not features.history_only:
        times = [dt.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S") for ts in times]
        min_time = min(times).strftime("%Y-%m-%d %H:%M")
        max_time = max(times).strftime("%Y-%m-%d %H:%M")

        col2.write(f"{min_time} / {max_time}")

    st.subheader("AI4S 平台")

    ai4s_result = load_ai4s_result()

    cols = st.columns(2, vertical_alignment="center")

    with cols[0]:
        col1, col2 = st.columns(2)
        col1.page_link(pages["AI4S"][0], label="AI4S 任务", use_container_width=True)
        col2.page_link(pages["AI4S"][1], label="AI4S 费用", use_container_width=True)
    with cols[1]:
        if ai4s_result and ai4s_result["state"] == "success":
            # 显示任务数量
            n_tasks = len(ai4s_result) - 1
            st.write(f"运行中的任务数量：**{n_tasks}**")
        else:
            st.warning("最近完成的任务运行失败。")

    st.subheader("用户信息")

    stcol = st.columns([1, 3])

    stcol[0].page_link(pages["Info"][0], label="用户信息查询", use_container_width=True)
