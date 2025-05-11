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

parser.add_argument("--history_only", action="store_true", help="Only show history pages.")
args = parser.parse_args()

os.environ["ENABLE_NAME_DICT"] = "1" if args.enable_name_dict else "0"

if os.getenv("CONTRAIL_LOGGER_ADDED", "0") == "0":
    logger.add(
        "log/webapp_{time:YYYY-MM-DD}.log", rotation="00:00", encoding="utf-8", retention="7 days", level="TRACE"
    )
    os.environ["CONTRAIL_LOGGER_ADDED"] = "1"


st.set_page_config(page_icon="assets/logo/favicon.png")
st.logo("assets/logo/logo_small.png", size="large")

pages = {}

for name in args.add_device:
    pages[name] = []
    if not args.history_only:
        pages[name].append(st.Page(f"nodes/realtime_{name.lower()}.py", title=f"{name}: 实时状态"))
    pages[name].append(st.Page(f"nodes/history_{name.lower()}.py", title=f"{name}: 历史信息"))

if not args.disable_ai4s:
    from contrail.webapp import webapp_ai4s, webapp_fee

    pages["AI4S"] = [
        st.Page(webapp_ai4s, title="AI4S: 任务列表", url_path="ai4s"),
        st.Page(webapp_fee, title="AI4S: 费用记录", url_path="ai4s_fee"),
    ]

if not args.disable_info and args.enable_name_dict:
    from contrail.webapp import webapp_user_info

    pages["Info"] = [
        st.Page(webapp_user_info, title="用户信息查询", url_path="user_info"),
    ]


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
