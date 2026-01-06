import datetime as dt
import json
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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


def parse_resource_summary(payload):
    """解析资源池概览数据 (CPU/GPU/内存 的总量与使用量)"""
    if not isinstance(payload, dict):
        return None, "数据格式错误：不是字典。"

    try:
        res_info = payload.get("resource_info", {})
        if not res_info:
            return None, "数据格式错误：缺少 resource_info。"

        quota = res_info.get("quota", {})
        avail = res_info.get("availableQuota", {})

        # CPU
        cpu_total = quota.get("cpu", 0)
        cpu_avail = avail.get("cpu", 0)

        # GPU
        if len(quota.get("scalarResources", {})) != 1:
            return None, "数据格式错误：scalarResources 包含多种 GPU 类型，无法解析总量。"
        gpu_total = list(quota.get("scalarResources", {}).values())[0]
        gpu_avail = list(avail.get("scalarResources", {}).values())[0]

        # 内存 (MB -> GB)
        mem_total_mb = quota.get("memory", 0)
        mem_avail_mb = avail.get("memory", 0)

        mem_total_gb = int(mem_total_mb / 1024)
        mem_avail_gb = int(mem_avail_mb / 1024)

        return {
            "cpu": {"avail": cpu_avail, "total": cpu_total},
            "gpu": {"avail": gpu_avail, "total": gpu_total},
            "mem": {"avail": mem_avail_gb, "total": mem_total_gb},
        }, None

    except Exception as exc:
        return None, f"概览数据解析失败：{exc}"


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
            gpus = metrics.get("scalarResources", {})
            if len(gpus) != 1:
                return None, f"节点 {node_id} 包含多种 GPU 类型，无法解析配额。"
            gpu_count = list(gpus.values())[0]
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


def create_donut_chart(avail_val, total_val, color_used="rgba(243, 128, 1, 0.5)", color_free="rgb(61, 157, 243)"):
    used_val = total_val - avail_val

    fig = go.Figure(
        data=[
            go.Pie(
                values=[used_val, avail_val],
                labels=["Used", "Free"],
                hole=0.6,
                marker=dict(colors=[color_used, color_free]),
                textinfo="none",
                hoverinfo="label+value",
                sort=False,
                direction="clockwise",
                rotation=0,
            )
        ]
    )

    fig.update_layout(
        showlegend=False,
        margin=dict(l=10, r=10, t=10, b=10),
        height=160,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


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

    summary_data, summary_error = parse_resource_summary(payload)
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
        .stHorizontalBlock > .stColumn:first-child:has(div[data-testid="stCaptionContainer"]) {
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

    if summary_error:
        st.warning(f"概览图加载失败: {summary_error}")
    else:
        metrics_display = [
            {
                "title": "GPU",
                "avail": summary_data["gpu"]["avail"],
                "total": summary_data["gpu"]["total"],
                "unit": "",
            },
            {
                "title": "CPU",
                "avail": summary_data["cpu"]["avail"],
                "total": summary_data["cpu"]["total"],
                "unit": "",
            },
            {
                "title": "MEM",
                "avail": summary_data["mem"]["avail"],
                "total": summary_data["mem"]["total"],
                "unit": "GB",
            },
        ]

        # 使用 columns 布局三个图表
        st.subheader("资源概览")
        cols = st.columns(3)

        for col, item in zip(cols, metrics_display):
            with col:
                st.markdown(
                    f"<div style='text-align: center; color: #555; font-size: 1rem;'>{item['title']}</div>",
                    unsafe_allow_html=True,
                )

                fig = create_donut_chart(item["avail"], item["total"])
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

                unit_str = item["unit"]
                text_label = f"剩余: {item['avail']}{unit_str} / {item['total']}{unit_str}"
                st.markdown(
                    f"<div style='text-align: center; color: #666; font-size: 0.9rem; margin-top: -10px;'>{text_label}</div>",
                    unsafe_allow_html=True,
                )

    st.divider()

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

    st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("各节点资源详情")

    display_df = df[["Full ID", "GPU", "CPU", "Memory(GB)"]].copy()
    st.dataframe(
        display_df.style.background_gradient(cmap="Blues", subset=["GPU", "CPU", "Memory(GB)"]),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Full ID": st.column_config.TextColumn(label="节点 ID"),
            "Memory(GB)": st.column_config.NumberColumn(label="MEM", format="%0.2f GB"),
        },
    )


__all__ = ["webapp_ai4s_status"]

if __name__ == "__main__":
    webapp_ai4s_status()
