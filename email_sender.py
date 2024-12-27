import smtplib
from email.mime.text import MIMEText
import json
import datetime
import getpass
from string import Template
from typing import Optional, Callable
from loguru import logger


class EmailSender:
    def __init__(self, config_file: str = "email_config.json", password: Optional[str] = None):
        self.config = self.load_config(config_file)
        self.smtp_server = "smtp." + self.config["sender_email"].split("@")[1]
        self.smtp_port = self.config["smtp_port"]
        self.sender_email = self.config["sender_email"]
        self.password = password
        self.receivers = self.config["receivers"]

    @staticmethod
    def load_config(config_file: str) -> dict:
        """读取邮件配置文件"""
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load config file {config_file}: {e}")
            raise

    def send_email(self, subject: str, content: str) -> None:
        """发送邮件"""
        try:
            msg = MIMEText(content, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = ",".join(self.receivers)

            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as smtp_obj:
                smtp_obj.login(self.sender_email, self.password)
                smtp_obj.sendmail(self.sender_email, self.receivers, msg.as_string())
            logger.info("Email sent successfully.")

        except smtplib.SMTPAuthenticationError:
            logger.error("SMTP authentication failed. Check your email or password.")
        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email: {e}")


class EmailTemplate:
    def __init__(self, subject: str, content: str):
        self.subject = subject
        self.content = content

    def __call__(self, email_sender: EmailSender, **kwargs) -> None:
        """执行邮件发送"""
        template = Template(self.content)
        content = template.safe_substitute(**kwargs)
        email_sender.send_email(self.subject, content)


class BasicEvent:
    def __init__(
        self,
        init_status: bool = False,
        active_action: Optional[Callable[[EmailSender], None]] = None,
        deactive_action: Optional[Callable[[EmailSender], None]] = None,
    ):
        self.status = init_status
        self.active_action = active_action
        self.deactive_action = deactive_action

        self.event_start = None
        self.event_end = None

    def update(self, status: bool) -> None:
        """更新事件状态并触发相应的操作"""

        if status and not self.status:
            self.event_start = datetime.datetime.now()
            self.event_end = None
            self.status = True

            if self.active_action:
                self.active_action()

        elif not status and self.status:
            self.event_end = datetime.datetime.now()
            self.status = False

            if self.deactive_action:
                self.deactive_action()


# 示例：使用
if __name__ == "__main__":
    import time

    passport = getpass.getpass("Please enter your email password: ")
    email_sender = EmailSender(password=passport)

    template = EmailTemplate(
        subject="Test Email",
        content="""
        [Test Email]
        Time: ${time}
        This is a test email.
        """,
    )

    active_action = lambda: template(email_sender, time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    event = BasicEvent(active_action=active_action)

    time.sleep(5)
    event.update(True)  # 触发事件并执行邮件发送操作
