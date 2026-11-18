"""
Browser verification script using Selenium Edge.
Verifies logins:
- noah (Critical, streak & declining popup)
- jordan (streak only)
- aaliyah (declining only)
- emma (no popup, all good)
Captures screenshots of login page, dashboards, and popups in light and dark mode.
"""

import os
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

BASE_URL = "http://127.0.0.1:5000"
SCREENSHOTS_DIR = Path(__file__).resolve().parent / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


def get_driver():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    return webdriver.Edge(options=options)


def run_verification():
    driver = get_driver()
    results = {}

    try:
        # 1. Login Page - Light Mode
        print("1. Testing Login Page (Light & Dark)...")
        driver.get(f"{BASE_URL}/logout")
        driver.get(f"{BASE_URL}/login")
        time.sleep(1)
        driver.execute_script("document.documentElement.removeAttribute('data-theme');")
        driver.save_screenshot(str(SCREENSHOTS_DIR / "01_login_light.png"))

        # Login Page - Dark Mode
        driver.execute_script("document.documentElement.setAttribute('data-theme', 'dark');")
        time.sleep(0.5)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "02_login_dark.png"))

        # Helper to perform login
        def login_as(username, password="pass123"):
            driver.get(f"{BASE_URL}/logout")
            driver.get(f"{BASE_URL}/login")
            time.sleep(0.5)
            driver.find_element(By.ID, "username").clear()
            driver.find_element(By.ID, "username").send_keys(username)
            driver.find_element(By.ID, "password").clear()
            driver.find_element(By.ID, "password").send_keys(password)
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            time.sleep(1)

        # 2. Noah Williams (Critical, Streak + Declining)
        print("2. Testing Noah Williams (noah)...")
        login_as("noah")

        # Verify popup is open on load
        modal_backdrop = driver.find_element(By.ID, "alert-modal-backdrop")
        is_modal_open = "open" in modal_backdrop.get_attribute("class")
        modal_title = driver.find_element(By.ID, "alert-dialog-title").text
        reasons_text = driver.find_element(By.ID, "alert-dialog-desc").text
        guardian_msg = driver.find_element(By.ID, "modal-guardian-message").get_attribute("value")

        has_critical = "Critical" in reasons_text
        has_streak = "streak" in reasons_text.lower() or "consecutive" in reasons_text.lower()
        has_declining = "declining" in reasons_text.lower() or "dropped" in reasons_text.lower()

        driver.execute_script("document.documentElement.removeAttribute('data-theme');")
        time.sleep(0.3)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "03_noah_popup_light.png"))

        # Dark mode popup
        driver.execute_script("document.documentElement.setAttribute('data-theme', 'dark');")
        time.sleep(0.3)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "04_noah_popup_dark.png"))

        # Close popup via "I understand"
        understand_btn = driver.find_element(By.ID, "modal-understand-btn")
        understand_btn.click()
        time.sleep(0.5)

        # Noah Dashboard screenshot (light)
        driver.execute_script("document.documentElement.removeAttribute('data-theme');")
        time.sleep(0.3)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "05_noah_dashboard_light.png"))

        results["noah"] = {
            "popup_opened": is_modal_open,
            "title": modal_title,
            "has_critical": has_critical,
            "has_streak": has_streak,
            "has_declining": has_declining,
            "typographic_quotes": "’" in guardian_msg,
        }

        # 3. Jordan Miller (Streak Only)
        print("3. Testing Jordan Miller (jordan)...")
        login_as("jordan")

        modal_backdrop = driver.find_element(By.ID, "alert-modal-backdrop")
        is_modal_open = "open" in modal_backdrop.get_attribute("class")
        modal_title = driver.find_element(By.ID, "alert-dialog-title").text
        reasons_text = driver.find_element(By.ID, "alert-dialog-desc").text

        has_streak = "streak" in reasons_text.lower() or "consecutive" in reasons_text.lower()
        has_declining = "declining" in reasons_text.lower()

        driver.execute_script("document.documentElement.removeAttribute('data-theme');")
        time.sleep(0.3)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "06_jordan_popup_light.png"))

        # Close modal
        driver.find_element(By.ID, "modal-understand-btn").click()
        time.sleep(0.5)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "07_jordan_dashboard_light.png"))

        results["jordan"] = {
            "popup_opened": is_modal_open,
            "title": modal_title,
            "has_streak": has_streak,
            "has_declining": has_declining,
        }

        # 4. Aaliyah Patel (Declining Only)
        print("4. Testing Aaliyah Patel (aaliyah)...")
        login_as("aaliyah")

        modal_backdrop = driver.find_element(By.ID, "alert-modal-backdrop")
        is_modal_open = "open" in modal_backdrop.get_attribute("class")
        modal_title = driver.find_element(By.ID, "alert-dialog-title").text
        reasons_text = driver.find_element(By.ID, "alert-dialog-desc").text

        has_declining = "declining" in reasons_text.lower() or "dropped" in reasons_text.lower()
        has_streak = "streak" in reasons_text.lower() or "consecutive" in reasons_text.lower()

        driver.execute_script("document.documentElement.removeAttribute('data-theme');")
        time.sleep(0.3)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "08_aaliyah_popup_light.png"))

        # Close modal
        driver.find_element(By.ID, "modal-understand-btn").click()
        time.sleep(0.5)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "09_aaliyah_dashboard_light.png"))

        results["aaliyah"] = {
            "popup_opened": is_modal_open,
            "title": modal_title,
            "has_declining": has_declining,
            "has_streak": has_streak,
        }

        # 5. Emma Johnson (No Popup, All Good)
        print("5. Testing Emma Johnson (emma)...")
        login_as("emma")

        # Verify modal does NOT exist or is not displayed
        modals = driver.find_elements(By.ID, "alert-modal-backdrop")
        has_modal = len(modals) > 0
        bell_badge = driver.find_element(By.ID, "bell-badge-count")
        is_badge_hidden = "hidden" in bell_badge.get_attribute("class")
        all_good_text = driver.find_element(By.CSS_SELECTOR, ".notifications-panel").text

        driver.execute_script("document.documentElement.removeAttribute('data-theme');")
        time.sleep(0.3)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "10_emma_dashboard_light.png"))

        driver.execute_script("document.documentElement.setAttribute('data-theme', 'dark');")
        time.sleep(0.3)
        driver.save_screenshot(str(SCREENSHOTS_DIR / "11_emma_dashboard_dark.png"))

        results["emma"] = {
            "popup_opened": has_modal,
            "badge_hidden": is_badge_hidden,
            "all_good_present": "All Good" in all_good_text,
        }

        print("\nAll browser verification steps completed successfully!")
        return results

    finally:
        driver.quit()


if __name__ == "__main__":
    res = run_verification()
    for student, data in res.items():
        print(f"\nStudent: {student}")
        for k, v in data.items():
            print(f"  • {k}: {v}")
