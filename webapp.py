import os
import argparse
import streamlit as st

from dataclasses import dataclass
from loguru import logger
from streamlit_javascript import st_javascript
from user_agents import parse

from contrail.webapp import webapp_realtime, webapp_history, HomePage
from contrail.utils.config import enabled_features, devices_config, PageConfig


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


def custom_navigate(home, devices, features):
    # if st.button("**Contrail 主页**", use_container_width=True):
    #     st.switch_page(home)
    st.page_link(home, label="**Contrail 主页**", use_container_width=True)

    st.markdown("""<hr style="margin: 10px -10px 10px -10px;">""", unsafe_allow_html=True)
    st.markdown("#### 设备监控")

    for device_name, device_pages in devices.items():
        if enabled_features.history_only:
            st.page_link(device_pages[0], label=device_name, use_container_width=True)
        else:
            with st.popover(device_name, use_container_width=True):
                for page in device_pages:
                    st.page_link(page, label=page.title, use_container_width=True)

    st.markdown("""<hr style="margin: 5px -10px 10px -10px;">""", unsafe_allow_html=True)
    st.markdown("#### 其它功能")

    for feature_name, feature_pages in features.items():
        if len(feature_pages) == 1:
            st.page_link(feature_pages[0], label=feature_pages[0].title, use_container_width=True)
        else:
            with st.popover(feature_name, use_container_width=True):
                for page in feature_pages:
                    st.page_link(page, label=page.title, use_container_width=True)


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

    feature_p = feature_pages()
    pages |= feature_p

    home_p = st.Page(HomePage(pages, device_conf), title="Contrail 主页", url_path="home")
    pages["Home"].append(home_p)

    st.html(
        """<style>
        /* auto-refresh, javascript 隐藏 */
        .stElementContainer:has(.stCustomComponentV1[title="streamlit_autorefresh.st_autorefresh"], .stCustomComponentV1[title="streamlit_javascript.streamlit_javascript"]),
        .stElementContainer:has(.stHtml) {
            position:absolute !important;
            opacity: 0;
        }
        /* 侧边栏 - 宽度限制 */
        section.stSidebar {
            flex-shrink: 0.01 !important;
            max-width: 60vw;
            min-width: 0;
        }
        /* 侧边栏 - 折叠按钮 */
        div[data-testid="stSidebarCollapsedControl"] button {
            margin: -6px 0px -6px -45px;
            padding: 10px 10px 10px 50px;
        }
        /* 自定义导航栏 */
        div[data-testid="stSidebarUserContent"] button[data-testid="stPopoverButton"] {
            background-color: transparent;
            border: none;
            padding: 0;
            min-height: 1.2rem;
            flex-direction: row;
            justify-content: left;
            align-items: flex-start;
            margin-top: -0.375rem;
            margin-bottom: -0.375rem;
        }
        div[data-testid="stSidebarUserContent"] button[data-testid="stPopoverButton"]:hover {
            background-color: light-dark(rgba(151, 166, 195, 0.15), rgba(172, 177, 195, 0.15));
        }
        div[data-testid="stSidebarUserContent"] button[data-testid="stPopoverButton"] > * {
            color: light-dark(rgb(49, 51, 63), rgb(250, 250, 250));
            line-height: 2;
        }
        div[data-testid="stSidebarUserContent"] button[data-testid="stPopoverButton"] > div[data-testid="stMarkdownContainer"] {
            padding-left: 0.5rem;
        }
        /* 弹出菜单边距 */
        div[data-testid="stPopoverBody"] {
            padding: calc(-1px + 1rem) !important;
        }
        </style>"""
    )

    ua_string = st_javascript("""window.navigator.userAgent;""", key="ua_string")
    user_agent = parse(ua_string) if ua_string else None
    st.session_state.is_session_pc = user_agent.is_pc if user_agent else True

    with st.sidebar:
        custom_navigate(home_p, device_p, feature_p)

    pg = st.navigation(pages)
    pg.run()

    st.markdown("""<hr style="margin: 10px 0;">""", unsafe_allow_html=True)

    st.caption(
        """Powered by [**Contrail**<img alt="GitHub Repo stars" src="https://img.shields.io/github/stars/ZZH-qwq/Contrail" height="18" style="margin: -4px 0 0 4px;">](https://github.com/ZZH-qwq/Contrail) / by ZZH-qwq""",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
