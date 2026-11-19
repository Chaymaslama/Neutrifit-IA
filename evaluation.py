"""Étape 11 : évaluation chiffrée de l'agent sur des profils fixes.

Usage :
    python evaluation.py              # 5 essais par profil (défaut)
    python evaluation.py --n 3        # 3 essais par profil (économise le quota Gemini)
    python evaluation.py --profil demo

Pour chaque profil, on mesure :
  - valides du premier coup : le tout premier verifier_menu est déjà ok
  - plans enregistrés       : un plan validé a été sauvegardé au final (après correction si besoin)
  - appels d'outils moyens  : nombre d'appels d'outils par génération
  - écart moyen aux kcal    : |kcal du dernier menu vérifié - kcal cibles|

Le résultat est écrit dans evaluation_resultats.md (tableau prêt pour la soutenance).
Ces résultats portent sur un petit échantillon : à présenter comme des indications.
"""
import argparse
import statistics
import time

from backend.agent.agent import run_agent
from backend.database import init_db

PROFILS = {
    'demo': {'age': 21, 'sexe': 'F', 'poids': 60, 'taille': 168, 'activite': 'leger',
             'objectif': 'prise_masse', 'niveau': 'debutant', 'jours_dispo': 3,
             'materiel': ['halteres'], 'allergies': ['arachides'],
             'budget_dt_jour': 8, 'consignes': ''},
    'perte': {'age': 28, 'sexe': 'F', 'poids': 78, 'taille': 165, 'activite': 'sedentaire',
              'objectif': 'perte', 'niveau': 'debutant', 'jours_dispo': 4,
              'materiel': [], 'allergies': ['lait'],
              'budget_dt_jour': 10, 'consignes': ''},
    'limite': {'age': 24, 'sexe': 'M', 'poids': 85, 'taille': 180, 'activite': 'actif',
               'objectif': 'prise_masse', 'niveau': 'intermediaire', 'jours_dispo': 5,
               'materiel': ['halteres', 'elastique'], 'allergies': ['gluten', 'oeufs'],
               'budget_dt_jour': 4, 'consignes': ''},        # budget très bas + 2 allergies
}

LIBELLES = {'demo': 'Démonstration', 'perte': 'Perte de poids', 'limite': 'Cas limite'}


def evaluer(nom, profil, n):
    premier, final, appels, ecarts, erreurs = 0, 0, [], [], 0
    for i in range(n):
        try:
            r = run_agent(profil)
        except Exception as e:                      # clé invalide, quota, réseau...
            erreurs += 1
            print(f'  [{nom}] essai {i + 1}/{n} : ERREUR {type(e).__name__}: {e}')
            time.sleep(2)
            continue
        verifs = [j['sortie'] for j in r['journal']
                  if j['outil'] == 'verifier_menu' and isinstance(j['sortie'], dict)]
        ok1 = bool(verifs) and bool(verifs[0].get('ok'))
        premier += ok1
        final += bool(r['valide'])
        appels.append(len(r['journal']))
        if verifs and r['besoins'] and 'kcal' in verifs[-1]:
            ecarts.append(abs(verifs[-1]['kcal'] - r['besoins']['kcal']))
        print(f'  [{nom}] essai {i + 1}/{n} : 1er menu ok={ok1} · plan enregistré={r["valide"]} '
              f'· {len(r["journal"])} appels')
    essais = n - erreurs
    return {
        'premier': premier, 'final': final, 'essais': essais, 'erreurs': erreurs,
        'appels': round(statistics.mean(appels), 1) if appels else None,
        'ecart': round(statistics.mean(ecarts)) if ecarts else None,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=5, help='essais par profil')
    ap.add_argument('--profil', choices=list(PROFILS), help='un seul profil')
    args = ap.parse_args()
    init_db()

    noms = [args.profil] if args.profil else list(PROFILS)
    resultats = {}
    for nom in noms:
        print(f'Profil « {nom} » ({args.n} essais)')
        resultats[nom] = evaluer(nom, PROFILS[nom], args.n)

    lignes = ['| Profil | Valides du premier coup | Plans enregistrés au final | '
              'Appels d’outils en moyenne | Écart moyen aux kcal cibles |',
              '|---|---|---|---|---|']
    for nom, r in resultats.items():
        ecart = f"{r['ecart']} kcal" if r['ecart'] is not None else 'n/a'
        appels = r['appels'] if r['appels'] is not None else 'n/a'
        note = f" ({r['erreurs']} erreur(s) API)" if r['erreurs'] else ''
        lignes.append(f"| {LIBELLES[nom]} | {r['premier']} / {r['essais']} | "
                      f"{r['final']} / {r['essais']}{note} | {appels} | {ecart} |")
    tableau = '\n'.join(lignes)
    print('\n' + tableau)

    with open('evaluation_resultats.md', 'w', encoding='utf-8') as f:
        f.write('# Résultats d’évaluation NutriFit AI\n\n' + tableau + '\n\n'
                '> Petit échantillon : à présenter comme des indications, pas comme une preuve.\n'
                '> « Valides du premier coup » = premier verifier_menu déjà ok ; '
                '« Plans enregistrés » = plan validé après correction éventuelle.\n')
    print('\nTableau écrit dans evaluation_resultats.md')


if __name__ == '__main__':
    main()
