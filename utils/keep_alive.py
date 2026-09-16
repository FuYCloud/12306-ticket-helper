# utils/keep_alive.py
"""
主动保活线程：在等待抢票期间，定期检查 12306 会话状态。
默认静默运行，不会将浏览器窗口置顶或抢焦点。
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

    :param silent: True（默认）为静默模式，仅读取 URL，不切换窗口；
                   False 为主动模式，会切换到第一个窗口再读取（可能置顶）。
    """

    def __init__(self, driver, interval=480, check_url=None, silent=True):
        self.driver = driver
        self.interval = interval
        self.check_url = check_url or "https://kyfw.12306.cn/otn/leftTicket/init"
        self.silent = silent
        self._stop_event = threading.Event()
        self._thread = None

    def _loop(self):
        mode = "静默" if self.silent else "主动"
        logging.info(f"保活线程已启动（{mode}模式），间隔 {self.interval} 秒")

        while not self._stop_event.is_set():
            for _ in range(self.interval):
                if self._stop_event.is_set():
                    logging.info("保活线程已停止")
                    return
                time.sleep(1)

            try:
                if not self.silent:
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