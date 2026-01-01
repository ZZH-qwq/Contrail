import datetime as dt
import json
import os

import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from contrail.utils.config import query_ai4s_username

WARNING_THRESHOLD = dt.timedelta(minutes=20)
FALLBACK_THRESHOLD = dt.timedelta(minutes=20)
DEFAULT_DATA_FILE = "data/ai4s_data.json"
SUCCESS_DATA_FILE = "data/ai4s_data_last_success.json"


def load_json_payload(file_path=DEFAULT_DATA_FILE):
    """Read JSON payload and its update time without emitting UI side effects."""

    if not os.path.exists(file_path):
        return None, None, f"文件 {file_path} 不存在。"

    try:
        updated_at = dt.datetime.fromtimestamp(os.path.getmtime(file_path))
        return cached_read_data(updated_at, file_path), updated_at, None
    except Exception as exc:  # noqa: BLE001
        return None, None, str(exc)


@st.cache_data
def cached_read_data(update_time, file_path=DEFAULT_DATA_FILE):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def extract_state_and_tasks(payload):
    if not payload:
        return "failed", {}

    state = payload.get("state", "failed")
    tasks = {k: v for k, v in payload.items() if k != "state"}
    return state, tasks


def get_data(data, key):
    return [dt.datetime.fromtimestamp(x / 1000) for x in data[key]["values"][0]], data[key]["values"][1]


def display_data(i, task, key="last"):
    if not task:
        st.warning(f"任务 {i}：读取任务信息失败。")
        return

    basics, times, resources = st.columns([3, 3, 2], vertical_alignment="bottom")

    with basics:
        user = query_ai4s_username(task["user"])
        st.markdown(f"#### {task['task_name']}  \n创建者: **:blue[{user}]**")

    with times:
        st.markdown(f"开始: {task['start_time']}  \n活跃: **{task['active_time']}**")

    with resources:
        st.write(f"{task['cpus']} C / {task['memory']}  \n**GPU: {task['gpu_count']}**")

    if "data" not in task:
        st.warning(f"任务 {task['task_name']}：读取任务数据失败。")
        return

    gpu, gmem = st.columns(2)

    with gpu:
        timestamps, values = get_data(task["data"], "accelerator_duty_cycle")
        fig = px.line(x=timestamps, y=values)
        fig.update_yaxes(rangemode="tozero")
        fig.update_traces(hovertemplate=None)
        fig.update_layout(
            hovermode="x", yaxis_title="GPU 使用率 %", xaxis_title=None, margin=dict(l=0, r=0, t=0, b=0), height=120
        )
        st.plotly_chart(fig, width="stretch", key=f"{key}_{task['task_name']}_gpu")
    with gmem:
        timestamps, values = get_data(task["data"], "accelerator_memory_used_bytes")
        values_gb = [x / 1024**3 for x in values]
        fig = px.line(x=timestamps, y=values_gb)
        fig.update_yaxes(rangemode="tozero")
        fig.update_traces(hovertemplate=None)
        fig.update_layout(
            hovermode="x", yaxis_title="显存用量 GB", xaxis_title=None, margin=dict(l=0, r=0, t=0, b=0), height=120
        )
        st.plotly_chart(fig, width="stretch", key=f"{key}_{task['task_name']}_gmem")


def render_update(updated_at):
    if not updated_at:
        st.write("未找到记录")
        return

    delta_minutes = (dt.datetime.now() - updated_at).total_seconds() // 60
    formatted_time = updated_at.strftime("%Y-%m-%d %H:%M:%S")
    st.write(f"更新于 {formatted_time} / {delta_minutes:.0f} 分钟前")


def render_tasks(tasks, key="last"):
    if not tasks:
        st.info("没有正在运行的任务。")
        return
    for i, task in tasks.items():
        display_data(i, task, key)


def webapp_ai4s():
    st.title("AI4S: 任务列表")

    col1, col2, col3 = st.columns([4, 11, 1], vertical_alignment="center")

    col1.checkbox("自动刷新", key="ai4s_autorefresh", value=True)

    with col3:
        if st.session_state["ai4s_autorefresh"]:
            st_autorefresh(interval=60000, key="ai4s_task_monitor")

    current_payload, current_updated_at, current_error = load_json_payload(DEFAULT_DATA_FILE)
    success_payload, success_updated_at, _ = load_json_payload(SUCCESS_DATA_FILE)

    if current_error:
        st.error(current_error)
        return

    current_state, current_tasks = extract_state_and_tasks(current_payload)
    _, success_tasks = extract_state_and_tasks(success_payload)

    with col2:
        render_update(current_updated_at)
    if dt.datetime.now() - current_updated_at >= WARNING_THRESHOLD:
        st.warning("过去 20 分钟内没有任务数据更新：AI4S 爬虫程序可能离线。")

    curr_container = st.container()
    succ_container = None

    if current_state != "success" and success_updated_at:
        if dt.datetime.now() - success_updated_at <= FALLBACK_THRESHOLD:
            curr_container = st.expander("最近完成的任务")
            st.warning("最近完成的任务运行失败。显示最近的成功记录：")
            succ_container = st.container()
        else:
            succ_container = st.expander("最近的成功记录")
            st.warning("最近完成的任务运行失败：")
            curr_container = st.container()

    if succ_container:
        with succ_container:
            render_update(success_updated_at)
            render_tasks(success_tasks, key="success")
    with curr_container:
        render_tasks(current_tasks, key="last")
