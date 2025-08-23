import os
import argparse
import streamlit as st

from dataclasses import dataclass
from loguru import logger
from streamlit_javascript import st_javascript
from user_agents import parse

from contrail.webapp import webapp_realtime, webapp_history, HomePage
from contrail.utils import enabled_features, devices_config, PageConfig


class DevicePage:
    def __init__(self, func, config: PageConfig, is_realtime: bool):
        self.func = func
        self.config = config
        self.is_realtime = is_realtime
        self._db_path = config.realtime_db_path if is_realtime else config.history_db_path
        name_prefix = "realtime" if is_realtime else "history"
        self.__name__ = f"{name_prefix}_{self.config.hostname.lower()}"

    def __call__(self):
        self.func(
            hostname=self.config.hostname,
            db_path=self._db_path,
            config=self.config.config,
        )


def device_pages():
    pages = {}
    configs = {}

    for name, device_config in devices_config.items():
        pages[name] = []
        configs[name] = PageConfig(**device_config)
        if not enabled_features.history_only:
            pages[name].append(
                st.Page(
                    DevicePage(webapp_realtime, configs[name], is_realtime=True),
                    title=f"{name} 实时状态",
                    url_path=f"realtime_{name.lower()}",
                )
            )
        pages[name].append(
            st.Page(
                DevicePage(webapp_history, configs[name], is_realtime=False),
                title=f"{name} 历史信息",
                url_path=f"history_{name.lower()}",
            )
        )

    return pages, configs


def feature_pages():
    pages = {}

    if enabled_features.ai4s:
        from contrail.webapp.ai4s_tasks import webapp_ai4s
        from contrail.webapp.fee import webapp_fee

        pages["AI4S"] = [
            st.Page(webapp_ai4s, title="AI4S 任务列表", url_path="ai4s"),
            st.Page(webapp_fee, title="AI4S 费用记录", url_path="ai4s_fee"),
        ]

    if enabled_features.user_info and enabled_features.name_dict:
        from contrail.webapp.user_info import webapp_user_info

        pages["Info"] = [
            st.Page(webapp_user_info, title="用户信息查询", url_path="user_info"),
        ]

    return pages


def main():
    st.set_page_config(page_icon="assets/logo/favicon.png")
    st.logo("assets/logo/logo_small.png", size="large")

    if os.getenv("CONTRAIL_LOGGER_ADDED", "0") == "0":
        logger.add(
            "log/webapp_{time:YYYY-MM-DD}.log", rotation="00:00", encoding="utf-8", retention="7 days", level="TRACE"
        )
        os.environ["CONTRAIL_LOGGER_ADDED"] = "1"

    pages = {"Home": []}

    device_p, device_conf = device_pages()
    pages |= device_p

    pages |= feature_pages()

    pages["Home"].append(st.Page(HomePage(pages, device_conf), title="Contrail 主页", url_path="home"))

    st.html(
        """<style>
        /* auto-refresh, javascript 隐藏 */
        .stElementContainer:has(.stCustomComponentV1[title="streamlit_autorefresh.st_autorefresh"], .stCustomComponentV1[title="streamlit_javascript.streamlit_javascript"]),
        .stElementContainer:has(.stHtml) {
            position:absolute !important;
            opacity: 0;
        }
        /* 侧边栏 - 折叠按钮 */
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


if __name__ == "__main__":
    main()
