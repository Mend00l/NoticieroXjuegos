import html
import logging
import re
from datetime import datetime, timezone

import feedparser
import httpx

import criba
from fuentes import POR_NOMBRE, Fuente

logger = logging.getLogger(__name__)

# Varios de los once responden 403 al agente de una libreria. Con el de un
# Chrome normal entran los once, comprobado el 22-oct-2026.
CABECERAS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.8",
}

# Lo que cabe en el pie de foto de Telegram son 1024 caracteres contando las
# etiquetas. Se recorta el resumen bastante antes para que quepa el titular.
LARGO_RESUMEN = 300


def _limpiar(texto: str | None) -> str:
    """Quita etiquetas, entidades y los "Leer mas" del final."""
    if not texto:
        return ""
    plano = re.sub(r"<[^>]+>", " ", texto)
    plano = html.unescape(plano)
    plano = re.sub(r"\s+", " ", plano).strip()
    return criba.COLETILLAS.sub("", plano).strip()


def _recortar(texto: str) -> str:
    """Corta en el punto mas cercano, que cortar a mitad de frase se lee mal."""
    if len(texto) <= LARGO_RESUMEN:
        return texto
    trozo = texto[:LARGO_RESUMEN]
    punto = max(trozo.rfind(". "), trozo.rfind("? "), trozo.rfind("! "))
    if punto > LARGO_RESUMEN // 2:
        return trozo[: punto + 1]
    return trozo.rsplit(" ", 1)[0] + "..."


def _foto(entrada) -> str | None:
    """La foto que declara el item, si la declara.

    Solo de las etiquetas de medios. Se probo tambien coger el primer <img>
    del cuerpo como respaldo y **salia mal**: en un feed de WordPress el
    primer <img> del articulo era el emoji de la sirena, y el bot publicaba
    una imagen de 72x72 de s.w.org. Lo que falte aqui lo saca completar()
    del og:image, que ademas viene en 1200x630.
    """
    for medio in entrada.get("media_content", []) + entrada.get("media_thumbnail", []):
        url = medio.get("url")
        if url:
            return url
    for adjunto in entrada.get("enclosures", []):
        if adjunto.get("type", "").startswith("image") and adjunto.get("href"):
            return adjunto["href"]
    return None


def _fecha(entrada) -> datetime | None:
    """La fecha del item, si es creible.

    MeriStation y Zonared sirven fechas de hace cuatro años en noticias de
    hoy. Por eso lo nuevo **no se decide por fecha** sino por el guid: esta
    solo vale para ordenar la cola, y si viene rara se deja sin ella.
    """
    for campo in ("published_parsed", "updated_parsed"):
        marca = entrada.get(campo)
        if not marca:
            continue
        try:
            fecha = datetime(*marca[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
        # Nada de futuro ni de hace mas de un mes: eso es un feed mintiendo.
        ahora = datetime.now(timezone.utc)
        if -3600 < (ahora - fecha).total_seconds() < 31 * 86400:
            return fecha
    return None


async def leer(cliente: httpx.AsyncClient, fuente: Fuente, tope: int) -> list[dict]:
    """Baja un feed y devuelve sus noticias ya limpias."""
    try:
        respuesta = await cliente.get(fuente.feed, headers=CABECERAS)
        respuesta.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning(f"{fuente.nombre}: no se pudo leer el feed ({type(e).__name__})")
        return []

    analizado = feedparser.parse(respuesta.text)
    noticias = []
    for entrada in analizado.entries[:tope]:
        enlace = (entrada.get("link") or "").strip()
        titular = _limpiar(entrada.get("title"))
        if not enlace or not titular:
            continue
        # El guid es la clave de que una noticia ya se vio. Cuando el feed no
        # lo trae, el enlace hace de guid: es lo que no cambia.
        guid = (entrada.get("id") or enlace).strip()
        noticias.append({
            "fuente": fuente.nombre,
            "guid": guid,
            "enlace": enlace,
            "clave_enlace": criba.clave_enlace(enlace),
            "titular": titular,
            "resumen": _recortar(_limpiar(entrada.get("summary"))),
            "foto": _foto(entrada),
            "fecha": _fecha(entrada),
            # Las categorias del item. La criba las usa para distinguir la
            # publicidad de producto de Eurogamer ES, que por titular no se
            # distingue de una noticia.
            "categorias": [t.get("term") for t in entrada.get("tags", []) if t.get("term")],
        })
    return noticias


ETIQUETAS_OG = {
    "foto": re.compile(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I),
    "resumen": re.compile(
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']+)', re.I),
}
# Algunos ponen content antes de property. Pasa en Vandal.
ETIQUETAS_OG_AL_REVES = {
    "foto": re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', re.I),
    "resumen": re.compile(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:description["\']', re.I),
}


def _le_falta(noticia: dict) -> bool:
    return not noticia.get("foto") or len(noticia.get("resumen") or "") < 40


async def completar(cliente: httpx.AsyncClient, noticia: dict) -> dict:
    """Abre la pagina de la noticia para lo que el feed no dio.

    Se llama justo antes de publicar y no al sondear: asi no se gasta una
    peticion en las noticias que la criba va a tirar.

    Las fuentes marcadas con abrir_pagina se abren aunque no falte nada, y lo
    del og: manda sobre lo del feed. Vandal, por ejemplo, sirve en el feed la
    miniatura del video a 320x180 y en el og:image la misma foto a 1200x630.
    """
    fuente = POR_NOMBRE.get(noticia["fuente"])
    manda_og = bool(fuente and fuente.abrir_pagina)
    if not manda_og and not _le_falta(noticia):
        return noticia

    try:
        respuesta = await cliente.get(noticia["enlace"], headers=CABECERAS)
        respuesta.raise_for_status()
    except httpx.HTTPError as e:
        logger.info(f"{noticia['fuente']}: no se pudo abrir la pagina ({type(e).__name__})")
        return noticia

    cabeza = respuesta.text[:60000]
    for campo in ("foto", "resumen"):
        tiene = noticia.get("foto") if campo == "foto" else len(noticia.get("resumen") or "") >= 40
        if tiene and not manda_og:
            continue
        encontrado = (
            ETIQUETAS_OG[campo].search(cabeza)
            or ETIQUETAS_OG_AL_REVES[campo].search(cabeza)
        )
        if encontrado:
            valor = html.unescape(encontrado.group(1)).strip()
            noticia[campo] = _recortar(valor) if campo == "resumen" else valor
    return noticia
