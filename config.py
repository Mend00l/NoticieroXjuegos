import os

from dotenv import load_dotenv

load_dotenv()


def _texto(nombre: str) -> str | None:
    """Una variable puesta pero vacia es lo mismo que no tenerla."""
    return (os.getenv(nombre) or "").strip() or None


def _entero(nombre: str, por_defecto: int) -> int:
    try:
        return int(_texto(nombre) or por_defecto)
    except ValueError:
        return por_defecto


def _decimal(nombre: str, por_defecto: float) -> float:
    try:
        return float(_texto(nombre) or por_defecto)
    except ValueError:
        return por_defecto


TELEGRAM_TOKEN = _texto("TELEGRAM_TOKEN")

# Donde se publica.
#
# GRUPO_ID es el id del grupo, que es negativo y empieza por -100. TEMA_ID
# es el message_thread_id del tema: **sin el los mensajes no fallan, caen en
# el chat general del grupo**, que es peor que un error porque nadie se
# entera hasta que alguien se queja.
GRUPO_ID = _entero("GRUPO_ID", 0)
TEMA_ID = _entero("TEMA_ID", 0)


def _los_que_mandan(texto: str | None) -> list[int]:
    """Quien puede usar los comandos. Lo que no sea un numero se tira."""
    numeros = []
    for trozo in (texto or "").replace(";", ",").split(","):
        trozo = trozo.strip()
        if trozo.isdigit() and int(trozo) not in numeros:
            numeros.append(int(trozo))
    return numeros


ADMINS = _los_que_mandan(os.getenv("ADMIN_ID"))

DATABASE_URL = _texto("DATABASE_URL")
# asyncpg usa "prefer" por su cuenta: cifra si el servidor quiere y se
# conforma con texto plano si no, sin decir nada. "require" impide esa caida
# silenciosa, que la conexion va por la direccion publica de Railway.
DB_SSL = _texto("DB_SSL") or "require"

# Cada cuanto se miran los feeds. Quince minutos es el equilibrio: ningun
# medio de la lista publica mas de dos noticias en ese rato, y sondear mas a
# menudo solo multiplica peticiones para encontrar lo mismo.
MINUTOS_SONDEO = _entero("MINUTOS_SONDEO", 15)

# Segundos entre un mensaje y el siguiente.
#
# El sondeo encuentra las noticias a rafagas: cuando cierra un estudio salen
# ocho a la vez. Sin esta pausa el tema se llena de golpe y luego esta medio
# dia muerto. No es un tope de noticias, solo salen de una en una: a 45
# segundos la cola admite mucho mas de lo que dan los once feeds juntos.
PAUSA_PUBLICACION = _entero("PAUSA_PUBLICACION", 45)

# Cuanto tienen que parecerse dos titulares para darlos por la misma
# noticia, de 0 a 1.
#
# El 0.5 no esta puesto a ojo: medido con herramientas/barrido.py sobre los
# 141 titulares reales del 22-oct-2026, con 18 parejas repetidas y 10 falsas
# apuntadas a mano. A 0.5 caza las 18 y no cuela ninguna de las 10; a 0.55
# se le escapan 6. Para volver a medirlo con otra tanda esta el barrido.
UMBRAL_PARECIDO = _decimal("UMBRAL_PARECIDO", 0.5)
# Cuantas horas atras se busca el parecido. Mas de dos dias y empieza a
# confundir la noticia con su secuela ("sale el parche" / "sale el parche 2").
HORAS_PARECIDO = _entero("HORAS_PARECIDO", 48)

# Cuantas noticias como maximo se cogen de cada feed en cada sondeo. Pone
# tope al primer arranque, que si no publicaria las cien de Eurogamer.
TOPE_POR_FUENTE = _entero("TOPE_POR_FUENTE", 15)


def validar():
    """Falla al arrancar si falta algo, en vez de a mitad de camino."""
    faltan = [
        nombre
        for nombre, valor in (
            ("TELEGRAM_TOKEN", TELEGRAM_TOKEN),
            ("GRUPO_ID", GRUPO_ID),
            ("TEMA_ID", TEMA_ID),
            ("DATABASE_URL", DATABASE_URL),
        )
        if not valor
    ]
    if faltan:
        raise SystemExit("Faltan variables de entorno: " + ", ".join(faltan))
