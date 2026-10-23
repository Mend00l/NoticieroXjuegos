import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx

import config
import criba
import feeds
from db.pool import pool
from fuentes import FUENTES

logger = logging.getLogger(__name__)


async def sondear() -> dict:
    """Mira los once feeds y guarda lo que sea nuevo. Devuelve el recuento."""
    async with httpx.AsyncClient(follow_redirects=True, timeout=25.0) as cliente:
        resultados = await asyncio.gather(
            *(feeds.leer(cliente, f, config.TOPE_POR_FUENTE) for f in FUENTES),
            return_exceptions=True,
        )

    encontradas = []
    for fuente, resultado in zip(FUENTES, resultados):
        if isinstance(resultado, Exception):
            logger.warning(f"{fuente.nombre}: fallo al leer ({resultado!r})")
            continue
        encontradas.extend(resultado)

    # De las mas viejas a las mas nuevas, para que la cola salga en orden y
    # para que entre dos noticias parecidas sobreviva la primera que se dijo.
    # Las que no traen fecha creible van al final y se ordenan por fuente.
    encontradas.sort(key=lambda n: n["fecha"] or datetime.now(timezone.utc))

    cuenta = {"nuevas": 0, "descartadas": 0, "repetidas": 0, "ya_vistas": 0, "arranque": 0}
    async with pool().acquire() as con:
        # El primer sondeo encuentra lo ultimo de once feeds: unas cien
        # noticias de los dos ultimos dias. Publicarlas seria estrenar el
        # tema con cien mensajes viejos, asi que **la primera vez solo se
        # anotan**. A partir de ahi ya se publica lo que vaya saliendo.
        estreno = await con.fetchval("SELECT NOT EXISTS (SELECT 1 FROM noticias)")
        if estreno:
            logger.info("Primer sondeo: se anota lo que hay sin publicarlo")
        recientes = await _claves_recientes(con)
        for noticia in encontradas:
            resultado = await _guardar(con, noticia, recientes, estreno)
            cuenta[resultado] += 1

    logger.info(
        f"Sondeo: {cuenta['nuevas']} a la cola, {cuenta['descartadas']} por la criba, "
        f"{cuenta['repetidas']} repetidas de otro medio, {cuenta['ya_vistas']} ya vistas, "
        f"{cuenta['arranque']} anotadas sin publicar"
    )
    return cuenta


async def _claves_recientes(con) -> list[tuple[int, str, set[str]]]:
    """Titulares de las ultimas horas, para comparar parecidos.

    Solo las que cuentan: las publicadas y las que esperan en la cola. Una
    descartada no tapa a otra, que si no un falso positivo se arrastraria.
    """
    desde = datetime.now(timezone.utc) - timedelta(hours=config.HORAS_PARECIDO)
    filas = await con.fetch(
        "SELECT id, fuente, claves FROM noticias "
        "WHERE vista > $1 AND descartada IS NULL",
        desde,
    )
    return [(f["id"], f["fuente"], set(f["claves"])) for f in filas]


async def _guardar(con, noticia: dict, recientes: list, estreno: bool) -> str:
    """Mete una noticia y dice que se hizo con ella."""
    motivo = criba.motivo_descarte(
        noticia["titular"], noticia["enlace"], noticia.get("categorias")
    )
    claves = criba.palabras_clave(noticia["titular"])

    if not motivo:
        for otro_id, otra_fuente, otras in recientes:
            if criba.parecido(claves, otras) >= config.UMBRAL_PARECIDO:
                motivo = f"repetida de {otra_fuente} (#{otro_id})"
                break

    if not motivo and estreno:
        motivo = "primer arranque"

    fila = await con.fetchrow(
        "INSERT INTO noticias "
        "  (fuente, guid, enlace, clave_enlace, titular, resumen, foto, claves, fecha, descartada) "
        "VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) "
        "ON CONFLICT DO NOTHING RETURNING id",
        noticia["fuente"], noticia["guid"], noticia["enlace"], noticia["clave_enlace"],
        noticia["titular"], noticia["resumen"], noticia["foto"],
        sorted(claves), noticia["fecha"], motivo,
    )
    if fila is None:
        return "ya_vistas"

    if motivo is None:
        # Entra en la lista de la vuelta, para que dos medios que publican lo
        # mismo en el mismo sondeo no salgan los dos.
        recientes.append((fila["id"], noticia["fuente"], claves))
        return "nuevas"
    if motivo == "primer arranque":
        return "arranque"
    if motivo.startswith("repetida"):
        return "repetidas"
    return "descartadas"


async def siguiente_de_cola() -> dict | None:
    """La noticia mas vieja que espera turno."""
    async with pool().acquire() as con:
        fila = await con.fetchrow(
            "SELECT id, fuente, enlace, titular, resumen, foto FROM noticias "
            "WHERE publicada IS NULL AND descartada IS NULL "
            "ORDER BY vista, id LIMIT 1"
        )
    return dict(fila) if fila else None


async def marcar_publicada(id_noticia: int, resumen: str | None, foto: str | None):
    """Deja constancia, y guarda lo que se saco de la pagina al completarla."""
    async with pool().acquire() as con:
        await con.execute(
            "UPDATE noticias SET publicada = now(), resumen = $2, foto = $3 WHERE id = $1",
            id_noticia, resumen, foto,
        )


async def apartar(id_noticia: int, motivo: str):
    """Saca de la cola lo que no se ha podido publicar, para que no la atasque."""
    async with pool().acquire() as con:
        await con.execute(
            "UPDATE noticias SET descartada = $2 WHERE id = $1", id_noticia, motivo
        )


async def estado() -> dict:
    desde = datetime.now(timezone.utc) - timedelta(hours=24)
    async with pool().acquire() as con:
        fila = await con.fetchrow(
            "SELECT "
            "  count(*) FILTER (WHERE publicada IS NULL AND descartada IS NULL) AS cola, "
            "  count(*) FILTER (WHERE publicada > $1) AS publicadas, "
            "  count(*) FILTER (WHERE descartada IS NOT NULL AND vista > $1) AS descartadas, "
            "  count(*) AS total "
            "FROM noticias",
            desde,
        )
        por_fuente = await con.fetch(
            "SELECT fuente, count(*) AS n FROM noticias "
            "WHERE publicada > $1 GROUP BY fuente ORDER BY n DESC",
            desde,
        )
    return {**dict(fila), "por_fuente": [(f["fuente"], f["n"]) for f in por_fuente]}


async def descartes(cuantos: int = 20) -> list[dict]:
    async with pool().acquire() as con:
        filas = await con.fetch(
            "SELECT fuente, titular, descartada FROM noticias "
            "WHERE descartada IS NOT NULL ORDER BY id DESC LIMIT $1",
            cuantos,
        )
    return [dict(f) for f in filas]
