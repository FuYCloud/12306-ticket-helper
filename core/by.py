# core/by.py
import logging
import time
import sys

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.action_chains import ActionChains

from utils.config_loader import get as cfg
from utils.cookie_manager import (
    list_records, save_record, touch_record, get_record,
)

STARTS          = cfg("起点站", "")
ENDS            = cfg("终点站", "")
DTIME           = cfg("购票日期", "")
ORDER           = cfg("车次序号", 1)

_raw_users = cfg("乘车人", [])
if isinstance(_raw_users, str):
    _raw_users = [_raw_users]
USERS = [u for u in _raw_users if u]

_raw_seats = cfg("席别", "二等座")
if isinstance(_raw_seats, str):
    _raw_seats = [_raw_seats]
SEATS = [s for s in _raw_seats if s] or ["二等座"]

PER_USER_SEAT = str(cfg("启用按乘客设置席别", False)).strip().lower() in ("true", "1", "yes")

if not USERS:
    USER_SEAT = {}
elif PER_USER_SEAT and len(SEATS) > 1:
    USER_SEAT = {}
    for i, u in enumerate(USERS):
        USER_SEAT[u] = SEATS[i] if i < len(SEATS) else SEATS[-1]
else:
    USER_SEAT = {u: SEATS[0] for u in USERS}

_unique_seats = set(USER_SEAT.values()) if USER_SEAT else set()
MULTI_SEAT = len(_unique_seats) > 1
UNIFIED_SEAT = next(iter(_unique_seats)) if len(_unique_seats) == 1 else SEATS[0]

STUDENT         = cfg("学生票", "false")
EXECUTABLE_PATH = cfg("驱动路径", "./asset/chromedriver.exe")
SEAT            = cfg("座位偏好", "")

MAX_QUERY           = cfg("最大查询次数", 0)
QUERY_INTERVAL      = cfg("查询间隔", 0.05)
SEAT_ROW_START      = cfg("选座起始排", 1)
SEAT_ROW_END        = cfg("选座结束排", 5)
SCAN_TIMEOUT        = cfg("扫码超时", 120)
LOGIN_CHOICE_TIMEOUT = cfg("登录选择超时", 60)
POST_SUCCESS_WAIT   = cfg("成功后停留", 60)
HIDE_QRCODE         = cfg("隐藏无关二维码", True)

DEBUG_MODE = str(cfg("调试模式", False)).strip().lower() in ("true", "1", "yes")

logger = logging.getLogger()
logger.setLevel(logging.DEBUG if DEBUG_MODE else logging.INFO)
if logger.handlers:
    logger.handlers.clear()
handler = logging.FileHandler('app.log', mode='a', encoding='utf-8')
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

SEAT_TYPE_PREFIX = {
    "二等座": "erdeng",
    "一等座": "yideng",
    "特等座": "tedeng",
    "商务座": "shangwu",
}


class Byticket(object):
    executable_path = EXECUTABLE_PATH
    starts = STARTS
    ends = ENDS
    dtime = DTIME
    order = ORDER
    users = USERS
    student = str(STUDENT).strip().lower() in ("true", "1", "yes")
    seat = SEAT

    ticket_url = "https://kyfw.12306.cn/otn/leftTicket/init?linktypeid=dc"
    login_url = "https://kyfw.12306.cn/otn/resources/login.html"
    initmy_url = "https://kyfw.12306.cn/otn/view/index.html"

    def __init__(self):
        self.driver = None
        self.wait = None
        self.xb = UNIFIED_SEAT
        self.multi_seat = MULTI_SEAT

    def close(self):
        """关闭浏览器（外部手动调用）"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logging.debug(f"关闭浏览器时异常: {e}")
            self.driver = None

    def _init_driver(self):
        options = Options()
        options.page_load_strategy = 'eager'

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-infobars")
        options.add_argument("--start-maximized")
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        options.add_experimental_option("useAutomationExtension", False)

        service = Service(self.executable_path)
        self.driver = webdriver.Chrome(service=service, options=options)

        self.driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )

        self.wait = WebDriverWait(self.driver, 10, poll_frequency=0.1)
        logging.info("浏览器已启动")

    def _safe_click(self, element):
        """三级兜底点击：原生 click → JS click → ActionChains。"""
        try:
            element.click()
            return True
        except Exception:
            pass
        try:
            self.driver.execute_script("arguments[0].click();", element)
            return True
        except Exception:
            pass
        try:
            ActionChains(self.driver).move_to_element(element).click().perform()
            return True
        except Exception:
            return False

    def _input_with_timeout(self, prompt, timeout):
        """
        带超时的输入：
          - 正常输入并回车 → 返回输入字符串（可能为空）
          - 超时未输入      → 返回 None
        Windows 用 msvcrt 逐字符读取；其他平台直接 input。
        """
        if sys.platform != "win32":
            return input(prompt)

        import msvcrt
        print(prompt, end="", flush=True)
        start = time.time()
        chars = []
        while time.time() - start < timeout:
            if msvcrt.kbhit():
                ch = msvcrt.getwch()
                if ch == "\r":
                    print()
                    return "".join(chars)
                elif ch == "\x08":
                    if chars:
                        chars.pop()
                        print("\b \b", end="", flush=True)
                elif ch == "\x03":
                    raise KeyboardInterrupt
                else:
                    chars.append(ch)
                    print(ch, end="", flush=True)
            time.sleep(0.05)
        print()
        return None

    def _ask_login_choice(self):
        """
        在启动浏览器之前询问用户登录方式。
        返回：
          - 选中的记录 dict   → 走 Cookie 登录
          - None              → 走扫码登录
        """
        records = list_records()
        if not records:
            return None

        print("\n===== 已保存的扫码记录 =====")
        for i, rec in enumerate(records, 1):
            last = time.strftime("%Y-%m-%d %H:%M", time.localtime(rec.get("last_used", 0)))
            print(f"  {i}. {rec['account']}  （最近使用：{last}）")
        print(f"  {len(records) + 1}. 扫码添加新记录")
        print("==============================")
        print(f"请输入编号（{LOGIN_CHOICE_TIMEOUT} 秒内未输入将自动选择最近使用的「{records[0]['account']}」）：")

        choice = self._input_with_timeout("> ", LOGIN_CHOICE_TIMEOUT)

        if choice is None or choice.strip() == "":
            selected = records[0]
            print(f"自动选择：{selected['account']}")
            return selected

        choice = choice.strip()
        if choice == str(len(records) + 1):
            return None
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(records):
                print("无效编号，将使用扫码登录。")
                return None
        except ValueError:
            print("无效输入，将使用扫码登录。")
            return None
        return records[idx]

    def _inject_hide_css(self):
        """注入 CSS 隐藏登录页页脚二维码区域，不影响登录二维码 #J-qrImg。"""
        if not HIDE_QRCODE:
            return
        try:
            injected = self.driver.execute_script("""
                if (!document.getElementById('hide-qr-style')) {
                    var s = document.createElement('style');
                    s.id = 'hide-qr-style';
                    s.textContent = '.foot-code, .foot-code * { display: none !important; }';
                    document.head.appendChild(s);
                    return 1;
                }
                return 0;
            """)
            if injected:
                logging.debug("已注入 CSS 隐藏页脚二维码")
        except Exception as e:
            logging.debug(f"注入隐藏 CSS 失败: {e}")

    def _is_logged_in(self):
        """判断当前是否已登录成功"""
        try:
            url = self.driver.current_url
        except Exception:
            return False
        if "login" in url.lower() or "passport" in url.lower():
            return False
        for xp in (
            '//a[contains(text(),"我的12306")]',
            '//a[contains(text(),"退出")]',
            '//div[contains(@class,"user-info")]',
        ):
            try:
                self.driver.find_element(By.XPATH, xp)
                return True
            except Exception:
                continue
        return False

    def _cookie_login(self, record):
        """用指定记录里的 Cookie 尝试登录。返回 True/False。"""
        account_name = record["account"]
        cookies = record["cookies"]

        try:
            self.driver.get(self.login_url)
            time.sleep(0.8)

            try:
                self.driver.delete_all_cookies()
            except Exception as e:
                logging.debug(f"清除旧 cookie 时异常: {e}")

            added = 0
            for c in cookies:
                cookie_dict = {
                    "name": c["name"],
                    "value": c["value"],
                    "domain": c.get("domain", ".12306.cn"),
                    "path": c.get("path", "/"),
                }
                try:
                    self.driver.add_cookie(cookie_dict)
                    added += 1
                except Exception as e:
                    logging.debug(f"添加 cookie [{c['name']}] 失败: {e}")

            logging.info(f"已为「{account_name}」注入 {added}/{len(cookies)} 个 cookie")

            self.driver.get(self.initmy_url)
            time.sleep(2)

            if self._is_logged_in():
                logging.info(f"使用扫码记录「{account_name}」登录成功！")
                touch_record(account_name)
                return True
            else:
                logging.warning(f"扫码记录「{account_name}」已失效，需要重新扫码。")
                return False
        except Exception as e:
            logging.warning(f"Cookie 登录失败：{e}")
            return False

    def _scan_login(self):
        """走扫码登录流程。"""
        try:
            self.driver.delete_all_cookies()
        except Exception:
            pass

        self.driver.get(self.login_url)
        time.sleep(1)

        try:
            account = self.wait.until(EC.presence_of_element_located(
                (By.XPATH, '//div[@class="login-box"]//li[@class="login-hd-account"]/a')))
            self._safe_click(account)
        except Exception as e:
            logging.debug(f"切换扫码登录标签时异常（可能已在此页）: {e}")

        logging.info("请扫码登录！")

        try:
            WebDriverWait(self.driver, 10, poll_frequency=0.1).until(
                EC.presence_of_element_located((By.ID, "J-qrImg"))
            )
        except Exception:
            logging.warning("未检测到登录二维码，页面结构可能已变化")

        deadline = time.time() + SCAN_TIMEOUT
        last_log_time = 0
        while time.time() < deadline:
            if self._is_logged_in():
                break

            self._inject_hide_css()

            now = time.time()
            if now - last_log_time > 5:
                try:
                    current_url = self.driver.current_url
                except Exception:
                    current_url = ""
                logging.debug(f"等待扫码中，当前 URL: {current_url}")
                last_log_time = now

            time.sleep(1)
        else:
            raise Exception(f"登录超时（{SCAN_TIMEOUT} 秒内未检测到登录成功）")

        logging.info("扫码登录成功！")
        time.sleep(1)

        try:
            cookies = self.driver.get_cookies()
            default_name = f"账号_{len(list_records()) + 1}"
            print(f"\n请输入该账号的备注名（直接回车使用默认名「{default_name}」）：")
            name = input("> ").strip()
            if not name:
                name = default_name
            result = save_record(name, cookies)
            if result == "updated":
                logging.info(f"已更新账号「{name}」的扫码记录")
            else:
                logging.info(f"已保存账号「{name}」的扫码记录")
        except Exception as e:
            logging.warning(f"保存扫码记录失败：{e}")

    def login(self):
        """完整登录流程。"""
        try:
            selected = self._ask_login_choice()
            self._init_driver()

            if selected is not None:
                if self._cookie_login(selected):
                    return
                print("扫码记录已失效，转为扫码登录。")

            self._scan_login()

        except Exception as e:
            logging.error("登录过程中发生错误: %s", e)
            raise

    def _set_seat_types(self, user_rows):
        """在订单确认页为每位乘客设置席别。"""
        for idx, user in enumerate(self.users, start=1):
            seat = USER_SEAT.get(user)
            if not seat:
                continue

            seat_select_el = None
            try:
                seat_select_el = self.driver.find_element(By.ID, f"seatType_{idx}")
            except Exception:
                pass

            if seat_select_el is None and user in user_rows:
                try:
                    seat_select_el = user_rows[user].find_element(By.XPATH, './/select')
                except Exception:
                    pass

            if seat_select_el is None:
                logging.warning(f"未找到「{user}」的席别选择框，跳过")
                continue

            try:
                seat_select = Select(seat_select_el)
                matched = False
                for option in seat_select.options:
                    if seat in option.text:
                        seat_select.select_by_visible_text(option.text)
                        matched = True
                        break
                if matched:
                    logging.info(f"已为「{user}」选择席别「{seat}」")
                else:
                    logging.warning(f"席别「{seat}」在「{user}」的可选项中不存在")
            except Exception as e:
                logging.error(f"为「{user}」设置席别失败：{e}")
                raise

    def set_cookies(self):
        try:
            self.driver.add_cookie({"name": "_jc_save_fromStation", "value": self.starts})
            self.driver.add_cookie({"name": "_jc_save_toStation", "value": self.ends})
            self.driver.add_cookie({"name": "_jc_save_fromDate", "value": self.dtime})
            self.driver.refresh()
        except Exception as e:
            logging.error("设置Cookie时发生错误: %s", e)
            raise

    def _select_seat(self):
        """在选座框中按席别 + 座位号选择。多席别订单跳过。"""
        if self.multi_seat:
            logging.info("订单包含多种席别，跳过在线选座，由系统自动分配座位")
            return False

        prefix = SEAT_TYPE_PREFIX.get(self.xb, "erdeng")

        try:
            WebDriverWait(self.driver, 8, poll_frequency=0.1).until(
                EC.visibility_of_element_located((By.ID, "id-seat-sel"))
            )
        except Exception:
            self.driver.save_screenshot("seat_error.png")
            logging.warning("选座框未出现，跳过选座")
            return False

        base_xpath = (
            f'//div[@id="id-seat-sel"]'
            f'//div[starts-with(@id, "{prefix}") and not(contains(@style, "none"))]'
        )

        for row in range(SEAT_ROW_START, SEAT_ROW_END + 1):
            seat_xpath = f'{base_xpath}//a[@id="{row}{self.seat}"]'
            try:
                seat_element = WebDriverWait(self.driver, 1.5, poll_frequency=0.05).until(
                    EC.presence_of_element_located((By.XPATH, seat_xpath))
                )
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", seat_element
                )
                time.sleep(0.1)
                self._safe_click(seat_element)
                logging.info(f"已点击第 {row} 排座位 {self.seat}（席别：{self.xb}）")

                time.sleep(0.12)
                cls = seat_element.get_attribute("class") or ""
                if "cur" in cls:
                    logging.info(f"座位 {row}{self.seat} 已成功选中")
                else:
                    logging.warning(f"座位 {row}{self.seat} 点击后 class={cls}，可能未选中")
                return True
            except Exception:
                continue

        self.driver.save_screenshot("seat_error.png")
        logging.warning(f"未找到可用的 {self.seat} 座位，已保存 seat_error.png")
        return False

    def start(self):
        """主流程，成功返回 True，失败返回 False。"""
        try:
            self.driver.get(self.ticket_url)
            self.set_cookies()

            user_rows = {}
            count = 0
            last_log_count = 0

            while True:
                if MAX_QUERY > 0 and count > MAX_QUERY:
                    logging.error(f"超过最大查询次数（{MAX_QUERY}），退出程序。")
                    return False

                try:
                    query_btn = self.wait.until(
                        EC.element_to_be_clickable((By.ID, "query_ticket"))
                    )
                    self._safe_click(query_btn)
                    count += 1

                    if count - last_log_count >= 10:
                        logging.info(f"已查询 {count} 次...")
                        last_log_count = count

                    book_btns = WebDriverWait(self.driver, 3, poll_frequency=0.1).until(
                        EC.presence_of_all_elements_located(
                            (By.XPATH, '//tbody[@id="queryLeftTable"]/tr/td[@class="no-br"]')
                        )
                    )

                    if self.order == 0:
                        for o, btn in enumerate(book_btns):
                            self.order = o + 1
                            btn.find_element(By.XPATH, './a').click()
                            time.sleep(0.5)
                    else:
                        book_btns[self.order - 1].find_element(By.XPATH, './a').click()

                    for _ in range(100):
                        if len(self.driver.window_handles) > 1:
                            break
                        time.sleep(0.02)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    logging.info(f"已进入订单页面（第 {count} 次查询）")
                    break

                except Exception:
                    time.sleep(QUERY_INTERVAL)
                    continue

            try:
                user_checks = self.wait.until(
                    EC.visibility_of_all_elements_located(
                        (By.XPATH, '//ul[@id="normal_passenger_id"]/li')
                    )
                )
                for user in self.users:
                    for check in user_checks:
                        label = check.find_element(By.XPATH, './label')
                        if user in label.text:
                            check.find_element(By.XPATH, './input').click()
                            user_rows[user] = check
                            logging.info(f"已勾选乘客「{user}」")
                            break
            except Exception as e:
                logging.error("选择乘车人时发生错误: %s", e)
                raise

            try:
                close_id = 'dialog_xsertcj_ok' if self.student else 'dialog_xsertcj_cancel'
                close_btn = WebDriverWait(self.driver, 3, poll_frequency=0.1).until(
                    EC.element_to_be_clickable((By.ID, close_id))
                )
                self._safe_click(close_btn)
            except Exception as e:
                logging.error("关闭弹出框时发生错误: %s", e)
                raise

            try:
                self._set_seat_types(user_rows)
            except Exception as e:
                logging.error("设置席别时发生错误: %s", e)
                raise

            try:
                submit_btn = self.driver.find_element(By.ID, "submitOrder_id")
                self._safe_click(submit_btn)
                logging.info("已点击提交订单")

                time.sleep(0.3)
                self._select_seat()

                confirm_btn = WebDriverWait(self.driver, 6, poll_frequency=0.1).until(
                    EC.element_to_be_clickable((By.ID, "qr_submit_id"))
                )

                logging.info(
                    f"确认按钮状态: displayed={confirm_btn.is_displayed()}, "
                    f"enabled={confirm_btn.is_enabled()}, "
                    f"text={confirm_btn.text.strip()}"
                )

                if not self._safe_click(confirm_btn):
                    self.driver.save_screenshot("confirm_error.png")
                    logging.error("确认按钮点击失败，已截图 confirm_error.png")
                    raise Exception("确认按钮点击失败")

                logging.info("已点击确认，等待提交结果")
                time.sleep(0.6)

                try:
                    second_confirm = WebDriverWait(self.driver, 2, poll_frequency=0.1).until(
                        EC.element_to_be_clickable((By.XPATH,
                            '//div[contains(@class,"dhx_modal") or contains(@class,"dhx_wins")]'
                            '//a[contains(text(),"确定") or contains(text(),"确认")]'))
                    )
                    self._safe_click(second_confirm)
                    logging.info("已点击二次确认")
                except Exception:
                    pass

                logging.info("抢票成功，请尽快支付！浏览器将保留，可手动操作。")
                return True

            except Exception as e:
                logging.error("提交订单时发生错误: %s", e)
                raise

        except Exception as e:
            logging.error("主流程发生错误: %s", e)
            return False


if __name__ == '__main__':
    try:
        bt = Byticket()
        bt.start()
    except Exception as e:
        logging.error("程序启动时发生错误: %s", e)