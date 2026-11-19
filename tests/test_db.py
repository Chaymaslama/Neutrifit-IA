import sqlite3
from backend.data.import_aliments import importer, CHEMIN
import backend.database as database


def test_import_aliments_sans_cellule_vide(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'test.db')
    n = importer(CHEMIN)
    assert 40 <= n <= 50
    con = database.get_db()
    assert con.execute('SELECT COUNT(*) FROM aliments').fetchone()[0] == n
    assert con.execute("SELECT COUNT(*) FROM aliments WHERE nom IS NULL OR nom=''").fetchone()[0] == 0
    valides = {'arachides', 'gluten', 'lait', 'oeufs', 'poisson', 'fruits_a_coque', 'soja', 'sesame'}
    for r in con.execute('SELECT allergenes FROM aliments'):
        vals = set(filter(None, r['allergenes'].split(';')))
        assert vals <= valides
