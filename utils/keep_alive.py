# utils/keep_alive.py
"""
主动保活线程：在等待抢票期间，定期执行轻量操作维持 12306 登录会话。
"""

import logging
import time
import threading


class KeepAlive:
    """
    在后台线程中定期执行保活操作。
    用法：
        ka = KeepAlive(driver, interval=480)
        ka.start()
        ...
        ka.stop()
    """

    def __init__(self, driver, interval=480, check_url=None):
        """
        :param driver:   Selenium WebDriver 实例
        :param interval: 保活间隔（秒），默认 480 秒（8 分钟）
        :param check_url: 用于检测会话是否有效的 URL，默认用 12306 购票页
        """
        self.driver = driver
        self.interval = interval
        self.check_url = check_url or "https://kyfw.12306.cn/otn/leftTicket/init"
        self._stop_event = threading.Event()
        self._thread = None

    def _loop(self):
        logging.info(f"保活线程已启动，间隔 {self.interval} 秒")
        while not self._stop_event.is_set():
            for _ in range(self.interval):
                if self._stop_event.is_set():
                    return
                time.sleep(1)

            try:
                handles = self.driver.window_handles
                if handles:
                    self.driver.switch_to.window(handles[0])

                current_url = self.driver.current_url
                if "login" in current_url.lower():
                    logging.warning("检测到会话可能已失效（被重定向到登录页），"
                                    "请手动重新扫码或重启程序！")
                    self._stop_event.set()
                    return

                logging.info("保活检查完成，会话正常")
            except Exception as e:
                logging.warning(f"保活检查异常（可忽略）: {e}")

        logging.info("保活线程已停止")

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3)