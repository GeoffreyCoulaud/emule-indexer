"""Interpolation des patterns regex et alternance de dates (cf. spec §8.2)."""

import datetime

# Noms de mois français SANS accent (déjà repliés) : les patterns sont matchés
# contre fold(raw), qui retire les diacritiques. Ainsi "fevrier" matche "février".
FRENCH_MONTHS: dict[int, str] = {
    1: "janvier",
    2: "fevrier",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "aout",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "decembre",
}


def date_alternation_pattern(d: datetime.date) -> str:
    r"""Fragment RE2 ``(?:…)`` couvrant les formes usuelles d'une date.

    Couvre ``21 septembre 2008`` (jour mois-replié année), ``21/09/2008``
    (jour/mois/année) et ``2008-09-21`` (année/mois/jour). ``0*`` tolère un
    préfixe de zéros (un ou plusieurs) sur jour et mois.

    Bords numériques gardés par ``(?:^|[^0-9])`` / ``(?:[^0-9]|$)`` : un
    chiffre voisin est rejeté (le jour ``5`` ne matche pas dans
    ``15/09/2008``), mais un séparateur de release courant (``_``, lettre,
    ``.``) ou un bord de chaîne reste accepté (``keroro_21/09/2008`` matche).
    RE2 n'ayant pas de lookaround, on consomme un caractère voisin — sans
    effet pour une recherche booléenne ``search()``.

    Les séparateurs internes ``[/.\-]`` peuvent différer entre eux (filet
    large voulu ; RE2 sans backreference ne peut les contraindre identiques).
    """
    day = d.day
    month = d.month
    year = d.year
    month_name = FRENCH_MONTHS[month]
    head = r"(?:^|[^0-9])"
    tail = r"(?:[^0-9]|$)"
    literal = rf"{head}0*{day}\s+{month_name}\s+{year}{tail}"
    dmy = rf"{head}0*{day}[/.\-]0*{month}[/.\-]{year}{tail}"
    ymd = rf"{head}{year}[/.\-]0*{month}[/.\-]0*{day}{tail}"
    return rf"(?:{literal}|{dmy}|{ymd})"
