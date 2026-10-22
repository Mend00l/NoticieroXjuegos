# noticias-bot

Lee feeds RSS de videojuegos y publica las noticias en un tema de un grupo de
Telegram, una a una y sin repetirlas.

## Qué hace, por dentro

1. Cada 15 minutos lee los 9 feeds a la vez.
2. De cada noticia se queda con el titular, el resumen, la foto y el enlace.
3. Pasa la criba: fuera guías, análisis, reviews, códigos diarios, cine y
   televisión. Lo que tira queda apuntado con el motivo (`/descartes`).
4. Mira si es la misma noticia que ya contó otro medio en las últimas 48 h.
5. Lo que queda va a una cola y sale **una noticia cada 45 segundos**, para
   que una tanda de diez no caiga de golpe en el tema.
6. Justo antes de publicar, si falta la foto o el resumen, abre la página de
   la noticia y los saca de sus etiquetas `og:`.

## Las fuentes

Nueve, y cada una está por un motivo. Están en `fuentes.py` con el volumen
que dio cada una en 24 horas, medido el 22-oct-2026.

| Fuente | Idioma | Noticias/24 h |
|---|---|---|
| Vandal | es | 30 |
| HobbyConsolas | es | 35 |
| Eurogamer ES | es | 9 |
| LaPS4 | es | 4 |
| VGC | en | 10 |
| Eurogamer | en | 10 |
| Gematsu | en | 15 |
| Nintendo Life | en | 12 |
| Pure Xbox | en | 10 |

**Cuatro no se pueden usar**, comprobado una a una:

- **3DJuegos**: se quedó sin RSS. 404 en todas las rutas y su HTML no
  declara ningún feed.
- **MeriStation**: los feeds están congelados. `portada.xml` se quedó en
  febrero de 2023 y `noticias.xml` en marzo de 2024.
- **SomosXbox**: 403 incluso con `curl_cffi` imitando a Chrome.
- **GuiltyBit**: el dominio ya no resuelve.

Fuera a propósito: **Nintenderos** (no la quieres, así que lo de Nintendo
sale de Vandal y HobbyConsolas en español y de Nintendo Life en inglés),
Areajugones y VidaExtra (mezclan cine y televisión),
Polygon y Destructoid (viven de las guías), PC Gamer (resúmenes de 30
caracteres), IGN España (ofertas y series, y casi todo lo suyo ya lo cuenta
otro), PS Blog y Xbox Wire (promoción de su propia tienda).

## Cómo no se repite una noticia

Tres redes, de la más segura a la más fina:

1. **Mismo guid del mismo feed.** Índice único en `(fuente, guid)`.
2. **Mismo enlace**, aunque cambie el guid. Pasa cuando un medio actualiza
   la noticia. El enlace se normaliza antes: fuera `?utm_*`, anclas y la
   barra final.
3. **La misma noticia contada por otro medio.** Se comparan las palabras del
   titular, se pide un 50% de solape y tres palabras en común, y se mira
   contra las últimas 48 horas.

La tercera no está puesta a ojo. `herramientas/barrido.py` la mide contra
141 titulares reales con 18 parejas repetidas y 10 falsas apuntadas a mano:
a 0,5 caza las 18 y no cuela ninguna de las 10.

**Lo que no caza:** dos medios que cuentan lo mismo sin compartir tres
palabras del titular. Con español e inglés mezclados eso pasa cuando el
sujeto se traduce. Para eso habría que traducir el titular antes de
comparar, y hoy no se hace.

## Comandos

Solo para quien esté en `ADMIN_ID`:

- `/estado` - cola, publicadas y descartadas en 24 h, y cuánto va dando cada fuente.
- `/descartes` - las últimas 20 descartadas con el motivo. **Esto es lo que
  sirve para ajustar la criba**: se mira lo que ha tirado de verdad en vez
  de adivinar.
- `/sondear` - fuerza un sondeo sin esperar los 15 minutos.

## Arrancar en local

```
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.example .env
```

Rellenar el `.env` y `python main.py`.

**El primer arranque no publica nada.** Los 9 feeds traen unas 100 noticias
de los dos últimos días, y publicarlas sería estrenar el tema con cien
mensajes viejos. La primera vez solo se anotan; a partir de ahí se publica
lo que vaya saliendo.

## Probar

```
venv\Scripts\python -m herramientas.ensayo
```

Lee los feeds de verdad y dice qué publicaría, qué tiraría la criba y qué
daría por repetido, sin base de datos y sin Telegram. Enseña además tres
mensajes montados tal como saldrían.

```
venv\Scripts\python -m herramientas.afinar solape 0.5
venv\Scripts\python -m herramientas.barrido
```

Para volver a medir la detección de repetidas con una tanda nueva.

Las pruebas necesitan el Postgres local. Las que solo miran lógica corren
sin nada:

```
D:\Claude_projects\pgsql-pruebas\pgsql\bin\pg_ctl.exe ^
  -D D:\Claude_projects\pgsql-pruebas\datos-banco -l pg.log start
venv\Scripts\python -m pytest
```

Usan su propia base, `noticias_prueba`, que se crea sola; no tocan el
`banco` de Miss_Avisos.

## Desplegar en Railway

**Sin `railway.toml`.** Comprobado en su documentación el 22-oct-2026: los
servicios nuevos ya lo ignoran, y el 1-dic-2026 hay corte duro. Lo que lo
sustituye, `.railway/railway.ts`, no se lee al desplegar: hay que aplicarlo
con `railway config apply` desde el CLI. Para un servicio no merece la pena.

Así que el comando de arranque va en el panel del servicio:

```
python main.py
```

Y luego:

1. Añadir un Postgres al proyecto y poner `DATABASE_URL` por referencia al
   servicio, no copiada a mano.
2. `DB_SSL=require`.
3. `TELEGRAM_TOKEN`, `GRUPO_ID`, `TEMA_ID` y `ADMIN_ID`.
4. El bot tiene que ser miembro del grupo para poder escribir en el tema.

## Lo que falta

- Los datos: token del bot, id del grupo y id del tema.
- Desplegarlo, que Railway está caído.
- Decidir si se traducen los titulares en inglés. Ahora salen tal cual.
