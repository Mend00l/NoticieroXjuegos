"""La criba y el parecido, que corren sin base de datos."""
import criba
import feeds
import publicar


def test_tira_las_guias_por_la_ruta():
    assert criba.motivo_descarte(
        "65 Switch Games You Should Check Out",
        "https://www.nintendolife.com/guides/65-switch-games",
    )


def test_tira_el_cine_de_hobbyconsolas():
    """Casi la mitad de su feed es /hobbycine. Esta se colo en el tema."""
    assert criba.motivo_descarte(
        "Crítica de Leones en invierno, el violento thriller de Albert Pintó",
        "https://www.hobbyconsolas.com/hobbycine/critica-leones-invierno-violento-thriller_7052389_0.html",
    )


def test_tira_la_publicidad_de_hobbyconsolas():
    assert criba.motivo_descarte(
        "Regalo perfecto para fans de El Señor de los Anillos: sujetalibros",
        "https://www.hobbyconsolas.com/recomendados/regalo-perfecto-fans-senor-anillos_7051000_0.html",
    )


def test_tira_los_analisis_sin_seccion_en_la_direccion():
    """Eurogamer no tiene seccion: el titular entero es la ruta."""
    assert criba.motivo_descarte(
        "Nintendo Switch Sports Resort review",
        "https://www.eurogamer.net/nintendo-switch-sports-resort-review",
    )
    assert criba.motivo_descarte(
        "After a few hours with Yakuza studio's soulful Stranger Than Heaven",
        "https://www.eurogamer.net/stranger-than-heaven-preview",
    )
    assert criba.motivo_descarte(
        "Mini reseña de Penguin Colony - Horror cósmico y colonialismo",
        "https://www.eurogamer.es/penguin-colony-analisis-review",
    )


def test_tira_las_guias_tambien_en_singular():
    """VGC usa /guide, no /guides."""
    assert criba.motivo_descarte(
        "Nintendo Switch Sports Resort: Archery Secret Target locations",
        "https://www.videogameschronicle.com/guide/nintendo-switch-sports-resort-archery/",
    )


def test_tira_las_guias_que_acaban_en_guide():
    """Nintendo Everything tampoco tiene seccion: ahi el guion no es barra."""
    assert criba.motivo_descarte(
        "Spocco Points farming guide for Nintendo Switch Sports Resort",
        "https://nintendoeverything.com/nintendo-switch-sports-resort-spocco-points-farming-guide/",
    )


def test_una_noticia_de_eurogamer_sigue_pasando():
    """La comprobacion de que los sufijos no se han llevado las noticias."""
    assert criba.motivo_descarte(
        "BioWare is closing down and Mass Effect 5 is cancelled",
        "https://www.eurogamer.net/bioware-closing-down-mass-effect-5-cancelled",
    ) is None


def test_tira_los_analisis_por_el_titular():
    assert criba.motivo_descarte(
        "Análisis de Nintendo Switch Sports Resort",
        "https://www.eurogamer.es/analisis-switch-sports",
    )


def test_tira_los_codigos_diarios():
    assert criba.motivo_descarte(
        "FREE FIRE MAX | Códigos de hoy jueves 22 de octubre de 2026",
        "https://vandal.elespanol.com/noticia/free-fire",
    )


def test_deja_pasar_una_noticia():
    assert criba.motivo_descarte(
        "EA cierra Bioware y cancela el próximo Mass Effect",
        "https://vandal.elespanol.com/noticia/ea-cierra-bioware",
    ) is None


def test_caza_la_misma_noticia_en_dos_idiomas():
    """Lo que mas repetido sale: el mismo cierre contado en español y en ingles."""
    una = criba.palabras_clave("EA cierra Bioware, cancela el próximo Mass Effect y despide a 400 personas")
    otra = criba.palabras_clave("EA is closing BioWare and cancelling the next Mass Effect")
    assert criba.parecido(una, otra) >= 0.5


def test_no_junta_dos_noticias_del_mismo_juego():
    """Mismo juego, noticias distintas: una de requisitos y otra de fecha."""
    una = criba.palabras_clave("Shrek 2 Remastered pide una RTX 5070 y desata las críticas")
    otra = criba.palabras_clave("Shrek 2 Remastered Gets Official November Release Date")
    assert criba.parecido(una, otra) < 0.5


def test_no_junta_por_la_coletilla_del_medio():
    """Nintendo Life acaba muchos titulares en "Here Are The Full Patch Notes"."""
    una = criba.palabras_clave("Cyberpunk 2077: Edgerunners 2 Update (2.5) Officially Revealed, Here Are The Full Patch Notes")
    otra = criba.palabras_clave("Nintendo Switch Sports Resort Has Been Updated To Ver. 1.1.0, Here Are The Full Patch Notes")
    assert criba.parecido(una, otra) < 0.5


def test_no_junta_por_la_paja_del_lanzamiento():
    una = criba.palabras_clave("Pratfall coming to PS5, Xbox Series, and Switch 2")
    otra = criba.palabras_clave("RV There Yet? coming to PS5, Switch 2 on October 29")
    assert criba.parecido(una, otra) < 0.5


def test_el_enlace_se_normaliza():
    """El mismo articulo con y sin campaña es el mismo articulo."""
    limpio = criba.clave_enlace("https://www.vandal.net/noticia/abc/")
    assert limpio == criba.clave_enlace("http://vandal.net/noticia/abc?utm_source=rss#arriba")


def test_tira_la_publicidad_por_la_categoria():
    """Eurogamer ES etiqueta su publicidad con Tecnologia y solo con eso."""
    assert criba.motivo_descarte(
        "WALL-E compactó basura durante 700 años y este Roomba te libra de vaciar el polvo",
        "https://www.eurogamer.es/wall-e-compacto-basura-durante-700-anos-y-este-roomba",
        ["Tecnología"],
    )


def test_una_noticia_con_varias_categorias_pasa():
    """Que Tecnologia este no basta: tiene que ser la unica."""
    assert criba.motivo_descarte(
        "Anunciado Serious Sam: The Third Encounter",
        "https://www.eurogamer.es/anunciado-serious-sam-the-third-encounter",
        ["Croteam", "Shooter", "PC", "Tecnología"],
    ) is None


def test_una_noticia_sin_categorias_pasa():
    """La noticia del dia venia sin una sola categoria: la lista vacia no es señal."""
    assert criba.motivo_descarte(
        "Electronic Arts despedirá a 400 trabajadores; ha cerrado BioWare",
        "https://www.eurogamer.es/electronic-arts-despedira-a-400-trabajadores",
        [],
    ) is None


def test_tira_las_promociones_de_tienda():
    """Las dos que se publicaron en el tema el 23-oct-2026."""
    assert criba.motivo_descarte(
        "Fanatical Halloween bundle gives you Prey, Doom 1 & 2, and Evil Within 1 & 2 for $11.66",
        "https://www.videogameschronicle.com/news/fanatical-halloween-bundle-gives-you-prey/",
        ["News"],
    )
    assert criba.motivo_descarte(
        "Consigue Call of Duty: Modern Warfare 4 y otras novedades al mejor precio "
        "con las ofertas de Instant Gaming",
        "https://vandal.elespanol.com/noticia/2026296016/consigue-call-of-duty-modern-warfare-4/",
        ["PC"],
    )


def test_tira_los_juegos_gratis_de_epic_y_prime():
    assert criba.motivo_descarte(
        "Ya disponibles gratis en Epic Games Store dos juegos de terror muy diferentes",
        "https://vandal.elespanol.com/noticia/2026295000/ya-disponibles-gratis-en-epic/",
    )
    assert criba.motivo_descarte(
        "Amazon regala hoy 2 nuevos juegos gratis de PC a todos los suscriptores de Amazon Prime",
        "https://vandal.elespanol.com/noticia/2026295001/amazon-regala-hoy-2-juegos/",
    )


def test_tira_el_mismo_anuncio_con_otra_redaccion():
    """El post de GAME llego dos veces, redactado distinto en cada medio."""
    assert criba.motivo_descarte(
        "GAME estrena nueva web y lo celebra con más de 100 ofertas de hasta el 50 % de descuento",
        "https://vandal.elespanol.com/noticia/2026296012/game-estrena-nueva-web/",
        ["PC PS5 XSX Switch2"],
    )
    assert criba.motivo_descarte(
        "GAME renueva su web y lo celebra con precios de estreno y auténticos chollazos, "
        "por tiempo limitado",
        "https://www.hobbyconsolas.com/videojuegos/game-renueva-su-web-celebra-con-precios-estreno_7052742_0.html",
        ["Juegos"],
    )


def test_tira_las_guias_de_como_empezar():
    """Se colo porque el patron solo tenia conseguir, desbloquear y tres mas."""
    assert criba.motivo_descarte(
        "Cómo empezar la misión de Cyberpunk Edgerunners 2 en Cyberpunk 2077",
        "https://www.hobbyconsolas.com/videojuegos/como-empezar-mision-edgerunners_7052000_0.html",
        ["Juegos"],
    )


def test_un_reportaje_que_empieza_por_como_sigue_pasando():
    """"Como" a secas no vale: hace falta el verbo de guia detras."""
    assert criba.motivo_descarte(
        "Cómo Nintendo convirtió una consola fallida en la más vendida de su historia",
        "https://www.hobbyconsolas.com/videojuegos/como-nintendo-convirtio-consola_7052001_0.html",
        ["Juegos"],
    ) is None


def test_una_noticia_de_la_tienda_sigue_pasando():
    """Con el nombre de la tienda a secas se irian noticias de la tienda."""
    assert criba.motivo_descarte(
        "Epic Games Store llega a Android en Europa tras la ley de mercados digitales",
        "https://vandal.elespanol.com/noticia/2026295002/epic-games-store-llega-a-android/",
    ) is None


def test_una_noticia_de_precios_no_es_promocion():
    """Lo que distingue la promocion no es hablar de precios ni de gratis."""
    noticias_buenas = [
        ("Xbox's next-gen console to reportedly cost up to $1,800",
         "https://www.eurogamer.net/microsoft-next-gen-xbox-helix-date-price"),
        ("Football Manager 27 will be free to play for five days before its full release",
         "https://www.eurogamer.net/football-manager-27-free-to-play-five-days"),
        ("The Wolf Among Us Remastered tendrá un descuento temporal para los compradores",
         "https://www.eurogamer.es/the-wolf-among-us-remastered-tendra-un-descuento-temporal"),
        ("Xbox cloud gaming prices revealed, with 50 hours of ad-free game-time",
         "https://www.eurogamer.net/xbox-cloud-gaming-prices-revealed"),
    ]
    for titular, enlace in noticias_buenas:
        assert criba.motivo_descarte(titular, enlace) is None, titular


def test_tira_el_podcast_de_eurogamer():
    assert criba.motivo_descarte(
        "Nitro 1x09: El cierre de BioWare, el supuesto precio y fecha de la próxima Xbox",
        "https://www.eurogamer.es/nitro-1x09-el-cierre-de-bioware-el-supuesto-precio",
    )


def test_quita_el_leer_mas_con_tilde():
    """Eurogamer ES lo escribe con tilde y se colaba dentro de la cita."""
    limpio = feeds._limpiar(
        "<p>Digital Sun ha anunciado un retraso indefinido de los playtest. Leer más</p>"
    )
    assert limpio.endswith("playtest.")
    assert "Leer" not in limpio


def test_el_resumen_va_en_una_cita():
    texto = publicar.montar({
        "titular": "Shigeru Miyamoto explains why AI won't make creativity obsolete",
        "resumen": "Mario and Zelda creator argues that the rise of AI could make creators even more important",
        "fuente": "VGC",
        "enlace": "https://www.videogameschronicle.com/news/miyamoto-ai",
    })
    assert "<blockquote>Mario and Zelda creator" in texto
    assert "important</blockquote>" in texto
    # El titular y la fuente quedan fuera de la cita.
    assert texto.startswith("<b>Shigeru")
    assert texto.endswith("VGC</a>")


def test_sin_cita_el_mensaje_es_el_de_antes():
    """El respaldo por si Telegram no acepta la cita en el pie de una foto."""
    noticia = {
        "titular": "Un titular",
        "resumen": "Un resumen",
        "fuente": "VGC",
        "enlace": "https://www.videogameschronicle.com/news/x",
    }
    assert "blockquote" not in publicar.montar(noticia, cita=False)
    assert "Un resumen" in publicar.montar(noticia, cita=False)


def test_el_mensaje_con_cita_tambien_cabe_en_el_pie():
    """Las etiquetas de la cita cuentan para el limite de 1024."""
    texto = publicar.montar({
        "titular": "Un titular normal de una noticia de videojuegos",
        "resumen": "palabra " * 400,
        "fuente": "Vandal",
        "enlace": "https://vandal.elespanol.com/noticia/abc",
    })
    assert len(texto) <= publicar.TOPE_PIE
    assert texto.count("<blockquote>") == 1
    assert texto.count("</blockquote>") == 1


def test_el_mensaje_cabe_en_el_pie_de_foto():
    larga = {
        "titular": "Un titular normal de una noticia de videojuegos",
        "resumen": "palabra " * 400,
        "fuente": "Vandal",
        "enlace": "https://vandal.elespanol.com/noticia/abc",
    }
    texto = publicar.montar(larga)
    assert len(texto) <= publicar.TOPE_PIE
    # Y lo que se recorta es el resumen, nunca el titular ni el enlace.
    assert larga["titular"] in texto
    assert larga["enlace"] in texto


def test_el_mensaje_escapa_el_html():
    """Un titular con < o & no puede romper el parse_mode HTML."""
    texto = publicar.montar({
        "titular": "Half-Life 3 & <b>Portal</b>: lo que se sabe",
        "resumen": "",
        "fuente": "Vandal",
        "enlace": "https://vandal.elespanol.com/noticia/abc",
    })
    assert "<b>Portal</b>: lo que" not in texto
    assert "&amp;" in texto
