import datetime
import json
import os
import re
import time

import boto3
import requests
from selenium import webdriver


class Chrome:
    def headless_lambda(self):
        options = webdriver.ChromeOptions()
        options.binary_location = "/opt/headless/python/bin/headless-chromium"
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--single-process")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280x1696")
        options.add_argument("--disable-application-cache")
        options.add_argument("--disable-infobars")
        options.add_argument("--hide-scrollbars")
        options.add_argument("--enable-logging")
        options.add_argument("--log-level=0")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--homedir=/tmp")
        options.add_argument("--disable-dev-shm-usage")

        options.add_experimental_option(
            "prefs",
            {
                "download.default_directory": "/tmp",
                "plugins.always_open_pdf_externally": True,
            },
        )

        driver = webdriver.Chrome(
            executable_path="/opt/headless/python/bin/chromedriver",
            chrome_options=options,
        )
        return driver


ssm_client = boto3.client("ssm")


def get_parameter_store(name, withdecryption=True):
    response = ssm_client.get_parameter(Name=name, WithDecryption=withdecryption)
    return json.loads(response["Parameter"]["Value"])


def lambda_handler(event, context):
    chrome = Chrome()
    driver = chrome.headless_lambda()
    login_url = "https://www.k.kyoto-u.ac.jp/student/la/top"
    driver.get(login_url)

    ECS_ACCOUNT = get_parameter_store("/kulasis/crediential", True)
    CHANNEL_IDS = get_parameter_store("/slack/kuinfo2019/channel_id", False)
    # CHANNEL_ID_KULASIS_LA = CHANNEL_IDS["channel_id_test"]
    # CHANNEL_ID_KULASIS_UT = CHANNEL_IDS["channel_id_test"]
    CHANNEL_ID_KULASIS_LA = CHANNEL_IDS["channel_id_kulasis_la"]
    CHANNEL_ID_KULASIS_UT = CHANNEL_IDS["channel_id_kulasis_ut"]
    # CHANNEL_ID_PANDA = CHANNEL_IDS["channel_id_test"]
    CHANNEL_ID_PANDA = CHANNEL_IDS["channel_id_panda"]
    SLACK_API_URLS = get_parameter_store("/slack/api", False)
    HISTORY_API_URL = SLACK_API_URLS["history_api_url"]
    POST_API_URL = SLACK_API_URLS["post_api_url"]
    UPLOAD_API_URL = SLACK_API_URLS["upload_api_url"]
    TOKEN = get_parameter_store("/slack/kuinfo2019/credentials/bot_token", True)[
        "bot_token"
    ]

    ## KULASIS

    driver.find_element_by_id("username").send_keys(ECS_ACCOUNT["ecs-id"])
    driver.find_element_by_id("password").send_keys(ECS_ACCOUNT["password"])
    driver.find_element_by_name("_eventId_proceed").click()

    # 大学院入学前後の暫定処理
    if "shibboleth_login" in driver.current_url:
        driver.find_element_by_class_name("login-button").click()

    ##### 全学生向け共通掲示板

    # 重複確認

    payload = {"token": TOKEN, "channel": CHANNEL_ID_KULASIS_LA}

    dt_now = datetime.datetime.now()

    response = requests.get(HISTORY_API_URL, params=payload)
    json_data = response.json()
    history_link_list = []
    divide_time = (datetime.datetime.now() - datetime.timedelta(hours=24)).timestamp()

    print("-----slack履歴確認開始-----")

    for item in json_data["messages"]:
        if "bot_id" in item and float(item["ts"]) > divide_time:
            if "subtype" in item and item["subtype"] == "bot_message":
                try:
                    print(
                        item["attachments"][0]["fallback"],
                        item["attachments"][0]["title_link"],
                    )
                    history_link_list.append(item["attachments"][0]["title_link"])
                except:
                    print("*****")

    print("-----slack履歴確認終了-----")
    print(history_link_list)

    new_list = []

    # 全学生向け共通掲示板Information
    print("-----全学生向け共通掲示板Information-----")

    today = (
        str(dt_now.year)
        + "/"
        + "{:02d}".format(dt_now.month)
        + "/"
        + "{:02d}".format(dt_now.day)
    )

    information_details_link = []
    information_title = []
    info_table = driver.find_element_by_class_name(
        "panel-info"
    ).find_elements_by_tag_name("tr")

    for item in info_table:
        if today in item.text:
            information_details_link.append(
                item.find_element_by_tag_name("a").get_attribute("href")
            )
            information_title.append(item.find_element_by_tag_name("a").text)

    for link, title in zip(information_details_link, information_title):
        if "https://www.k.kyoto-u.ac.jp/student/la/information_detail" in link:
            driver.get(link)
            table_item = driver.find_element_by_class_name(
                "table"
            ).find_elements_by_tag_name("tr")
            text = table_item[3].find_elements_by_tag_name("td")[0].text
        else:
            text = link

        if not link in history_link_list:
            new_list += [title]

            if (
                not "https://www.k.kyoto-u.ac.jp/student/la/information_detail" in link
            ) or (table_item[4].find_elements_by_tag_name("td")[0].text == ""):
                data = {
                    "token": TOKEN,
                    "channel": CHANNEL_ID_KULASIS_LA,
                    "username": u"全学生向け共通掲示板 Information",
                    "attachments": json.dumps(
                        [
                            {
                                "fallback": title,
                                "title": title,
                                "title_link": link,
                                "color": "#36c5f0",
                                "fields": [
                                    {
                                        "value": text,
                                    }
                                ],
                                "ts": datetime.datetime.now().timestamp(),
                            }
                        ]
                    ),
                    "icon_emoji": u":books:",
                }
            else:
                attachment_file = (
                    table_item[4]
                    .find_elements_by_tag_name("td")[0]
                    .find_element_by_tag_name("a")
                    .get_attribute("href")
                )
                data = {
                    "token": TOKEN,
                    "channel": CHANNEL_ID_KULASIS_LA,
                    "username": u"全学生向け共通掲示板 Information",
                    "attachments": json.dumps(
                        [
                            {
                                "fallback": title,
                                "title": title,
                                "title_link": link,
                                "color": "#36c5f0",
                                "fields": [
                                    {
                                        "value": text,
                                    }
                                ],
                                "actions": [
                                    {
                                        "type": "button",
                                        "text": "添付ファイルを表示",
                                        "url": attachment_file,
                                    }
                                ],
                                "ts": datetime.datetime.now().timestamp(),
                            }
                        ]
                    ),
                    "icon_emoji": u":books:",
                }

            requests.post(POST_API_URL, data=data)

    if new_list == []:
        print("新しいお知らせはありません。")
    else:
        for item in new_list:
            print(item)

    ##### 工学部

    # 重複確認

    payload = {"token": TOKEN, "channel": CHANNEL_ID_KULASIS_UT}

    dt_now = datetime.datetime.now()

    response = requests.get(HISTORY_API_URL, params=payload)
    json_data = response.json()
    history_link_list = []
    divide_time = (datetime.datetime.now() - datetime.timedelta(hours=24)).timestamp()

    print("-----slack履歴確認開始-----")

    for item in json_data["messages"]:
        if "bot_id" in item and float(item["ts"]) > divide_time:
            if "subtype" in item and item["subtype"] == "bot_message":
                try:
                    print(
                        item["attachments"][0]["fallback"],
                        item["attachments"][0]["title_link"],
                    )
                    # history_list.append(item["attachments"][0]["fallback"])
                    history_link_list.append(item["attachments"][0]["title_link"])
                except:
                    print("*****")

    print("-----slack履歴確認終了-----")
    print(history_link_list)

    new_list = []

    # 工学部掲示板
    driver.command_executor._commands["send_command"] = (
        "POST",
        "/session/$sessionId/chromium/send_command",
    )
    params = {
        "cmd": "Page.setDownloadBehavior",
        "params": {"behavior": "allow", "downloadPath": "/tmp"},
    }
    driver.execute("send_command", params=params)

    print("-----工学部掲示板-----")

    today = (
        str(dt_now.year) + "/" + str(dt_now.month) + "/" + "{:02d}".format(dt_now.day)
    )

    notice_t = "https://www.k.kyoto-u.ac.jp/student/u/t/notice/general"
    driver.get(notice_t)

    report_details_link = []
    table = driver.find_element_by_class_name(
        "no_scroll_list"
    ).find_elements_by_tag_name("tr")

    for item in table[2:-2]:
        target = item.find_elements_by_tag_name("td")[1].text.split("/")
        if (
            (target[0] == "情報学" or target[0] == "全")
            and (target[2] == "全" or ("4" in target[2]))
        ) and (today in item.find_elements_by_tag_name("td")[3].text):
            report_details_link.append(
                item.find_element_by_tag_name("a").get_attribute("href")
            )

    for link in report_details_link:
        driver.get(link)
        table_item = driver.find_element_by_class_name(
            "relaxed_table"
        ).find_elements_by_tag_name("tr")
        title = table_item[2].find_elements_by_tag_name("td")[1].text
        text = table_item[4].find_elements_by_tag_name("td")[1].text

        if not link in history_link_list:
            new_list += [title]

            if "ファイルを表示" in driver.find_element_by_class_name("relaxed_table").text:
                attachment_file = (
                    table_item[5]
                    .find_elements_by_tag_name("td")[1]
                    .find_element_by_tag_name("a")
                    .get_attribute("href")
                )
                data = {
                    "token": TOKEN,
                    "channel": CHANNEL_ID_KULASIS_UT,
                    "username": u"工学部教務・厚生情報",
                    "attachments": json.dumps(
                        [
                            {
                                "fallback": title,
                                "title": title,
                                "title_link": link,
                                "color": "#2eb886",
                                "fields": [
                                    {
                                        "value": text,
                                    }
                                ],
                                "actions": [
                                    {
                                        "type": "button",
                                        "text": "ファイルを表示",
                                        "url": attachment_file,
                                    }
                                ],
                                "ts": datetime.datetime.now().timestamp(),
                            }
                        ]
                    ),
                    "icon_emoji": u":books:",
                }
                requests.post(POST_API_URL, data=data)
                try:
                    driver.get(attachment_file)
                    time.sleep(3)
                    for file_in_tmp in os.listdir("/tmp/"):
                        base, ext = os.path.splitext(file_in_tmp)
                        if ext == ".pdf":
                            files = {"file": open("/tmp/{}".format(file_in_tmp), "rb")}
                            param = {
                                "token": TOKEN,
                                "channels": CHANNEL_ID_KULASIS_UT,
                                "username": u"工学部教務・厚生情報",
                            }
                            requests.post(
                                url=UPLOAD_API_URL,
                                params=param,
                                files=files,
                            )
                            os.remove("/tmp/{}".format(file_in_tmp))
                except Exception as e:
                    print("ERROR has occured:", e.args)

            else:
                data = {
                    "token": TOKEN,
                    "channel": CHANNEL_ID_KULASIS_UT,
                    "username": u"工学部教務・厚生情報",
                    "attachments": json.dumps(
                        [
                            {
                                "fallback": title,
                                "title": title,
                                "title_link": link,
                                "color": "#2eb886",
                                "fields": [
                                    {
                                        "value": text,
                                    }
                                ],
                                "ts": datetime.datetime.now().timestamp(),
                            }
                        ]
                    ),
                    "icon_emoji": u":books:",
                }
                requests.post(
                    url=UPLOAD_API_URL,
                    params=param,
                    files=files,
                )

    if new_list == []:
        print("新しいお知らせはありません。")
    else:
        for item in new_list:
            print(item)

    ## PANDA

    payload = {"token": TOKEN, "channel": CHANNEL_ID_PANDA}
    response = requests.get(HISTORY_API_URL, params=payload)
    json_data = response.json()
    kadai_history = []
    for item in json_data["messages"]:
        if "subtype" in item and item["subtype"] == "bot_message":
            # 以前の投稿にattachmentsないとエラーになる
            kadai_history.append(
                (item["attachments"][0]["footer"], item["attachments"][0]["ts"])
            )

    login_url = "https://panda.ecs.kyoto-u.ac.jp/cas/login?service=https%3A%2F%2Fpanda.ecs.kyoto-u.ac.jp%2Fsakai-login-tool%2Fcontainer"
    driver.get(login_url)
    driver.find_element_by_id("username").send_keys(ECS_ACCOUNT["ecs-id"])
    driver.find_element_by_id("password").send_keys(ECS_ACCOUNT["password"])
    driver.find_element_by_name("submit").click()

    tabInfo = {}
    for elementCollection in driver.find_elements_by_css_selector(".fav-sites-entry"):
        lectureID = elementCollection.find_element_by_css_selector("a").get_attribute(
            "data-site-id"
        )
        lectureName = (
            elementCollection.find_element_by_css_selector("div")
            .find_element_by_css_selector("a")
            .get_attribute("title")
        )
        lectureLink = (
            elementCollection.find_element_by_css_selector("div")
            .find_element_by_css_selector("a")
            .get_attribute("href")
        )
        tabInfo[lectureID] = {"lectureName": lectureName, "lectureLink": lectureLink}

    my_json = "https://panda.ecs.kyoto-u.ac.jp/direct/assignment/my.json"
    driver.get(my_json)
    json_text = driver.find_element_by_css_selector("pre").get_attribute("innerText")
    json_response = json.loads(json_text)
    for item in json_response["assignment_collection"]:
        lecture_name = tabInfo[item["context"]]["lectureName"]
        lecture_link = tabInfo[item["context"]]["lectureLink"]
        title = item["title"]
        dueDate_dt = datetime.datetime.fromtimestamp(item["dueTime"]["epochSecond"])
        dueDate = dueDate_dt.strftime("%Y/%m/%d %H:%M")
        timeLastModified = item["timeLastModified"]["epochSecond"]
        fallback_text = lecture_name + "（締切：" + dueDate + "）"
        instructions = re.sub(r"<.+?>", "", item["instructions"])
        kadai_id = item["id"]

        if (kadai_id, timeLastModified) in kadai_history:
            continue
        if dueDate_dt < dt_now:
            continue

        data = {
            "token": TOKEN,
            "username": u"PandA課題",
            "channel": CHANNEL_ID_PANDA,
            "icon_emoji": u":panda_face:",
            "attachments": json.dumps(
                [
                    {
                        "fallback": fallback_text,
                        "title": title,
                        "title_link": lecture_link,
                        "fields": [
                            {
                                "title": "講義名",
                                "value": lecture_name,
                            },
                            {
                                "title": "締め切り",
                                "value": dueDate,
                            },
                            {
                                "title": "課題内容",
                                "value": instructions,
                            },
                        ],
                        "footer": item["id"],
                        "ts": timeLastModified,
                    }
                ]
            ),
        }
        requests.post(POST_API_URL, data=data)

    driver.quit()
    return True
