import asyncio
import logging
from html import escape

import httpx
import telegram.error
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import config
import feeds
import noticias
import publicar
from db import pool
from fuentes import FUENTES

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

ZONA = "Europe/Madrid"

# APScheduler descarta de fabrica una cita que llega con un segundo de
# retraso, y no avisa: para el no ha fallado, no ha llegado a correr. Este
# bot se pasa el rato esperando a nueve servidores, asi que un sondeo puede
# tocar con el bucle ocupado. Con una hora de cortesia se ejecuta igual.
GRACIA = {"misfire_grace_time": 3600}


# Comandos
def _manda(update: Update) -> bool:
    return bool(update.effective_user and update.effective_user.id in config.ADMINS)


async def cmd_estado(update: Update, contexto: ContextTypes.DEFAULT_TYPE):
    if not _manda(update):
        return
    datos = await noticias.estado()
    lineas = [
        f"<b>Noticias</b>: {datos['cola']} en cola",
        f"Publicadas en 24 h: {datos['publicadas']}",
        f"Descartadas en 24 h: {datos['descartadas']}",
        f"Vistas en total: {datos['total']}",
        f"Fuentes: {len(FUENTES)}",
    ]
    # Si la cola esta muerta, el bot sigue contestando a esto tan contento y
    # no publica nada. Que lo diga aqui, que es el primer sitio donde se
    # mira cuando el tema lleva horas callado.
    cola = contexto.application.bot_data.get("cola")
    if cola is None or cola.done():
        lineas.insert(0, "<b>LA COLA NO ESTA CORRIENDO</b>, mira el log")

    if datos["por_fuente"]:
        lineas.append("")
        lineas += [f"{escape(n)}: {c}" for n, c in datos["por_fuente"]]
    await update.message.reply_html("\n".join(lineas))


async def cmd_descartes(update: Update, contexto: ContextTypes.DEFAULT_TYPE):
    """Lo que la criba ha tirado, para poder ajustarla con datos."""
    if not _manda(update):
        return
    filas = await noticias.descartes()
    if not filas:
        await update.message.reply_text("Nada descartado todavía.")
        return
    lineas = [
        f"<b>{escape(f['fuente'])}</b>: {escape(f['titular'][:90])}\n"
        f"   <i>{escape(f['descartada'])}</i>"
        for f in filas
    ]
    await update.message.reply_html("\n".join(lineas))


async def cmd_sondear(update: Update, contexto: ContextTypes.DEFAULT_TYPE):
    """Fuerza un sondeo sin esperar los quince minutos."""
    if not _manda(update):
        return
    await update.message.reply_text("Sondeando los feeds...")
    cuenta = await noticias.sondear()
    await update.message.reply_text(
        f"{cuenta['nuevas']} a la cola, {cuenta['descartadas']} por la criba, "
        f"{cuenta['repetidas']} repetidas, {cuenta['ya_vistas']} ya vistas."
    )


# La cola
#
# Cuantas veces se reintenta una noticia antes de apartarla. Apartarla hace
# falta --una foto que Telegram no traga esta a la cabeza de la cola y
# dejarla ahi para el bot entero-- pero al primer intento es demasiado
# pronto: un corte de red no es culpa de la noticia.
INTENTOS = 5

# Y cuando el problema **no es la noticia sino el destino**, no se aparta
# nada: se espera. Un tema cerrado, el bot sin permiso o expulsado se
# arreglan cuando Edu los arregla, y tirar las noticias mientras seria
# perderlas todas sin que nadie las haya leido. Esto paso de verdad: el
# codigo trataba TOPIC_CLOSED como error permanente.
DESTINO_CAIDO = (
    "topic_closed",
    "topic is closed",
    "message thread not found",
    "chat not found",
    "not enough rights",
    "have no rights",
    "bot was kicked",
    "bot is not a member",
    "bot was blocked",
)
ESPERA_DESTINO = 120


def _es_el_destino(e: Exception) -> bool:
    if isinstance(e, telegram.error.Forbidden):
        return True
    texto = str(e).lower()
    return any(t in texto for t in DESTINO_CAIDO)


async def bucle_cola(bot):
    """Saca una noticia cada PAUSA_PUBLICACION segundos.

    En un bucle propio y no en una cita del planificador porque lo que hace
    falta aqui es un ritmo constante, no una hora concreta: asi una tanda de
    diez noticias tarda siete minutos en salir en vez de caer de golpe.

    **Este bucle no puede morir.** Si muere, el bot se queda verde y mudo:
    los comandos contestan, el sondeo sigue llenando la cola y no sale una
    sola noticia. Por eso todo el cuerpo va dentro del try y el except no
    toca nada que pueda no existir.
    """
    fallos = {}
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as cliente:
        while True:
            noticia = None
            try:
                noticia = await noticias.siguiente_de_cola()
                if noticia is None:
                    await asyncio.sleep(20)
                    continue

                completa = await feeds.completar(cliente, noticia)
                await publicar.enviar(bot, completa)
                await noticias.marcar_publicada(
                    noticia["id"], completa.get("resumen"), completa.get("foto")
                )
                fallos.pop(noticia["id"], None)
                logger.info(f"Publicada [{noticia['fuente']}] {noticia['titular'][:60]}")
                await asyncio.sleep(config.PAUSA_PUBLICACION)

            except asyncio.CancelledError:
                raise
            except Exception as e:
                await _tropiezo(e, noticia, fallos)


async def _tropiezo(e: Exception, noticia: dict | None, fallos: dict):
    """Que hacer cuando una noticia no ha salido."""
    if noticia is None:
        # Ni se ha llegado a coger una: la base, casi seguro.
        logger.exception("Fallo antes de coger una noticia de la cola")
        await asyncio.sleep(30)
        return

    if _es_el_destino(e):
        logger.error(
            f"No se puede escribir en el tema ({e}). La cola espera; "
            f"no se descarta nada. Revisa que el bot siga en el grupo, que "
            f"el tema este abierto y que tenga permiso para escribir en el."
        )
        await asyncio.sleep(ESPERA_DESTINO)
        return

    if isinstance(e, telegram.error.RetryAfter):
        logger.warning(f"Telegram pide esperar {e.retry_after} s")
        await asyncio.sleep(e.retry_after + 1)
        return

    veces = fallos[noticia["id"]] = fallos.get(noticia["id"], 0) + 1
    logger.warning(
        f"No sale la noticia {noticia['id']} (intento {veces} de {INTENTOS}): {e}"
    )
    if veces >= INTENTOS:
        await noticias.apartar(noticia["id"], f"{veces} intentos: {e}")
        fallos.pop(noticia["id"], None)
        logger.error(f"Apartada la noticia {noticia['id']} para no parar la cola")
    await asyncio.sleep(30)


def _vigilar(tarea: asyncio.Task):
    """Avisa a gritos si una tarea de fondo se muere.

    Sin esto, una tarea lanzada con create_task que revienta **no se nota**:
    asyncio se guarda la excepcion y solo la saca al recoger la basura. El
    servicio sigue en verde y el bot mudo, que es el peor fallo posible
    porque no deja rastro en el log.
    """
    if tarea.cancelled():
        return
    fallo = tarea.exception()
    if fallo is not None:
        logger.critical(f"La tarea {tarea.get_name()} ha muerto", exc_info=fallo)


# Arranque
async def al_arrancar(app: Application):
    await pool.iniciar()

    planificador = AsyncIOScheduler(timezone=ZONA)
    planificador.add_job(
        noticias.sondear,
        IntervalTrigger(minutes=config.MINUTOS_SONDEO, timezone=ZONA),
        **GRACIA,
    )
    planificador.start()
    app.bot_data["planificador"] = planificador

    cola = asyncio.create_task(bucle_cola(app.bot), name="cola")
    cola.add_done_callback(_vigilar)
    app.bot_data["cola"] = cola

    # Un sondeo al arrancar, que si no el primero llega a los quince minutos.
    primero = asyncio.create_task(noticias.sondear(), name="primer sondeo")
    primero.add_done_callback(_vigilar)
    app.bot_data["primer_sondeo"] = primero
    logger.info(f"En marcha con {len(FUENTES)} fuentes, sondeo cada {config.MINUTOS_SONDEO} min")


async def al_cerrar(app: Application):
    planificador = app.bot_data.get("planificador")
    if planificador:
        planificador.shutdown(wait=False)
    tarea = app.bot_data.get("cola")
    if tarea:
        tarea.cancel()
    await pool.cerrar()


def main():
    config.validar()
    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .post_init(al_arrancar)
        .post_shutdown(al_cerrar)
        .build()
    )
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("descartes", cmd_descartes))
    app.add_handler(CommandHandler("sondear", cmd_sondear))
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
