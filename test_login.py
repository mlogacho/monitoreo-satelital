import time
from playwright.sync_api import sync_playwright

def test():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://www.starlink.com/account/home")
        time.sleep(3)
        page.fill("input[type='text'], input[type='email']", "marcositels@gmail.com")
        page.click("button:has-text('Siguiente')")
        time.sleep(3)
        page.screenshot(path="login_step2.png")
        print("Done")
        browser.close()

if __name__ == "__main__":
    test()
