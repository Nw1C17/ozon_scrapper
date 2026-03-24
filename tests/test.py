import subprocess
import time
import sys
from pathlib import Path
from datetime import datetime

OZON_SCRIPT_PATH = Path(__file__).parent.parent / "ozon_search.py"   # поднимаемся на уровень выше из tests/

tasks = [
    ("игрушка трансформер", "1360855076"),
    ("нож походный", "1420710339"),
    ("машинка", "2873129423"),
]

def run_ozon_search(query: str, sku: str, browser: str = "chrome"):
    print(f"\n{'='*90}")
    print(f"Запуск поиска:  '{query}'  →  SKU {sku}")
    print(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*90}\n")


    try:
        result = subprocess.run([
            sys.executable,
            str(OZON_SCRIPT_PATH),
            "--query", query,
            "--sku", sku,
            "--browser", browser,
            "--max-positions", "120",
            "--no-headless",        # раскомментируй, если хочешь видеть браузер
        ], check=True, text=True)

    except subprocess.CalledProcessError as e:
        print(f"Ошибка выполнения ozon_search.py (код {e.returncode})")
    except Exception as ex:
        print(f"Неожиданная ошибка: {ex}")


if __name__ == "__main__":
    print("Запуск пакетного поиска позиций на Ozon...")
    print(f"Всего задач: {len(tasks)}\n")
    print(f"Используемый скрипт: {OZON_SCRIPT_PATH}\n")

    for i, (query, sku) in enumerate(tasks, 1):
        run_ozon_search(query, sku, browser="chrome")

        if i < len(tasks):
            print(f"\n→ Ожидание 30 секунд перед следующим запросом...\n")
            time.sleep(30)

    print("\n" + "="*90)
    print("="*90)