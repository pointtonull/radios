from decimal import Decimal as D
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
def update_path(path, strengh):
    """
    Propagates the sthengh changes for the given path
    """
    for url in path:
        node = m.Node.get_for_update(url=url)
        if not node:
            node = m.Node(url=url)
        node.strengh += D(strengh)
        node.runs += 1
        average = D(node.strengh / node.runs)
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
        print("%d %s" % (node.m8, node.url))

