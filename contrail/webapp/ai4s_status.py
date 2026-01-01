import datetime as dt
import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_autorefresh import st_autorefresh

WARNING_THRESHOLD = dt.timedelta(minutes=20)
DEFAULT_STATUS_FILE = "data/ai4s_quota_status.json"


def load_quota_payload(file_path=DEFAULT_STATUS_FILE):
    """Load quota JSON and its update time; no UI side effects."""

    if not os.path.exists(file_path):
        return None, None, f"文件 {file_path} 不存在。"

    try:
        updated_at = dt.datetime.fromtimestamp(os.path.getmtime(file_path))
        return cached_read_data(updated_at, file_path), updated_at, None
    except Exception as exc:  # noqa: BLE001
        return None, None, str(exc)


@st.cache_data
def cached_read_data(update_time, file_path=DEFAULT_STATUS_FILE):
    with open(file_path, "r", encoding="utf-8") as file:
        return json.load(file)


def parse_nodes_quota(payload):
    if not isinstance(payload, dict):
        return None, "数据格式错误：不是字典。"

    try:
        nodes_quota = payload["result"]["nodesQuota"]
    except Exception as exc:  # noqa: BLE001
        return None, f"数据格式错误：缺少 result/nodesQuota。({exc})"

    if not isinstance(nodes_quota, dict):
        return None, "数据格式错误：nodesQuota 不是字典。"

    rows = []
    for node_id, metrics in nodes_quota.items():
        try:
            gpu_count = metrics.get("scalarResources", {}).get("nvidia/NVIDIA-A800-SXM4-80GB", 0)
            try:
                short_name = f"#{node_id.split('-')[4].split('.')[0]}"
            except Exception:
                short_name = node_id[-5:] if len(node_id) >= 5 else node_id
            mem_gb = metrics.get("memory", 0) / 1024
            rows.append(
                {
                    "Full ID": node_id,
                    "ID": short_name,
                    "CPU": metrics.get("cpu", 0),
                    "Memory(GB)": round(mem_gb, 2),
                    "GPU": gpu_count,
                }
            )
        except Exception as exc:  # noqa: BLE001
            return None, f"节点 {node_id} 解析失败：{exc}"

    df = pd.DataFrame(rows)
    if df.empty:
        return df, None

    df = df.sort_values(by=["GPU", "CPU", "Memory(GB)", "ID"], ascending=[False, False, False, True])
    return df, None


def render_update(updated_at):
    if not updated_at:
        st.write("未找到记录")
        return

    delta_minutes = (dt.datetime.now() - updated_at).total_seconds() // 60
    formatted_time = updated_at.strftime("%Y-%m-%d %H:%M:%S")
    st.write(f"更新于 {formatted_time} / {delta_minutes:.0f} 分钟前")


def webapp_ai4s_status():
    st.title("AI4S 节点监控")

    col1, col2, col3 = st.columns([4, 11, 1], vertical_alignment="center")

    col1.checkbox("自动刷新", key="ai4s_status_autorefresh", value=True)

    with col3:
        if st.session_state.get("ai4s_status_autorefresh", True):
            st_autorefresh(interval=60000, key="ai4s_status_monitor")

    payload, updated_at, error = load_quota_payload()
    if error:
        st.error(error)
        return

    with col2:
        render_update(updated_at)

    if not updated_at or dt.datetime.now() - updated_at >= WARNING_THRESHOLD:
        st.warning("过去 20 分钟内没有配额数据更新：AI4S 爬虫程序可能离线。")

    df, parse_error = parse_nodes_quota(payload)
    if parse_error:
        st.error(parse_error)
        return

    if df is None or df.empty:
        st.info("没有可用的节点配额数据。")
        return

    st.html(
        """<style>
        /* 调整 column padding */
        .stHorizontalBlock > .stColumn {
            padding-right: 0.25rem;
            padding-bottom: 0.5rem;
        }
        /* 调整卡片背景 */
        .stHorizontalBlock > .stColumn:first-child:has(.stMarkdown) {
            background-color: light-dark(rgba(28, 131, 225, 0.1), rgba(61, 157, 243, 0.2));
            border-color: light-dark(rgba(28, 131, 225, 0.3), rgba(61, 157, 243, 0.4));
        }
        /* 调整数据字体 */
        div[data-testid="stMetricValue"] {
            font-size: 2.0rem;
        }
        /* 调整 Node ID 文字 */
        .stHorizontalBlock > .stColumn:first-child:has(.stMarkdown) div[data-testid="stElementContainer"]:last-child p * {
            display:inline-block;
            transform: translateY(-3px);
            overflow:hidden;
            text-overflow:ellipsis;
            width: 100%;
            white-space: nowrap;
        }
        </style>"""
    )

    best_node = df.iloc[0]

    st.subheader("推荐计算节点")

    with st.container():
        col1, col2, col3, col4 = st.columns([1.5, 1, 1, 1.5], border=True)
        with col1:
            st.caption("Node ID")
            st.markdown(f"**{best_node['Full ID']}**")
        with col2:
            st.metric(label="剩余 GPU", value=f"{best_node['GPU']} 张")
        with col3:
            st.metric(label="剩余 CPU", value=f"{best_node['CPU']} 核")
        with col4:
            st.metric(label="剩余 MEM", value=f"{best_node['Memory(GB)']} GB")

    st.divider()

    st.subheader("GPU 剩余分布")

    fig_bar = px.bar(
        df,
        x="ID",
        y="GPU",
        text="GPU",
        color="GPU",
        color_continuous_scale="Blues",
        height=250,
    )

    fig_bar.update_traces(
        textposition="outside",
        textfont=dict(size=16),
        cliponaxis=False,
    )

    fig_bar.update_layout(
        xaxis_title=None,
        yaxis_title=None,
        coloraxis_showscale=False,
        margin=dict(l=20, r=20, t=10, b=10),
        xaxis=dict(
            type="category",
            categoryorder="array",
            categoryarray=df["ID"].tolist(),
            tickfont=dict(size=14),
        ),
        yaxis=dict(tickfont=dict(size=14)),
    )

    st.plotly_chart(fig_bar, width="stretch")

    st.subheader("各节点资源详情")

    display_df = df[["Full ID", "GPU", "CPU", "Memory(GB)"]].copy()
    st.dataframe(
        display_df.style.background_gradient(cmap="Blues", subset=["GPU", "CPU", "Memory(GB)"]),
        width="stretch",
        hide_index=True,
        column_config={
            "Full ID": st.column_config.TextColumn(label="节点 ID"),
            "Memory(GB)": st.column_config.NumberColumn(label="MEM", format="%0.2f GB"),
        },
    )


__all__ = ["webapp_ai4s_status"]

if __name__ == "__main__":
    webapp_ai4s_status()
