"""Afinar la deteccion de repetidas con los titulares de hoy.

    python -m herramientas.afinar

Baja los feeds una vez, los guarda en disco y prueba varias formas de
medir el parecido. Imprime las parejas que juntaria cada una, para poder
mirar con los ojos si acierta antes de poner un numero en config.py.
"""
import asyncio
import itertools
import json
import os
import sys
from pathlib import Path

import httpx

import config
import criba
import feeds
from fuentes import FUENTES

CACHE = Path(os.environ.get("TEMP", ".")) / "titulares_hoy.json"


async def bajar():
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as cliente:
        resultados = await asyncio.gather(
            *(feeds.leer(cliente, f, config.TOPE_POR_FUENTE) for f in FUENTES),
            return_exceptions=True,
        )
    todas = []
    for resultado in resultados:
        if not isinstance(resultado, Exception):
            todas.extend({"fuente": n["fuente"], "titular": n["titular"],
                          "enlace": n["enlace"],
                          "categorias": n.get("categorias")} for n in resultado)
    return todas


def jaccard(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def solape(a, b):
    """Cuanto del titular corto esta en el largo. Mas justo entre titulares
    de distinto tamaño, que es lo normal entre dos medios."""
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def dice(a, b):
    return 2 * len(a & b) / (len(a) + len(b)) if a and b else 0.0


MEDIDAS = {"jaccard": jaccard, "solape": solape, "dice": dice}


def main():
    if CACHE.exists():
        todas = json.loads(CACHE.read_text(encoding="utf-8"))
        print(f"{len(todas)} titulares de {CACHE}")
    else:
        todas = asyncio.run(bajar())
        CACHE.write_text(json.dumps(todas, ensure_ascii=False), encoding="utf-8")
        print(f"{len(todas)} titulares bajados y guardados en {CACHE}")

    # Solo los que pasarian la criba: los demas no llegan a compararse.
    utiles = [
        n for n in todas
        if not criba.motivo_descarte(n["titular"], n["enlace"], n.get("categorias"))
    ]
    claves = {i: criba.palabras_clave(n["titular"]) for i, n in enumerate(utiles)}
    print(f"{len(utiles)} pasan la criba\n")

    for nombre, medida in MEDIDAS.items():
        for umbral in (0.35, 0.45, 0.55, 0.6):
            parejas = [
                (i, j, medida(claves[i], claves[j]))
                for i, j in itertools.combinations(range(len(utiles)), 2)
                if len(claves[i] & claves[j]) >= criba.MINIMO_COMUN
                and medida(claves[i], claves[j]) >= umbral
            ]
            print(f"{nombre:8} umbral {umbral}: {len(parejas)} parejas")

    # Y el detalle de la que mejor pinta tiene, para mirarla una a una.
    elegida = sys.argv[1] if len(sys.argv) > 1 else "solape"
    corte = float(sys.argv[2]) if len(sys.argv) > 2 else 0.45
    print(f"\n{'='*70}\nDETALLE: {elegida} a {corte}\n")
    for i, j in itertools.combinations(range(len(utiles)), 2):
        if len(claves[i] & claves[j]) < criba.MINIMO_COMUN:
            continue
        valor = MEDIDAS[elegida](claves[i], claves[j])
        if valor >= corte:
            print(f"{valor:.2f}  [{utiles[i]['fuente']}] {utiles[i]['titular'][:68]}")
            print(f"      [{utiles[j]['fuente']}] {utiles[j]['titular'][:68]}")
            print(f"      comun: {sorted(claves[i] & claves[j])}\n")


if __name__ == "__main__":
    main()
