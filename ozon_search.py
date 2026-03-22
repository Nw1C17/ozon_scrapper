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

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OzonSearchParser:
    """Парсер позиций товаров на Ozon с поддержкой разных браузеров и fallback драйверов."""

    MAX_PAGES = 20  # Максимальное количество страниц для обхода
    CAPTCHA_DELAY = 60  # Секунд ожидания при обнаружении капчи
    PAGE_LOAD_DELAY = (3, 6)  # Диапазон задержки после загрузки страницы

    def __init__(self, browser: str = "chrome", headless: bool = True,
                 proxy: Optional[str] = None, driver_path: Optional[str] = None):
        """
        Инициализация драйвера Selenium.

        :param browser: Тип браузера ('chrome', 'firefox', 'edge')
        :param headless: Запуск браузера в безголовом режиме
        :param proxy: URL прокси-сервера (опционально)
        :param driver_path: Путь к драйверу (если не указан, будет автоматическая загрузка/поиск)
        """
        self.browser = browser.lower()
        self.driver_path = driver_path
        self.driver = self._init_driver(headless, proxy)
        self.wait = WebDriverWait(self.driver, 20)
    def _get_driver_service(self) -> object:
        """
        Возвращает сервис для драйвера, используя либо переданный путь,
        либо автоматическое управление с повторными попытками загрузки.
        """
        # 1. Если указан явный путь и файл существует – используем его
        if self.driver_path and os.path.exists(self.driver_path):
            logger.info(f"Использую указанный драйвер: {self.driver_path}")
            return self._create_service(self.driver_path)

        # 2. Пытаемся найти драйвер в PATH
        driver_name = {
            "chrome": "chromedriver",
            "firefox": "geckodriver",
            "edge": "msedgedriver"
        }.get(self.browser)
        found_in_path = shutil.which(driver_name)
        if found_in_path:
            logger.info(f"Драйвер найден в PATH: {found_in_path}")
            return self._create_service(found_in_path)

        # 3. Если не нашли – пытаемся скачать через webdriver_manager
        #    с повторными попытками (например, 3 попытки с задержкой)
        max_retries = 3
        retry_delay = 5  # секунд
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
                    # После всех попыток – выбрасываем понятную ошибку
                    raise RuntimeError(
                        f"Не удалось загрузить драйвер для {self.browser} после {max_retries} попыток. "
                        f"Проверьте интернет-соединение, доступ к msedgedriver.azureedge.net и повторите. "
                        f"Вы также можете скачать драйвер вручную и указать путь через --driver-path, "
                        f"или добавить {driver_name} в PATH."
                    )

    def _create_service(self, driver_path: str) -> object:
        """Создаёт сервис для соответствующего браузера."""
        if self.browser == "chrome":
            return ChromeService(executable_path=driver_path)
        elif self.browser == "firefox":
            return FirefoxService(executable_path=driver_path)
        elif self.browser == "edge":
            return EdgeService(executable_path=driver_path)
        else:
            raise ValueError(f"Неподдерживаемый браузер: {self.browser}")

    def _init_driver(self, headless: bool, proxy: Optional[str]) -> webdriver.Remote:
        """Создаёт и настраивает драйвер для выбранного браузера."""
        service = self._get_driver_service()

        if self.browser == "chrome":
            options = webdriver.ChromeOptions()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument(
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            if proxy:
                options.add_argument(f"--proxy-server={proxy}")

            return webdriver.Chrome(service=service, options=options)

        elif self.browser == "firefox":
            options = webdriver.FirefoxOptions()
            if headless:
                options.add_argument("--headless")
            options.set_preference("dom.webdriver.enabled", False)
            options.set_preference("useAutomationExtension", False)
            options.set_preference("general.useragent.override",
                                   "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0")
            if proxy:
                options.set_preference("network.proxy.type", 1)
                options.set_preference("network.proxy.http", proxy.split("://")[1].split(":")[0])
                options.set_preference("network.proxy.http_port", int(proxy.split(":")[-1]))

            return webdriver.Firefox(service=service, options=options)

        elif self.browser == "edge":
            options = webdriver.EdgeOptions()
            if headless:
                options.add_argument("--headless=new")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
            if proxy:
                options.add_argument(f"--proxy-server={proxy}")

            return webdriver.Edge(service=service, options=options)

        else:
            raise ValueError(f"Неподдерживаемый браузер: {self.browser}. Доступны: chrome, firefox, edge")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.driver.quit()

    def _wait_for_products(self) -> bool:
        """Ожидание загрузки хотя бы одной ссылки на товар."""
        try:
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/product/']"))
            )
            return True
        except TimeoutException:
            logger.warning("Превышено время ожидания для загрузки ссылок на товары")
            return False

    def _get_page_skus(self) -> List[str]:
        """
        Извлечение SKU товаров из текущей страницы.
        Использует регулярное выражение для поиска числового идентификатора
        в ссылках вида /product/...-123456789/
        """
        skus = []
        product_links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/product/']")
        pattern = re.compile(r'/product/(?:[a-z0-9-]+-)?(\d+)')

        for link in product_links:
            href = link.get_attribute("href")
            match = pattern.search(href)
            if match:
                skus.append(match.group(1))

        # Удаляем дубликаты, сохраняя порядок
        unique_skus = list(dict.fromkeys(skus))

        if unique_skus:
            logger.info(f"Извлечено {len(unique_skus)} артикулов")
        else:
            logger.debug("Не найдено артикулов на странице")

        return unique_skus

    def find_position(self, query: str, target_sku: str, max_positions: int = 100) -> Dict[str, Any]:
        """
        Поиск позиции товара в выдаче Ozon.

        :param query: Поисковый запрос
        :param target_sku: SKU искомого товара
        :param max_positions: Максимальное количество просматриваемых позиций
        :return: Словарь с результатом поиска
        """
        target_sku = str(target_sku).strip()
        base_url = "https://www.ozon.ru/search/"
        page = 1
        positions_checked = 0
        found_position = None
        found_page = None

        while positions_checked < max_positions and page <= self.MAX_PAGES:
            params = f"?text={query.replace(' ', '+')}&page={page}"
            url = base_url + params
            logger.info(f"Загрузка страницы {page}: {url}")

            self.driver.get(url)
            time.sleep(random.uniform(*self.PAGE_LOAD_DELAY))

            # Проверка капчи (можно улучшить с помощью визуального анализа)
            if "captcha" in self.driver.page_source.lower():
                logger.warning("Обнаружена капча, ждем %s секунд...", self.CAPTCHA_DELAY)
                time.sleep(self.CAPTCHA_DELAY)
                self.driver.refresh()
                time.sleep(5)
                continue

            if not self._wait_for_products():
                logger.error("Товары не были загружены. Возможно капча или пустой вывод")
                break

            skus = self._get_page_skus()
            if not skus:
                logger.error("Не извлечено артикулов")
                break

            try:
                position_on_page = skus.index(target_sku) + 1
                found_position = positions_checked + position_on_page
                found_page = page
                logger.info(f"Найден артикул {target_sku} на позиции {found_position}")
                break
            except ValueError:
                pass

            positions_checked += len(skus)
            logger.info(f"Страница {page}: проверено {len(skus)} артикулов, всего {positions_checked}")
            page += 1

        # Формирование результата
        result = {
            "query": query,
            "sku": target_sku,
            "position": found_position if found_position is not None else "not_found",
            "page": found_page if found_page is not None else None,
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
    parser.add_argument("--browser", default="chrome", choices=["chrome", "firefox", "edge"],
                        help="Тип браузера (по умолчанию chrome)")
    parser.add_argument("--no-headless", action="store_false", dest="headless",
                        help="Отключить безголовый режим (показать окно браузера)")
    parser.add_argument("--proxy", help="Proxy URL (например, http://user:pass@host:port)")
    parser.add_argument("--max-positions", type=int, default=100,
                        help="Максимальное количество проверяемых позиций (по умолчанию 100)")
    parser.add_argument("--driver-path", help="Путь к драйверу браузера (если не указан, будет автоматически найден/загружен)")

    args = parser.parse_args()

    with OzonSearchParser(browser=args.browser, headless=args.headless,
                          proxy=args.proxy, driver_path=args.driver_path) as ozon_parser:
        result = ozon_parser.find_position(args.query, args.sku, max_positions=args.max_positions)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()