import logging
from html import escape

import telegram.error
from telegram import Bot, LinkPreviewOptions

import config

logger = logging.getLogger(__name__)

# Telegram admite 1024 caracteres en el pie de una foto y 4096 en un mensaje
# de texto. Se trabaja con el limite corto para los dos, que el mismo
# mensaje puede salir con foto o sin ella segun lo que diera el feed.
TOPE_PIE = 1024


def montar(noticia: dict, cita: bool = True) -> str:
    """El mensaje: titular en negrita, resumen en una cita, y la fuente como enlace.

    El enlace va en el nombre de la fuente y no suelto porque asi el mensaje
    dice de donde viene y se puede pulsar, sin una linea de direccion cruda.

    `cita` se puede apagar porque **no esta comprobado que Telegram acepte
    <blockquote> en el pie de una foto**: su documentacion lo da como
    entidad pero no dice nada de los pies. Si lo rechaza, enviar() vuelve a
    llamar aqui sin la cita en vez de perder la noticia.
    """
    titular = escape(noticia["titular"])
    fuente = escape(noticia["fuente"])
    enlace = escape(noticia["enlace"], quote=True)
    pie = f'<a href="{enlace}">{fuente}</a>'
    abre, cierra = ("<blockquote>", "</blockquote>") if cita else ("", "")

    cuerpo = f"<b>{titular}</b>\n\n{pie}"
    resumen = (noticia.get("resumen") or "").strip()
    if not resumen:
        return cuerpo

    # Se recorta el resumen, nunca el titular ni el enlace: si algo tiene que
    # caerse del mensaje, que sea lo que menos falta hace.
    hueco = TOPE_PIE - len(f"<b>{titular}</b>\n\n{abre}{cierra}\n\n{pie}")
    if hueco < 60:
        return cuerpo

    # Se quitan palabras del final y se mide **lo ya escapado**, que un & se
    # convierte en cinco caracteres y por ahi se salia del pie. Y se recorta
    # el texto original, no el escapado: cortar el escapado partiria una
    # entidad por la mitad y Telegram rechazaria el mensaje entero.
    palabras = resumen.split()
    recortado = False
    while palabras:
        texto = escape(" ".join(palabras)) + ("..." if recortado else "")
        if len(texto) <= hueco:
            break
        palabras.pop()
        recortado = True
    else:
        return cuerpo

    return f"<b>{titular}</b>\n\n{abre}{texto}{cierra}\n\n{pie}"


async def enviar(bot: Bot, noticia: dict):
    """Manda la noticia, y si la cita no cuela la manda sin ella."""
    try:
        await _mandar(bot, noticia, montar(noticia))
    except telegram.error.BadRequest as e:
        if "entit" not in str(e).lower():
            raise
        logger.warning(
            f"Telegram no acepta la cita en el mensaje ({e}); se manda sin ella"
        )
        await _mandar(bot, noticia, montar(noticia, cita=False))


async def _mandar(bot: Bot, noticia: dict, texto: str):
    """Con foto si la hay, y si no con vista previa."""
    destino = {"chat_id": config.GRUPO_ID, "message_thread_id": config.TEMA_ID}

    if noticia.get("foto"):
        try:
            await bot.send_photo(
                photo=noticia["foto"], caption=texto, parse_mode="HTML", **destino
            )
            return
        except telegram.error.BadRequest as e:
            # Si la queja es del formato y no de la foto, que suba: mandarlo
            # como texto con el mismo formato fallaria igual, y el log diria
            # "foto rechazada" cuando la foto no tiene nada que ver.
            if "entit" in str(e).lower():
                raise
            # Pasa: la foto que anuncia el feed da 404, o es un svg, o pesa
            # mas de lo que Telegram se traga. La noticia no se pierde por
            # eso, sale como texto.
            logger.info(f"{noticia['fuente']}: foto rechazada ({e}), va sin ella")

    await bot.send_message(
        text=texto,
        parse_mode="HTML",
        link_preview_options=LinkPreviewOptions(
            url=noticia["enlace"], prefer_large_media=True
        ),
        **destino,
    )
