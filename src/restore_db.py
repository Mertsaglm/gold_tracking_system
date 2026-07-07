"""SQLite'ı SQL dump'tan yeniden kurar (workflow'lar checkout sonrası bunu çağırır).

Kullanım: python -m src.restore_db
"""
from . import dbdump, util

if __name__ == "__main__":
    util.load_env()
    print(dbdump.restore(util.load_config()))
