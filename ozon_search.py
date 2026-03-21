import json
import time
import random
import argparse
import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class OzonSearchParser:
    """Парсер позиций товаров на Ozon."""

    MAX_PAGES = 20  # Максимальное количество страниц для обхода
    CAPTCHA_DELAY = 60  # Секунд ожидания при обнаружении капчи
    PAGE_LOAD_DELAY = (3, 6)  # Диапазон задержки после загрузки страницы

    def __init__(self, headless: bool = True, proxy: Optional[str] = None):
        """
        Инициализация драйвера Selenium.

        :param headless: Запуск браузера в безголовом режиме
        :param proxy: URL прокси-сервера (опционально)
        """
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

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.wait = WebDriverWait(self.driver, 20)

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
            logger.warning("Превышено время ожидания для загрузки ссылок на "
                           "товары")
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

    def find_position(self, query: str, target_sku: str, max_positions: int = 2000) -> Dict[str, Any]:
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

            # Проверка капчи
            if "captcha" in self.driver.page_source.lower():
                logger.warning("Обнаружена капча, ждем %s секунд...",
                               self.CAPTCHA_DELAY)
                time.sleep(self.CAPTCHA_DELAY)
                self.driver.refresh()
                time.sleep(5)
                continue

            if not self._wait_for_products():
                logger.error("Товары не были загружены. Возможно капча или "
                             "пустой вывод")
                break

            skus = self._get_page_skus()
            if not skus:
                logger.error("Не извлечено артикулов")
                break

            try:
                position_on_page = skus.index(target_sku) + 1
                found_position = positions_checked + position_on_page
                found_page = page
                logger.info(f"Найдке артикул {target_sku} на позиции"
                            f" {found_position}")
                break
            except ValueError:
                pass

            positions_checked += len(skus)
            logger.info(f"Страница {page}: "
                        f"Проверено {len(skus)} Артикулов,"
                        f" всего"
                        f" {positions_checked}")
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
    parser = argparse.ArgumentParser(description="Поиск позиции товара Ozon")
    parser.add_argument("--query", required=True, help="Строка поиска")
    parser.add_argument("--sku", required=True, help="Артикулов товара")
    parser.add_argument("--no-headless", action="store_false", dest="headless",
                        help="Отключить безголовый режим (показать окно браузера)")
    parser.add_argument("--proxy", help="Proxy URL")

    args = parser.parse_args()

    with OzonSearchParser(headless=args.headless, proxy=args.proxy) as ozon_parser:
        result = ozon_parser.find_position(args.query, args.sku)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()