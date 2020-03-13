#!/bin/sh
''''exec python -u -- "$0" ${1+"$@"} # '''
# vi: syntax=python

from collections import defaultdict
from decimal import Decimal as D
from json import loads as readjson
from random import choice, random, choices
from subprocess import Popen, PIPE, TimeoutExpired
import os
import re
import sys
import time

import requests
from requests.exceptions import ReadTimeout, ConnectionError

from lib import data
from lib.data import init_db


REGEX_MP_EXITING = re.compile(r"\s*Exiting... \((?P<reason>.*?)\)")

BLACKLIST = re.compile("|".join((
    "relig",
    "christ",
    "kids",
    "podcast",
    "sports",
    "talk",
    "children",
    "catho",
    "calmradio",
    "holiday",
    "christmas",
)), re.IGNORECASE)


def wait_for_connection():
    step = 1
    while os.system("ping -c 1 radiotime.com"):
        time.sleep(step)
        step *= 1.5
        if 60 < step:
            raise RuntimeError("Connection broken")


EXITING_REASONS = {
        "End of file": {"exit": False, "store": False,
                        "trigger": wait_for_connection},
        "Suspended":   {"exit": False, "store": True,
                        "trigger": wait_for_connection},
        "Quit":        {"exit": False, "store": True},
        "Control-C":   {"exit": True,  "store": False},
        None:          {"exit": False, "store": True},
}

HTTP_SESSION = requests.Session()
KEY_URL = {}

HOME      =  "http://opml.radiotime.com/"
BROWSE    =  HOME + "Browse.ashx"
DESCRIBE  =  HOME + "Describe.ashx"
TUNE      =  HOME + "Tune.ashx"


def retry(function, tries=10):
    last_error = None
    for attempt in range(tries):
        if attempt > 0:
            time.sleep(5)
        try:
            return function()
        except (ConnectionError, ReadTimeout) as error:
            print("Retrying connection")
            last_error = error
    else:
        raise last_error


def extract_urls(element, urls=None):
    if urls is None:
        urls = set()
    if isinstance(element, list):
        for item in element:
            extract_urls(item, urls)
    elif isinstance(element, dict):
        if "URL" in element:
            urls.add(element["URL"])
        elif "url" in element:
            urls.add(element["url"])
        elif "children" in element:
            extract_urls(element["children"], urls)
        elif "body" in element:
            extract_urls(element["body"], urls)
        elif "text" in element:
            return urls
        else:
            raise NotImplementedError("Not implemented!: %s" % element)
    else:
        raise NotImplementedError("Not implemented!: %s" % element)
    return urls


def get_json(url=BROWSE, params=[]):
    params = dict(params)
    params["render"] = "json"
    response = retry(lambda :HTTP_SESSION.get(url, params=params))
    try:
        json = response.json()
    except:
        if response.status_code == 403:
            raise RuntimeError("Queries limit reached.")
        else:
            raise NotImplementedError(response.text)
    return response.text


def get_urls(url=BROWSE, params=[]):
    json = data.get_url_cache(url + str(params))
    if not json:
        json = get_json(url, params)
        data.set_url_cache(url + str(params), json)
    json = readjson(json)

    try:
        title = json["head"]["title"]
    except KeyError:
        title = str(json.get("head", "\o/"))
    body = json["body"]
    urls = extract_urls(body)
    return title, urls


def weighted_choice(weights_options, entropy=1):
    if not weights_options:
        return None

    weights, options = zip(*weights_options)
    total = sum(weights)
    weights = [float(weight / total) ** (1 / entropy)
               for weight in weights]
    total = sum(weights)
    weights_options = list(zip(weights, options))
    accumulated = 0
    weight, option = choices(weights_options, weights)[0]
    print("%3d%%+" % ((weight / total) * 100), end=" ")
    return option


def choose_random(node=None, category=None, path=None, jump=False, entropy=1):
    if jump:
        print("\n\n# Jump (403)")
        url = weighted_choice(data.get_all_weights_urls(nostring=HOME),
                              entropy=entropy * 2)
        return [url]

    if path is None:
        path = []

    if node is None:
        try:
            title, urls = get_urls(params=(("c", category),))
        except RuntimeError:
            # Jump because too many requests.
            return choose_random(node, category, path, jump=True,
                                 entropy=entropy)
    else:
        if not "://" in node:
            node = "http://opml.radiotime.com/Browse.ashx?id=%s" % node
        path.append(node)
        try:
            title, urls = get_urls(node)
        except RuntimeError:
            # Jump because too many requests.
            return choose_random(node, category, path, jump=True,
                                 entropy=entropy)

    if title == "Browse":
        print("> %s(%.1f)" % (title, entropy))
    else:
        print("> %s" % title)
    weights_urls = data.get_weights_urls(urls)
    url = weighted_choice(weights_urls, entropy=entropy)
    if url is None:
        print("Empty list, restart.")
        path.append(None)
        return path

    if BLACKLIST.search(title) or BLACKLIST.search(url):
        print("** Blacklisted")
        path.append(None)
        return path
    elif HOME in url:
        return choose_random(url, path=path, entropy=entropy)
    else:
        path.append(url)
        return path


def play(url):
    """
    returns the time the user spent playing
    """
    command = "streamplayer '%s'" % url
    print("=> %s" % command)
    start_time = time.time()
    proc = Popen(command, shell=True, stderr=PIPE)
    store = True
    exit = False
    reason = None

    waited = 0
    step = 10
    while True:
        try:
            proc.wait(step)
        except KeyboardInterrupt:
            reason = "Control-C"
            break
        except TimeoutExpired:
            waited += step
        else:
            break

    end_time = time.time()
    runtime = end_time - start_time
    if (waited + step) < runtime:
        suspended = runtime - waited + step / 2
        print(f"Suspended for ~{round(suspended / 60):.0f} minutes")
        runtime = waited + step / 2
        reason = "Suspended"

    stderr = proc.stderr.readlines()
    if not reason:
        for line in stderr:
            line = line.decode()
            exiting = REGEX_MP_EXITING.match(line)
            if "Playlist parsing disabled for security reasons." in line:
                print("Parsing playlist: %s" % url)
                response = retry(lambda :HTTP_SESSION.get(url))
                text = response.text
                try:
                    url = re.findall(r"((?:http|ftp)s?.*?$)", text, re.M)[-1]
                except IndexError:
                    raise ValueError("Could not find url in:\n%s" % text)
                return play(url)
            if "Unsupported http 302 redirect to https protocol" in line:
                url = url.replace("http://", "https://")
                return play(url)
            if exiting:
                reason = exiting.group("reason")

    if reason is None:
        print("Found no reason:")
        for line in stderr:
            print("  %s" % line.rstrip())

    state = EXITING_REASONS[reason]
    exit = state["exit"]
    store = state["store"]
    state.get("trigger", int)()


    if runtime < 5:
        print("Reason: %s, after %f seconds" % (reason, runtime))
        store = True

    if store:
        if runtime < 60:
            runtime = 0
        strengh = runtime
    else:
        strengh = None

    return exit, strengh


def main():
    init_db()
    history = {}

    print("Keybinds:")
    print("  <q>: jump next station, learn new weights")
    print("  <Control-C>: exit without storing")
    print("  <Enter>: jump next station without storing")

    data.clean_cache()
    data.print_report()
    errorcode = 0

    entropy = .5
    while True:
        print("")
        choosed_time = time.time()
#         path = choose_random(category="music", entropy=entropy)
#         path = choose_random(category="local", entropy=entropy)
#         path = choose_random("r100325", entropy=entropy)
#         path = choose_random("r0", entropy=entropy)  # by location
#         path = choose_random(entropy=1, entropy=entropy)
        path = choose_random(entropy=entropy)  # any, all
        url = path[-1]
        history = {k: v
                   for k, v in history.items()
                   if v > (time.time() - 60 * 60 * 1)}
        if url is None:
            strengh = 0
            exit = False
        elif url in history:
            print("History hit")
            continue
        else:
            exit, strengh = play(url)
            history[url] = time.time()

        if exit:
            print("Closing")
            break
        if strengh is not None:
            print("Strengh: %d" % strengh)
            data.update_path(path, strengh)

        age = time.time() - choosed_time
        if age <= 120:
            entropy += .5
        else:
            entropy = 1

    return errorcode


if __name__ == "__main__":
    sys.exit(main())
