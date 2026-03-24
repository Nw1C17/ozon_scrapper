#!/usr/bin/env python3
"""
Скрипт для последовательного запуска парсера Ozon с тремя разными запросами.
Интервал между запусками — 30 секунд.
"""

import subprocess
import time
import sys
import argparse
from datetime import datetime

# Список тестовых заданий: (запрос, артикул)
TEST_CASES = [
    ("наушники bluetooth", "3493453026"),   # реальный товар
    ("книга python", "1769991502"),         # реальный товар
    ("несуществующий товар", "9999999999")  # заведомо отсутствует
]

def run_parser(script_path, query, sku, browser, headless, proxy, max_positions, driver_path):
    """Запускает основной скрипт с переданными аргументами."""
    cmd = [
        sys.executable, script_path,
        "--query", query,
        "--sku", sku,
        "--browser", browser,
        "--max-positions", str(max_positions)
    ]

    if not headless:
        # В парсере аргумент --no-headless отключает безголовый режим
        cmd.append("--no-headless")
    if proxy:
        cmd.extend(["--proxy", proxy])
    if driver_path:
        cmd.extend(["--driver-path", driver_path])

    print(f"\n{'='*60}")
    print(f"[{datetime.now().isoformat()}] Запуск: {query} (SKU={sku})")
    print(f"Команда: {' '.join(cmd)}")
    print('-'*60)

    try:
        # Явно указываем кодировку UTF-8, чтобы избежать UnicodeDecodeError
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', check=False)
        if result.stdout:
            print("STDOUT:")
            print(result.stdout)
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        print(f"[{datetime.now().isoformat()}] Завершён с кодом {result.returncode}")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Ошибка при запуске: {e}")
    finally:
        print('='*60 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Последовательный запуск парсера Ozon с тестовыми запросами")
    parser.add_argument("--script", default="ozon_search.py", help="Путь к основному скрипту парсера")
    parser.add_argument("--browser", default="chrome", choices=["chrome", "firefox", "edge", "camoufox"],
                        help="Тип браузера (по умолчанию chrome)")
    parser.add_argument("--visible", action="store_true",
                        help="Показать окно браузера (отключить безголовый режим)")
    parser.add_argument("--proxy", help="Прокси-сервер (например, http://user:pass@host:port)")
    parser.add_argument("--max-positions", type=int, default=100, help="Максимум проверяемых позиций")
    parser.add_argument("--driver-path", help="Путь к драйверу Selenium (только для chrome/firefox/edge)")
    parser.add_argument("--delay", type=int, default=30, help="Задержка между запусками в секундах (по умолчанию 30)")
    args = parser.parse_args()

    headless = not args.visible   # visible = True -> headless = False

    for idx, (query, sku) in enumerate(TEST_CASES, start=1):
        print(f"\n--- Запуск {idx}/{len(TEST_CASES)} ---")
        run_parser(args.script, query, sku, args.browser, headless,
                   args.proxy, args.max_positions, args.driver_path)

        if idx < len(TEST_CASES):
            print(f"Ожидание {args.delay} секунд перед следующим запуском...")
            time.sleep(args.delay)

    print("\nВсе запуски завершены.")

if __name__ == "__main__":
    main()