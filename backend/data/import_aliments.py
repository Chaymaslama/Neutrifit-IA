import csv
from pathlib import Path
from backend.database import get_db, init_db

CHEMIN = Path(__file__).resolve().parent / 'aliments.csv'


def importer(chemin=CHEMIN):
    init_db()
    con = get_db()
    con.execute('DELETE FROM aliments')
    n = 0
    with open(chemin, encoding='utf-8') as f:
        for l in csv.DictReader(f):
            con.execute('INSERT INTO aliments VALUES (?,?,?,?,?,?,?,?,?)',
                        (int(l['id']), l['nom'], l['categorie'], float(l['kcal_100g']),
                         float(l['proteines_100g']), float(l['glucides_100g']),
                         float(l['lipides_100g']), float(l['prix_dt_kg']), l['allergenes']))
            n += 1
    con.commit()
    con.close()
    return n


if __name__ == '__main__':
    print(importer(), 'aliments importés')
