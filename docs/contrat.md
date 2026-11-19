# Contrat JSON (étape 0)

## Valeurs possibles
- sexe : `F` ou `M`
- activite : `sedentaire`, `leger`, `modere`, `actif`
- objectif : `perte`, `maintien`, `prise_masse`
- niveau : `debutant`, `intermediaire`
- allergies (liste normalisée) : `arachides`, `gluten`, `lait`, `oeufs`, `poisson`, `fruits_a_coque`, `soja`, `sesame`
- repas : `petit_dejeuner`, `dejeuner`, `diner`, `collation`

## Profil
```python
profil = {
    'age': 21, 'sexe': 'F', 'poids': 60, 'taille': 168,
    'activite': 'leger', 'objectif': 'prise_masse', 'niveau': 'debutant',
    'jours_dispo': 3, 'materiel': ['halteres'],
    'allergies': ['arachides'], 'budget_dt_jour': 8, 'consignes': '',
}
```

## Menu
```python
menu = {'items': [{'repas': 'dejeuner', 'aliment_id': 12, 'quantite_g': 150}]}
```

## Table aliments
id, nom, categorie, kcal_100g, proteines_100g, glucides_100g, lipides_100g, prix_dt_kg, allergenes (séparés par `;`, vide si aucun)

## Réponse de /generate
valide, besoins, menu, verification, courses, seances, texte, journal, plan_id
