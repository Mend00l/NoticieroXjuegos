from dataclasses import dataclass


@dataclass(frozen=True)
class Fuente:
    nombre: str
    idioma: str
    feed: str
    # Algunos feeds no sirven la foto en el item, o sirven el articulo entero
    # en vez de un resumen. Para esos hay que abrir la pagina de la noticia y
    # leer sus etiquetas og:. Es una peticion extra, asi que solo las que lo
    # necesitan de verdad, y comprobado feed a feed el 22-oct-2026.
    abrir_pagina: bool = False


# Las nueve fuentes, con lo que dio cada una en 24 horas el 22-oct-2026.
#
# Estan los dos generalistas en español (Vandal, HobbyConsolas) porque son
# los que llegan primero, y Eurogamer ES porque no hace clickbait. En ingles
# solo lo que no se solapa: VGC da las exclusivas de industria y Gematsu
# cubre Japon, que no cubre nadie mas.
#
# Fuera a proposito, y no por olvido: **Nintenderos y LaPS4 no las quiere
# Edu**, asi que lo de Nintendo y lo de PlayStation sale de los generalistas
# y, en ingles, de Nintendo Life y Pure Xbox; Areajugones y VidaExtra
# mezclan cine y television en el mismo feed; Polygon y Destructoid viven de
# las guias; PC Gamer sirve resumenes de treinta caracteres, que no dan para
# un mensaje; PS Blog y Xbox Wire son la promocion de su propia tienda.
#
# Y cuatro que no se pueden usar aunque se quiera: 3DJuegos se quedo sin RSS
# (404 en todas las rutas y su HTML no declara feed), SomosXbox responde 403
# incluso con curl_cffi imitando a Chrome, guiltybit.com ya no resuelve, y
# MeriStation tiene los feeds congelados desde 2023.
FUENTES = [
    # Mete el articulo entero en description (hasta 8.700 caracteres) y
    # sirve la miniatura del video a 320x180 cuando el og:image esta a
    # 1200x630: de las nueve, la que mas gana abriendo la pagina.
    Fuente("Vandal", "es", "https://vandal.elespanol.com/rss/", abrir_pagina=True),
    # **Se queda, decidido el 23-oct-2026. No volver a proponer quitarla.**
    #
    # Es la fuente que mas mantenimiento cuesta: de las cinco fugas tapadas
    # ese dia, cuatro eran suyas (el cine de /hobbycine, los anuncios de
    # /recomendados, la promocion de GAME y una guia de "como empezar"). Su
    # feed mezcla cuatro cosas y no las distingue con categorias.
    #
    # Pero medido: trae 15 por sondeo, publica 5, y la aportacion neta son
    # esas 5 --con ella 92 publicables, sin ella 87--. Son noticia de verdad
    # y alguna no la da nadie mas. A Edu le interesan.
    Fuente("HobbyConsolas", "es", "https://www.hobbyconsolas.com/rss"),
    # Aqui iba MeriStation, que no tiene feed vivo (ver mas abajo). Se probo
    # IGN España en su hueco y se dejo fuera: entra limpia, pero mete ofertas
    # ("por menos de 30 euros puedes hacerte con...") y series de television,
    # y subio las repetidas de 15 a 23, o sea que casi todo lo suyo ya lo
    # contaba otro. Para volver a meterla basta una linea aqui.
    # El feed de SOLO NOTICIAS, no el general. Lo declara su propio HTML en
    # /archive/news y no estaba a la vista. El general trae ademas los
    # analisis, los avances y **el podcast Nitro**, que se publico en el
    # tema el 23-oct-2026. Con este, la criba no tiene que tirar nada suyo.
    Fuente("Eurogamer ES", "es", "https://www.eurogamer.es/feed/news"),
    Fuente("VGC", "en", "https://www.videogameschronicle.com/feed/"),
    Fuente("Eurogamer", "en", "https://www.eurogamer.net/feed/news"),
    Fuente("Gematsu", "en", "https://www.gematsu.com/feed"),
    Fuente("Nintendo Life", "en", "https://www.nintendolife.com/feeds/latest"),
    # Entra sabiendo lo que cuesta, medido el 23-oct-2026: de sus 9
    # publicables, 2 eran noticias que Vandal y Eurogamer ES ya habian dado
    # en español, y eso el detector de repetidas **no lo caza**, porque los
    # titulares no comparten tres palabras entre idiomas. Se acepta porque
    # las otras 7 no las da nadie mas: lanzamientos pequeños de Switch y las
    # ventas de Famitsu. Apenas pisa a Nintendo Life, al contrario de lo que
    # parecia.
    Fuente("Nintendo Everything", "en", "https://nintendoeverything.com/feed"),
    Fuente("Pure Xbox", "en", "https://www.purexbox.com/feeds/latest"),
]

POR_NOMBRE = {f.nombre: f for f in FUENTES}
