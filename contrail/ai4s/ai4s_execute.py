from loguru import logger
import json
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options
import schedule

# Cookie文件路径
COOKIE_FILE = "data/cookies.txt"


def screenshot(driver, filename="screenshots/body.png"):
    # logger.trace(f"Taking screenshot: {filename}")
    # body = driver.find_element(By.XPATH, "/html/body")
    # body.screenshot(filename)
    pass


def set_filter(driver):
    logger.trace("Setting filter")
    filter_input = None

    try:
        filter_input = driver.find_element(
            By.CSS_SELECTOR,
            ".mf-notebook-list > .du-listpage-toolbar > .aibp-notebook-search-form > .ant-row > .ant-col.ant-col-24:nth-child(1) > .ant-row-flex > .ant-col.ant-col-8:nth-child(2) .ant-select-selection--multiple .ant-select-selection__placeholder",
        )
        screenshot(driver)
    except Exception as e:
        logger.error(f"Error setting filter: {e}")
        time.sleep(0.5)

    filter_input.click()
    time.sleep(0.5)

    screenshot(driver)

    select_item = driver.find_element(
        By.CSS_SELECTOR,
        ".ant-select-dropdown.ant-select-dropdown--multiple.ant-select-dropdown-placement-bottomLeft ul.ant-select-dropdown-menu.ant-select-dropdown-menu-root.ant-select-dropdown-menu-vertical > li.ant-select-dropdown-menu-item:nth-child(3)",
    )
    select_item.click()
    time.sleep(0.5)

    screenshot(driver)

    confirm_button = driver.find_element(
        By.CSS_SELECTOR,
        ".mf-notebook-list > .du-listpage-toolbar > .aibp-notebook-search-form > .ant-row > .ant-col.ant-col-24:nth-child(2) > .ant-row-flex > .ant-col.ant-col-8:nth-child(3) > .ant-form-item > .ant-col-offset-6 .button-info > .ant-btn:nth-child(1)",
    )
    confirm_button.click()
    time.sleep(0.5)

    screenshot(driver)


def close_row(driver, row):
    logger.trace("Closing row")
    try:
        close_button = row.find_element(By.CSS_SELECTOR, "td:last-child > div > .table-action:nth-child(4)")
        close_button.click()
        time.sleep(1)

        screenshot(driver)

        confirm_button = driver.find_element(
            By.CSS_SELECTOR, ".ant-modal-confirm-btns > button.ant-btn.ant-btn-primary"
        )
        confirm_button.click()
        time.sleep(0.5)
    except Exception as e:
        logger.error(f"Error closing row: {e}")


def check_respond(driver, timeout=10):
    logger.trace("Checking response")
    data = {}

    start_time = time.time()
    while (time.time() - start_time) < timeout:
        try:
            screenshot(driver)

            logs = driver.get_log("performance")
            for entry in logs:
                log = json.loads(entry["message"])["message"]

                if log["method"] != "Network.responseReceived":
                    continue

                response = log["params"]["response"]
                url = response["url"]
                content_type = response["mimeType"]

                # 筛选出目标请求：URL 和内容类型匹配
                if "monitor/api/ds/query" in url and "application/json" in content_type:
                    # 获取响应的内容（数据），通过 requestId 调用 getResponseBody
                    request_id = log["params"]["requestId"]

                    # 使用 DevTools 获取响应体
                    try:
                        response_body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                        body_data = response_body.get("body", "")

                        if response_body:
                            try:
                                # 将解码后的字符串转换为 JSON 格式
                                json_data = json.loads(body_data)

                                query_string = json_data["results"]["A"]["frames"][0]["schema"]["meta"][
                                    "executedQueryString"
                                ]

                                if "container_accelerator_duty_cycle" in query_string:
                                    data["accelerator_duty_cycle"] = json_data["results"]["A"]["frames"][0]["data"]
                                elif "container_accelerator_memory_used_bytes" in query_string:
                                    data["accelerator_memory_used_bytes"] = json_data["results"]["A"]["frames"][0][
                                        "data"
                                    ]
                                else:
                                    continue

                                if "accelerator_duty_cycle" in data and "accelerator_memory_used_bytes" in data:
                                    return data

                            except json.JSONDecodeError as e:
                                logger.error(f"Error parsing JSON data: {e}")
                    except Exception as e:
                        logger.error(f"Error getting response body: {e}")
                        continue

        except Exception as e:
            logger.error(f"Error checking response, session may be invalid: {e}")
            return None

        time.sleep(0.5)

    return None


class WebDriverManager:
    def __init__(self, target_url):
        self.target_url = target_url
        self.driver = None
        self.chrome_options = None
        self.service = None
        self._setup_options()

    def _setup_options(self):
        """设置Chrome选项"""
        self.chrome_options = Options()
        self.chrome_options.add_argument("--headless")
        self.chrome_options.add_argument("--enable-logging")
        self.chrome_options.add_argument("--auto-open-devtools-for-tabs")

        self.service = Service("resource/chromedriver")

        # 启用 Performance Logging
        self.chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    def _create_driver(self, retries=2):
        """创建新的WebDriver实例，带重试逻辑"""
        logger.info("Creating new WebDriver instance")
        last_exception = None
        for attempt in range(1, retries + 1):
            try:
                if self.driver:
                    try:
                        self.driver.quit()
                    except Exception:
                        pass

                self.driver = webdriver.Chrome(service=self.service, options=self.chrome_options)
                self.driver.set_window_size(1920, 2333)
                logger.info(f"WebDriver created successfully on attempt {attempt}")
                return True
            except Exception as e:
                logger.error(f"Failed to create WebDriver on attempt {attempt}: {e}")
                last_exception = e
                time.sleep(1)
        logger.error(f"All {retries} attempts to create WebDriver failed: {last_exception}")
        return False

    def _login(self):
        """执行登录流程"""
        try:
            # 读取并修改Cookie的到期时间
            with open(COOKIE_FILE, "r") as file:
                cookies = json.loads(file.read())

            # 修改Cookie的到期时间为当前时间 + 30 天
            new_expiry_time = int(time.time()) + 86400 * 30
            for cookie in cookies:
                if "expiry" in cookie:
                    cookie["expires"] = new_expiry_time

            # 打开目标网站以初始化session
            self.driver.get("http://aiplatform.ai4s.sjtu.edu.cn/")
            time.sleep(0.5)

            # 添加Cookie到浏览器
            for cookie in cookies:
                self.driver.add_cookie(cookie)

            # 再次访问目标网站
            self.driver.get(self.target_url)
            time.sleep(2)

            # 检查登录状态
            logger.info(f"Page title: {self.driver.title}")
            logger.info(f"Current URL: {self.driver.current_url}")

            if self.driver.current_url.find("login?projectType=NORMAL") != -1:
                logger.error("Login failed")
                return False

            logger.info("Login successful")
            return True
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    def is_session_valid(self):
        """检查WebDriver会话是否有效"""
        if not self.driver:
            return False
        try:
            # 尝试获取当前URL
            _ = self.driver.current_url
            return True
        except Exception as e:
            if "invalid session id" in str(e) or "session deleted" in str(e):
                return False
            return True

    def ensure_session(self):
        """确保会话有效，如果无效则重新创建"""
        if not self.is_session_valid():
            logger.warning("WebDriver session is invalid, recreating...")
            if self._create_driver() and self._login():
                # 重新设置筛选条件
                try:
                    set_filter(self.driver)
                    return True
                except Exception as e:
                    logger.error(f"Failed to set filter after session recreation: {e}")
                    return False
            return False
        return True

    def get_driver(self):
        """获取有效的WebDriver实例"""
        if self.ensure_session():
            return self.driver
        return None

    def close(self):
        """安全关闭WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
        self.driver = None


def collect_task_basic_info(driver, row):
    """收集任务的基本信息和详情页链接"""
    try:
        task = {}

        task_name = row.find_element(By.CSS_SELECTOR, "td:nth-child(2)").text
        task["task_name"] = task_name

        active_time = row.find_element(By.CSS_SELECTOR, "td:nth-child(5)").text
        task["active_time"] = active_time

        resource = row.find_element(By.CSS_SELECTOR, "td:nth-child(6)").text.replace("\n", " ")
        task["cpus"] = resource.split(" ")[0].split("：")[1]
        task["gpu_type"] = resource.split("：")[2].split(" / ")[0]
        task["gpu_count"] = resource.split(" / ")[1].split(" ")[0]
        task["memory"] = resource.split("：")[3]

        user = row.find_element(By.CSS_SELECTOR, "td:nth-last-child(2)").text
        task["user"] = user

        # 获取详情页链接
        view_button = row.find_element(By.CSS_SELECTOR, "td:last-child > div > .table-action:nth-child(1)")
        detail_link = view_button.get_attribute("href")
        task["detail_link"] = detail_link

        logger.info(f"Collected basic info for task: {task_name}, User: {user}")
        logger.info(f"Resource: {resource}")

        return task
    except Exception as e:
        logger.error(f"Error collecting basic task info: {e}")
        return None


def get_task_detail_info(driver_manager, task):
    """获取任务的详细信息（开始时间和性能数据）"""
    if not task or not task.get("detail_link"):
        return task

    try:
        driver = driver_manager.get_driver()
        if not driver:
            logger.error("No valid driver available for detail collection")
            return task

        # 导航到详情页
        driver.get(task["detail_link"])
        time.sleep(2)
        screenshot(driver)

        # 获取开始时间
        try:
            start_time = driver.find_element(
                By.CSS_SELECTOR,
                ".mf-notebook-detail-box.aibp-detail-container div.ant-spin-container > div > div .aibp-detail-section:nth-child(1) .du-gridview > .du-gridview-row:nth-child(2) > .ant-col.ant-col-8:nth-child(1) div.du-gridview-row-content",
            ).text
            task["start_time"] = start_time
        except Exception as e:
            logger.warning(f"Failed to get start_time for {task['task_name']}: {e}")
            task["start_time"] = "N/A"

        # 获取性能数据
        try:
            driver.execute_script("console.clear();")
            time.sleep(0.5)
            json_data = check_respond(driver)
            if json_data:
                task["data"] = json_data
                logger.info(f"Successfully collected performance data for {task['task_name']}")
            else:
                logger.warning(f"No performance data found for {task['task_name']}")
        except Exception as e:
            logger.warning(f"Failed to get performance data for {task['task_name']}: {e}")

        return task

    except Exception as e:
        logger.error(f"Error getting task detail info for {task.get('task_name', 'unknown')}: {e}")
        return task


def execute(target_url):
    logger.info("Executing main function with two-phase processing to preserve filter state")

    # 创建WebDriver管理器
    driver_manager = WebDriverManager(target_url)

    try:
        # 初始化WebDriver和登录
        if not driver_manager._create_driver():
            logger.error("Failed to create initial WebDriver")
            return None

        if not driver_manager._login():
            logger.error("Failed to login")
            return None

        # 设置筛选条件
        driver = driver_manager.get_driver()
        if not driver:
            return None

        set_filter(driver)

        # 检查是否有数据
        if driver.find_elements(By.CSS_SELECTOR, ".mf-notebook-list .ant-table-default .ant-table-placeholder"):
            logger.info("No data found")
            return {"state": "success"}

        # 第一阶段：收集所有任务的基本信息和详情页链接
        logger.info("Phase 1: Collecting basic information for all tasks")
        rows = driver.find_elements(By.CSS_SELECTOR, ".mf-notebook-list .ant-table-tbody .ant-table-row-level-0")
        tasks_basic_info = []

        for i, row in enumerate(rows):
            logger.info(f"Collecting basic info for row {i + 1}/{len(rows)}")

            # 收集基本信息
            task_info = collect_task_basic_info(driver, row)
            if task_info:
                tasks_basic_info.append((i, task_info))
            else:
                logger.warning(f"Failed to collect basic info for row {i}")

            time.sleep(0.5)

        logger.info(f"Phase 1 completed: collected {len(tasks_basic_info)} tasks")

        # 第二阶段：获取每个任务的详细信息
        logger.info("Phase 2: Collecting detailed information for each task")
        data = {"state": "success"}

        for i, task_info in tasks_basic_info:
            logger.info(f"Getting details for task {i + 1}/{len(tasks_basic_info)}: {task_info['task_name']}")

            # 获取详细信息
            complete_task = get_task_detail_info(driver_manager, task_info)
            data[i] = complete_task

            if complete_task is None or "data" not in complete_task:
                data["state"] = "failed"
                logger.warning(f"Failed to get complete data for task: {task_info['task_name']}")

        logger.info(f"Phase 2 completed: processed {len(tasks_basic_info)} tasks")
        return data

    except Exception as e:
        logger.error(f"Error executing main function: {e}")
        return None

    finally:
        driver_manager.close()


def job(target_url):
    logger.info("Starting job")
    data = execute(target_url)
    if data is not None:
        with open("data/ai4s_data.json", "w") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        if data["state"] == "success":
            with open("data/ai4s_data_last_success.json", "w") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
        logger.info(
            f"Job completed at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} with state: {data['state']}"
        )
    else:
        logger.error(f"Job failed at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--url", type=str, required=True, help="The target URL")
    parser.add_argument("--interval", type=int, default=5, help="The interval in minutes")
    args = parser.parse_args()

    logger.add("log/ai4s_execute_{time:YYYY-MM-DD}.log", rotation="00:00", retention="7 days", level="TRACE")
    logger.info("Starting scheduled job")
    schedule.every(args.interval).minutes.do(job, args.url)

    try:
        job(args.url)

        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Program exited")
        exit(0)
