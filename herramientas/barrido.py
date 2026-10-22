"""Barrido: que umbral de frecuencia y de parecido aciertan mas.

    python -m herramientas.barrido

Usa los titulares que dejo guardados herramientas.afinar. Las parejas de
verdad y las falsas estan apuntadas a mano en ACIERTOS y FALLOS mirando la
tanda del 22-oct-2026, asi que esto mide, no adivina.
"""
import itertools
import json
import os
from pathlib import Path

import criba

CACHE = Path(os.environ.get("TEMP", ".")) / "titulares_hoy.json"

# Parejas que SI son la misma noticia, por un trozo de cada titular.
ACIERTOS = [
    ("EA cierra Bioware", "EA is closing BioWare"),
    ("Ys VIII Lacrimosa of DANA", "Ys VIII: Lacrimosa of Dana"),
    ("Phantom Blade Zero confirma", "Phantom Blade Zero luce"),
    ("Phantom Blade Zero confirma", "Phantom Blade Zero launch trailer"),
    ("Electronic Arts comunica", "Electronic Arts despedir"),
    ("Electronic Arts comunica", "EA is closing BioWare"),
    ("Anunciado Serious Sam", "Serious Sam: The Third Encounter announced"),
    ("Cyberpunk 2077 recibir", "Cyberpunk 2077 version 2.5"),
    ("Phantom Blade Zero luce", "Phantom Blade Zero launch trailer"),
    ("EA is closing BioWare", "BioWare is closing down"),
    ("EA is closing BioWare", "Mass Effect 5 Cancelled As Legendary"),
    ("Cyberpunk 2077 is getting another", "Cyberpunk 2077 version 2.5"),
    ("Ace Driver Victory Lap is the next", "Arcade Archives Ace Driver"),
    ("A permanent Pok", "A Permanent Pok"),
    ("BioWare is closing down", "Mass Effect 5 Cancelled As Legendary"),
    ("CD Projekt Red details new Cyberpunk", "Cyberpunk 2077 version 2.5"),
    ("Cyberpunk 2077 version 2.5", "Cyberpunk 2077: Edgerunners 2 Update"),
    ("EA Shuts Down Legendary RPG", "Mass Effect 5 Cancelled As Legendary"),
]

# Parejas que NO lo son, aunque compartan palabras.
FALLOS = [
    ("Hatsune Miku Connecting Puzzle", "RV There Yet?"),
    ("Hatsune Miku Connecting Puzzle", "Pratfall coming to PS5"),
    ("CRYMELIGHT demo now available", "LET IT DIE: INFERNO demo"),
    ("RV There Yet?", "Pratfall coming to PS5"),
    ("RV There Yet?", "Xbox Announces Eight Titles"),
    ("Console Archives Raiden Project", "Arcade Archives Ace Driver"),
    ("Comparativa en v", "Nintendo Switch Sports Resort estrena"),
    ("Los jugadores de Nintendo Switch Sports", "Nintendo Switch Sports Resort estrena"),
    # Mismo juego, dos noticias: una de requisitos y otra de fecha.
    ("Shrek 2 Remastered pide una RTX", "Shrek 2 Remastered Gets Official"),
    # Las dos acaban en la coletilla de Nintendo Life "Here Are The Full
    # Patch Notes", que es lo unico que comparten.
    ("Cyberpunk 2077: Edgerunners 2 Update", "Nintendo Switch Sports Resort Has Been"),
]


def buscar(titulares, trozo):
    for i, n in enumerate(titulares):
        if trozo.lower() in n["titular"].lower():
            return i
    return None


def main():
    todas = json.loads(CACHE.read_text(encoding="utf-8"))
    utiles = [n for n in todas if not criba.motivo_descarte(n["titular"], n["enlace"])]
    claves = [criba.palabras_clave(n["titular"]) for n in utiles]

    etiquetadas = []
    for esperado, parejas in ((True, ACIERTOS), (False, FALLOS)):
        for uno, otro in parejas:
            i, j = buscar(utiles, uno), buscar(utiles, otro)
            if i is None or j is None:
                print(f"OJO: no encuentro '{uno if i is None else otro}'")
                continue
            etiquetadas.append((i, j, esperado))

    buenas = sum(1 for _, _, e in etiquetadas if e)
    malas = len(etiquetadas) - buenas
    print(f"{len(utiles)} titulares, {buenas} parejas buenas y {malas} malas apuntadas")
    print(f"minimo de palabras en comun: {criba.MINIMO_COMUN}\n")
    print(f"{'umbral':7} {'cazadas':10} {'perdidas':10} {'falsos':9} juntadas en total")

    for umbral in (0.4, 0.45, 0.5, 0.55, 0.6):
        cazadas = sum(
            1 for i, j, e in etiquetadas
            if e and criba.parecido(claves[i], claves[j]) >= umbral
        )
        falsos = sum(
            1 for i, j, e in etiquetadas
            if not e and criba.parecido(claves[i], claves[j]) >= umbral
        )
        # Y las que juntaria sin estar apuntadas, para no mirar solo lo mio.
        total = sum(
            1 for i, j in itertools.combinations(range(len(utiles)), 2)
            if criba.parecido(claves[i], claves[j]) >= umbral
        )
        print(f"{umbral:<7} {cazadas}/{buenas:<8} {buenas - cazadas:<10} "
              f"{falsos}/{malas:<7} {total}")


if __name__ == "__main__":
    main()
