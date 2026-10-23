import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# Rutas que delatan lo que no es noticia. Filtrar por la direccion es mas
# fiable que por el titular: la seccion la pone el medio y no cambia, el
# titular lo escribe una persona distinta cada vez.
RUTAS_FUERA = (
    "/guia",
    "/guias/",
    "/analisis",
    "/trucos",
    "/cine/",
    "/series/",
    "/television/",
    "/peliculas/",
    "/review",
    "/guide",
    "/how-to",
    "/walkthrough",
    "/features/",
    # Casi la mitad del feed de HobbyConsolas es esto: 18 de 40 el 23-oct-2026.
    "/hobbycine",
    "/hobbyseries",
    # Y /recomendados son anuncios de producto, no noticias ("Regalo
    # perfecto para fans de El Señor de los Anillos: sujetalibros...").
    "/recomendados",
)

# Eurogamer, en español y en ingles, **no tiene seccion en la direccion**:
# el titular entero es la ruta, asi que no hay carpeta que filtrar. Sus
# analisis y avances se reconocen por como acaba la direccion. Sin esto se
# colaban "Nintendo Switch Sports Resort review" y "Mini reseña de Penguin
# Colony", que el titular tampoco delata.
SUFIJOS_FUERA = (
    "-review",
    "-preview",
    "-analisis",
    "-resena",
    "-impresiones",
    # Nintendo Everything tampoco tiene seccion, y sus guias acaban asi:
    # "...-spocco-points-farming-guide". El "/guide" de arriba no las pilla
    # porque ahi no hay barra, sino guion.
    "-guide",
    "-guides",
    "-walkthrough",
)

# Y el titular como segunda red, para lo que el medio publica en la seccion
# de noticias sin serlo. Van sin tildes porque se comparan ya normalizados.
TITULOS_FUERA = (
    re.compile(r"^guia\b"),
    re.compile(r"\bguia (de|completa|para)\b"),
    re.compile(r"\bcomo (conseguir|desbloquear|encontrar|derrotar|subir)\b"),
    re.compile(r"\btrucos\b"),
    re.compile(r"\b(todos los|todas las) (codigos|cofres|coleccionables|personajes)\b"),
    re.compile(r"\bcodigos (de|para|canjeables)\b"),
    re.compile(r"^analisis\b"),
    re.compile(r"\banalisis de\b"),
    re.compile(r"^critica\b"),
    re.compile(r"\bcritica de\b"),
    re.compile(r"\bresena de\b"),
    re.compile(r"^mini resena\b"),
    re.compile(r"^impresiones de\b"),
    # El podcast de Eurogamer, que se numera "Nitro 1x09". Con su feed de
    # solo noticias ya no deberia aparecer, pero el guardia es una linea.
    re.compile(r"^nitro \d+x\d+\b"),
    re.compile(r"^meripodcast\b"),
    re.compile(r"\bdonde (encontrar|esta|estan)\b"),
    re.compile(r"\b(los|las) \d+ mejores\b"),
    re.compile(r"^(guide|walkthrough)\b"),
    re.compile(r"\bhow to\b"),
    re.compile(r"\btier list\b"),
    re.compile(r"^all .{3,40}\b(locations|codes|characters|answers|recipes|players)\b"),
    re.compile(r"\b(codes|redeem codes) (for|list)\b"),
    re.compile(r"^review\b"),
    re.compile(r"\breview:\b"),
    re.compile(r"\b(review|preview|roundup)$"),
    re.compile(r"\bexplained\b"),
)

# Eurogamer ES cuela publicidad de producto **dentro de su feed de
# noticias**: "WALL-E compacto basura durante 700 años y este Roomba te
# libra de vaciar el polvo", "Tu Switch 2, un solo cable y una pared blanca
# y ya estas jugando a 80 pulgadas con este proyector de bolsillo". Unas 7
# de cada 40.
#
# Por titular no hay forma decente de cazarlas: hablan de videojuegos. Pero
# **el RSS las etiqueta**: llevan Tecnologia como UNICA categoria, mientras
# las noticias de verdad llevan categorias de juego (Nintendo, Shooter, PC).
#
# Se pide que sea la unica, no que este: una noticia con varias categorias
# entre las que haya Tecnologia es una noticia. Y **la lista vacia no vale
# como señal**: "Electronic Arts despedira a 400 trabajadores" venia sin una
# sola categoria y es la noticia del dia.
CATEGORIAS_FUERA = {"tecnologia", "technology", "gadgets", "ofertas", "deals"}

# Promociones de tienda. VGC las publica como noticia y las etiqueta "News"
# igual que todo lo demas, asi que aqui no hay categoria que mirar: hubo que
# ir al titular. Ejemplo del 23-oct-2026: "Fanatical Halloween bundle gives
# you Prey, Doom 1 & 2, and Evil Within 1 & 2 for $11.66".
#
# **Lo que las distingue no es que hablen de precios.** "Xbox's next-gen
# console to reportedly cost up to $1,800" es la noticia del dia, y "The
# Wolf Among Us Remastered tendra un descuento temporal" tambien. Lo que las
# distingue es que **el protagonista es una tienda**, no un juego ni quien
# lo hace. De ahi que esto sea una lista de tiendas y no de palabras como
# "oferta" o "descuento", que se llevarian noticias de verdad.
#
# Las ofertas ya tienen sus bots: ofertasXbot y digitalesXjuegos.
# **Ojo: estos patrones se comparan contra el titular normalizado**, y
# normalizar() se come los simbolos. Un patron con % o $ no caza nunca:
# "ofertas de hasta el 50 % de descuento" llega aqui como "50 de descuento".
# Se perdio un rato con `\d+% de descuento`, que cazaba cero.
#
# Cada uno de estos esta comprobado contra los 240 titulares del 23-oct-2026:
# caza su promocion y no toca ninguna noticia.
TIENDAS_FUERA = (
    re.compile(r"\bfanatical\b"),
    re.compile(r"\bhumble (bundle|choice)\b"),
    re.compile(r"\bgreen man gaming\b"),
    re.compile(r"\bcdkeys\b"),
    re.compile(r"\bgamivo\b"),
    re.compile(r"\binstant gaming\b"),
    re.compile(r"\bgamesplanet\b"),
    re.compile(r"\bal mejor precio\b"),
    re.compile(r"\ben oferta por menos de\b"),
    re.compile(r"\bofertas de hasta\b"),
    re.compile(r"\bmejores ofertas\b"),
    re.compile(r"^free play days\b"),
    re.compile(r"\bdeal of the (day|week)\b"),
    re.compile(r"\bbest deals\b"),
    # Los juegos gratis semanales de Epic y los que regala Prime. Se pide la
    # tienda **y** la palabra de regalo, en cualquier orden: con la tienda
    # sola se irian noticias de la tienda ("Epic Games Store llega a
    # Android"), que si son noticia.
    re.compile(r"\bepic games store\b.*\b(gratis|regala|regalo)\b"),
    re.compile(r"\b(gratis|regala|regalo)\b.*\bepic games store\b"),
    re.compile(r"\b(amazon prime|prime gaming)\b.*\b(gratis|regala|regalo)\b"),
    re.compile(r"\b(gratis|regala|regalo)\b.*\b(amazon prime|prime gaming)\b"),
)

# Palabras que no distinguen una noticia de otra. Sin quitarlas, dos
# titulares con "el nuevo juego de" ya salen parecidos sin hablar de lo mismo.
VACIAS = {
    "a", "al", "ante", "con", "de", "del", "desde", "el", "en", "entre", "es",
    "esta", "este", "ha", "han", "hasta", "la", "las", "lo", "los", "mas",
    "no", "para", "por", "que", "se", "segun", "ser", "si", "sin", "sobre",
    "son", "su", "sus", "tiene", "un", "una", "uno", "y", "ya",
    "about", "after", "all", "an", "and", "are", "as", "at", "be", "been",
    "but", "by", "for", "from", "full", "get", "gets", "had", "has", "have",
    "here", "in", "into", "is", "it", "its", "may", "new", "not", "now", "of",
    "on", "one", "or", "our", "out", "over", "that", "the", "their", "there",
    "they", "this", "to", "up", "was", "were", "what", "when", "which", "who",
    "will", "with", "you", "your",
}


def normalizar(texto: str) -> str:
    """Minusculas, sin tildes y sin signos. Para comparar, no para mostrar."""
    plano = unicodedata.normalize("NFKD", texto or "")
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    plano = plano.lower()
    plano = re.sub(r"[^a-z0-9 ]+", " ", plano)
    return re.sub(r"\s+", " ", plano).strip()


# Paja de titular de videojuegos: plataformas, meses y el verbo de turno
# para decir que algo sale. Va en lista fija y no por frecuencia porque sale
# en pocos titulares de cada tanda pero **nunca** distingue una noticia de
# otra: sin esto, "Pratfall coming to PS5" y "RV There Yet? coming to PS5"
# salian como la misma noticia.
#
# Lo que NO esta aqui a proposito: "update" y "actualizacion". Parecen paja
# igual, pero quitarlas separaba las seis noticias de la 2.5 de Cyberpunk,
# que es justo lo que hay que juntar.
PAJA = {
    "ps5", "ps4", "ps3", "psvr", "switch", "xbox", "playstation", "nintendo",
    "steam", "series", "consola", "console", "consolas",
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre",
    "january", "february", "march", "april", "june", "july", "august",
    "september", "october", "november", "december",
    "coming", "launch", "launches", "launching", "available", "demo",
    "release", "released", "out",
    "lanzamiento", "disponible", "llega", "llegan", "llegara", "saldra",
    "fecha", "trailer", "traileres",
}


def palabras_clave(titular: str) -> set[str]:
    """Las palabras del titular que de verdad dicen de que va."""
    return {
        p for p in normalizar(titular).split()
        if len(p) > 2 and p not in VACIAS and p not in PAJA
    }


# Palabras en comun que hacen falta aparte del porcentaje.
#
# Con dos bastaba para juntar "Shrek 2 Remastered pide una RTX 5070" con
# "Shrek 2 Remastered Gets Official Release Date": mismo juego, dos noticias
# distintas, y la segunda se perdia. Con tres, las que son de verdad la misma
# noticia siguen cazandose (comparten el sujeto **y** lo que pasa:
# "bioware mass effect", "blade phantom zero").
MINIMO_COMUN = 3


def parecido(unas: set[str], otras: set[str]) -> float:
    """Cuanto del titular corto esta dentro del largo, de 0 a 1.

    No es Jaccard a proposito. Dos medios cuentan lo mismo con titulares de
    distinto tamaño ("EA is closing BioWare" frente a "EA cierra Bioware,
    cancela el proximo Mass Effect y despide a 400 personas"), y el Jaccard
    los separa por lo que le sobra al largo: medido sobre 141 titulares
    reales del 22-oct-2026 cazaba 1 pareja de 18, y esto las 18.

    Tambien se probo descartar las palabras mas repetidas de cada tanda, al
    estilo del IDF, y **sale peor**: la noticia que repiten seis medios es
    justo la que hace frecuentes sus propias palabras, asi que tiraba
    "cyberpunk" y "bioware" y bajaba de 18 aciertos a 8.
    """
    if not unas or not otras:
        return 0.0
    comunes = unas & otras
    if len(comunes) < MINIMO_COMUN:
        return 0.0
    return len(comunes) / min(len(unas), len(otras))


# Lo que ponen los medios al final del resumen y no es resumen.
#
# Ojo con las tildes: aqui se compara el texto **tal cual**, no normalizado,
# porque el resumen se publica. Eurogamer ES escribe "Leer más" con tilde y
# el patron sin ella no la pillaba, asi que salia dentro de la cita en cada
# mensaje suyo. De ahi la clase [aá].
COLETILLAS = re.compile(
    r"(leer m[aá]s|ver m[aá]s|read more|continue reading|"
    r"the post .* appeared first on .*|seguir leyendo)\s*\.?\s*$",
    re.IGNORECASE,
)


def clave_enlace(enlace: str) -> str:
    """El mismo articulo llega con y sin ?utm_, con y sin barra final.

    Sin normalizar, el bot publica dos veces la misma noticia solo porque un
    medio cambio la campaña de la direccion entre dos sondeos.
    """
    partes = urlsplit(enlace.strip())
    consulta = [
        (k, v) for k, v in parse_qsl(partes.query)
        if not k.lower().startswith(("utm_", "fbclid", "gclid", "ref", "mc_"))
    ]
    servidor = partes.netloc.lower()
    if servidor.startswith("www."):
        servidor = servidor[4:]
    return urlunsplit(("https", servidor, partes.path.rstrip("/"), urlencode(consulta), ""))


def motivo_descarte(
    titular: str, enlace: str, categorias: list[str] | None = None
) -> str | None:
    """Por que no se publica esto. None si si se publica."""
    if categorias:
        suyas = {normalizar(c) for c in categorias if c}
        if suyas and suyas <= CATEGORIAS_FUERA:
            return f"categoria {sorted(suyas)[0]}"

    ruta = urlsplit(enlace).path.lower().rstrip("/")
    for trozo in RUTAS_FUERA:
        if trozo in ruta:
            return f"ruta {trozo}"
    for sufijo in SUFIJOS_FUERA:
        if ruta.endswith(sufijo):
            return f"direccion acaba en {sufijo}"

    plano = normalizar(titular)
    for patron in TITULOS_FUERA:
        if patron.search(plano):
            return f"titular {patron.pattern}"
    for patron in TIENDAS_FUERA:
        if patron.search(plano):
            return f"promocion de tienda {patron.pattern}"

    return None
