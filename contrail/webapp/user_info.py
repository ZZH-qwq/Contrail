import streamlit as st
import pandas as pd

from contrail.utils.name_dict import NAME_DICT_FEE, dict_username


@st.cache_data
def convert_dict_to_df(dict_data):
    """
    将字典转换为 DataFrame。
    """
    df = pd.DataFrame.from_dict(dict_data, orient="index", columns=["用户信息"])
    df.index.name = "用户名"
    return df


@st.cache_data
def search_user(hostname, input=""):
    """
    查询用户信息。
    """
    dict_host = {
        "leo": dict_username("leo.db"),
        "virgo": dict_username("virgo.db"),
        "ai4s": NAME_DICT_FEE,
    }
    user_df = pd.DataFrame.from_dict(dict_host[hostname], orient="index", columns=["用户信息"])
    user_df.index.name = "用户名"

    if input == "":
        return user_df

    # search in both index and column
    mask = user_df.index.str.contains(input, case=False)
    mask |= user_df["用户信息"].str.contains(input, case=False)

    return user_df[mask]


def webapp_user_info():
    """
    用户信息查询页面
    """
    st.title("用户信息查询")

    search_input = st.text_input("输入用户名或信息", "")

    leo, virgo, ai4s = st.columns(3)

    with leo:
        st.subheader("Leo")
        st.dataframe(search_user("leo", search_input), width=500)
    with virgo:
        st.subheader("Virgo")
        st.dataframe(search_user("virgo", search_input), width=500)
    with ai4s:
        st.subheader("AI4S")
        st.dataframe(search_user("ai4s", search_input), width=500)

    with st.expander(""):
        st.caption("我超, 盒!")
