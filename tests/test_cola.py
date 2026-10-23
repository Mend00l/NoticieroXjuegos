"""Que un fallo del destino no se lleve las noticias por delante."""
import telegram.error

import main


def test_el_tema_cerrado_es_del_destino():
    """Con esto se descartaban todas las noticias una a una, en silencio."""
    assert main._es_el_destino(telegram.error.BadRequest("Topic_closed"))


def test_el_hilo_que_no_existe_es_del_destino():
    assert main._es_el_destino(
        telegram.error.BadRequest("Message thread not found")
    )


def test_sin_permiso_es_del_destino():
    assert main._es_el_destino(telegram.error.Forbidden("bot was kicked"))
    assert main._es_el_destino(telegram.error.BadRequest("not enough rights"))


def test_una_foto_mala_no_es_del_destino():
    """Esa si hay que apartarla: la cola no puede pararse por una foto."""
    assert not main._es_el_destino(
        telegram.error.BadRequest("Wrong file identifier/HTTP URL specified")
    )
    assert not main._es_el_destino(
        telegram.error.BadRequest("Failed to get HTTP URL content")
    )
