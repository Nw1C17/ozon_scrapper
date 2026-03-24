from seleniumwire import webdriver
from selenium.webdriver.firefox.options import Options

options = Options()
options.binary_location = r"C:\Program Files\Mozilla Firefox\firefox.exe"

proxy_options = {
    'proxy': {
        'http': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
        'https': f'http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}',
    }
}

driver = webdriver.Firefox(options=options, seleniumwire_options=proxy_options)
driver.get("https://www.ozon.ru/")
print(driver.title)
driver.quit()