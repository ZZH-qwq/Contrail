import json
import os
import streamlit as st


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
        result = json.load(f)

    return result


class HomePage:
    def __init__(self, pages: st.Page):
        self.pages = pages
        self.__name__ = "homepage"

    def __call__(self):
        webapp_homepage(pages=self.pages)


def webapp_homepage(pages: st.Page):
    """
    首页
    """
    st.title("Contrail")

    config = load_config()

    devices = [conf["hostname"] for conf in config["devices"].values()]
    features = config["features"]

    st.subheader("服务器列表")

    n_cols = 3
    for i in range(0, len(devices), n_cols):
        cols = st.columns(n_cols, border=True)
        for j, col in enumerate(cols):
            if i + j >= len(devices):
                break
            with col:
                dev = devices[i + j]

                st.subheader(dev, divider="gray")
                if not features["history_only"]:
                    cols = st.columns(2)
                    with cols[0]:
                        st.page_link(pages[dev][0], label="实时状态", use_container_width=True)
                    with cols[1]:
                        st.page_link(pages[dev][1], label="历史信息", use_container_width=True)
                else:
                    st.page_link(pages[dev][1], label="历史信息", use_container_width=True)

    st.subheader("AI4S 平台")

    ai4s_result = load_ai4s_result()

    cols = st.columns(2, vertical_alignment="center")

    with cols[0]:
        subcols = st.columns(2)
        with subcols[0]:
            st.page_link(pages["AI4S"][0], label="AI4S 任务", use_container_width=True)
        with subcols[1]:
            st.page_link(pages["AI4S"][1], label="AI4S 费用", use_container_width=True)
    with cols[1]:
        if ai4s_result and ai4s_result["state"] == "success":
            # 显示任务数量
            n_tasks = len(ai4s_result) - 1
            st.write(f"运行中的任务数量：**{n_tasks}**")
        else:
            st.warning("最近完成的任务运行失败。")

    st.subheader("用户信息")

    cols = st.columns(2, vertical_alignment="bottom")

    with cols[0]:
        st.page_link(pages["Info"][0], label="用户信息查询", use_container_width=True)
