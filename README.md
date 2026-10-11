# Mercearia: sistema de pedidos

Sistema web de pedidos com duas áreas:

- **Loja (clientes)**: catálogo por categoria com busca, carrinho, escolha entre entrega e retirada, forma de pagamento e uma página para acompanhar o status do pedido.
- **Painel (`/admin`)**: lista de pedidos por status com atualização automática, troca de status (novo → em separação → pronto/saiu para entrega → concluído, ou cancelado), link para o WhatsApp do cliente e cadastro de produtos com preço, estoque e visibilidade na loja.

Feito em Python com Flask e SQLite. O frontend usa HTML, CSS e JavaScript puro, sem build.

## Como rodar

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Abra http://127.0.0.1:5000 para a loja e http://127.0.0.1:5000/admin para o painel.

Na primeira execução é criado o banco `instance/mercearia.db` com alguns produtos de exemplo. Para começar do zero, apague a pasta `instance/`.

## Configuração (variáveis de ambiente)

| Variável | Padrão | Uso |
|---|---|---|
| `MERCEARIA_ADMIN_SENHA` | `admin123` | Senha do painel. **Troque antes de colocar no ar.** |
| `MERCEARIA_TAXA_ENTREGA_CENTAVOS` | `500` | Taxa de entrega em centavos (500 = R$ 5,00). |
| `MERCEARIA_SECRET_KEY` | gerada em `instance/secret_key` | Chave das sessões. |
| `FLASK_DEBUG` | desligado | `1` ativa o modo de desenvolvimento. |

Exemplo no PowerShell:

```powershell
$env:MERCEARIA_ADMIN_SENHA = "uma-senha-forte"
python app.py
```

## Regras de negócio

- Os preços são guardados em centavos e o servidor recalcula o total; o valor enviado pelo navegador não é usado.
- O estoque baixa quando o pedido é feito. Se dois clientes disputam o último item, só um pedido passa.
- Cancelar um pedido devolve os itens ao estoque. Um pedido cancelado não muda mais de status.
- Produtos com estoque zero aparecem como "Esgotado". Produtos ocultos somem da loja, mas continuam nos pedidos antigos.
- O cliente acompanha o pedido por um link com código aleatório (`/pedido/<código>`). A página se atualiza sozinha a cada minuto.

## Estrutura

```
app.py              rotas, validação e regras
schema.sql          tabelas: produtos, pedidos, itens_pedido
templates/          páginas da loja e do painel (templates/admin/)
static/style.css    visual
static/carrinho.js  carrinho no navegador, catálogo e checkout
```

## Antes de publicar na internet

`python app.py` usa o servidor de desenvolvimento do Flask. Para produção, use um servidor WSGI (por exemplo `waitress-serve --port=8000 app:app` no Windows) atrás de HTTPS e defina uma senha forte. O login do painel não limita tentativas, então vale adicionar isso se o painel ficar exposto.
