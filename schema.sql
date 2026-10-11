CREATE TABLE IF NOT EXISTS produtos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nome            TEXT    NOT NULL,
    categoria       TEXT    NOT NULL DEFAULT 'Outros',
    preco_centavos  INTEGER NOT NULL CHECK (preco_centavos >= 0),
    unidade         TEXT    NOT NULL DEFAULT 'un',
    estoque         INTEGER NOT NULL DEFAULT 0 CHECK (estoque >= 0),
    ativo           INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS pedidos (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo                 TEXT    NOT NULL UNIQUE,
    cliente_nome           TEXT    NOT NULL,
    cliente_telefone       TEXT    NOT NULL,
    tipo_entrega           TEXT    NOT NULL CHECK (tipo_entrega IN ('entrega', 'retirada')),
    endereco               TEXT,
    pagamento              TEXT    NOT NULL,
    observacao             TEXT,
    subtotal_centavos      INTEGER NOT NULL,
    taxa_entrega_centavos  INTEGER NOT NULL DEFAULT 0,
    total_centavos         INTEGER NOT NULL,
    status                 TEXT    NOT NULL DEFAULT 'novo',
    criado_em              TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),
    atualizado_em          TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS itens_pedido (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id                INTEGER NOT NULL REFERENCES pedidos(id) ON DELETE CASCADE,
    produto_id               INTEGER REFERENCES produtos(id) ON DELETE SET NULL,
    nome_produto             TEXT    NOT NULL,
    unidade                  TEXT    NOT NULL,
    preco_unitario_centavos  INTEGER NOT NULL,
    quantidade               INTEGER NOT NULL CHECK (quantidade > 0)
);

CREATE INDEX IF NOT EXISTS idx_pedidos_status ON pedidos(status);
CREATE INDEX IF NOT EXISTS idx_itens_pedido ON itens_pedido(pedido_id);
