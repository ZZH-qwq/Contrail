import datetime as dt

import streamlit as st


def render_update_time(updated_at: dt.datetime | None, show_delta: bool = True, show_warning: bool = True):
    """
    显示更新时间信息。
    """
    if updated_at is None:
        if show_warning:
            st.write("未找到记录")
        return

    formatted_time = updated_at.strftime("%Y-%m-%d %H:%M:%S")
    if show_delta:
        now = dt.datetime.now(updated_at.tzinfo)
        delta_minutes = (now - updated_at).total_seconds() // 60
        st.write(f"更新于 {formatted_time} / {delta_minutes:.0f} 分钟前")
    else:
        st.write(f"更新于 {formatted_time}")
