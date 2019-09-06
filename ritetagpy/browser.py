# selenium
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver import DesiredCapabilities
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import Remote

# general libs
from time import sleep

# local project
from .util import interruption_handler
from .util import highlight_print
from .util import emergency_exit
from .util import get_current_url
from .util import check_authorization
from .util import web_address_navigator


def set_selenium_remote_session(
    use_firefox, logger, selenium_url="", selenium_driver=None
):
    """
    Starts remote session for a selenium server.
    Creates a new selenium driver instance for remote session or uses provided
    one. Useful for docker setup.

    :param selenium_url: string
    :param selenium_driver: selenium WebDriver
    :return: self
    """

    if selenium_driver:
        browser = selenium_driver  # convert_selenium_browser(selenium_driver)
    else:
        desired_caps = (
            DesiredCapabilities.FIREFOX if use_firefox else DesiredCapabilities.CHROME
        )
        browser = get_remote_browser(
            command_executor=selenium_url, desired_capabilities=desired_caps
        )

    message = "Session started!"
    highlight_print("browser", message, "initialization", "info", logger)
    print("")

    return browser


def proxy_authentication(browser, logger, proxy_username, proxy_ritetag_password):
    """ Authenticate proxy using popup alert window """
    try:
        # sleep(1) is enough, sleep(2) is to make sure we
        # give time to the popup windows
        sleep(2)
        alert_popup = browser.switch_to_alert()
        alert_popup.send_keys(
            "{username}{tab}{ritetag_password}{tab}".format(
                username=proxy_username,
                tab=Keys.TAB,
                ritetag_password=proxy_ritetag_password,
            )
        )
        alert_popup.accept()
    except Exception:
        logger.warn("Unable to proxy authenticate")


def close_browser(browser, threaded_session, logger):
    with interruption_handler(threaded=threaded_session):
        # delete cookies
        try:
            browser.delete_all_cookies()
        except Exception as exc:
            if isinstance(exc, WebDriverException):
                logger.exception(
                    "Error occurred while deleting cookies "
                    "from web browser!\n\t{}".format(str(exc).encode("utf-8"))
                )

        # close web browser
        try:
            browser.quit()
        except Exception as exc:
            if isinstance(exc, WebDriverException):
                logger.exception(
                    "Error occurred while "
                    "closing web browser!\n\t{}".format(str(exc).encode("utf-8"))
                )


def retry(max_retry_count=3, start_page=None):
    """Decorator which refreshes the page and tries to execute the function again.
    Use it like that: @retry() => the '()' are important because its a decorator with params."""

    def real_decorator(org_func):
        def wrapper(*args, **kwargs):
            browser = None

            # try to find instance of a browser in the arguments
            # all webdriver classes (chrome, firefox, ...) inherit from Remote
            # class
            for arg in args:
                if not isinstance(arg, Remote):
                    continue

                browser = arg
                break

            else:
                for _, value in kwargs.items():
                    if not isinstance(value, Remote):
                        continue

                    browser = value
                    break

            if not browser:
                print("not able to find browser in parameters!")
                return org_func(*args, **kwargs)

            if max_retry_count == 0:
                print("max retry count is set to 0, this function is useless right now")
                return org_func(*args, **kwargs)

            # get current page if none is given
            if not start_page:
                start_page = browser.current_url

            rv = None
            retry_count = 0
            while True:
                try:
                    rv = org_func(*args, **kwargs)
                    break
                except Exception as e:
                    # TODO: maybe handle only certain exceptions here
                    retry_count += 1

                    # if above max retries => throw original exception
                    if retry_count > max_retry_count:
                        raise e

                    rv = None

                    # refresh page
                    browser.get(start_page)

            return rv

        return wrapper

    return real_decorator


class custom_browser(Remote):
    """Custom browser instance for manupulation later on"""

    def find_element_by_xpath(self, *args, **kwargs):
        """example usage of hooking into built in functions"""
        rv = super(custom_browser, self).find_element_by_xpath(*args, **kwargs)
        return rv

    def wait_for_valid_connection(self, username, logger):
        counter = 0
        while True and counter < 10:
            sirens_wailing, emergency_state = emergency_exit(self, username, logger)
            if sirens_wailing and emergency_state == "not connected":
                print("brNo1")
                logger.warning("there is no valid connection")
                counter += 1
                sleep(60)
            else:
                break

    def wait_for_valid_authorization(self, username, logger):
        # save current page
        current_url = get_current_url(self)

        # stuck on invalid auth
        auth_method = "activity counts"
        counter = 0
        while True and counter < 10:
            login_state = check_authorization(self, username, auth_method, logger)
            if login_state is False:
                print("brNo2")
                logger.warning("not logged in")
                counter += 1
                sleep(60)
            else:
                break

        # return to original page
        web_address_navigator(self, current_url)


def get_remote_browser(command_executor, desired_capabilities):
    browser = webdriver.Remote(
        command_executor=command_executor, desired_capabilities=desired_capabilities
    )

    return browser  # convert_selenium_browser(browser)


def convert_selenium_browser(driver):
    """Changed the class to our custom class"""
    driver.__class__ = custom_browser
    return driver
