ITEMS = {
    'type': 'array',
    'description': 'Aliments du menu : une ligne par aliment et par repas',
    'items': {
        'type': 'object',
        'properties': {
            'repas': {'type': 'string', 'enum': ['petit_dejeuner', 'dejeuner', 'diner', 'collation']},
            'aliment_id': {'type': 'integer', 'description': 'id fourni par chercher_aliments'},
            'quantite_g': {'type': 'integer', 'description': 'quantité en grammes'},
        },
        'required': ['repas', 'aliment_id', 'quantite_g'],
    },
}


def outil(nom, description, proprietes=None, requis=None):
    """Outil au format « function calling » compatible OpenAI (Groq, OpenRouter, Mistral…)."""
    schema = {'type': 'object', 'properties': proprietes or {}}
    if requis:
        schema['required'] = requis
    return {'type': 'function',
            'function': {'name': nom, 'description': description, 'parameters': schema}}


TOOLS = [
    outil('calculer_besoins',
          'Calcule les calories et les protéines cibles du profil. À appeler en premier.'),
    outil('chercher_aliments',
          'Liste les aliments autorisés (allergènes déjà exclus) avec id, kcal, protéines et prix. '
          'Filtre facultatif par catégorie.',
          {'categorie': {'type': 'string'}}),
    outil('verifier_menu',
          'Vérifie un menu : allergènes, calories, protéines, budget. '
          'Si ok est faux, corrige le menu et revérifie.',
          {'items': ITEMS}, ['items']),
    outil('construire_seance',
          'Sélectionne les exercices adaptés au niveau, au matériel et aux jours disponibles.'),
    outil('liste_courses',
          'Calcule la liste de courses de la semaine et son coût en dinars pour un menu.',
          {'items': ITEMS}, ['items']),
    outil('enregistrer_plan',
          'Enregistre le menu. Refusé si ce menu exact n’a pas été validé par verifier_menu.',
          {'items': ITEMS}, ['items']),
]
