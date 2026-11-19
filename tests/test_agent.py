"""Teste la boucle de l'agent avec un faux client (aucun appel réseau, aucune clé)."""
import json
from types import SimpleNamespace as NS
import backend.database as database
from backend.data.import_aliments import importer
from backend.agent import agent

PROFIL = {'age': 21, 'sexe': 'F', 'poids': 60, 'taille': 168, 'activite': 'leger',
          'objectif': 'prise_masse', 'niveau': 'debutant', 'jours_dispo': 3,
          'materiel': ['halteres'], 'allergies': ['arachides'], 'budget_dt_jour': 8,
          'consignes': ''}


def appel(nom, **args):
    return NS(id='call_' + nom, function=NS(name=nom, arguments=json.dumps(args)))


def reponse(appels=None, texte=None):
    return NS(choices=[NS(message=NS(content=texte, tool_calls=appels or None))])


class FauxClient:
    def __init__(self, etapes):
        self.etapes = iter(etapes)
        self.chat = NS(completions=self)

    def create(self, **kw):
        return next(self.etapes)


def id_de(nom):
    con = database.get_db()
    r = con.execute('SELECT id FROM aliments WHERE nom = ?', (nom,)).fetchone()
    con.close()
    return r['id']


def menu_valide():
    q = [('petit_dejeuner', 'Pain (baguette)', 200), ('dejeuner', 'Pâtes cuites', 400),
         ('dejeuner', 'Poulet blanc cuit', 250), ('diner', 'Huile d’olive', 30),
         ('collation', 'Banane', 200)]
    return [{'repas': r, 'aliment_id': id_de(n), 'quantite_g': g} for r, n, g in q]


def test_agent_corrige_puis_enregistre(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'test.db')
    importer()
    bon = menu_valide()
    mauvais = [{'repas': 'dejeuner', 'aliment_id': id_de('Riz blanc cuit'), 'quantite_g': 100}]
    faux = FauxClient([
        reponse([appel('calculer_besoins')]),
        reponse([appel('chercher_aliments')]),
        reponse([appel('verifier_menu', items=mauvais)]),        # refusé : calories trop basses
        reponse([appel('verifier_menu', items=bon)]),            # corrigé : validé
        reponse([appel('construire_seance')]),
        reponse([appel('liste_courses', items=bon)]),
        reponse([appel('enregistrer_plan', items=bon)]),
        reponse(texte='Voici ton plan.'),
    ])
    monkeypatch.setattr(agent, '_client', faux)
    r = agent.run_agent(PROFIL)
    verifs = [j['sortie'] for j in r['journal'] if j['outil'] == 'verifier_menu']
    assert [v['ok'] for v in verifs] == [False, True]
    assert r['valide'] and r['plan_id'] and r['courses'] and r['seances']
    assert r['texte'] == 'Voici ton plan.'
    # l'allergène est exclu de la recherche
    recherche = next(j for j in r['journal'] if j['outil'] == 'chercher_aliments')['sortie']
    assert all(a['nom'] != 'Cacahuètes' for a in recherche)


def test_agent_refuse_menu_non_valide(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'test.db')
    importer()
    mauvais = [{'repas': 'dejeuner', 'aliment_id': id_de('Riz blanc cuit'), 'quantite_g': 100}]
    faux = FauxClient([
        reponse([appel('calculer_besoins')]),
        reponse([appel('enregistrer_plan', items=mauvais)]),     # saute la vérification
        reponse(texte='fin'),
    ])
    monkeypatch.setattr(agent, '_client', faux)
    r = agent.run_agent(PROFIL)
    assert r['valide'] is False and r['plan_id'] is None
    assert r['journal'][1]['sortie']['ok'] is False


def test_agent_outil_inconnu_et_max_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(database, 'DB_PATH', tmp_path / 'test.db')
    importer()
    faux = FauxClient([reponse([appel('supprimer_tout')])] * 5)
    monkeypatch.setattr(agent, '_client', faux)
    r = agent.run_agent(PROFIL, max_steps=3)
    assert r['journal'][0]['sortie'] == {'erreur': 'outil inconnu'}
    assert len(r['journal']) == 3 and 'Limite' in r['texte']
