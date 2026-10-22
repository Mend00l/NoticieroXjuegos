"""Ensayo: lee los feeds de verdad y dice que haria, sin base y sin Telegram.

    python -m herramientas.ensayo

Sirve para ajustar la criba y el umbral de parecido mirando titulares reales
antes de tocar nada en produccion.
"""
import asyncio
import sys
from datetime import datetime, timezone

import httpx

import config
import criba
import feeds
import publicar
from fuentes import FUENTES


async def main():
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as cliente:
        resultados = await asyncio.gather(
            *(feeds.leer(cliente, f, config.TOPE_POR_FUENTE) for f in FUENTES),
            return_exceptions=True,
        )

        todas = []
        print("FUENTE                 LEIDAS")
        for fuente, resultado in zip(FUENTES, resultados):
            if isinstance(resultado, Exception):
                print(f"{fuente.nombre:22} FALLO {resultado!r}")
                continue
            print(f"{fuente.nombre:22} {len(resultado)}")
            todas.extend(resultado)

        ahora = datetime.now(timezone.utc)
        todas.sort(key=lambda n: n["fecha"] or ahora)

        pasan, por_criba, repetidas = [], [], []
        vistas = []
        for noticia in todas:
            motivo = criba.motivo_descarte(noticia["titular"], noticia["enlace"])
            claves = criba.palabras_clave(noticia["titular"])
            if not motivo:
                for otra_fuente, otras, otro_titular in vistas:
                    if criba.parecido(claves, otras) >= config.UMBRAL_PARECIDO:
                        motivo = f"repetida de {otra_fuente}: {otro_titular[:60]}"
                        break
            if motivo and "repetida" in motivo:
                repetidas.append((noticia, motivo))
            elif motivo:
                por_criba.append((noticia, motivo))
            else:
                pasan.append(noticia)
                vistas.append((noticia["fuente"], claves, noticia["titular"]))

        print(f"\n{'='*70}\nSE PUBLICARIAN {len(pasan)}")
        for n in pasan:
            foto = "foto" if n["foto"] else "SIN FOTO"
            resumen = "resumen" if len(n["resumen"] or "") > 40 else "SIN RESUMEN"
            print(f"  [{n['fuente']}] [{foto}/{resumen}] {n['titular'][:75]}")

        print(f"\n{'='*70}\nLA CRIBA TIRA {len(por_criba)}")
        for n, motivo in por_criba:
            print(f"  [{n['fuente']}] {n['titular'][:60]}\n      -> {motivo}")

        print(f"\n{'='*70}\nREPETIDAS EN OTRO MEDIO {len(repetidas)}")
        for n, motivo in repetidas:
            print(f"  [{n['fuente']}] {n['titular'][:60]}\n      -> {motivo}")

        # Y como queda el mensaje. Las que no traen foto o resumen se
        # completan abriendo la pagina, igual que haria el bot al publicar.
        print(f"\n{'='*70}\nTRES MENSAJES DE MUESTRA")
        for n in pasan[:3]:
            completa = await feeds.completar(cliente, dict(n))
            print(f"\n--- {completa['fuente']} ---")
            print(f"foto: {completa['foto']}")
            print(publicar.montar(completa))

        print(f"\n{'='*70}")
        print(f"Leidas {len(todas)}, publicarian {len(pasan)}, "
              f"criba {len(por_criba)}, repetidas {len(repetidas)}")


if __name__ == "__main__":
    # El ensayo no publica ni toca la base, asi que no necesita token.
    sys.exit(asyncio.run(main()) or 0)
