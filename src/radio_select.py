#!/usr/bin/env python
#-*- coding: UTF-8 -*-

from collections import defaultdict
from decimal import Decimal as D
from random import choice, random
from subprocess import Popen, PIPE
from sys import exit
import time

import requests

from lib import data
from lib.data import m, init_db


HTTP_SESSION = requests.Session()
KEY_URL = {}

HOME      =  "http://opml.radiotime.com/"
BROWSE    =  HOME + "Browse.ashx"
DESCRIBE  =  HOME + "Describe.ashx"
TUNE      =  HOME + "Tune.ashx"


def extract_urls(element, urls=None):
    if urls is None:
        urls = []
    if isinstance(element, list):
        for item in element:
            extract_urls(item, urls)
    elif isinstance(element, dict):
        if "URL" in element:
            urls.append(element["URL"])
        elif "url" in element:
            urls.append(element["url"])
        elif "children" in element:
            extract_urls(element["children"], urls)
        elif "body" in element:
            extract_urls(element["body"], urls)
        else:
            raise NotImplementedError("Not implemented!")
    else:
        raise NotImplementedError("Not implemented!")
    return urls


def get_json(url=BROWSE, params={}):
    params["render"] = "json"
    return HTTP_SESSION.get(url, params=params).json()


def weighted_choice(weights_options):
    total = sum(max(10, weight) for weight, option in weights_options)
    partial = int(round(D(random()) * total))
    accumulated = 0
    for weight, option in weights_options:
        accumulated += weight
        if accumulated >= partial:
            return option
    return option


def choose_random(node=None, category=None, path=[]):
    print("Choose from %s" % (node or category))
    if node is None:
        childs = get_json(params={"c": category})
    else:
        path.append(node)
        childs = get_json(node)
    body = childs["body"]
    urls = extract_urls(body)
    weights_urls = data.get_weights_urls(urls)
    url = weighted_choice(weights_urls)
    if HOME in url:
        return choose_random(url, path=path)
    else:
        path.append(url)
        return path


def play(url):
    """
    returns the time the user spent playing
    """
    start_time = time.time()
    command = "streamplayer '%s'" % url
    proc = Popen(command, shell=True)
    proc.wait()
    end_time = time.time()
    return end_time - start_time


def main():
    init_db()

    while True:
        path = choose_random(category="music")
        url = path[-1]
        strengh = play(url)
        data.update_path(path, strengh)
        time.sleep(2)


if __name__ == "__main__":
    exit(main())
