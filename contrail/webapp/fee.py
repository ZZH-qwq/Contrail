import streamlit as st
import plotly.express as px

from ai4s.fee_extractor import *


def webapp_fee():
    """
    费用记录页面
    """
    DB_PATH = "data/fee.db"

    st.title("AI4S: 费用记录")

    min_date, max_date = query_min_max_date(DB_PATH, "fee_data")

    # call back function -> runs BEFORE the rest of the app
    def reset_button():
        st.session_state["fee_start_date"] = min_date
        st.session_state["fee_end_date"] = max_date
        return

    # 日期范围选择
    col1, col2, reset = st.columns([5, 5, 2], vertical_alignment="bottom")

    start_date = col1.date_input("开始日期", value=min_date, key="fee_start_date")
    end_date = col2.date_input("结束日期", value=max_date, key="fee_end_date")

    reset.button("重置", use_container_width=True, on_click=reset_button)

    # 确保用户输入的时间范围有效
    if start_date >= end_date:
        st.error("结束日期必须晚于开始日期！")
    else:
        # 查询数据库
        start_time = start_date.strftime("%Y-%m-%d")
        end_time = end_date.strftime("%Y-%m-%d")

        # 显示结果
        total_cost = query_total_cost_by_date_range(DB_PATH, "fee_data", start_time, end_time)
        st.subheader(f"总费用：{total_cost:.0f} 元")
        st.write(f"查询范围：{start_time} 至 {end_time}")

        period, user = st.tabs(["按时间查询", "按用户查询"])

        df = query_cost_by_date_range(DB_PATH, "fee_data", start_time, end_time)

        if not df.empty:
            fig = px.bar(
                df,
                x="资源使用人员",
                y="总消费金额",
                hover_data="任务数量",
                title="费用与任务数量统计",
                labels={"总消费金额": "总金额 (元)"},
            )
            user.plotly_chart(fig)
            user.subheader("详细统计")
            user.dataframe(df)  # 显示结果表格
        else:
            user.warning("该日期范围内没有记录。")

        duration_days = (end_date - start_date).days
        group_by = "month" if duration_days > 60 else "day"
        df = query_cost_by_day_or_month(DB_PATH, "fee_data", start_time, end_time, group_by)

        if not df.empty:
            fig = px.bar(
                df,
                x="月份" if group_by == "month" else "日期",
                y="总消费金额",
                color="资源使用人员",
                hover_data="任务数量",
                barmode="stack",
                title="费用与任务数量统计",
                labels={"总消费金额": "总金额 (元)"},
            )
            period.plotly_chart(fig)
            period.subheader("详细统计")
            period.dataframe(df)
