import sqlite3
from backend.agent.tools import Outils

ALIMENTS = {
    1: {'nom': 'Thon', 'categorie': 'poisson', 'kcal_100g': 130, 'proteines_100g': 28,
        'prix_dt_kg': 30, 'allergenes': 'poisson'},
    2: {'nom': 'Riz', 'categorie': 'cereales', 'kcal_100g': 130, 'proteines_100g': 3,
        'prix_dt_kg': 3, 'allergenes': ''},
}
PROFIL = {'age': 30, 'sexe': 'F', 'poids': 40, 'taille': 150, 'activite': 'sedentaire',
          'objectif': 'perte', 'niveau': 'debutant', 'jours_dispo': 3, 'materiel': [],
          'allergies': [], 'budget_dt_jour': None}


def outils(**modif):
    con = sqlite3.connect(':memory:')
    con.execute('CREATE TABLE plans (id INTEGER PRIMARY KEY AUTOINCREMENT, profil_json TEXT,'
                ' plan_json TEXT, valide INTEGER, date TEXT DEFAULT CURRENT_TIMESTAMP)')
    o = Outils({**PROFIL, **modif}, ALIMENTS, con)
    o.besoins = {'kcal': 130, 'proteines_g': 28}    # cible simple pour les tests
    return o


def menu(aid, q):
    return [{'repas': 'dejeuner', 'aliment_id': aid, 'quantite_g': q}]


def test_plancher_calories():
    assert outils().calculer_besoins()['kcal'] >= 1200


def test_allergene_detecte():
    r = outils(allergies=['poisson']).verifier_menu(menu(1, 100))
    assert not r['ok'] and any('allergène' in p for p in r['problemes'])


def test_chercher_aliments_exclut_allergene():
    noms = [a['nom'] for a in outils(allergies=['poisson']).chercher_aliments()]
    assert 'Thon' not in noms and 'Riz' in noms


def test_aliment_inconnu():
    assert not outils().verifier_menu(menu(99, 100))['ok']


def test_budget_depasse():
    o = outils(budget_dt_jour=5)
    o.besoins = {'kcal': 1300, 'proteines_g': 280}
    assert any('budget' in p for p in o.verifier_menu(menu(1, 1000))['problemes'])


def test_enregistrer_refuse_menu_non_valide():
    assert not outils().enregistrer_plan(menu(1, 100))['ok']


def test_enregistrer_accepte_menu_valide():
    o = outils()
    assert o.verifier_menu(menu(1, 100))['ok']
    assert o.enregistrer_plan(menu(1, 100))['ok']


def test_liste_courses_total():
    o = outils()
    r = o.liste_courses(menu(2, 100))        # 100 g x 7 jours = 700 g de riz à 3 DT/kg
    assert r['lignes'][0]['quantite_g'] == 700 and r['total_dt'] == 2.1


def test_construire_seance_filtre_niveau_et_materiel():
    r = outils(materiel=['halteres']).construire_seance()
    noms = [e['nom'] for e in r['exercices_candidats']]
    assert 'Squat avec haltère' in noms and 'Pompes classiques' not in noms
    assert 'Rowing avec élastique' not in noms
