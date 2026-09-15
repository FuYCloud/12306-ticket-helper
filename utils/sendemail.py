# 发送邮件（提醒是否购票成功）
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from utils.config_loader import get as cfg

enabled  = str(cfg("启用邮件通知", True)).strip().lower() in ("true", "1", "yes")
sender   = cfg("发件邮箱", "")
pwd      = cfg("邮箱授权码", "")
receiver = cfg("收件邮箱", "")
sender_nickname   = cfg("发件人昵称", "12306抢票助手")
receiver_nickname = cfg("收件人昵称", "我")
smtp_server = cfg("SMTP服务器", "smtp.qq.com")
smtp_port   = int(cfg("SMTP端口", 465))


def mail(title, message):
    if not enabled:
        return False
    if not sender or not pwd or not receiver:
        print("[邮件] 未配置邮箱信息，跳过发送。")
        return False

    ret = True
    try:
        msg = MIMEText(message, 'plain', 'utf-8')
        msg['From'] = formataddr([sender_nickname, sender])
        msg['To'] = formataddr([receiver_nickname, receiver])
        msg['Subject'] = title

        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(sender, pwd)
        server.sendmail(sender, [receiver], msg.as_string())
        server.quit()
    except Exception as e:
        ret = False
        print(e)
    return ret


if __name__ == '__main__':
    ret = mail('Test', 'Test')
    if ret:
        print("邮件发送成功!")
    else:
        print("邮件发送失败!")