#!/usr/bin/env python
#-*- coding: UTF-8 -*-

from collections import defaultdict
from decimal import Decimal as D
from functools import lru_cache
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
        else:
            raise NotImplementedError("Not implemented!")
    else:
        raise NotImplementedError("Not implemented!")
    return urls


def get_json(url=BROWSE, params=[]):
    params = dict(params)
    params["render"] = "json"
    response = HTTP_SESSION.get(url, params=params)
    try:
        json = response.json()
    except:
        raise ValueError(response.text)
    return json


@lru_cache(maxsize=1024)
def get_urls(url=BROWSE, params=[]):
    childs = get_json(url, params)
    body = childs["body"]
    urls = extract_urls(body)
    return urls


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
        urls = get_urls(params=(("c", category),))
    else:
        path.append(node)
        urls = get_urls(node)
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
    print("=> %s" % command)
    proc = Popen(command, shell=True)
    proc.wait()
    end_time = time.time()
    strengh = max(end_time - start_time - 30, 0) # average time for sound to start
    return strengh


def main():
    init_db()

    while True:
        print("")
        path = choose_random(category="music")
        url = path[-1]
        strengh = play(url)
        data.update_path(path, strengh)


if __name__ == "__main__":
    exit(main())
