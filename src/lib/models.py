from decimal import Decimal
from pony.orm import *


db = Database()


class Node(db.Entity):
    id = PrimaryKey(int, auto=True)
    url = Required(str, unique=True)
    strengh = Optional(Decimal, default=0, volatile=True)
    runs = Optional(int, default=0, volatile=True, unsigned=True)
    m12 = Optional(Decimal, default=0, volatile=True)
    m24 = Optional(Decimal, default=0, volatile=True)
    cache = Optional('Cache')


class Cache(db.Entity):
    id = PrimaryKey(int, auto=True)
    lastupdated = Required(float)
    content = Optional(LongStr, lazy=True)
    node = Required(Node)
