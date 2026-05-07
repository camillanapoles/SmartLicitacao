import os
import time
import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from insight_collector import InsightCollector, get_collector

BASE_URL = os.getenv("BASE_URL", "https://smartlic.tech")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "tiago.sasaki@gmail.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_TOTP_SECRET = os.getenv("ADMIN_TOTP_SECRET", "")
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"

MFA_SCREEN = (
    By.XPATH,
    "//*[contains(normalize-space(.), 'Verificação em dois fatores') "
    "or contains(normalize-space(.), 'dois fatores')]",
)
MFA_CODE_INPUT = (
    By.CSS_SELECTOR,
    "input[autocomplete='one-time-code'], "
    "input[inputmode='numeric'], "
    "input[name*='code' i], "
    "input[id*='code' i], "
    "input[type='tel']",
)
MFA_SUBMIT_BUTTON = (By.CSS_SELECTOR, "button[type='submit']")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL.rstrip("/")


@pytest.fixture(scope="session")
def collector() -> InsightCollector:
    c = InsightCollector()
    c.metric("base_url", BASE_URL)
    return c


@pytest.fixture(scope="session")
def driver():
    opts = ChromeOptions()
    if HEADLESS:
        opts.add_argument("--headless=new")
    opts.add_argument("--window-size=1280,720")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--lang=pt-BR")
    opts.add_experimental_option("prefs", {"download.prompt_for_download": False})

    drv = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=opts,
    )
    drv.implicitly_wait(10)
    drv.set_page_load_timeout(60)
    yield drv
    drv.quit()


def _mfa_screen_visible(driver) -> bool:
    """Return True if the MFA verification screen is currently displayed."""
    return any(element.is_displayed() for element in driver.find_elements(*MFA_SCREEN))


def _complete_mfa_if_required(driver, base_url: str, timeout: int = 30) -> bool:
    """Complete TOTP MFA flow if the MFA screen appears after password submission.

    Returns True if MFA was completed, False if MFA screen was not shown.
    Skips the test (via pytest.skip) if MFA is required but ADMIN_TOTP_SECRET is absent.
    """
    login_url = f"{base_url}/login"
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: not d.current_url.startswith(login_url) or _mfa_screen_visible(d)
        )
    except TimeoutException:
        if not _mfa_screen_visible(driver):
            raise

    if not _mfa_screen_visible(driver):
        return False

    if not ADMIN_TOTP_SECRET:
        pytest.skip(
            "ADMIN_TOTP_SECRET não configurado — obrigatório para testes autenticados com MFA"
        )

    import pyotp

    totp = pyotp.TOTP(ADMIN_TOTP_SECRET.replace(" ", ""))
    # Wait out the current window if fewer than 5 seconds remain to avoid expiry on submit.
    remaining = 30 - (time.time() % 30)
    if remaining < 5:
        time.sleep(remaining + 1)
    totp_code = totp.now()
    code_input = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(MFA_CODE_INPUT)
    )
    code_input.clear()
    code_input.send_keys(totp_code)
    driver.find_element(*MFA_SUBMIT_BUTTON).click()

    WebDriverWait(driver, timeout).until(
        lambda d: not d.current_url.startswith(login_url)
    )
    return True


@pytest.fixture(scope="session")
def logged_in_driver(driver, base_url, collector):
    """Driver com sessão de admin autenticada. Faz login uma única vez."""
    if not ADMIN_PASSWORD:
        pytest.skip("ADMIN_PASSWORD não configurado — pule testes autenticados")
    from pages.login_page import LoginPage

    page = LoginPage(driver, base_url)
    page.navigate_to()
    t0 = time.time()

    email_el = page.wait_for_clickable(*LoginPage.EMAIL_INPUT)
    email_el.clear()
    email_el.send_keys(ADMIN_EMAIL)

    pwd_el = driver.find_element(*LoginPage.PASSWORD_INPUT)
    pwd_el.clear()
    pwd_el.send_keys(ADMIN_PASSWORD)

    page.js_click(driver.find_element(*LoginPage.SUBMIT_BUTTON))
    mfa_completed = _complete_mfa_if_required(driver, base_url)

    login_time = time.time() - t0
    collector.metric("login_success_seconds", login_time)
    collector.metric("login_mfa_completed", mfa_completed)
    return driver


@pytest.fixture(autouse=True)
def _set_test_name(request):
    try:
        c = request.getfixturevalue("collector")
        c.set_test(request.node.name)
    except Exception:
        pass


def pytest_sessionfinish(session, exitstatus):
    c = get_collector()
    if c:
        c.save("insights_report.json")
        c.print_summary()
