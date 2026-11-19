from typing import Literal
from pydantic import BaseModel, Field


class Profil(BaseModel):
    age: int = Field(ge=18, le=80)
    sexe: Literal['F', 'M']
    poids: float = Field(ge=35, le=250)
    taille: int = Field(ge=130, le=230)
    activite: Literal['sedentaire', 'leger', 'modere', 'actif']
    objectif: Literal['perte', 'maintien', 'prise_masse']
    niveau: Literal['debutant', 'intermediaire']
    jours_dispo: int = Field(ge=1, le=6)
    materiel: list[Literal["halteres", "elastique"]] = Field(default_factory=list)
    allergies: list[Literal["arachides", "gluten", "lait", "oeufs", "poisson", "fruits_a_coque", "soja", "sesame"]] = Field(default_factory=list)
    budget_dt_jour: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    consignes: str = Field('', max_length=200)
