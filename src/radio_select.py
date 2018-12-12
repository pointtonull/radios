#!/usr/bin/env python
#-*- coding: UTF-8 -*-

from collections import defaultdict
from decimal import Decimal as D
from json import loads as readjson
from random import choice, random
from subprocess import Popen, PIPE
import re
import sys
import time

import requests

from lib import data
from lib.data import init_db

REGEX_MP_EXITING = re.compile(r"\s*Exiting... \((?P<reason>.*?)\)")

EXITING_REASONS = {
        "End of file": {"exit": False, "store": False},
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

PROC = None


# def signal_handler(sig, frame):
#     print(sig, frame)
#     if PROC is not None:
#         PROC.kill()
#         time.sleep(1)
#         PROC.terminate()
#     sys.exit(0)

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
    response = HTTP_SESSION.get(url, params=params)
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
    except:
        title = json.get("head", "\o/")
    body = json["body"]
    urls = extract_urls(body)
    return title, urls


def weighted_choice(weights_options, randomness=0.3):
    if not weights_options:
        return None

    if random() <= (1 - randomness):
        total = sum(weight for weight, option in weights_options)
        partial = D(random()) * total
        accumulated = 0
        option = None
        for weight, option in weights_options:
            accumulated += weight
            if accumulated >= partial:
#                 print("  %d %s" % (round(weight), option))
                return option

    weight, option = choice(weights_options)
#     print("  * %s" % option)
    return option


def choose_random(node=None, category=None, path=None, jump=False):
    if jump:
        print("\n\n# Jump (403)")
        url = weighted_choice(data.get_all_weights_urls(nostring=HOME), randomness=0.1)
        return [url]

    if path is None:
        path = []

        if random() <= .10:
            print("# Jump")
            url = weighted_choice(data.get_all_weights_urls(), randomness=0.1)

            if HOME in url:
                return choose_random(url, path=[url])
            else:
                return [url]

    if node is None:
        try:
            title, urls = get_urls(params=(("c", category),))
        except RuntimeError:
            # Jump because too many requests.
            return choose_random(node, category, path, jump=True)
    else:
        if not "://" in node:
            node = "http://opml.radiotime.com/Browse.ashx?id=%s" % node
        path.append(node)
        try:
            title, urls = get_urls(node)
        except RuntimeError:
            # Jump because too many requests.
            return choose_random(node, category, path, jump=True)

    print("> %s" % title)
    weights_urls = data.get_weights_urls(urls)
    url = weighted_choice(weights_urls, randomness=.5)
    if url is None:
        if path:
            print("Empty list, restart.")
            return None
        else:
            raise NotImplementedError("Still not sure what to do here.")
    if HOME in url:
        return choose_random(url, path=path)
    else:
        path.append(url)
        return path


def play(url):
    """
    returns the time the user spent playing
    """
    global PROC
    if ".pls" in url or ".m3u" in url:
        # MPlayer will not parse pls because of security reasons
        print("Parsing playlist: %s" % url)
        response = HTTP_SESSION.get(url)
        text = response.text
        try:
            url = re.findall(r"((?:http|ftp)s?.*?$)", text, re.M)[-1]
        except IndexError:
            raise ValueError("Could not find url in:\n%s" % text)

        return play(url)

    if "football" in url:
        return True, 0

    command = "streamplayer '%s'" % url
    print("=> %s" % command)
    start_time = time.time()
    PROC = Popen(command, shell=True, stderr=PIPE)
    store = True
    exit = False
    reason = None

    try:
        PROC.wait()
    except KeyboardInterrupt:
        reason = "Control-C"
    end_time = time.time()

    stderr = PROC.stderr.readlines()
    if not reason:
        for line in stderr:
            line = line.decode()
            exiting = REGEX_MP_EXITING.match(line)
            if exiting:
                reason = exiting.group("reason")

    if reason is None:
        print("Not found reason:")
        for line in stderr:
            print("  %s" % line.rstrip())

    state = EXITING_REASONS[reason]
    exit = state["exit"]
    store = state["store"]

    runtime = end_time - start_time
    if runtime < 20:
        print("Reason: %s, after %f seconds" % (reason, runtime))
    if store:
        strengh = max(runtime - 120, 0)
    else:
        strengh = None

    return exit, strengh


def main():
    init_db()
    history = [None] * 5

    print("Keybinds:")
    print("  <q>: jump next station, learn new weights")
    print("  <Control-C>: exit without storing")
    print("  <Enter>: jump next station without storing")

    data.clean_cache()
    data.print_report()
    errorcode = 0

    while True:
        print("")
#         path = choose_random(category="music")
#         path = choose_random(category="local")
#         path = choose_random("r100325") # Colombia
        path = choose_random()
        try:
            url = path[-1]
        except TypeError:
            continue

        if url in history:
            print("History hit")
            continue
        else:
            history.append(url)
            history.pop(0)

        exit, strengh = play(url)
        if exit:
            print("Closing")
            break
        if not strengh is None:
            strengh =  min(strengh, 60 * 60 * 2) # cap to two hours
            data.update_path(path, strengh)

#     signal.pause()
    return errorcode


if __name__ == "__main__":
    sys.exit(main())
