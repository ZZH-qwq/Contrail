import streamlit as st
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


def get_gpu_color(N_GPU, not_pc):
    gpu_color = alt.Color("gpu_index:N").title("GPU").scale(domain=range(N_GPU), range=COLOR_SCHEME)
    if not_pc:
        gpu_color = gpu_color.legend(orient="bottom", titleOrient="left", columns=4)
    return gpu_color


def render_detail_view(start_time, end_time, DB_PATH, axis_x, PARAMS):
    try:
        gpu_utilization_df = query_gpu_realtime_usage(start_time, end_time, DB_PATH)
        gpu_memory_df = query_gpu_memory_realtime_usage(start_time, end_time, DB_PATH)
    except Exception as e:
        st.error(f"查询详细数据时出现错误：{e}")
        logger.error(f"Error querying realtime details: {e}")
        return

    (N_GPU, GMEM, DURATION, not_pc) = PARAMS
    gpu_tooltips = [alt.Tooltip(str(i), type="quantitative") for i in range(N_GPU)]
    gpu_color = get_gpu_color(N_GPU, not_pc)

    # 交互选择器配置
    nearest = alt.selection_point(nearest=True, on="pointerover", fields=["timestamp"], empty=False)
    when_near = alt.when(nearest)

    st.subheader("使用率 %")
    base_util = alt.Chart(gpu_utilization_df).encode(axis_x)
    line_util = base_util.mark_line().encode(
        gpu_color,
        alt.Y("gpu_utilization:Q").title(None).scale(alt.Scale(domain=[0, 100])),
    )
    points_util = line_util.mark_point().encode(opacity=when_near.then(alt.value(1)).otherwise(alt.value(0)))
    rules_util = (
        base_util.transform_pivot("gpu_index", value="gpu_utilization", groupby=["timestamp"])
        .mark_rule()
        .encode(
            opacity=when_near.then(alt.value(0.3)).otherwise(alt.value(0)),
            tooltip=gpu_tooltips,
        )
        .add_params(nearest)
    )
    chart = alt.layer(line_util, points_util, rules_util)
    st.altair_chart(chart, width="stretch")  # pyright: ignore[reportArgumentType]

    st.subheader("显存用量 GB")
    base_mem = alt.Chart(gpu_memory_df).transform_calculate(memory="datum.used_memory / 0x40000000").encode(axis_x)
    line_mem = base_mem.mark_line().encode(
        gpu_color,
        alt.Y("memory:Q").title(None).scale(alt.Scale(domain=[0, GMEM])),
    )
    points_mem = line_mem.mark_point().encode(opacity=when_near.then(alt.value(1)).otherwise(alt.value(0)))
    rules_mem = (
        base_mem.transform_pivot("gpu_index", value="memory", groupby=["timestamp"])
        .mark_rule()
        .encode(
            opacity=when_near.then(alt.value(0.3)).otherwise(alt.value(0)),
            tooltip=gpu_tooltips,
        )
        .add_params(nearest)
    )
    chart = alt.layer(line_mem, points_mem, rules_mem)
    st.altair_chart(chart, width="stretch")  # pyright: ignore[reportArgumentType]


def render_user_view(start_time, end_time, DB_PATH, axis_x):
    try:
        user_gpu_df = query_user_gpu_realtime_usage(start_time, end_time, DB_PATH)
        user_gpu_memory_df = query_user_gpu_memory_realtime_usage(start_time, end_time, DB_PATH)

        # 处理用户名
        user_gpu_df["user"] = user_gpu_df["user"].apply(lambda x: query_server_username(DB_PATH, x))
        user_gpu_memory_df["user"] = user_gpu_memory_df["user"].apply(lambda x: query_server_username(DB_PATH, x))
    except Exception as e:
        st.error(f"查询用户数据时出现错误：{e}")
        logger.error(f"Error querying user data: {e}")
        return

    gpu_opacity = alt.Opacity("gpu_index:N").title("GPU")
    user_color = alt.Color("user:N").title("用户").scale(range=COLOR_SCHEME)

    st.subheader("用户使用率 %")
    st.altair_chart(
        alt.Chart(user_gpu_df)
        .mark_area()
        .encode(
            user_color,
            gpu_opacity,
            axis_x,
            alt.Y("gpu_utilization:Q").title(None),
        ),
        width="stretch",
    )

    st.subheader("用户显存用量 GB")
    st.altair_chart(
        alt.Chart(user_gpu_memory_df)
        .transform_calculate(memory="datum.used_memory / 0x40000000")
        .mark_area()
        .encode(
            user_color,
            gpu_opacity,
            axis_x,
            alt.Y("memory:Q").title(None),
        ),
        width="stretch",
    )


def render_summary_view(start_time, end_time, DB_PATH, axis_x, PARAMS):
    try:
        gpu_utilization_df = query_gpu_realtime_usage(start_time, end_time, DB_PATH)
        gpu_memory_df = query_gpu_memory_realtime_usage(start_time, end_time, DB_PATH)
    except Exception as e:
        st.error(f"查询汇总数据时出现错误：{e}")
        logger.error(f"Error querying summary data: {e}")
        return

    (N_GPU, GMEM, DURATION, not_pc) = PARAMS
    gpu_color = get_gpu_color(N_GPU, not_pc)

    st.subheader("总使用率 %")
    st.altair_chart(
        alt.Chart(gpu_utilization_df)
        .mark_area()
        .encode(
            gpu_color,
            axis_x,
            alt.Y("gpu_utilization:Q").title(None).scale(alt.Scale(domain=[0, 100 * N_GPU])),
            alt.FillOpacityValue(0.5),
        ),
        width="stretch",
    )

    st.subheader("总显存用量 GB")
    st.altair_chart(
        alt.Chart(gpu_memory_df)
        .transform_calculate(memory="datum.used_memory / 0x40000000")
        .mark_area()
        .encode(
            gpu_color,
            axis_x,
            alt.Y("memory:Q").title(None).scale(alt.Scale(domain=[0, GMEM * N_GPU])),
            alt.FillOpacityValue(0.5),
        ),
        width="stretch",
    )


def webapp_realtime(hostname="Virgo", db_path="data/gpu_history_virgo.db", config={}):
    DB_PATH = db_path
    DURATION = config.get("DURATION", 30)
    N_GPU = config.get("N_GPU", 8)
    GMEM = config.get("GMEM", 48)
    LIMIT = config.get("LIMIT", 1000)

    not_pc = not st.session_state.get("is_session_pc", True)
    if not_pc:
        DURATION = DURATION / 2

    st.html(
        """<style>
        @media (max-width: 640px) { .stColumn { min-width: calc(50% - 1rem); } }
        </style>"""
    )

    st.title(f"{hostname}: 实时状态")

    col1, col2 = st.columns([4, 12], vertical_alignment="center")
    upd_container = col2.empty()

    # 刷新次数计数器
    if "autorefresh" not in st.session_state:
        st.session_state["autorefresh"] = True
    auto_refresh = col1.checkbox("自动刷新", key="autorefresh")
    refresh_interval = 1 if auto_refresh else None

    monitor_key = f"gpu_monitor_count_{hostname}"
    if monitor_key not in st.session_state:
        st.session_state[monitor_key] = 0

    prev_refresh_key = f"prev_autorefresh_{hostname}"
    if auto_refresh and st.session_state.get(prev_refresh_key) is False:
        st.session_state[monitor_key] = 0
    st.session_state[prev_refresh_key] = auto_refresh

    warning_container = st.empty()
    panel_empty = st.empty()
    st.divider()

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

    # === 定义 Fragment ===
    @st.fragment(run_every=refresh_interval)
    def _render_fragment():
        if auto_refresh:
            st.session_state[monitor_key] += 1

        if LIMIT is not None and st.session_state[monitor_key] >= LIMIT:
            st.session_state["autorefresh"] = False
            st.session_state[monitor_key] = -1
            st.rerun()

        if st.session_state[monitor_key] == -1:
            warning_container.warning("标签页长时间未活动，自动刷新已停止：请重新勾选或刷新页面以继续监控。")

        if st.session_state.get(f"_selection_realtime_{hostname}", None) is None:
            st.session_state[f"_selection_realtime_{hostname}"] = "**详细信息**"

        end_time_dt = dt.datetime.now(tz=dt.timezone.utc)
        start_time_dt = end_time_dt - dt.timedelta(seconds=DURATION)
        start_time = start_time_dt.strftime("%Y-%m-%d %H:%M:%S")
        end_time = end_time_dt.strftime("%Y-%m-%d %H:%M:%S")

        try:
            gpu_current_df = query_latest_gpu_info(DB_PATH, end_time)

            check_usage_df = query_gpu_realtime_usage(start_time, end_time, DB_PATH)

        except Exception as e:
            warning_container.error(f"查询数据时出现错误：{e}")
            logger.error(f"Error querying realtime data: {e}")
            return

        if not gpu_current_df.empty:
            current_timestamp = gpu_current_df["timestamp"].max()
            upd_container.write(f"更新于：{current_timestamp}")

        if check_usage_df.empty:
            warning_container.warning(f"过去 {DURATION} 秒内没有 GPU 数据记录：GPU 监控程序可能离线。")
            return

        with panel_empty.container():
            status_panel(gpu_current_df, N_GPU=N_GPU, GMEM=GMEM)

        # 基础图表配置
        axis_end = dt.datetime.now() - dt.timedelta(seconds=1)
        axis_start = axis_end - dt.timedelta(seconds=DURATION)
        axis_x = (
            alt.X("timestamp:T").axis(labelSeparation=10).title(None).scale(alt.Scale(domain=(axis_start, axis_end)))
        )
        PARAMS = (N_GPU, GMEM, DURATION, not_pc)

        # 根据选择渲染不同视图
        if select == "**详细信息**" or select is None:
            render_detail_view(start_time, end_time, DB_PATH, axis_x, PARAMS)
        elif select == "**用户使用**":
            render_user_view(start_time, end_time, DB_PATH, axis_x)
        elif select == "**汇总数据**":
            render_summary_view(start_time, end_time, DB_PATH, axis_x, PARAMS)

    # === 执行 Fragment ===
    _render_fragment()
