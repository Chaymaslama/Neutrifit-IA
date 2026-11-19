"""Scénario local fixe, exclusivement pour la démonstration (pas un LLM)."""
from ..database import get_db
from .tools import Outils, charger_aliments

def run_demo(profil):
    con = get_db()
    try:
        o = Outils(profil, charger_aliments(con), con)
        journal = []
        def call(nom, **args):
            result = getattr(o, nom)(**args)
            journal.append(dict(outil=nom, entree=args, sortie=result))
            return result
        call('calculer_besoins'); call('chercher_aliments')
        # Exemple fixe issu des tests, contrôlé pour le profil réellement saisi.
        items = [dict(repas=r, aliment_id=i, quantite_g=q) for r,i,q in [('petit_dejeuner',4,200),('dejeuner',2,400),('dejeuner',12,250),('diner',24,30),('collation',35,200)]]
        if call('verifier_menu', items=items)['ok']:
            call('construire_seance'); call('liste_courses',items=items); call('enregistrer_plan',items=items)
        result = o.reponse('Démonstration locale : scénario fixe, sans IA distante. Les préférences libres ne sont pas interprétées. Utilisez le mode Groq pour un programme personnalisé.',journal)
        result['mode']='demo'
        return result
    finally: con.close()
