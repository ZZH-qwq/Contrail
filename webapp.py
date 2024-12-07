import os
import argparse
import streamlit as st


parser = argparse.ArgumentParser()
parser.add_argument("--disable_ai4s", action="store_true", help="Disable AI4S monitoring.")
parser.add_argument("--disable_info", action="store_true", help="Disable user information query.")
parser.add_argument("--enable_name_dict", action="store_true", help="Enable name dictionary mapping.")

parser.add_argument("--add_device", type=str, nargs="+", help="List of devices to monitor.", default=["Leo", "Virgo"])
args = parser.parse_args()

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

pg = st.navigation(pages)
pg.run()

st.html("""<hr style="margin-bottom: 0;">""")

st.caption(
    """Powered by [**Contrail**<img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/ZZH-qwq/Contrail" height="18" style="margin: -4px 0 0 4px;">](https://github.com/ZZH-qwq/Contrail) / by ZZH-qwq""",
    unsafe_allow_html=True,
)
