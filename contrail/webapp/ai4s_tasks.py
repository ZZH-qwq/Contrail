import streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import altair as alt
import datetime as dt
import json
import os

from contrail.utils import query_ai4s_username


def read_json_result(file="data/ai4s_data.json", display_warning=True):
    if not os.path.exists(file):
        st.error(f"文件 {file} 不存在。")
        return {"state": "failed"}
    update_timestamp = os.path.getmtime(file)
    update_time = dt.datetime.fromtimestamp(update_timestamp)
    timedelta = dt.datetime.now() - update_time
    st.write(f"更新于 {update_time.strftime("%Y-%m-%d %H:%M:%S")} / {timedelta.total_seconds()//60:.0f} 分钟前")
    if display_warning:
        if timedelta.total_seconds() > 1200:
            st.warning("过去 20 分钟内没有任务数据更新：AI4S 爬虫程序可能离线。")
    return cached_read_data(update_timestamp, file)


@st.cache_data
def cached_read_data(update_time, file="data/ai4s_data.json"):
    with open(file, "r") as file:
        data = json.loads(file.read())
    return data


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
        st.plotly_chart(fig, use_container_width=True, key=f"{key}_{task['task_name']}_gpu")
    with gmem:
        timestamps, values = get_data(task["data"], "accelerator_memory_used_bytes")
        values_gb = [x / 1024**3 for x in values]
        fig = px.line(x=timestamps, y=values_gb)
        fig.update_yaxes(rangemode="tozero")
        fig.update_traces(hovertemplate=None)
        fig.update_layout(
            hovermode="x", yaxis_title="显存用量 GB", xaxis_title=None, margin=dict(l=0, r=0, t=0, b=0), height=120
        )
        st.plotly_chart(fig, use_container_width=True, key=f"{key}_{task['task_name']}_gmem")


def webapp_ai4s():
    st.title("AI4S: 任务列表")

    col1, col2, col3 = st.columns([4, 11, 1], vertical_alignment="center")

    col1.checkbox("自动刷新", key="ai4s_autorefresh", value=True)

    with col3:
        if st.session_state["ai4s_autorefresh"]:
            st_autorefresh(interval=60000, key="ai4s_task_monitor")

    with col2:
        data = read_json_result()

    last_state = data.get("state", "failed")
    data.pop("state", None)

    if not data:
        st.info("没有正在运行的任务。")

    # last_container = st.container() if last_state == "success" else st.expander("最近完成的任务")

    if last_state == "success":
        last_container = st.container()
    else:
        last_container = st.expander("最近完成的任务")
        st.warning("最近完成的任务运行失败。显示最近的成功记录：")

        success_data = read_json_result("data/ai4s_data_last_success.json", False)
        if success_data:
            success_data.pop("state", None)
            if not success_data:
                st.info("成功的任务记录为空。")
            for i, task in success_data.items():
                display_data(i, task, "success")
        else:
            st.warning("没有成功的任务记录。")

    with last_container:
        for i, task in data.items():
            display_data(i, task, "last")
            # st.markdown("---")
