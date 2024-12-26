import smtplib
from email.mime.text import MIMEText
import json
from loguru import logger


class EmailSender:
    def __init__(self, config_file="email_config.json", password=None):
        with open(config_file, "r") as f:
            self.config = json.load(f)
        self.smtp_server = "smtp." + self.config["sender_email"].split("@")[1]
        self.smtp_port = self.config["smtp_port"]
        self.sender_email = self.config["sender_email"]
        self.password = password
        self.receivers = self.config["receivers"]

    def send_email(self, subject, content):
        try:
            msg = MIMEText(content, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = "Server"
            msg["To"] = ",".join(self.receivers)
            smtpObj = smtplib.SMTP_SSL(self.smtp_server, self.smtp_port)
            smtpObj.login(self.sender_email, self.password)
            smtpObj.sendmail(self.sender_email, self.receivers, msg.as_string())
            logger.info("Email sent successfully.")
        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email: {e}")
