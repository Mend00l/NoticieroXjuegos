import logging
from pathlib import Path

import asyncpg

from config import DATABASE_URL, DB_SSL

logger = logging.getLogger(__name__)

MIGRACIONES = Path(__file__).parent / "migraciones"

# Segundos que una conexion puede estar ociosa antes de reciclarla. La
# conexion va por la direccion publica de Railway, que pasa por un proxy TCP
# que corta lo que lleva un rato sin usarse; asyncpg no se entera hasta que
# intenta hablar y entonces revienta con "connection was closed in the middle
# of operation". Reciclandolas cada minuto se cierran antes que el proxy.
INACTIVA_MAXIMA = 60.0
# Ninguna consulta de este bot tarda esto. Si lo hace, es que algo va mal.
ESPERA_MAXIMA = 30.0

_pool: asyncpg.Pool | None = None


def pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("La base de datos no está iniciada")
    return _pool


async def iniciar():
    global _pool
    # Con un Postgres local no hay TLS que pedir, y "require" lo tumbaria.
    ssl = None if DB_SSL in ("disable", "prefer") else DB_SSL
    logger.info(f"Conectando a la base de datos con ssl={ssl}")
    _pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=1,
        max_size=5,
        ssl=ssl,
        max_inactive_connection_lifetime=INACTIVA_MAXIMA,
        command_timeout=ESPERA_MAXIMA,
    )
    await _aplicar_migraciones()


async def cerrar():
    if _pool is not None:
        await _pool.close()


async def _aplicar_migraciones():
    async with _pool.acquire() as con:
        await con.execute(
            "CREATE TABLE IF NOT EXISTS migraciones ("
            "  nombre TEXT PRIMARY KEY,"
            "  aplicada TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        aplicadas = {f["nombre"] for f in await con.fetch("SELECT nombre FROM migraciones")}

        for fichero in sorted(MIGRACIONES.glob("*.sql")):
            if fichero.name in aplicadas:
                continue
            logger.info(f"Aplicando migración {fichero.name}")
            async with con.transaction():
                await con.execute(fichero.read_text(encoding="utf-8"), timeout=None)
                await con.execute(
                    "INSERT INTO migraciones (nombre) VALUES ($1)", fichero.name
                )
            logger.info(f"Migración {fichero.name} aplicada")
