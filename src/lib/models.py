from decimal import Decimal
from pony.orm import *


db = Database()


class Node(db.Entity):
    id = PrimaryKey(int, auto=True)
    url = Required(str, unique=True)
    strengh = Optional(Decimal, default=0)
    runs = Optional(int, default=0, unsigned=True)
    m8 = Optional(Decimal, default=0)
    m16 = Optional(Decimal, default=0)
    m32 = Optional(Decimal, default=0)

