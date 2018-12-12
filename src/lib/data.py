from decimal import Decimal as D
from pprint import pprint
import time

from . import models as m

HOME      =  "http://opml.radiotime.com/"
BROWSE    =  HOME + "Browse.ashx"
DESCRIBE  =  HOME + "Describe.ashx"
TUNE      =  HOME + "Tune.ashx"

def init_db(db_dict=None):
    db_dict = db_dict or {
        'provider': 'sqlite',
        'filename': 'radios.sqlite',
        'create_db': True,
    }

    try:
        m.db.bind(**db_dict)
        m.db.generate_mapping(create_tables=True)
    except Exception as error:
        if "was already bound" in repr(error):
            logging.info("Reusing DB connection: %s" % error)
        elif "Mapping was already generated" in repr(error):
            logging.info("Already mapped: %s" % error)
        else:
            raise


@m.db_session
def clean_cache(limit=3600*24*7):
    """
    Defaults to one week
    """
    since = time.time() - limit
    olds = m.select(cache
                    for cache in m.Cache
                    if cache.lastupdated < since)
    return olds.delete()


@m.db_session
def get_url_cache(url):
    cache = m.select(cache
                     for cache in m.Cache
                     if cache.url == url).first()
    if cache:
        print("(+)", end="")
        return cache.content
    else:
        print("(-)", end="")


@m.db_session
def set_url_cache(url, content):
    cache = m.Cache.get_for_update(url=url)
    if cache:
        cache.content = content
        cache.lastupdated=time.time()
    else:
        cache = m.Cache(url=url, content=content, lastupdated=time.time())


@m.db_session
def get_all_weights_urls(string=""):
    return m.select((node.m8, node.url)
                    for node in m.Node
                    if string in node.url)[:]


@m.db_session
def get_weights_urls(urls):
    weights_url = []
    for url in urls:
        node = m.Node.get(url=url)
        if node is None:
            weights_url.append((0, url))
        else:
            weights_url.append((node.m8, url))
    return weights_url


@m.db_session
def print_report():
    average_score, scored_nodes = m.select((m.avg(node.m8), m.count(node))
            for node in m.Node).first()
    scored_radios = m.select(m.count(node)
            for node in m.Node
            if HOME not in node.url).first()
    cached_pages = m.select(m.count(cache) for cache in m.Cache).first()
    print("\nStats:")
    for key, value in locals().items():
        print("  %s: %s" % (key.replace("_", " "), value))



@m.db_session
def update_path(path, strengh):
    """
    Propagates the sthengh changes for the given path
    """
    print("Updating weights:")
    for url in path:
        if url is None:
            continue
        node = m.Node.get_for_update(url=url)
        if not node:
            node = m.Node(url=url)
        node.strengh += D(strengh)
        node.runs += 1
        average = D(node.strengh / node.runs)
        old_m8 = node.m8
        if node.runs > 8:
            node.m8 = D(node.m8 * 7 + D(strengh)) / 8
        else:
            node.m8 = average
        if node.runs > 16:
            node.m16 = D(node.m16 * 15 + D(strengh)) / 16
        else:
            node.m16 = average
        if node.runs > 32:
            node.m32 = D(node.m8 * 31 + D(strengh)) / 32
        else:
            node.m32 = average
        print("  %12s  %s" % ("%d (%+d)" % (node.m8, round(node.m8 - old_m8)), node.url))

