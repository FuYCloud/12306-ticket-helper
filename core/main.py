import sys
import os
import time
import logging
import datetime
import threading

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from utils.config_loader import get as cfg
from core.by import Byticket
from utils.sendemail import mail
from utils.keep_alive import KeepAlive

TIME = cfg("开抢时间", "")
KEEP_ALIVE_INTERVAL = cfg("保活间隔", 480)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
if logger.handlers:
    logger.handlers.clear()

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler('app.log', mode='a', encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def _send_mail_async(title, message):
    threading.Thread(target=mail, args=(title, message), daemon=True).start()


def _is_browser_closed_error(err_text):
    """判断是否为浏览器窗口被关闭导致的中断。"""
    keywords = (
        "invalid session id",
        "no such window",
        "disconnected",
        "chrome not reachable",
        "session deleted",
    )
    return any(k in err_text for k in keywords)


def _wait_browser_closed(by):
    """等待浏览器被手动关闭。检测到连接断开或窗口消失后返回。"""
    while True:
        try:
            _ = by.driver.window_handles
            time.sleep(1)
        except Exception:
            return


def job_callback(by):
    """执行抢票。抢票成功后保持浏览器打开，直到用户手动关闭。"""
    try:
        result = by.start()
        if result:
            _send_mail_async("12306抢票成功", "车票已成功抢到，请尽快支付！")
            logging.info("抢票成功，浏览器保持打开，请手动完成支付。关闭浏览器后程序将自动退出。")
            _wait_browser_closed(by)
            logging.info("浏览器已关闭，程序退出。")
        else:
            _send_mail_async("购票失败", "未能成功抢到车票，请检查日志或稍后再试。")
            by.close()
    except Exception as e:
        err_text = str(e).lower()
        if _is_browser_closed_error(err_text):
            logging.error("浏览器窗口已关闭，抢票中断。请重新运行程序。")
            _send_mail_async("购票中断", "浏览器窗口已关闭，抢票中断。请重新运行程序。")
        else:
            logging.error("任务执行过程中发生错误: %s", e)
            _send_mail_async("购票异常", f"抢票过程出错：{e}")
        by.close()
    sys.exit(0)


def wait_until(target_str):
    """分段等待：远时低频、近时高频、最后 20ms 自旋，误差 < 10ms。"""
    target = datetime.datetime.strptime(target_str, "%Y-%m-%d %H:%M:%S")
    while True:
        delta = (target - datetime.datetime.now()).total_seconds()
        if delta <= 0:
            return
        if delta > 2:
            time.sleep(0.5)
        elif delta > 0.2:
            time.sleep(0.05)
        elif delta > 0.02:
            time.sleep(0.005)
        else:
            time.sleep(0.001)


def main():
    try:
        if not TIME:
            logging.error("配置文件中未填写「开抢时间」。")
            sys.exit(1)

        by = Byticket()
        by.login()
        logging.info(f"任务已安排，将在 {TIME} 执行")

        ka = KeepAlive(by.driver, interval=KEEP_ALIVE_INTERVAL)
        ka.start()
        try:
            wait_until(TIME)
        finally:
            ka.stop()

        job_callback(by)
    except Exception as e:
        err_text = str(e).lower()
        if _is_browser_closed_error(err_text):
            logging.error("浏览器窗口已关闭，程序中断。请重新运行程序。")
        else:
            logging.error("程序启动时发生错误: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()