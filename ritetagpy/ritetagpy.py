import random
import os
import signal
import logging
import pickle
import re

import sqlite3

from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import WebDriverException
import time
import unittest

from .time_util import sleep

from .util import parse_cli_args
from .util import check_authorization

# from .exceptions import RitetagPyError
from socialcommons.file_manager import get_logfolder
from socialcommons.file_manager import get_workspace

# from .login_util import dismiss_notification_offer

from socialcommons.browser import set_selenium_local_session
from socialcommons.exceptions import SocialPyError
from .settings import Settings
import traceback

from .database_engine import get_database

import configparser

HOME = "/Users/ishandutta2007"
CWD = HOME + "/Documents/Projects/RitetagPy"

config = configparser.ConfigParser()
config.read(CWD + "/config.txt")

CHROME_DRIVER_PATH = CWD + "/chromedriver"

from pprint import pprint as pp

from colorama import Fore

import base64
import json
import requests

from base64 import b64encode


class RitetagPy:
    def __init__(self, fb_userid=None, fb_password=None, tags_to_check=[]):
        if fb_userid and fb_password:
            self.fb_userid = fb_userid
            self.fb_password = fb_password
        else:
            cli_args = parse_cli_args()
            self.fb_userid = cli_args.fb_userid
            self.fb_password = cli_args.fb_password

        self.multi_logs = True
        self.logfolder = get_logfolder(self.fb_userid, self.multi_logs, Settings)
        self.logger = self.get_ritetagpy_logger()
        # self.logfolder = HOME + '/RitetagPy/logs/' + self.fb_userid
        self.use_api = False
        # for mhp in memory_hogging_processes:
        #     self.check_kill_process(mhp)
        self.browser = None  # Initiated later
        self.page_delay = 25
        self.use_firefox = False
        self.bypass_suspicious_attempt = False
        self.bypass_with_mobile = False
        self.disable_image_load = False
        self.browser_profile_path = None
        self.headless_browser = False
        self.proxy_chrome_extension = None
        self.proxy_username = None
        self.proxy_fb_password = None
        self.proxy_address = None
        self.proxy_port = None
        self.use_stored_metadata = False
        self.latest_term = None
        self.clsosing_line = ""
        self.launch = True
        self.tags_to_check = tags_to_check
        Settings.profile["name"] = self.fb_userid

        if not get_workspace(Settings):
            raise SocialPyError("Oh no! I don't have a workspace to work at :'(")

        get_database(Settings, make=True)
        if self.use_api == False:
            self.set_selenium_local_session(Settings)

    def get_ritetagpy_logger(self):
        logger = logging.getLogger(self.fb_userid)
        logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler("{}general.log".format(self.logfolder))
        file_handler.setLevel(logging.DEBUG)
        extra = {"fb_userid": self.fb_userid}
        logger_formatter = logging.Formatter(
            "%(levelname)s [%(asctime)s] [RitetagPy:%(fb_userid)s]  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(logger_formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.DEBUG)
        console_handler.setFormatter(logger_formatter)
        logger.addHandler(console_handler)

        logger = logging.LoggerAdapter(logger, extra)
        return logger

    def set_selenium_local_session(self, Settings):
        self.browser, err_msg = set_selenium_local_session(
            self.proxy_address,
            self.proxy_port,
            self.proxy_chrome_extension,
            self.headless_browser,
            self.use_firefox,
            self.browser_profile_path,
            # Replaces
            # browser User
            # Agent from
            # "HeadlessChrome".
            self.disable_image_load,
            self.page_delay,
            self.logger,
            Settings,
        )
        if len(err_msg) > 0:
            raise SocialPyError(err_msg)

    def login_browser(self):
        try:
            self.browser.get("https://ritetag.com/sign/facebook")
            sleep(10)

            cookie_loaded = False

            # try to load cookie from username
            try:
                for cookie in pickle.load(
                    open(
                        "{0}{1}_cookie.pkl".format(self.logfolder, self.fb_userid), "rb"
                    )
                ):
                    self.browser.add_cookie(cookie)
                    cookie_loaded = True
            except (WebDriverException, OSError, IOError):
                self.logger.info("Cookie file not found, creating cookie...")

            if cookie_loaded:
                self.logger.info(
                    "Issue with cookie for user {}. Creating "
                    "new cookie...".format(self.fb_userid)
                )

            input_fb_userid = self.browser.find_element_by_xpath("//input[@id='email']")
            (
                ActionChains(self.browser)
                .move_to_element(input_fb_userid)
                .click()
                .send_keys(self.fb_userid)
                .perform()
            )
            sleep(2)

            input_fb_password = self.browser.find_element_by_xpath(
                "//input[@id='pass']"
            )
            (
                ActionChains(self.browser)
                .move_to_element(input_fb_password)
                .click()
                .send_keys(self.fb_password)
                .perform()
            )
            sleep(2)

            (
                ActionChains(self.browser)
                .move_to_element(input_fb_password)
                .click()
                .send_keys(Keys.ENTER)
                .perform()
            )
            sleep(10)

        except Exception as e:
            self.logger.error(e)
            if self.browser:
                self.browser.quit()
            return False

        if "https://ritekit.com/accounts" in self.browser.current_url:
            self.logger.info("Loggedin by entering fb_userid fb_password")
            return True
        else:
            self.logger.error("Something went wrong while Logging in")
            return False

    def update_color_in_db(self, term, col, is_banned, logger):
        try:
            db, id = get_database(Settings)
            conn = sqlite3.connect(db)

            with conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()

                cur.execute(
                    "SELECT * FROM termColor WHERE term=:name_var", {"name_var": term}
                )
                data = cur.fetchone()
                upload_data = dict(data) if data else None

                if upload_data is None:
                    cur.execute(
                        "INSERT INTO termColor (term, col, is_banned, modified) VALUES (?, ?, ?, STRFTIME('%Y-%m-%d %H:%M:%S', 'now', 'localtime'))",
                        (term, col, is_banned),
                    )
                else:
                    sql = "UPDATE termColor set col = ?, is_banned = ?, modified = STRFTIME('%Y-%m-%d %H:%M:%S', 'now', 'localtime') WHERE term = ?"
                    cur.execute(sql, (col, is_banned, term))

                conn.commit()

        except Exception as exc:
            logger.error(
                "Dap! Error occurred with update color:\n\t{}".format(
                    str(exc).encode("utf-8")
                )
            )

        finally:
            if conn:
                conn.close()

    def get_reports(self, term):
        print(term, ":")
        url = "https://ritetag.com/hashtag-stats/{}".format(term)
        self.browser.get(url)
        sleep(15)
        ps = self.browser.find_elements_by_tag_name("p")
        while len(ps) < 4:
            sleep(30)
            ps = self.browser.find_elements_by_tag_name("p")
        col = 0
        is_banned = 0
        ps = ps[1:3]
        for i, p in enumerate(ps):
            print(i, p.text)
            if i == 1:
                if "not banned" not in p.text:
                    is_banned = 1
                    break
            elif i == 0:
                if "Use this hashtag to get seen now" in p.text:
                    col = 3
                elif "Use this hashtag to get seen over time" in p.text:
                    col = 2
                elif (
                    "Do not use this hashtag, very few people are following it"
                    in p.text
                ):
                    col = 1
            else:
                pass

        self.update_color_in_db(term, col, is_banned, self.logger)

    def run(self):
        try:
            self.login_browser()
            for tag in self.tags_to_check:
                self.get_reports(tag)
        except Exception as e:
            print(e)
        self.browser.quit()
