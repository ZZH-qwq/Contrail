import streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import altair as alt
import datetime as dt

from contrail.gpu.GPU_query_db import *
from contrail.utils.config import query_server_username

# pyright: basic


COLOR_SCHEME = px.colors.qualitative.Plotly


def status_panel(gpu_current_df, N_GPU=8, GMEM=80):
    for i in range(0, N_GPU, 4):
        cols = st.columns(4)
        for j in range(4):
            if i + j >= N_GPU:
                break
            with cols[j]:
                gpu_info = gpu_current_df.iloc[i + j]
                st.subheader(f"GPU {gpu_info['gpu_index']}")
                st.progress(gpu_info["gpu_utilization"] / 100, text=f"使用率：{gpu_info['gpu_utilization']}%")
                st.progress(
                    gpu_info["used_memory"] / 0x40000000 / GMEM,
                    text=f"显存用量：{gpu_info['used_memory']/0x40000000:.2f} GB",
                )


def store_value(key: str) -> None:
    st.session_state["_" + key] = st.session_state[key]


def load_value(key: str) -> None:
    st.session_state[key] = st.session_state.get("_" + key, None)


def webapp_realtime(hostname="Virgo", db_path="data/gpu_history_virgo.db", config={}):
    DB_PATH = db_path  # 数据库路径

    DURATION = config.get("DURATION", 30)
    N_GPU = config.get("N_GPU", 8)
    GMEM = config.get("GMEM", 48)
    LIMIT = config.get("LIMIT", 1000)

    not_pc = not st.session_state.get("is_session_pc", True)
    if not_pc:
        DURATION = DURATION / 2

    st.html(
        """<style>
        /* column 修改 */
        @media (max-width: 640px) {
            .stColumn {
                min-width: calc(50% - 1rem);
            }
        }
        </style>"""
    )

    st.title(f"{hostname}: 实时状态")

    col1, col2, col3 = st.columns([4, 11, 1], vertical_alignment="center")

    col1.checkbox("自动刷新", key="autorefresh", value=True)

    with col3:
        if st.session_state["autorefresh"]:
            st_autorefresh(interval=1000, limit=LIMIT, key=f"gpu_monitor_{hostname}")

    curr_refresh = st.session_state.get(f"gpu_monitor_{hostname}", 0)
    if curr_refresh is not None and LIMIT is not None and curr_refresh >= LIMIT - 1:
        st.warning(f"标签页长时间未活动，自动刷新已停止：请刷新页面以继续监控。")

    if st.session_state.get(f"_selection_realtime_{hostname}", None) is None:
        st.session_state[f"_selection_realtime_{hostname}"] = "**详细信息**"

    # 查询时间范围：过去 30 秒
    def get_time_range():
        end_time = dt.datetime.now(tz=dt.timezone.utc)
        start_time = end_time - dt.timedelta(seconds=DURATION)
        return start_time.strftime("%Y-%m-%d %H:%M:%S"), end_time.strftime("%Y-%m-%d %H:%M:%S")

    start_time, end_time = get_time_range()

    try:
        # 最新数据
        gpu_current_df = query_latest_gpu_info(DB_PATH, end_time)

        # 获取数据
        gpu_utilization_df = query_gpu_realtime_usage(start_time, end_time, DB_PATH)

    except Exception as e:
        st.error(f"查询数据时出现错误：{e}")
        logger.error(f"Error querying realtime data: {e}")
        return

    if not gpu_current_df.empty:
        current_timestamp = gpu_current_df["timestamp"].max()
        col2.write(f"更新于：{current_timestamp}")

    # 如果没有数据，提示用户
    if gpu_utilization_df.empty:
        st.warning(f"过去 {DURATION} 秒内没有 GPU 数据记录：GPU 监控程序可能离线。")
        return

    panel_container = st.container()

    st.divider()

    axis_end = dt.datetime.now() - dt.timedelta(seconds=1)
    axis_start = axis_end - dt.timedelta(seconds=DURATION)
    axis_x = alt.X("timestamp:T").axis(labelSeparation=10).title(None).scale(alt.Scale(domain=(axis_start, axis_end)))
    gpu_color = alt.Color("gpu_index:N").title("GPU").scale(domain=range(N_GPU), range=COLOR_SCHEME)
    gpu_opacity = alt.Opacity("gpu_index:N").title("GPU")
    user_color = alt.Color("user:N").title("用户").scale(range=COLOR_SCHEME)

    nearest = alt.selection_point(nearest=True, on="pointerover", fields=["timestamp"], empty=False)
    when_near = alt.when(nearest)
    gpu_tooltips = [alt.Tooltip(str(i), type="quantitative") for i in range(N_GPU)]

    if not_pc:
        gpu_color = gpu_color.legend(orient="bottom", titleOrient="left", columns=4)
        # gpu_opacity = gpu_opacity.legend(orient="bottom", titleOrient="left", columns=4)
        # user_color = user_color.legend(orient="top", titleOrient="left", columns=4)

    load_value(f"selection_realtime_{hostname}")
    select = st.pills(
        "信息选择",
        ["**详细信息**", "**用户使用**", "**汇总数据**"],
        label_visibility="collapsed",
        selection_mode="single",
        key=f"selection_realtime_{hostname}",
        on_change=store_value,
        args=(f"selection_realtime_{hostname}",),
    )

    try:
        if select == "**详细信息**":
            gpu_utilization_df = query_gpu_realtime_usage(start_time, end_time, DB_PATH)
            gpu_memory_df = query_gpu_memory_realtime_usage(start_time, end_time, DB_PATH)
        elif select == "**用户使用**":
            user_gpu_df = query_user_gpu_realtime_usage(start_time, end_time, DB_PATH)
            user_gpu_memory_df = query_user_gpu_memory_realtime_usage(start_time, end_time, DB_PATH)
        elif select == "**汇总数据**":
            gpu_utilization_df = query_gpu_realtime_usage(start_time, end_time, DB_PATH)
            gpu_memory_df = query_gpu_memory_realtime_usage(start_time, end_time, DB_PATH)

    except Exception as e:
        st.error(f"查询数据时出现错误：{e}")
        logger.error(f"Error querying realtime details: {e}")
        return

    finally:
        with panel_container:
            status_panel(gpu_current_df, N_GPU=N_GPU, GMEM=GMEM)

        if select == "**详细信息**":
            # GPU 每台设备的利用率折线图
            st.subheader("使用率 %")

            base = alt.Chart(gpu_utilization_df).encode(axis_x)

            line = base.mark_line().encode(
                gpu_color,
                alt.Y("gpu_utilization:Q").title(None).scale(alt.Scale(domain=[0, 100])),
            )
            points = line.mark_point().encode(opacity=when_near.then(alt.value(1)).otherwise(alt.value(0)))
            rules = (
                base.transform_pivot("gpu_index", value="gpu_utilization", groupby=["timestamp"])
                .mark_rule()
                .encode(
                    opacity=when_near.then(alt.value(0.3)).otherwise(alt.value(0)),
                    tooltip=gpu_tooltips,
                )
                .add_params(nearest)
            )
            chart = alt.layer(line, points, rules)

            st.altair_chart(chart, use_container_width=True)  # pyright: ignore[reportArgumentType]

            # GPU 内存使用情况
            st.subheader("显存用量 GB")

            base = alt.Chart(gpu_memory_df).transform_calculate(memory="datum.used_memory / 0x40000000").encode(axis_x)

            line = base.mark_line().encode(
                gpu_color,
                alt.Y("memory:Q").title(None).scale(alt.Scale(domain=[0, GMEM])),
            )
            points = line.mark_point().encode(opacity=when_near.then(alt.value(1)).otherwise(alt.value(0)))
            rules = (
                base.transform_pivot("gpu_index", value="memory", groupby=["timestamp"])
                .mark_rule()
                .encode(
                    opacity=when_near.then(alt.value(0.3)).otherwise(alt.value(0)),
                    tooltip=gpu_tooltips,
                )
                .add_params(nearest)
            )
            chart = alt.layer(line, points, rules)

            st.altair_chart(chart, use_container_width=True)  # pyright: ignore[reportArgumentType]

        elif select == "**用户使用**":
            user_gpu_df["user"] = user_gpu_df["user"].apply(lambda x: query_server_username(DB_PATH, x))
            user_gpu_memory_df["user"] = user_gpu_memory_df["user"].apply(lambda x: query_server_username(DB_PATH, x))

            st.subheader("用户使用率 %")
            chart = (
                alt.Chart(user_gpu_df)
                .mark_area()
                .encode(
                    user_color,
                    gpu_opacity,
                    axis_x,
                    alt.Y("gpu_utilization:Q").title(None),
                )
            )
            st.altair_chart(chart, use_container_width=True)

            st.subheader("用户显存用量 GB")
            chart = (
                alt.Chart(user_gpu_memory_df)
                .transform_calculate(memory="datum.used_memory / 0x40000000")
                .mark_area()
                .encode(
                    user_color,
                    gpu_opacity,
                    axis_x,
                    alt.Y("memory:Q").title(None),
                )
            )
            st.altair_chart(chart, use_container_width=True)

        elif select == "**汇总数据**":
            # 总 GPU 使用率折线图
            st.subheader("总使用率 %")
            chart = (
                alt.Chart(gpu_utilization_df)
                .mark_area()
                .encode(
                    gpu_color,
                    axis_x,
                    alt.Y("gpu_utilization:Q").title(None).scale(alt.Scale(domain=[0, 100 * N_GPU])),
                    alt.FillOpacityValue(0.5),
                )
            )
            st.altair_chart(chart, use_container_width=True)

            # 总显存用量情况
            st.subheader("总显存用量 GB")
            chart = (
                alt.Chart(gpu_memory_df)
                .transform_calculate(memory="datum.used_memory / 0x40000000")
                .mark_area()
                .encode(
                    gpu_color,
                    axis_x,
                    alt.Y("memory:Q").title(None).scale(alt.Scale(domain=[0, GMEM * N_GPU])),
                    alt.FillOpacityValue(0.5),
                )
            )
            st.altair_chart(chart, use_container_width=True)
