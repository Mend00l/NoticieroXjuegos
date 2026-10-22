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
async def bucle_cola(bot):
    """Saca una noticia cada PAUSA_PUBLICACION segundos.

    En un bucle propio y no en una cita del planificador porque lo que hace
    falta aqui es un ritmo constante, no una hora concreta: asi una tanda de
    diez noticias tarda siete minutos en salir en vez de caer de golpe.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as cliente:
        while True:
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
                logger.info(f"Publicada [{noticia['fuente']}] {noticia['titular'][:60]}")
                await asyncio.sleep(config.PAUSA_PUBLICACION)

            except asyncio.CancelledError:
                raise
            except telegram.error.RetryAfter as e:
                logger.warning(f"Telegram pide esperar {e.retry_after} s")
                await asyncio.sleep(e.retry_after + 1)
            except telegram.error.BadRequest as e:
                # Esto no se arregla reintentando, y la noticia esta a la
                # cabeza de la cola: dejarla ahi es parar el bot entero.
                logger.error(f"Telegram rechaza la noticia {noticia['id']}: {e}")
                await noticias.apartar(noticia["id"], f"Telegram: {e}")
            except Exception:
                logger.exception("Fallo al publicar, se reintenta")
                await asyncio.sleep(30)


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
    app.bot_data["cola"] = asyncio.create_task(bucle_cola(app.bot))
    # Un sondeo al arrancar, que si no el primero llega a los quince minutos.
    app.bot_data["primer_sondeo"] = asyncio.create_task(noticias.sondear())
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
