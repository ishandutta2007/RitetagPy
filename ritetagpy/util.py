from math import ceil
import signal
from platform import system
from platform import python_version
from subprocess import call
import sqlite3
from contextlib import contextmanager
from argparse import ArgumentParser

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.by import By

from .time_util import sleep
from .time_util import sleep_actual
from .database_engine import get_database
from .settings import Settings

from selenium.common.exceptions import WebDriverException
from selenium.common.exceptions import TimeoutException


def parse_cli_args():
    AP_kwargs = dict(
        prog="RitetagPy",
        description="Parse RitetagPy constructor's arguments",
        epilog="And that's how you'd pass arguments by CLI..",
        conflict_handler="resolve",
    )
    if python_version() < "3.5":
        parser = CustomizedArgumentParser(**AP_kwargs)
    else:
        AP_kwargs.update(allow_abbrev=False)
        parser = ArgumentParser(**AP_kwargs)

    parser.add_argument("-u", "--fb_userid", help="FB account", type=str, metavar="abc")
    parser.add_argument(
        "-p", "--fb_password", help="Fb Password", type=str, metavar="123"
    )
    args, args_unknown = parser.parse_known_args()
    return args


@contextmanager
def interruption_handler(
    threaded=False,
    SIG_type=signal.SIGINT,
    handler=signal.SIG_IGN,
    notify=None,
    logger=None,
):
    """ Handles external interrupt, usually initiated by the user like
    KeyboardInterrupt with CTRL+C """
    if notify is not None and logger is not None:
        print("ihno")
        logger.warning(notify)

    if not threaded:
        original_handler = signal.signal(SIG_type, handler)

    try:
        yield

    finally:
        if not threaded:
            signal.signal(SIG_type, original_handler)


def web_address_navigator(browser, link):
    """Checks and compares current URL of web page and the URL to be
    navigated and if it is different, it does navigate"""
    current_url = get_current_url(browser)
    total_timeouts = 0
    page_type = None  # file or directory

    # remove slashes at the end to compare efficiently
    if current_url is not None and current_url.endswith("/"):
        current_url = current_url[:-1]

    if link.endswith("/"):
        link = link[:-1]
        page_type = "dir"  # slash at the end is a directory

    new_navigation = current_url != link

    if current_url is None or new_navigation:
        link = link + "/" if page_type == "dir" else link  # directory links
        # navigate faster

        while True:
            try:
                browser.get(link)
                # update server calls
                update_activity()
                sleep(2)
                break

            except TimeoutException as exc:
                if total_timeouts >= 7:
                    raise TimeoutException(
                        "Retried {} times to GET '{}' webpage "
                        "but failed out of a timeout!\n\t{}".format(
                            total_timeouts,
                            str(link).encode("utf-8"),
                            str(exc).encode("utf-8"),
                        )
                    )
                total_timeouts += 1
                sleep(2)


def highlight_print(
    username=None, message=None, priority=None, level=None, logger=None
):
    """ Print headers in a highlighted style """
    # can add other highlighters at other priorities enriching this function

    # find the number of chars needed off the length of the logger message
    output_len = 28 + len(username) + 3 + len(message) if logger else len(message)
    show_logs = Settings.show_logs

    if priority in ["initialization", "end"]:
        # OOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOOO
        # E.g.:          Session started!
        # oooooooooooooooooooooooooooooooooooooooooooooooo
        upper_char = "O"
        lower_char = "o"

    elif priority == "login":
        # ................................................
        # E.g.:        Logged in successfully!
        # ''''''''''''''''''''''''''''''''''''''''''''''''
        upper_char = "."
        lower_char = "'"

    elif priority == "feature":  # feature highlighter
        # ________________________________________________
        # E.g.:    Starting to interact by users..
        # """"""""""""""""""""""""""""""""""""""""""""""""
        upper_char = "_"
        lower_char = '"'

    elif priority == "user iteration":
        # ::::::::::::::::::::::::::::::::::::::::::::::::
        # E.g.:            User: [1/4]
        upper_char = ":"
        lower_char = None

    elif priority == "post iteration":
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # E.g.:            Post: [2/10]
        upper_char = "~"
        lower_char = None

    elif priority == "workspace":
        # ._. ._. ._. ._. ._. ._. ._. ._. ._. ._. ._. ._.
        # E.g.: |> Workspace in use: "C:/Users/El/InstaPy"
        upper_char = " ._. "
        lower_char = None

    if upper_char and (show_logs or priority == "workspace"):
        print("\n{}".format(upper_char * int(ceil(output_len / len(upper_char)))))

    if level == "info":
        if logger:
            logger.info(message)
        else:
            print(message)

    elif level == "warning":
        if logger:
            logger.warning(message)
        else:
            print(message)

    elif level == "critical":
        if logger:
            logger.critical(message)
        else:
            print(message)

    if lower_char and (show_logs or priority == "workspace"):
        print("{}".format(lower_char * int(ceil(output_len / len(lower_char)))))


def ping_server(host, logger):
    """
    Return True if host (str) responds to a ping request.
    Remember that a host may not respond to a ping (ICMP) request even if
    the host name is valid.
    """
    logger.info("Pinging '{}' to check the connectivity...".format(str(host)))

    # ping command count option as function of OS
    param = "-n" if system().lower() == "windows" else "-c"
    # building the command. Ex: "ping -c 1 google.com"
    command = " ".join(["ping", param, "1", str(host)])
    need_sh = False if system().lower() == "windows" else True

    # pinging
    ping_attempts = 2
    connectivity = None

    while connectivity is not True and ping_attempts > 0:
        connectivity = call(command, shell=need_sh) == 0

        if connectivity is False:
            logger.warning(
                "Pinging the server again!\t~total attempts left: {}".format(
                    ping_attempts
                )
            )
            ping_attempts -= 1
            sleep(5)

    if connectivity is False:
        logger.critical("There is no connection to the '{}' server!".format(host))
        return False

    return True


def emergency_exit(browser, username, logger):
    """ Raise emergency if the is no connection to server OR if user is not
    logged in """
    using_proxy = True if Settings.connection_type == "proxy" else False
    # ping the server only if connected directly rather than through a proxy
    if not using_proxy:
        server_address = "instagram.com"
        connection_state = ping_server(server_address, logger)
        if connection_state is False:
            return True, "not connected"

    # check if the user is logged in
    auth_method = "activity counts"
    login_state = check_authorization(browser, username, auth_method, logger)
    if login_state is False:
        return True, "not logged in"

    return False, "no emergency"


def check_authorization(
    browser, ritetag_email, ritetag_profile_id, method, logger, notify=True
):
    """ Check if user is NOW logged in """
    if notify is True:
        logger.info("Checking if '{}' is logged in...".format(ritetag_email))

    current_url = get_current_url(browser)
    if not current_url or "https://www.publish.ritetag.com" not in current_url:
        # profile_link = 'https://publish.ritetag.com/profile/{}/tab/queue'.format(ritetag_profile_id)
        # web_address_navigator(browser, profile_link)
        return False
    return True


def click_element(browser, element, tryNum=0):
    """
    There are three (maybe more) different ways to "click" an element/button.
    1. element.click()
    2. element.send_keys("\n")
    3. browser.execute_script("document.getElementsByClassName('" +
    element.get_attribute("class") + "')[0].click()")

    I'm guessing all three have their advantages/disadvantages
    Before committing over this code, you MUST justify your change
    and potentially adding an 'if' statement that applies to your
    specific case. See the following issue for more details
    https://github.com/timgrossmann/InstaPy/issues/1232

    explaination of the following recursive function:
      we will attempt to click the element given, if an error is thrown
      we know something is wrong (element not in view, element doesn't
      exist, ...). on each attempt try and move the screen around in
      various ways. if all else fails, programmically click the button
      using `execute_script` in the browser.
      """

    try:
        # use Selenium's built in click function
        element.click()

        # update server calls after a successful click by selenium
        update_activity()

    except Exception:
        # click attempt failed
        # try something funky and try again

        if tryNum == 0:
            # try scrolling the element into view
            browser.execute_script(
                "document.getElementsByClassName('"
                + element.get_attribute("class")
                + "')[0].scrollIntoView({ inline: 'center' });"
            )

        elif tryNum == 1:
            # well, that didn't work, try scrolling to the top and then
            # clicking again
            browser.execute_script("window.scrollTo(0,0);")

        elif tryNum == 2:
            # that didn't work either, try scrolling to the bottom and then
            # clicking again
            browser.execute_script("window.scrollTo(0,document.body.scrollHeight);")

        else:
            # try `execute_script` as a last resort
            # print("attempting last ditch effort for click, `execute_script`")
            browser.execute_script(
                "document.getElementsByClassName('"
                + element.get_attribute("class")
                + "')[0].click()"
            )
            # update server calls after last click attempt by JS
            update_activity()
            # end condition for the recursive function
            return

        # update server calls after the scroll(s) in 0, 1 and 2 attempts
        update_activity()

        # sleep for 1 second to allow window to adjust (may or may not be
        # needed)
        sleep_actual(1)

        tryNum += 1

        # try again!
        click_element(browser, element, tryNum)


def get_current_url(browser):
    """ Get URL of the loaded webpage """
    try:
        current_url = browser.execute_script("return window.location.href")

    except WebDriverException:
        try:
            current_url = browser.current_url

        except WebDriverException:
            current_url = None

    return current_url


def update_activity(action="server_calls"):
    """ Record every Instagram server call (page load, content load, likes,
        comments, follows, unfollow). """
    # check action availability
    # quota_supervisor("server_calls")

    # get a DB and start a connection
    db, id = get_database()
    conn = sqlite3.connect(db)

    with conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # collect today data
        cur.execute(
            "SELECT * FROM recordActivity WHERE profile_id=:var AND "
            "STRFTIME('%Y-%m-%d %H', created) == STRFTIME('%Y-%m-%d "
            "%H', 'now', 'localtime')",
            {"var": id},
        )
        data = cur.fetchone()

        if data is None:
            # create a new record for the new day
            cur.execute(
                "INSERT INTO recordActivity VALUES "
                "(?, 0, 0, 0, 0, 1, STRFTIME('%Y-%m-%d %H:%M:%S', "
                "'now', 'localtime'))",
                (id,),
            )

        else:
            # sqlite3.Row' object does not support item assignment -> so,
            # convert it into a new dict
            data = dict(data)

            # update
            data[action] += 1
            # quota_supervisor(action, update=True)

            if action != "server_calls":
                # always update server calls
                data["server_calls"] += 1
                # quota_supervisor("server_calls", update=True)

            sql = (
                "UPDATE recordActivity set likes = ?, comments = ?, "
                "follows = ?, unfollows = ?, server_calls = ?, "
                "created = STRFTIME('%Y-%m-%d %H:%M:%S', 'now', "
                "'localtime') "
                "WHERE  profile_id=? AND STRFTIME('%Y-%m-%d %H', created) "
                "== "
                "STRFTIME('%Y-%m-%d %H', 'now', 'localtime')"
            )

            cur.execute(
                sql,
                (
                    data["likes"],
                    data["comments"],
                    data["follows"],
                    data["unfollows"],
                    data["server_calls"],
                    id,
                ),
            )

        # commit the latest changes
        conn.commit()


def explicit_wait(browser, track, ec_params, logger, timeout=35, notify=True):
    """
    Explicitly wait until expected condition validates

    :param browser: webdriver instance
    :param track: short name of the expected condition
    :param ec_params: expected condition specific parameters - [param1, param2]
    :param logger: the logger instance
    """
    # list of available tracks:
    # <https://seleniumhq.github.io/selenium/docs/api/py/webdriver_support/
    # selenium.webdriver.support.expected_conditions.html>

    if not isinstance(ec_params, list):
        ec_params = [ec_params]

    # find condition according to the tracks
    if track == "VOEL":
        elem_address, find_method = ec_params
        ec_name = "visibility of element located"

        find_by = (
            By.XPATH
            if find_method == "XPath"
            else By.CSS_SELECTOR
            if find_method == "CSS"
            else By.CLASS_NAME
        )
        locator = (find_by, elem_address)
        condition = ec.visibility_of_element_located(locator)

    elif track == "TC":
        expect_in_title = ec_params[0]
        ec_name = "title contains '{}' string".format(expect_in_title)

        condition = ec.title_contains(expect_in_title)

    elif track == "PFL":
        ec_name = "page fully loaded"
        condition = lambda browser: browser.execute_script(
            "return document.readyState"
        ) in ["complete" or "loaded"]

    elif track == "SO":
        ec_name = "staleness of"
        element = ec_params[0]

        condition = ec.staleness_of(element)

    # generic wait block
    try:
        wait = WebDriverWait(browser, timeout)
        result = wait.until(condition)

    except TimeoutException:
        if notify is True:
            logger.info(
                "Timed out with failure while explicitly waiting until {}!\n".format(
                    ec_name
                )
            )
        return False

    return result


def reload_webpage(browser):
    """ Reload the current webpage """
    browser.execute_script("location.reload()")
    update_activity()
    sleep(2)

    return True


class CustomizedArgumentParser(ArgumentParser):
    """
     Subclass ArgumentParser in order to turn off
    the abbreviation matching on older pythons.

    `allow_abbrev` parameter was added by Python 3.5 to do it.
    Thanks to @paul.j3 - https://bugs.python.org/msg204678 for this solution.
    """

    def _get_option_tuples(self, option_string):
        """
         Default of this method searches through all possible prefixes
        of the option string and all actions in the parser for possible
        interpretations.

        To view the original source of this method, running,
        ```
        import inspect; import argparse; inspect.getsourcefile(argparse)
        ```
        will give the location of the 'argparse.py' file that have this method.
        """
        return []
