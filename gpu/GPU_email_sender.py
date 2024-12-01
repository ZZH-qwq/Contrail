import smtplib
from loguru import logger
from email.mime.text import MIMEText
def send_email(mail_host, sender_user, sender_passport, receivers, content):

    title = 'Server Warning'
    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = "Server"
    message['To'] = ",".join(receivers)
    message['Subject'] = title
    try:
        smtpObj = smtplib.SMTP_SSL(mail_host, 465)
        smtpObj.login(sender_user, sender_passport) 
        smtpObj.sendmail(sender_user, receivers, message.as_string())
        logger.info("Mail has been send successfully.")
    except smtplib.SMTPException as e:
        logger.info(e)
