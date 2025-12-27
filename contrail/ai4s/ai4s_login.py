"""Interactive login helper that stores cookies using config-defined URLs and paths."""

import sys
import json
import time
import getpass
from pathlib import Path

from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from contrail.ai4s.config import Ai4sConfig
from contrail.ai4s.base import take_screenshot


def login_and_save_cookies(config_path: Path | None = None) -> None:
    config = Ai4sConfig.load(config_path)
    config.ensure_directories()

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    service = Service(str(config.paths.chromedriver_path))

    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_window_size(1920, 1080)

    login_entry = config.cookie.login_entry
    cookie_target = config.cookie.cookie_url
    screenshot_dir = config.paths.screenshot_path
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Open {screenshot_dir}/login.png to view the login process")

    def snap() -> None:
        take_screenshot(driver, f"login", screenshot_dir, enabled=True)

    driver.get(login_entry)

    try:
        logger.info(f"Opened login page: {driver.title}")
        time.sleep(0.5)

        # 查找登录按钮并点击
        login_button = driver.find_element(By.CSS_SELECTOR, ".index_portal_action__glZy6")
        login_button.click()
        time.sleep(0.5)

        login_button = driver.find_element(By.CSS_SELECTOR, ".index_login_body__-f1e7 button")
        login_button.click()

        # switch to login tab
        driver.switch_to.window(driver.window_handles[-1])
        time.sleep(0.5)
        snap()

        # 模拟用户输入
        username_field = driver.find_element(By.CSS_SELECTOR, "#input-login-user")
        password_field = driver.find_element(By.CSS_SELECTOR, "#input-login-pass")
        captcha_field = driver.find_element(By.CSS_SELECTOR, "#input-login-captcha")

        username = input("Please input the username: ")
        password = getpass.getpass("Please input the password: ")

        if username != "":
            # 保存验证码图片
            captcha_img = driver.find_element(By.XPATH, '//*[@id="captcha-img"]')
            captcha_img.screenshot(str(screenshot_dir / "captcha.png"))
            snap()

            captcha_text = input("Please input the captcha text: ")

            # Fill the captcha input with input
            captcha_field.send_keys(captcha_text)

            username_field.send_keys(username)
            password_field.send_keys(password)
            password_field.send_keys(Keys.RETURN)

            time.sleep(1)

        snap()
        _ = input("If needed, scan the QR code and press Enter to continue...")

        snap()
        _ = input("Press Enter to continue...")

        aiplatform = driver.find_element(By.CSS_SELECTOR, ".index_portal_link__IHdQ3")
        aiplatform.click()
        time.sleep(0.5)

        driver.get(cookie_target)
        time.sleep(2)

        snap()
        _ = input("Press Enter to continue...")

        # save the cookies to json file
        cookies = driver.get_cookies()
        for cookie in cookies:
            # Set the cookie to expire in 365 days
            cookie["expiry"] = int(time.time()) + 365 * 24 * 60 * 60
            driver.add_cookie(cookie)

        cookie_path = config.cookie.cookie_path
        cookie_path.write_text(json.dumps(cookies), encoding="utf-8")
        logger.info(f"Saved cookies to {cookie_path}")

    finally:
        driver.quit()


if __name__ == "__main__":
    # loguru let stdout logger only show info level and above
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    login_and_save_cookies()
