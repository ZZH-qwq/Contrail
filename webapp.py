import os
import argparse
import streamlit as st

from dataclasses import dataclass
from loguru import logger
from streamlit_javascript import st_javascript
from user_agents import parse

from contrail.webapp import webapp_realtime, webapp_history, HomePage, load_config


@dataclass
class EnabledFeature:
    ai4s: bool = False
    user_info: bool = False
    name_dict: bool = False
    history_only: bool = False


@dataclass
class PageConfig:
    hostname: str
    realtime_db_path: str = None
    history_db_path: str = None
    config: dict = None

    def __post_init__(self):
        if not self.realtime_db_path:
            self.realtime_db_path = f"data/gpu_info_{self.hostname.lower()}.db"
        if not self.history_db_path:
            self.history_db_path = f"data/gpu_history_{self.hostname.lower()}.db"
        if not self.config:
            raise ValueError("Config must be provided.")


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


def device_pages(devices: dict, features: EnabledFeature):
    pages = {}

    for name, device_config in devices.items():
        pages[name] = []
        if not features.history_only:
            pages[name].append(
                st.Page(
                    DevicePage(webapp_realtime, PageConfig(**device_config), is_realtime=True),
                    title=f"{name} 实时状态",
                    url_path=f"realtime_{name.lower()}",
                )
            )
        pages[name].append(
            st.Page(
                DevicePage(webapp_history, PageConfig(**device_config), is_realtime=False),
                title=f"{name} 历史信息",
                url_path=f"history_{name.lower()}",
            )
        )

    return pages


def feature_pages(features: EnabledFeature):
    pages = {}

    if features.ai4s:
        from contrail.webapp import webapp_ai4s, webapp_fee

        pages["AI4S"] = [
            st.Page(webapp_ai4s, title="AI4S 任务列表", url_path="ai4s"),
            st.Page(webapp_fee, title="AI4S 费用记录", url_path="ai4s_fee"),
        ]

    if features.user_info and features.name_dict:
        from contrail.webapp import webapp_user_info

        pages["Info"] = [
            st.Page(webapp_user_info, title="用户信息查询", url_path="user_info"),
        ]

    return pages


def main():
    st.set_page_config(page_icon="assets/logo/favicon.png")
    st.logo("assets/logo/logo_small.png", size="large")

    config = load_config()

    features = EnabledFeature(**config["features"])
    devices = config["devices"]

    os.environ["ENABLE_NAME_DICT"] = "1" if features.name_dict else "0"

    if os.getenv("CONTRAIL_LOGGER_ADDED", "0") == "0":
        logger.add(
            "log/webapp_{time:YYYY-MM-DD}.log", rotation="00:00", encoding="utf-8", retention="7 days", level="TRACE"
        )
        os.environ["CONTRAIL_LOGGER_ADDED"] = "1"

    pages = {"Home": []}

    pages |= device_pages(devices, features)

    pages |= feature_pages(features)

    pages["Home"].append(st.Page(HomePage(pages), title="Contrail 主页", url_path="home"))

    st.html(
        """<style>
        /* auto-refresh 隐藏 */
        .stElementContainer:has(.stCustomComponentV1),
        .stElementContainer:has(.stHtml) {
            position:absolute !important;
            opacity: 0;
        }
        /* 侧边栏 - 折叠按钮 */
        div[data-testid="stSidebarCollapsedControl"] button {
            margin: -6px 0px -6px -45px;
            padding: 10px 10px 10px 50px;
        }
        /* 主页 - 设备标题 */
        .stColumn:has(a[data-testid="stPageLink-NavLink"]) h3 {
            padding-top: 0px;
        }
        /* 主页 - 设备操作按钮 */
        .stColumn a[data-testid="stPageLink-NavLink"] {
            background-color: #aaa2;
            justify-content: center;
        }
        /* 主页 - column 修改 */
        @media (max-width: 640px) {
            .stColumn:has(a[data-testid="stPageLink-NavLink"]) .stColumn {
                min-width: calc(50% - 1rem);
            }
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
