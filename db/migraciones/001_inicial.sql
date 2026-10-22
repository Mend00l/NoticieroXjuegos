-- Una fila por noticia vista, publicada o no.
--
-- Se guardan tambien las descartadas, y con el motivo: es la unica forma de
-- ajustar la criba mirando lo que ha tirado de verdad en vez de adivinando.
CREATE TABLE noticias (
    id            BIGSERIAL PRIMARY KEY,
    fuente        TEXT NOT NULL,
    guid          TEXT NOT NULL,
    enlace        TEXT NOT NULL,
    clave_enlace  TEXT NOT NULL,
    titular       TEXT NOT NULL,
    resumen       TEXT,
    foto          TEXT,
    -- Las palabras del titular que cuentan, ya normalizadas. Se guardan
    -- hechas para no recalcularlas en cada comparacion.
    claves        TEXT[] NOT NULL DEFAULT '{}',
    fecha         TIMESTAMPTZ,
    vista         TIMESTAMPTZ NOT NULL DEFAULT now(),
    publicada     TIMESTAMPTZ,
    -- NULL = se publica. Con texto = por que no.
    descartada    TEXT
);

-- Las dos claves de que una noticia ya se vio. La del guid tapa el feed que
-- repite el item; la del enlace tapa al medio que cambia el guid al
-- actualizar la noticia, que si no saldria dos veces.
CREATE UNIQUE INDEX noticias_guid ON noticias (fuente, guid);
CREATE UNIQUE INDEX noticias_enlace ON noticias (clave_enlace);

-- Para sacar la siguiente de la cola.
CREATE INDEX noticias_cola ON noticias (vista)
    WHERE publicada IS NULL AND descartada IS NULL;

-- Para buscar titulares parecidos en las ultimas horas.
CREATE INDEX noticias_recientes ON noticias (vista DESC);
