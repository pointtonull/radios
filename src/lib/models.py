from decimal import Decimal
from pony.orm import *


db = Database()


class Node(db.Entity):
    id = PrimaryKey(int, auto=True)
    url = Required(str, unique=True)
    strengh = Optional(Decimal, default=200, volatile=True)
    runs = Optional(int, default=1, volatile=True, unsigned=True)
    m8 = Optional(Decimal, default=200, volatile=True)
    m16 = Optional(Decimal, default=200, volatile=True)


class Cache(db.Entity):
    id = PrimaryKey(int, auto=True)
    url = Required(str, unique=True)
    lastupdated = Optional(float, default=0)
    content = Optional(LongStr)
