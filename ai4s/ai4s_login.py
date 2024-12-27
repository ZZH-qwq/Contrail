import time
import json
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.options import Options

import argparse
import getpass

parser = argparse.ArgumentParser()
parser.add_argument("--url", type=str, required=True, help="The URL of the target website.")
args = parser.parse_args()

# 设置ChromeDriver
chrome_options = Options()
chrome_options.add_argument("--headless")
service = Service("ai4s/chromedriver")

driver = webdriver.Chrome(service=service, options=chrome_options)

driver.set_window_size(1920, 1080)

# 打开目标网站
url = "http://ai4s.sjtu.edu.cn/"
target_url = args.url
driver.get(url)

try:
    print(driver.title)
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
    body = driver.find_element(By.XPATH, "/html/body")
    body.screenshot("screenshots/body.png")

    # 模拟用户输入
    username_field = driver.find_element(By.CSS_SELECTOR, "#input-login-user")
    password_field = driver.find_element(By.CSS_SELECTOR, "#input-login-pass")
    captcha_field = driver.find_element(By.CSS_SELECTOR, "#input-login-captcha")

    username = input("Please input the username: ")
    password = getpass.getpass("Please input the password: ")

    if username != "":
        # 保存验证码图片
        captcha_img = driver.find_element(By.XPATH, '//*[@id="captcha-img"]')
        captcha_img.screenshot("screenshots/captcha.png")
        body = driver.find_element(By.XPATH, "/html/body")
        body.screenshot("screenshots/body.png")

        captcha_text = input("Please input the captcha text: ")

        # Fill the captcha input with input
        captcha_field.send_keys(captcha_text)

        username_field.send_keys(username)
        password_field.send_keys(password)
        password_field.send_keys(Keys.RETURN)

        time.sleep(1)

    body = driver.find_element(By.XPATH, "/html/body")
    body.screenshot("screenshots/body.png")
    _ = input("If needed, scan the QR code and press Enter to continue...")

    body = driver.find_element(By.XPATH, "/html/body")
    body.screenshot("screenshots/body.png")
    _ = input("Press Enter to continue...")

    aiplatform = driver.find_element(By.CSS_SELECTOR, ".index_portal_link__IHdQ3")
    aiplatform.click()
    time.sleep(0.5)

    driver.get(target_url)
    time.sleep(2)

    body = driver.find_element(By.XPATH, "/html/body")
    body.screenshot("screenshots/body.png")
    _ = input("Press Enter to continue...")

    # save the cookies to json file
    cookies = driver.get_cookies()
    for cookie in cookies:
        # Set the cookie to expire in 365 days
        cookie["expiry"] = int(time.time()) + 365 * 24 * 60 * 60
        driver.add_cookie(cookie)

    with open("data/cookies.txt", "w") as file:
        file.write(json.dumps(cookies))

finally:
    # 关闭浏览器
    driver.quit()
