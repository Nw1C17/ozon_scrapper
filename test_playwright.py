from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.firefox.connect_over_cdp("http://localhost:9222")
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
    )
    page = context.new_page()
    # Здесь можно добавить stealth-скрипты
    page.goto("https://www.ozon.ru")