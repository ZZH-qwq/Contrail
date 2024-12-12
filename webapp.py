import os
import argparse
import streamlit as st

from loguru import logger
from streamlit_javascript import st_javascript
from user_agents import parse


parser = argparse.ArgumentParser()
parser.add_argument("--disable_ai4s", action="store_true", help="Disable AI4S monitoring.")
parser.add_argument("--disable_info", action="store_true", help="Disable user information query.")
parser.add_argument("--enable_name_dict", action="store_true", help="Enable name dictionary mapping.")

parser.add_argument("--add_device", type=str, nargs="+", help="List of devices to monitor.", default=["Leo", "Virgo"])
args = parser.parse_args()

logger.add("log/webapp_{time:YYYY-MM-DD}.log", rotation="00:00", encoding="utf-8", retention="7 days", level="INFO")

pages = {}

for name in args.add_device:
    pages[name] = [
        st.Page(f"webapp/realtime_{name.lower()}.py", title=f"{name}: 实时状态"),
        st.Page(f"webapp/history_{name.lower()}.py", title=f"{name}: 历史信息"),
    ]

if not args.disable_ai4s:
    pages["AI4S"] = [
        st.Page("webapp/ai4s_tasks.py", title="AI4S: 任务列表"),
        st.Page("webapp/fee.py", title="AI4S: 费用记录"),
    ]

if not args.disable_info and args.enable_name_dict:
    pages["Info"] = [
        st.Page("webapp/user_info.py", title="用户信息查询"),
    ]

os.environ["ENABLE_NAME_DICT"] = "1" if args.enable_name_dict else "0"


st.set_page_config(page_icon="assets/logo/favicon.png")
st.logo("assets/logo/logo_small.png", size="large")

st.html(
    """<style>
    .stElementContainer:has(.stCustomComponentV1),
    .stElementContainer:has(.stHtml) {
        position:absolute !important;
        opacity: 0;
    }
    div[data-testid="stSidebarCollapsedControl"] button {
        margin: -6px 0px -6px -45px;
        padding: 10px 10px 10px 50px;
    }
    </style>"""
)

ua_string = st_javascript("""window.navigator.userAgent;""", key="ua_string")
user_agent = parse(ua_string) if ua_string else None
st.session_state.is_session_pc = user_agent.is_pc if user_agent else True

pg = st.navigation(pages)
pg.run()

st.markdown("""<hr style="margin: 10px 0;">""", unsafe_allow_html=True)

st.caption(
    """Powered by [**Contrail**<img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/ZZH-qwq/Contrail" height="18" style="margin: -4px 0 0 4px;">](https://github.com/ZZH-qwq/Contrail) / by ZZH-qwq""",
    unsafe_allow_html=True,
)
