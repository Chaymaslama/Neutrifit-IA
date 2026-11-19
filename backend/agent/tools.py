import json
from copy import deepcopy
from pathlib import Path

EXERCICES = Path(__file__).resolve().parent.parent / 'data' / 'exercices.json'


def charger_aliments(con):
    rows = con.execute('SELECT * FROM aliments').fetchall()
    return {r['id']: dict(r) for r in rows}


class Outils:
    """Outils de l'agent, liés au profil de la requête (allergies et budget viennent du code)."""

    def __init__(self, profil, aliments, con):
        self.profil, self.aliments, self.con = profil, aliments, con
        self.besoins = self.verification = self.menu_valide = None
        self.courses = self.seances = self.plan_id = None

    def calculer_besoins(self):
        p = self.profil
        bmr = 10 * p['poids'] + 6.25 * p['taille'] - 5 * p['age'] + (5 if p['sexe'] == 'M' else -161)
        facteurs = {'sedentaire': 1.2, 'leger': 1.375, 'modere': 1.55, 'actif': 1.725}
        ajust = {'perte': 0.85, 'maintien': 1.0, 'prise_masse': 1.12}[p['objectif']]
        plancher = 1500 if p['sexe'] == 'M' else 1200   # plancher de sécurité (valeurs usuelles, à vérifier)
        kcal = max(round(bmr * facteurs[p['activite']] * ajust), plancher)
        self.besoins = {'kcal': kcal, 'proteines_g': round(p['poids'] * 1.8)}   # estimations générales
        return self.besoins

    def chercher_aliments(self, categorie=None):
        interdits = set(self.profil['allergies'])
        return [{'id': i, 'nom': a['nom'], 'categorie': a['categorie'],
                 'kcal_100g': a['kcal_100g'], 'prot_100g': a['proteines_100g'],
                 'prix_dt_kg': a['prix_dt_kg']}
                for i, a in self.aliments.items()
                if not interdits & set(a['allergenes'].split(';'))
                and (categorie is None or a['categorie'] == categorie)]

    def verifier_menu(self, items):
        if self.plan_id is not None:
            return {"ok": False, "problemes": ["Plan déjà enregistré"]}
        self.menu_valide = None
        self.verification = None
        self.courses = None
        if not isinstance(items, list) or not items or len(items) > 40:
            return {"ok": False, "problemes": ["Menu vide ou trop long"]}
        if self.besoins is None:
            return {'ok': False, 'problemes': ['appelle d’abord calculer_besoins']}
        problemes, kcal, prot, cout = [], 0.0, 0.0, 0.0
        for it in items:
            if not isinstance(it, dict) or type(it.get('aliment_id')) is not int or type(it.get('quantite_g')) is not int or not 1 <= it['quantite_g'] <= 1000 or it.get('repas') not in ('petit_dejeuner','dejeuner','diner','collation'):
                problemes.append('Ligne de menu invalide')
                continue
            aid, q = it['aliment_id'], it['quantite_g']
            a = self.aliments.get(aid)
            if a is None:
                problemes.append(f'aliment inconnu : {aid}')
                continue
            kcal += a['kcal_100g'] * q / 100
            prot += a['proteines_100g'] * q / 100
            cout += a['prix_dt_kg'] * q / 1000
            for al in self.profil['allergies']:
                if al in a['allergenes'].split(';'):
                    problemes.append(f'allergène {al} dans ' + a['nom'])
        cible_kcal, cible_prot = self.besoins['kcal'], self.besoins['proteines_g']
        budget = self.profil.get('budget_dt_jour')
        if abs(kcal - cible_kcal) > 0.15 * cible_kcal:
            problemes.append(f'calories {round(kcal)} trop éloignées de {cible_kcal}')
        if prot < 0.8 * cible_prot:
            problemes.append(f'protéines {round(prot)} g insuffisantes (cible {cible_prot} g)')
        if budget is not None and cout > budget:
            problemes.append(f'coût {cout:.1f} DT au-dessus du budget {budget} DT')
        res = {'ok': not problemes, 'problemes': problemes, 'kcal': round(kcal),
               'proteines_g': round(prot), 'cout_dt': round(cout, 2)}
        self.verification = res
        self.menu_valide = deepcopy(items) if res['ok'] else None
        return res

    def construire_seance(self):
        p = self.profil
        with open(EXERCICES, encoding='utf-8') as f:
            ex = json.load(f)
        niveaux = {'debutant': ['debutant'],
                   'intermediaire': ['debutant', 'intermediaire']}[p['niveau']]
        ok = [e for e in ex if e['niveau'] in niveaux
              and (e['materiel'] == 'aucun' or e['materiel'] in p['materiel'])]
        self.seances = {'jours': p['jours_dispo'], 'exercices_candidats': ok}
        return self.seances

    def liste_courses(self, items, jours=7):
        if self.plan_id is not None:
            return self.courses
        if type(jours) is not int or jours != 7:
            return {"erreur": "La liste couvre exactement 7 jours"}
        totaux = {}
        for it in items:
            totaux[it['aliment_id']] = totaux.get(it['aliment_id'], 0) + it['quantite_g'] * jours
        lignes = [{'aliment': self.aliments[i]['nom'], 'quantite_g': g,
                   'cout_dt': round(self.aliments[i]['prix_dt_kg'] * g / 1000, 2)}
                  for i, g in totaux.items() if i in self.aliments]
        self.courses = {'lignes': lignes, 'total_dt': round(sum(l['cout_dt'] for l in lignes), 2)}
        return self.courses

    def enregistrer_plan(self, items):
        if self.menu_valide is None or items != self.menu_valide:
            return {'ok': False, 'erreur': 'menu non validé : appelle verifier_menu avec ce menu'}
        self.liste_courses(items)
        self.construire_seance()
        if self.plan_id is not None:
            return {"ok": True, "plan_id": self.plan_id}
        plan = {'besoins': self.besoins, 'menu': {'items': items},
                'verification': self.verification, 'courses': self.courses,
                'seances': self.seances}
        cur = self.con.execute(
            'INSERT INTO plans (profil_json, plan_json, valide) VALUES (?,?,1)',
            (json.dumps(self.profil, ensure_ascii=False), json.dumps(plan, ensure_ascii=False)))
        self.con.commit()
        self.plan_id = cur.lastrowid
        return {'ok': True, 'plan_id': self.plan_id}

    def reponse(self, texte, journal):          # réponse finale de /generate
        res = {'valide': self.plan_id is not None and self.menu_valide is not None, 'besoins': self.besoins,
               'menu': {'items': self.menu_valide} if self.menu_valide else None,
               'verification': self.verification, 'courses': self.courses,
               'seances': self.seances, 'texte': texte, 'journal': journal,
               'plan_id': self.plan_id}
        if self.plan_id and self.menu_valide is not None:                        # complète le plan sauvegardé avec le texte final
            self.con.execute('UPDATE plans SET plan_json = ? WHERE id = ?',
                             (json.dumps(res, ensure_ascii=False), self.plan_id))
            self.con.commit()
        return res
