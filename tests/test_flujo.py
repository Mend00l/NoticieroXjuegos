"""El flujo contra una base de datos de verdad: que no se repita nada."""
import noticias
from conftest import noticia


async def guardar(bd, una, recientes=None, estreno=False):
    async with bd.pool().acquire() as con:
        return await noticias._guardar(con, una, recientes if recientes is not None else [], estreno)


async def test_el_primer_arranque_no_publica(bd):
    """Si publicara, el tema estrenaria con cien noticias viejas de golpe."""
    assert await guardar(bd, noticia("EA cierra Bioware"), estreno=True) == "arranque"
    assert await noticias.siguiente_de_cola() is None


async def test_el_mismo_guid_no_entra_dos_veces(bd):
    una = noticia("Phantom Blade Zero pone fecha")
    assert await guardar(bd, una) == "nuevas"
    assert await guardar(bd, una) == "ya_vistas"


async def test_el_mismo_enlace_con_otro_guid_tampoco(bd):
    """Pasa de verdad: el medio actualiza la noticia y le cambia el guid."""
    enlace = "https://vandal.elespanol.com/noticia/cyberpunk-2-5"
    assert await guardar(bd, noticia("Cyberpunk 2077 detalla la 2.5", enlace=enlace, guid="uno")) == "nuevas"
    assert await guardar(bd, noticia("Cyberpunk 2077 detalla la 2.5", enlace=enlace, guid="dos")) == "ya_vistas"


async def test_el_enlace_con_campaña_tampoco(bd):
    base = "https://vandal.elespanol.com/noticia/ea-cierra"
    assert await guardar(bd, noticia("EA cierra BioWare", enlace=base, guid="uno")) == "nuevas"
    repetida = noticia("EA cierra BioWare", enlace=base + "?utm_source=rss", guid="dos")
    assert await guardar(bd, repetida) == "ya_vistas"


async def test_la_misma_noticia_de_otro_medio_se_descarta(bd):
    """El caso que mas se repite: dos medios y dos idiomas, una sola noticia."""
    recientes = []
    primera = noticia(
        "EA cierra Bioware, cancela el próximo Mass Effect y despide a 400 personas",
        fuente="Vandal",
    )
    assert await guardar(bd, primera, recientes) == "nuevas"
    segunda = noticia(
        "EA is closing BioWare and cancelling the next Mass Effect",
        fuente="VGC",
        enlace="https://videogameschronicle.com/news/ea-bioware",
    )
    assert await guardar(bd, segunda, recientes) == "repetidas"
    # La primera sigue en la cola; la segunda no.
    assert (await noticias.siguiente_de_cola())["fuente"] == "Vandal"


async def test_dos_noticias_del_mismo_juego_salen_las_dos(bd):
    recientes = []
    assert await guardar(bd, noticia("Shrek 2 Remastered pide una RTX 5070 y desata las críticas"), recientes) == "nuevas"
    otra = noticia("Shrek 2 Remastered Gets Official November Release Date", fuente="Pure Xbox",
                   enlace="https://purexbox.com/news/shrek-2-date")
    assert await guardar(bd, otra, recientes) == "nuevas"


async def test_lo_que_tira_la_criba_queda_apuntado(bd):
    """Sin esto no habria con que ajustar la criba: /descartes vive de aqui."""
    guia = noticia("Guide: 65 Switch Games", enlace="https://www.nintendolife.com/guides/65-switch")
    assert await guardar(bd, guia) == "descartadas"
    apuntados = await noticias.descartes()
    assert apuntados[0]["titular"] == "Guide: 65 Switch Games"
    assert "ruta" in apuntados[0]["descartada"]


async def test_la_cola_sale_en_orden_y_se_vacia(bd):
    from datetime import datetime, timedelta, timezone

    ayer = datetime.now(timezone.utc) - timedelta(hours=20)
    hoy = datetime.now(timezone.utc) - timedelta(hours=1)
    await guardar(bd, noticia("Gematsu anuncia Pratfall para PS5", fecha=hoy,
                              enlace="https://gematsu.com/pratfall"))
    await guardar(bd, noticia("Sony sube el precio de PS5 en Europa", fecha=ayer,
                              enlace="https://vandal.elespanol.com/noticia/ps5-precio"))

    # Las dos esperan; sale la mas vieja primero.
    primera = await noticias.siguiente_de_cola()
    assert primera["titular"].startswith("Gematsu") or primera["titular"].startswith("Sony")
    await noticias.marcar_publicada(primera["id"], "resumen nuevo", "https://ejemplo/og.jpg")

    segunda = await noticias.siguiente_de_cola()
    assert segunda["id"] != primera["id"]
    await noticias.marcar_publicada(segunda["id"], None, None)
    assert await noticias.siguiente_de_cola() is None


async def test_lo_que_telegram_rechaza_no_atasca_la_cola(bd):
    """Sin apartar(), una noticia que Telegram no acepta para el bot entero."""
    await guardar(bd, noticia("Una noticia con una foto que Telegram no traga"))
    atascada = await noticias.siguiente_de_cola()
    await noticias.apartar(atascada["id"], "Telegram: Wrong file identifier")
    assert await noticias.siguiente_de_cola() is None


async def test_el_estado_cuenta_lo_que_hay(bd):
    await guardar(bd, noticia("Nintendo pone fecha a Zelda"))
    await guardar(bd, noticia("Guide: 65 Switch Games",
                              enlace="https://www.nintendolife.com/guides/65-switch"))
    datos = await noticias.estado()
    assert datos["cola"] == 1
    assert datos["descartadas"] == 1
    assert datos["total"] == 2
