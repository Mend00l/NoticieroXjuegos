"""Que secciones sirve cada feed, para construir la criba con datos.

    python -m herramientas.secciones

Imprime los primeros tramos de la direccion de cada noticia, con cuantas
hay de cada uno y un titular de muestra. Sirve para ver de un vistazo que
un medio tiene seccion propia de cine o de guias, en vez de descubrirlo
porque se cuela una en el tema.
"""
import asyncio
from collections import Counter, defaultdict
from urllib.parse import urlsplit

import httpx

import config
import criba
import feeds
from fuentes import FUENTES


async def main():
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as cliente:
        resultados = await asyncio.gather(
            *(feeds.leer(cliente, f, 40) for f in FUENTES),
            return_exceptions=True,
        )

    for fuente, resultado in zip(FUENTES, resultados):
        if isinstance(resultado, Exception):
            print(f"\n=== {fuente.nombre}: FALLO {resultado!r}")
            continue

        cuenta = Counter()
        tirados = Counter()
        muestra = defaultdict(list)
        for n in resultado:
            tramos = [t for t in urlsplit(n["enlace"]).path.split("/") if t]
            seccion = "/" + (tramos[0] if tramos else "")
            cuenta[seccion] += 1
            # Se pregunta a la criba de verdad, con la direccion entera. Antes
            # se comprobaba solo la seccion contra RUTAS_FUERA, y eso decia
            # que /features pasaba cuando en realidad se filtra.
            motivo = criba.motivo_descarte(n["titular"], n["enlace"])
            if motivo:
                tirados[seccion] += 1
            else:
                muestra[seccion].append(n["titular"])

        print(f"\n=== {fuente.nombre} ({len(resultado)} noticias)")
        for seccion, veces in cuenta.most_common():
            fuera = tirados[seccion]
            pasan = muestra[seccion]
            marca = f"tira {fuera}/{veces}".ljust(11)
            ejemplo = pasan[0][:58] if pasan else "(todas fuera)"
            print(f"  {marca} {seccion:26} {ejemplo}")


if __name__ == "__main__":
    asyncio.run(main())
