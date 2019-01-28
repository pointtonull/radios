#!/usr/bin/env python3
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
from requests.exceptions import ReadTimeout, ConnectionError

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
    except:
        title = json.get("head", "\o/")
    body = json["body"]
    urls = extract_urls(body)
    return title, urls


def weighted_choice(weights_options, randomness=2):
    if not weights_options:
        return None

    weights_options = [(w ** D(1/randomness), o) for w, o in weights_options]
    total = sum(w for w, o in weights_options)
    partial = D(random()) * total
    accumulated = 0
    option = None
    for weight, option in weights_options:
        accumulated += weight
        if accumulated >= partial:
            print("%3d%%" % round((weight / total) * 100), end=" ")
            return option
    print("%3d%%+" % round((weight / total) * 100), end=" ")
    return option


def choose_random(node=None, category=None, path=None, jump=False, randomness=1):
    if jump:
        print("\n\n# Jump (403)")
        url = weighted_choice(data.get_all_weights_urls(nostring=HOME), randomness=randomness*2)
        return [url]

    if path is None:
        path = []

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
    url = weighted_choice(weights_urls, randomness=randomness)
    if url is None:
        print("Empty list, restart.")
        path.append(None)
        return path
    if HOME in url:
        return choose_random(url, path=path)
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

    try:
        proc.wait()
    except KeyboardInterrupt:
        reason = "Control-C"
    end_time = time.time()

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
        print("Not found reason:")
        for line in stderr:
            print("  %s" % line.rstrip())

    state = EXITING_REASONS[reason]
    exit = state["exit"]
    store = state["store"]

    runtime = end_time - start_time

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

    while True:
        print("")
#         path = choose_random(category="music")
#         path = choose_random(category="local")
#         path = choose_random("r100325") # Colombia
#         path = choose_random("r0") # Location
        path = choose_random(randomness=1)
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

    return errorcode


if __name__ == "__main__":
    sys.exit(main())
