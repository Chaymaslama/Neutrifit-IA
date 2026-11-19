"""Tests complémentaires des étapes 8 à 11 (aucun appel réseau, aucune clé API)."""
import sqlite3

from fastapi.testclient import TestClient

import backend.database as database
from backend.agent.tools import Outils
from backend.data.import_aliments import importer
from backend.main import app
from backend.routers import generate as generate_router
from backend.schemas import Profil

client = TestClient(app)

ALIMENTS = {
    1: {'nom': 'Riz', 'categorie': 'cereales', 'kcal_100g': 130, 'proteines_100g': 3,
        'prix_dt_kg': 4, 'allergenes': ''},
    2: {'nom': 'Poulet', 'categorie': 'viandes', 'kcal_100g': 165, 'proteines_100g': 31,
        'prix_dt_kg': 16, 'allergenes': ''},
    3: {'nom': 'Cacahuètes', 'categorie': 'fruits_secs', 'kcal_100g': 567, 'proteines_100g': 26,
        'prix_dt_kg': 12, 'allergenes': 'arachides'},
}
PROFIL = {'age': 21, 'sexe': 'F', 'poids': 60, 'taille': 168, 'activite': 'leger',
          'objectif': 'prise_masse', 'niveau': 'debutant', 'jours_dispo': 3,
          'materiel': ['halteres'], 'allergies': ['arachides'], 'budget_dt_jour': 8,
          'consignes': ''}


def outils(**modif):
    con = sqlite3.connect(':memory:')
    return Outils({**PROFIL, **modif}, ALIMENTS, con)


# ---------- étape 8 : séances et courses ----------
def test_liste_courses_total_attendu():
    o = outils()
    r = o.liste_courses([{'repas': 'dejeuner', 'aliment_id': 1, 'quantite_g': 200},
                         {'repas': 'diner', 'aliment_id': 1, 'quantite_g': 100},
                         {'repas': 'diner', 'aliment_id': 2, 'quantite_g': 150}])
    # riz : 300 g x 7 = 2100 g -> 8,40 DT ; poulet : 150 g x 7 = 1050 g -> 16,80 DT
    lignes = {l['aliment']: l for l in r['lignes']}
    assert lignes['Riz']['quantite_g'] == 2100 and lignes['Riz']['cout_dt'] == 8.4
    assert lignes['Poulet']['quantite_g'] == 1050 and lignes['Poulet']['cout_dt'] == 16.8
    assert r['total_dt'] == 25.2


def test_construire_seance_filtre_niveau_et_materiel():
    s = outils(niveau='debutant', materiel=[]).construire_seance()
    noms = {e['nom'] for e in s['exercices_candidats']}
    assert s['jours'] == 3
    assert 'Squat au poids du corps' in noms                       # matériel « aucun »
    assert 'Squat avec haltère' not in noms                        # pas d'haltères
    assert 'Pompes classiques' not in noms                         # niveau intermédiaire


def test_construire_seance_intermediaire_avec_halteres():
    s = outils(niveau='intermediaire', materiel=['halteres']).construire_seance()
    noms = {e['nom'] for e in s['exercices_candidats']}
    assert 'Pompes classiques' in noms and 'Squat avec haltère' in noms


# ---------- étape 6 : calculs et filtre d'allergènes ----------
def test_calculer_besoins_formule_mifflin():
    b = outils().calculer_besoins()
    # BMR = 10*60 + 6,25*168 - 5*21 - 161 = 1384 ; x1,375 x1,12 = 2131
    assert b == {'kcal': 2131, 'proteines_g': 108}


def test_chercher_aliments_exclut_allergene_et_filtre_categorie():
    o = outils()
    tous = {a['nom'] for a in o.chercher_aliments()}
    assert 'Cacahuètes' not in tous and {'Riz', 'Poulet'} <= tous
    assert [a['nom'] for a in o.chercher_aliments('viandes')] == ['Poulet']


# ---------- étape 9 : affinage ----------
def test_consignes_limitees_a_200_caracteres():
    p = {**PROFIL, 'consignes': 'x' * 201}
    assert client.post('/generate', json=p).status_code == 422
    assert Profil(**{**PROFIL, 'consignes': 'x' * 200}).consignes == 'x' * 200


def test_consignes_transmises_a_l_agent(monkeypatch):
    monkeypatch.setenv("NUTRIFIT_MODE", "ai")
    recu = {}

    def faux_agent(profil, max_steps=12):
        recu.update(profil)
        return {'valide': False, 'journal': []}

    monkeypatch.setattr(generate_router, 'run_agent', faux_agent)
    p = {**PROFIL, 'consignes': 'je n’aime pas le thon'}
    assert client.post('/generate', json=p).status_code == 200
    assert recu['consignes'] == 'je n’aime pas le thon'


# ---------- étape 10 : frontend et erreurs propres ----------
def test_frontend_servi():
    r = client.get('/app/')
    assert r.status_code == 200
    assert 'NutriFit AI' in r.text and 'innerHTML' not in r.text.replace('jamais innerHTML', '')


def test_generate_renvoie_503_propre_si_l_agent_plante(monkeypatch):
    monkeypatch.setenv("NUTRIFIT_MODE", "ai")
    def plante(profil, max_steps=12):
        raise RuntimeError('clé API invalide (détail interne)')

    monkeypatch.setattr(generate_router, 'run_agent', plante)
    r = client.post('/generate', json=PROFIL)
    assert r.status_code == 503
    assert 'invalide' not in r.text                       # le détail interne ne fuite pas
    assert r.json()['detail'] == 'Service IA indisponible, réessayez.'


def test_pas_de_budget_accepte():
    assert Profil(**{**PROFIL, 'budget_dt_jour': None}).budget_dt_jour is None


# ---------- étape 11 : les profils d'évaluation sont valides ----------
def test_profils_evaluation_valides():
    from evaluation import PROFILS
    assert set(PROFILS) == {'demo', 'perte', 'limite'}
    for p in PROFILS.values():
        Profil(**p)


def test_plans_historique_apres_import(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'h.db')
    importer()
    assert client.get('/plans').json() == []
