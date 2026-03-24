import json
import time
import random
import argparse
import re
import logging
import os
import shutil
from datetime import datetime
from typing import Optional, Dict, Any, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

try:
    from camoufox import Camoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False
    logging.warning("Camoufox не установлен. Установите: pip install camoufox")


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]


class OzonSearchParser:
    MAX_PAGES = 20
    CAPTCHA_DELAY_RANGE = (60, 120)
    PAGE_LOAD_DELAY = (3, 6)

    def __init__(self, browser: str = "chrome", headless: bool = True,
                 proxy: Optional[str] = None, driver_path: Optional[str] = None):
        self.browser = browser.lower()
        self.headless = headless
        self.proxy = proxy
        self.driver_path = driver_path

        # Для Selenium
        self.driver = None
        self.wait = None

        # Для Camoufox
        self.camoufox_ctx = None
        self.camoufox_browser = None
        self.camoufox_page = None

        if self.browser == "camoufox" and not CAMOUFOX_AVAILABLE:
            raise ImportError("Camoufox не установлен. Установите: pip install camoufox")

    def _init_selenium(self):
        """Создаёт Selenium-драйвер."""
        service = self._get_driver_service()
        user_agent = random.choice(USER_AGENTS)
        logger.info(f"Использую User-Agent: {user_agent}")

        if self.browser == "chrome":
            options = webdriver.ChromeOptions()
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(f"--user-agent={user_agent}")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            if self.proxy:
                options.add_argument(f"--proxy-server={self.proxy}")

            self.driver = webdriver.Chrome(service=service, options=options)

        elif self.browser == "firefox":
            options = webdriver.FirefoxOptions()
            if self.headless:
                options.add_argument("--headless")
            options.set_preference("dom.webdriver.enabled", False)
            options.set_preference("useAutomationExtension", False)
            options.set_preference("media.navigator.enabled", False)
            options.set_preference("network.http.use-cache", False)
            options.set_preference("privacy.trackingprotection.enabled", False)
            options.set_preference("general.useragent.override", user_agent)
            if self.proxy:
                proxy_parts = self.proxy.split("://")[1].split(":")
                proxy_host = proxy_parts[0]
                proxy_port = int(proxy_parts[1].split("/")[0])
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", proxy_host)
                options.set_preference("network.proxy.http_port", proxy_port)
                options.set_preference("network.proxy.ssl", proxy_host)
                options.set_preference("network.proxy.ssl_port", proxy_port)

            self.driver = webdriver.Firefox(service=service, options=options)

        elif self.browser == "edge":
            options = webdriver.EdgeOptions()
            if self.headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(f"--user-agent={user_agent}")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            if self.proxy:
                options.add_argument(f"--proxy-server={self.proxy}")

            self.driver = webdriver.Edge(service=service, options=options)

        else:
            raise ValueError(f"Неподдерживаемый браузер: {self.browser}")

        self.wait = WebDriverWait(self.driver, 20)

    def _init_camoufox(self):
        """Запускает Camoufox внутри контекстного менеджера."""
        proxy_dict = None
        if self.proxy:
            proxy_dict = {"server": self.proxy}

        self.camoufox_ctx = Camoufox(
            headless=self.headless,
            humanize=True,
            geoip=True,
            proxy=proxy_dict,
        )
        self.camoufox_browser = self.camoufox_ctx.__enter__()

        # Проверяем наличие метода new_page и вызываем его
        if hasattr(self.camoufox_browser, "new_page"):
            self.camoufox_page = self.camoufox_browser.new_page()
        else:
            # Возможные альтернативы (на случай изменения API)
            if hasattr(self.camoufox_browser, "new_context"):
                self.camoufox_page = self.camoufox_browser.new_context()
                logger.warning("Использую new_context вместо new_page")
            else:
                raise AttributeError(
                    "Объект Camoufox не имеет методов new_page или new_context. "
                    "Проверьте версию библиотеки."
                )

    def _get_driver_service(self):
        """Возвращает сервис для Selenium."""
        if self.driver_path and os.path.exists(self.driver_path):
            logger.info(f"Использую указанный драйвер: {self.driver_path}")
            return self._create_service(self.driver_path)

        driver_name = {
            "chrome": "chromedriver",
            "firefox": "geckodriver",
            "edge": "msedgedriver"
        }.get(self.browser)
        found_in_path = shutil.which(driver_name)
        if found_in_path:
            logger.info(f"Драйвер найден в PATH: {found_in_path}")
            return self._create_service(found_in_path)

        max_retries = 3
        retry_delay = 5
        for attempt in range(1, max_retries + 1):
            try:
                if self.browser == "chrome":
                    manager = ChromeDriverManager()
                elif self.browser == "firefox":
                    manager = GeckoDriverManager()
                elif self.browser == "edge":
                    manager = EdgeChromiumDriverManager()
                else:
                    raise ValueError(f"Неподдерживаемый браузер: {self.browser}")

                driver_path = manager.install()
                logger.info(f"Драйвер успешно загружен: {driver_path}")
                return self._create_service(driver_path)

            except Exception as e:
                logger.warning(f"Попытка {attempt}/{max_retries} загрузки драйвера не удалась: {e}")
                if attempt < max_retries:
                    logger.info(f"Повторная попытка через {retry_delay} секунд...")
                    time.sleep(retry_delay)
                else:
                    raise RuntimeError(
                        f"Не удалось загрузить драйвер для {self.browser} после {max_retries} попыток. "
                        f"Проверьте интернет-соединение, доступ к msedgedriver.azureedge.net и повторите. "
                        f"Вы также можете скачать драйвер вручную и указать путь через --driver-path, "
                        f"или добавить {driver_name} в PATH."
                    )

    def _create_service(self, driver_path: str):
        if self.browser == "chrome":
            return ChromeService(executable_path=driver_path)
        elif self.browser == "firefox":
            return FirefoxService(executable_path=driver_path)
        elif self.browser == "edge":
            return EdgeService(executable_path=driver_path)
        else:
            raise ValueError(f"Неподдерживаемый браузер: {self.browser}")

    def __enter__(self):
        if self.browser == "camoufox":
            self._init_camoufox()
        else:
            self._init_selenium()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.browser == "camoufox":
            if self.camoufox_ctx:
                try:
                    self.camoufox_ctx.__exit__(exc_type, exc_val, exc_tb)
                except Exception as e:
                    logger.debug(f"Ошибка при закрытии Camoufox: {e}")
        else:
            if self.driver:
                try:
                    self.driver.quit()
                except Exception as e:
                    logger.debug(f"Ошибка при закрытии драйвера: {e}")

    # ---------- Selenium методы ----------
    def _wait_for_products_selenium(self) -> bool:
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/product/']"))
            )
            return True
        except TimeoutException:
            logger.warning("Превышено время ожидания для загрузки ссылок на товары")
            return False

    def _get_page_skus_selenium(self) -> List[str]:
        skus = []
        product_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/product/']")
        pattern = re.compile(r'/product/(?:[a-z0-9-]+-)?(\d+)')

        for link in product_links:
            href = link.get_attribute("href")
            match = pattern.search(href)
            if match:
                skus.append(match.group(1))

        unique_skus = list(dict.fromkeys(skus))
        if unique_skus:
            logger.info(f"Извлечено {len(unique_skus)} артикулов")
        else:
            logger.debug("Не найдено артикулов на странице")
        return unique_skus

    # ---------- Camoufox методы ----------
    def _wait_for_products_camoufox(self) -> bool:
        try:
            self.camoufox_page.wait_for_selector("a[href*='/product/']", timeout=15000)
            return True
        except Exception:
            logger.warning("Превышено время ожидания для загрузки ссылок на товары")
            return False

    def _get_page_skus_camoufox(self) -> List[str]:
        skus = []
        links = self.camoufox_page.query_selector_all("a[href*='/product/']")
        pattern = re.compile(r'/product/(?:[a-z0-9-]+-)?(\d+)')

        for link in links:
            href = link.get_attribute("href")
            if href:
                match = pattern.search(href)
                if match:
                    skus.append(match.group(1))

        unique_skus = list(dict.fromkeys(skus))
        if unique_skus:
            logger.info(f"Извлечено {len(unique_skus)} артикулов")
        else:
            logger.debug("Не найдено артикулов на странице")
        return unique_skus

    # ---------- Основной метод ----------
    def find_position(self, query: str, target_sku: str, max_positions: int = 100) -> Dict[str, Any]:
        target_sku = str(target_sku).strip()
        base_url = "https://www.ozon.ru/search/"
        page = 1
        positions_checked = 0
        found_position = None
        found_page = None

        if self.browser == "camoufox":
            # Camoufox версия
            max_pages = (max_positions // 24) + 1
            while positions_checked < max_positions and page <= max_pages:
                url = f"{base_url}?text={query.replace(' ', '+')}&page={page}"
                logger.info(f"Загрузка страницы {page}: {url}")

                self.camoufox_page.goto(url, wait_until="networkidle")
                time.sleep(random.uniform(*self.PAGE_LOAD_DELAY))

                if "captcha" in self.camoufox_page.content().lower():
                    delay = random.uniform(*self.CAPTCHA_DELAY_RANGE)
                    logger.warning(f"Обнаружена капча, ждём {delay:.1f} секунд...")
                    time.sleep(delay)
                    logger.info("Обновляем страницу после ожидания")
                    self.camoufox_page.reload()
                    continue

                if not self._wait_for_products_camoufox():
                    logger.error("Товары не загрузились")
                    break

                skus = self._get_page_skus_camoufox()
                if not skus:
                    logger.error("Не извлечено артикулов")
                    break

                try:
                    pos_on_page = skus.index(target_sku) + 1
                    found_position = positions_checked + pos_on_page
                    found_page = page
                    logger.info(f"Найден артикул {target_sku} на позиции {found_position}")
                    break
                except ValueError:
                    pass

                positions_checked += len(skus)
                logger.info(f"Страница {page}: проверено {len(skus)} артикулов, всего {positions_checked}")
                page += 1

        else:
            # Selenium версия
            while positions_checked < max_positions and page <= self.MAX_PAGES:
                url = f"{base_url}?text={query.replace(' ', '+')}&page={page}"
                logger.info(f"Загрузка страницы {page}: {url}")

                self.driver.get(url)
                time.sleep(random.uniform(*self.PAGE_LOAD_DELAY))

                try:
                    self.driver.execute_script("""
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        if (navigator.webdriver !== undefined) {
                            delete navigator.webdriver;
                        }
                    """)
                except Exception as e:
                    logger.debug(f"Маскировка webdriver не удалась: {e}")

                if "captcha" in self.driver.page_source.lower():
                    delay = random.uniform(*self.CAPTCHA_DELAY_RANGE)
                    logger.warning(f"Обнаружена капча, ждём {delay:.1f} секунд...")
                    time.sleep(delay)
                    self.driver.refresh()
                    time.sleep(5)
                    continue

                if not self._wait_for_products_selenium():
                    logger.error("Товары не загрузились")
                    break

                skus = self._get_page_skus_selenium()
                if not skus:
                    logger.error("Не извлечено артикулов")
                    break

                try:
                    pos_on_page = skus.index(target_sku) + 1
                    found_position = positions_checked + pos_on_page
                    found_page = page
                    logger.info(f"Найден артикул {target_sku} на позиции {found_position}")
                    break
                except ValueError:
                    pass

                positions_checked += len(skus)
                logger.info(f"Страница {page}: проверено {len(skus)} артикулов, всего {positions_checked}")
                page += 1

        result = {
            "query": query,
            "sku": target_sku,
            "position": found_position if found_position is not None else "not_found",
            "page": found_page,
            "total_checked": positions_checked,
            "timestamp": datetime.now().isoformat()
        }

        if found_position is None or found_position > max_positions:
            result["position"] = "not_found"
            result["page"] = None

        return result


def main():
    parser = argparse.ArgumentParser(description="Поиск позиции товара на Ozon")
    parser.add_argument("--query", required=True, help="Строка поиска")
    parser.add_argument("--sku", required=True, help="Артикул товара")
    parser.add_argument("--browser", default="chrome",
                        choices=["chrome", "firefox", "edge", "camoufox"],
                        help="Тип браузера (по умолчанию chrome)")
    parser.add_argument("--no-headless", action="store_false", dest="headless",
                        help="Отключить безголовый режим (показать окно браузера)")
    parser.add_argument("--proxy", help="Proxy URL (например, http://user:pass@host:port)")
    parser.add_argument("--max-positions", type=int, default=100,
                        help="Максимальное количество проверяемых позиций (по умолчанию 100)")
    parser.add_argument("--driver-path", help="Путь к драйверу браузера (только для Selenium)")

    args = parser.parse_args()

    with OzonSearchParser(browser=args.browser, headless=args.headless,
                          proxy=args.proxy, driver_path=args.driver_path) as ozon:
        result = ozon.find_position(args.query, args.sku, max_positions=args.max_positions)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()