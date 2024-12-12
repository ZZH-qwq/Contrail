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


def handle_row(driver, row):
    logger.trace("Handling row")
    task = {}

    assert driver.current_url.find("notebook/org") != -1, "Not in the correct page"
    curr_tab = driver.current_window_handle

    try:

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
        logger.info(f"Task: {task_name}, User: {user}")
        logger.info(f"Resource: {resource}")

        view_button = row.find_element(By.CSS_SELECTOR, "td:last-child > div > .table-action:nth-child(1)")
        view_button.send_keys(Keys.CONTROL + Keys.RETURN)
        driver.switch_to.window(driver.window_handles[-1])

        # 检测是否是正确的页面
        idx = -1
        timestamp = time.time()
        while (
            driver.current_url.find("notebook/detail") == -1
            and idx > -1 * len(driver.window_handles)
            and (time.time() - timestamp) < 10
        ):
            idx -= 1
            driver.switch_to.window(driver.window_handles[idx])

        if driver.current_url.find("notebook/detail") == -1:
            logger.warning("Page navigation failed")
            return None

        # 清除控制台日志
        driver.execute_script("console.clear();")
        time.sleep(0.5)

        json_data = check_respond(driver)
        if json_data:
            task["data"] = json_data

        # 获取开始时间
        start_time = driver.find_element(
            By.CSS_SELECTOR,
            ".mf-notebook-detail-box.aibp-detail-container div.ant-spin-container > div > div .aibp-detail-section:nth-child(1) .du-gridview > .du-gridview-row:nth-child(2) > .ant-col.ant-col-8:nth-child(1) div.du-gridview-row-content",
        ).text
        task["start_time"] = start_time

        # driver.switch_to.window(driver.window_handles[-1])
        # idx = -1
        # while driver.current_url.find("notebook/org") == -1 and idx > -1 * len(driver.window_handles):
        #     idx -= 1
        #     driver.switch_to.window(driver.window_handles[idx])

    except Exception as e:
        logger.error(f"Error handling row: {e}")
        return None

    finally:
        if len(driver.window_handles) > 1 and driver.current_url.find("notebook/detail") != -1:
            driver.close()
        driver.switch_to.window(curr_tab)

    screenshot(driver)

    return task


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
                # 获取响应的内容（数据），通过 requestId ��调用 getResponseBody
                request_id = log["params"]["requestId"]

                # 使用 DevTools 获取响应体
                response_body = driver.execute_cdp_cmd("Network.getResponseBody", {"requestId": request_id})
                body_data = response_body.get("body", "")

                if response_body:
                    try:
                        # 将解码后的字符串转换为 JSON 格式
                        json_data = json.loads(body_data)

                        query_string = json_data["results"]["A"]["frames"][0]["schema"]["meta"]["executedQueryString"]

                        if "container_accelerator_duty_cycle" in query_string:
                            data["accelerator_duty_cycle"] = json_data["results"]["A"]["frames"][0]["data"]
                        elif "container_accelerator_memory_used_bytes" in query_string:
                            data["accelerator_memory_used_bytes"] = json_data["results"]["A"]["frames"][0]["data"]
                        else:
                            continue

                        if "accelerator_duty_cycle" in data and "accelerator_memory_used_bytes" in data:
                            return data

                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing JSON data: {e}")

        time.sleep(0.5)

    return None


def execute(target_url):
    logger.info("Executing main function")
    # 设置ChromeDriver
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--enable-logging")
    chrome_options.add_argument("--auto-open-devtools-for-tabs")
    service = Service("ai4s/chromedriver")

    # 启用 Performance Logging
    chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    driver = webdriver.Chrome(service=service, options=chrome_options)

    driver.set_window_size(1920, 2333)

    # 读取并修改Cookie的到期时间
    with open(COOKIE_FILE, "r") as file:
        cookies = json.loads(file.read())

    # 修改Cookie的到期时间为当前时间 + 30 天
    new_expiry_time = int(time.time()) + 86400 * 30
    for cookie in cookies:
        if "expiry" in cookie:
            cookie["expires"] = new_expiry_time

    try:
        # 打开目标网站以初始化session
        driver.get("http://aiplatform.ai4s.sjtu.edu.cn/")
        time.sleep(0.5)  # 等待页面加载

        # 添加Cookie到浏览器
        for cookie in cookies:
            driver.add_cookie(cookie)

        # 再次访问目标网站
        driver.get(target_url)
        time.sleep(2)  # 等待页面加载完成

        # 检查加载结果
        logger.info(f"Page title: {driver.title}")
        logger.info(f"Current URL: {driver.current_url}")

        screenshot(driver)
        if driver.current_url.find("login?projectType=NORMAL") != -1:
            logger.error("Login failed")
            raise Exception("登录失败，请检查Cookie是否过期！")

        logger.info("Login successful")

        # 设置筛选条件
        set_filter(driver)

        # 如果 .mf-notebook-list .ant-table-default .ant-table-placeholder 存在，则说明没有数据
        if driver.find_elements(By.CSS_SELECTOR, ".mf-notebook-list .ant-table-default .ant-table-placeholder"):
            logger.info("No data found")
            return {"state": "failed"}

        else:
            data = {"state": "success"}
            rows = driver.find_elements(By.CSS_SELECTOR, ".mf-notebook-list .ant-table-tbody .ant-table-row-level-0")

            for i, row in enumerate(rows):
                task = handle_row(driver, row)
                data[i] = task

                if task is None or "data" not in task:
                    data["state"] = "failed"

            # for row in rows:
            #     close_row(driver, row)

            return data

    except Exception as e:
        logger.error(f"Error executing main function: {e}")
        return None

    finally:
        logger.trace("Closing browser")
        # 关闭浏览器
        driver.quit()


def job(target_url):
    logger.info("Starting job")
    data = execute(target_url)
    if data is not None:
        with open("data/ai4s_data.json", "w") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        if data["state"] == "success":
            with open("data/ai4s_data_last_success.json", "w") as file:
                json.dump(data, file, ensure_ascii=False, indent=4)
    logger.info(f"Job completed at {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())} with state: {data['state']}")


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
        # job(args.url)

        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Program exited")
        exit(0)
