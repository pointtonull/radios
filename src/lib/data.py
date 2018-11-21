from decimal import Decimal as D
from . import models as m


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
def _get_node(url):
    node = m.Node.get_for_update(url=url)
    if not node:
        node = m.Node(url=url)
    return node


@m.db_session
def update_path(path, strengh):
    """
    Propagates the sthengh changes for the given path
    """
    for url in path:
        node = _get_node(url)
        node.strengh += D(strengh)
        node.runs += 1
        average = D(node.strengh / node.runs)
        if node.runs > 8:
            node.m8 = D(node.m8 * 7 + strengh) / 8
        else:
            node.m8 = average
        if node.runs > 16:
            node.m16 = D(node.m16 * 15 + strengh) / 16
        else:
            node.m16 = average
        if node.runs > 32:
            node.m32 = D(node.m8 * 31 + strengh) / 32
        else:
            node.m32 = average
        print("%d %s" % (node.m8, node.url))

