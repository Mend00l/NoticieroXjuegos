"""Preparativos comunes de las pruebas.

Las que solo miran logica corren en cualquier sitio y sin nada montado. Las
que tocan base de datos necesitan una local y se saltan solas si no la hay:

    D:\\Claude_projects\\pgsql-pruebas\\pgsql\\bin\\pg_ctl.exe ^
      -D D:\\Claude_projects\\pgsql-pruebas\\datos-banco -l pg.log start
    pytest

Usan su propia base, `noticias_prueba`, y no el `banco` de Miss_Avisos: lo
primero que hacen es vaciar la tabla, y compartirla seria llevarse por
delante las pruebas del otro bot.
"""
import os
from urllib.parse import urlparse, urlunparse

import pytest

# config.py llama a load_dotenv() al importarse. Se desactiva aqui arriba,
# que esto corre antes de que nadie importe config: un .env de verdad en la
# carpeta cambiaria los umbrales bajo los pies de las pruebas.
import dotenv

dotenv.load_dotenv = lambda *args, **kwargs: False

BANCO_URL = os.environ.get("BANCO_URL")
CASA = {"localhost", "127.0.0.1", "::1"}
BASE_PRUEBAS = "noticias_prueba"


def _cambiar_base(url: str, nombre: str) -> str:
    return urlunparse(urlparse(url)._replace(path=f"/{nombre}"))


# Se comprueba que la direccion es de esta maquina y no se coge DATABASE_URL:
# en el entorno de Edu esa es la de produccion, para desplegar, y estas
# pruebas vacian la tabla.
if BANCO_URL and urlparse(BANCO_URL).hostname not in CASA:
    raise RuntimeError(
        "BANCO_URL no apunta a esta maquina y estas pruebas vacian tablas"
    )


@pytest.fixture
async def bd():
    if not BANCO_URL:
        pytest.skip("sin BANCO_URL: no hay base de pruebas local")

    import asyncpg

    from db import pool

    # La base de pruebas se crea sola la primera vez.
    sistema = await asyncpg.connect(_cambiar_base(BANCO_URL, "postgres"))
    try:
        hay = await sistema.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", BASE_PRUEBAS
        )
        if not hay:
            await sistema.execute(f'CREATE DATABASE "{BASE_PRUEBAS}"')
    finally:
        await sistema.close()

    pool.DATABASE_URL = _cambiar_base(BANCO_URL, BASE_PRUEBAS)
    pool.DB_SSL = "disable"
    await pool.iniciar()
    async with pool.pool().acquire() as con:
        await con.execute("TRUNCATE noticias")
    yield pool
    await pool.cerrar()


def noticia(titular, fuente="Vandal", enlace=None, resumen="un resumen largo de prueba",
            foto="https://ejemplo/foto.jpg", guid=None, fecha=None):
    """Una noticia como la que devuelve feeds.leer()."""
    import criba

    enlace = enlace or "https://vandal.elespanol.com/noticia/" + str(abs(hash(titular)))
    return {
        "fuente": fuente,
        "guid": guid or enlace,
        "enlace": enlace,
        "clave_enlace": criba.clave_enlace(enlace),
        "titular": titular,
        "resumen": resumen,
        "foto": foto,
        "fecha": fecha,
    }
