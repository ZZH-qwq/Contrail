import streamlit as st
import pandas as pd

from contrail.utils.config import enabled_features, server_users, ai4s_users


@st.cache_data
def filter_user(type: str = "server", input: str = "") -> pd.DataFrame:
    """
    返回筛选后的用户信息
    """
    user_df = server_users if type == "server" else ai4s_users

    if input == "":
        return user_df

    # 模糊匹配
    mask = user_df.apply(lambda row: row.astype(str).str.contains(input, case=False).any(), axis=1)

    return user_df[mask]


def highlight_matches(input, s):
    if input == "":
        return ""
    return "background-color: #FFFF0080" if input.lower() in str(s).lower() else ""


def webapp_user_info():
    """
    用户信息查询页面
    """
    st.title("用户信息查询")

    search_input = st.text_input("输入用户名或信息", "")

    with st.container():
        st.subheader("服务器用户")
        st.dataframe(
            filter_user("server", search_input).style.map(
                lambda s: highlight_matches(search_input, s), subset=pd.IndexSlice[:, :]
            ),
            width="stretch",
        )
    with st.container():
        st.subheader("AI4S")
        st.dataframe(
            filter_user("ai4s", search_input).style.map(
                lambda s: highlight_matches(search_input, s), subset=pd.IndexSlice[:, :]
            ),
            width="stretch",
        )

    with st.expander(""):
        st.caption("我超, 盒!")
