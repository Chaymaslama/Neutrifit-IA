import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / 'nutrifit.db'


def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_db()
    con.executescript('''
        CREATE TABLE IF NOT EXISTS aliments (id INTEGER PRIMARY KEY, nom TEXT,
            categorie TEXT, kcal_100g REAL, proteines_100g REAL, glucides_100g REAL,
            lipides_100g REAL, prix_dt_kg REAL, allergenes TEXT);
        CREATE TABLE IF NOT EXISTS plans (id INTEGER PRIMARY KEY AUTOINCREMENT,
            profil_json TEXT, plan_json TEXT, valide INTEGER,
            date TEXT DEFAULT CURRENT_TIMESTAMP);
    ''')
    con.commit()
    con.close()
