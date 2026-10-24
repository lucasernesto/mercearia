# Mercearia: sistema de pedidos

Sistema web de pedidos com duas áreas:

- **Loja (clientes)**: catálogo por categoria com busca, carrinho, escolha entre entrega e retirada, forma de pagamento e uma página para acompanhar o status do pedido. Quem paga com Pix vê a chave, com botão para copiar, e um botão que abre o WhatsApp da loja com a mensagem do comprovante pronta.
- **Painel (`/admin`)**: lista de pedidos por status com atualização automática, troca de status (aguardando aprovação → aprovado → em separação → pronto/saiu para entrega → concluído, ou cancelado), link para o WhatsApp do cliente e cadastro de produtos com preço, estoque e visibilidade na loja.

Feito em Python com Flask e SQLite. O frontend usa HTML, CSS e JavaScript puro, sem build.

## Como rodar

Única exigência: **Python 3.9 ou mais recente** ([python.org](https://www.python.org/downloads/); no Windows, marque "Add python.exe to PATH" na instalação).

```bash
git clone git@github.com:lucasernesto/mercearia.git
cd mercearia
```

Depois, rode o script de inicialização:

- **Windows:** dê dois cliques em `iniciar.bat` ou rode `iniciar.bat` no terminal.
- **Linux/macOS:** `./iniciar.sh` (no Debian/Ubuntu pode ser preciso `sudo apt install python3-venv` antes).

Na primeira vez o script cria o ambiente virtual `.venv`, instala as dependências nas versões fixadas em `requirements.txt` e cria o arquivo `.env` a partir do `.env.example`. Nas próximas vezes ele só inicia o sistema.

Abra http://localhost:5000 para a loja e http://localhost:5000/admin para o painel.

O banco `instance/mercearia.db` é criado na primeira execução, com alguns produtos de exemplo. Ele fica só na máquina e não vai para o git. Para levar os dados de uma máquina para outra, copie a pasta `instance/`. Para começar do zero, apague essa pasta.

### Rodando sem o script

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # Linux/macOS: .venv/bin/python
.venv\Scripts\python app.py
```

## Configuração (arquivo `.env`)

Edite o `.env` na pasta do projeto. Variáveis definidas no próprio sistema operacional têm prioridade sobre o arquivo.

| Variável | Padrão | Uso |
|---|---|---|
| `MERCEARIA_ADMIN_SENHA` | `admin123` | Senha do painel. **Troque antes de colocar no ar.** |
| `MERCEARIA_TAXA_ENTREGA_CENTAVOS` | `500` | Taxa de entrega em centavos (500 = R$ 5,00). |
| `MERCEARIA_PIX_CHAVE` | vazio | Chave Pix mostrada ao cliente depois que a mercearia aprova o pedido. |
| `MERCEARIA_WHATSAPP` | vazio | WhatsApp da loja, com DDD, que recebe os comprovantes. Sem chave e sem número, a seção de Pix não aparece. |
| `MERCEARIA_HOST` | `127.0.0.1` | `0.0.0.0` libera o acesso de outros aparelhos da rede pelo IP da máquina. |
| `MERCEARIA_PORTA` | `5000` | Porta do servidor. |
| `MERCEARIA_SECRET_KEY` | gerada em `instance/secret_key` | Chave das sessões. |
| `FLASK_DEBUG` | `0` | `1` usa o servidor de desenvolvimento do Flask, que recarrega ao editar o código. |

Fora do modo de desenvolvimento, o sistema roda no [waitress](https://docs.pylonsproject.org/projects/waitress/), um servidor próprio para produção que funciona em Windows, Linux e macOS.

## Painel no celular

- **Como chegar:** no rodapé da loja há o link **Área da mercearia**, que leva ao login do painel. Depois de entrar, o topo da loja mostra o link **Painel**.
- **Manter conectado:** no login, a opção "Manter conectado neste aparelho por 30 dias" já vem marcada, para não digitar a senha toda vez. Desmarque em aparelhos de uso compartilhado.
- **Ícone na tela inicial:** abra o painel no celular e use **Adicionar à tela inicial** (Chrome no Android: menu ⋮; Safari no iPhone: botão Compartilhar). O atalho abre direto nos pedidos, em tela cheia, como um aplicativo.
- Pedidos e produtos aparecem em forma de cartões; tocar no cartão abre o pedido. O telefone do cliente é um link para ligar.

Para o celular acessar o sistema rodando num computador da loja, use `MERCEARIA_HOST=0.0.0.0` no `.env` e abra `http://<IP-do-computador>:5000` no celular, na mesma rede Wi-Fi.

## Regras de negócio

- Os preços são guardados em centavos e o servidor recalcula o total; o valor enviado pelo navegador não é usado.
- O estoque baixa quando o pedido é feito. Se dois clientes disputam o último item, só um pedido passa.
- Cancelar um pedido devolve os itens ao estoque. Um pedido cancelado não muda mais de status.
- Produtos com estoque zero aparecem como "Esgotado". Produtos ocultos somem da loja, mas continuam nos pedidos antigos.
- Todo pedido chega como "Aguardando aprovação". No Pix, a chave e o botão do comprovante só aparecem para o cliente depois que a mercearia aprova o pedido.
- O cliente acompanha o pedido por um link com código aleatório (`/pedido/<código>`). A página confere o status a cada 5 segundos e se atualiza sozinha quando a mercearia muda o status no painel.

## Estrutura

```
iniciar.bat         prepara e inicia no Windows
iniciar.sh          prepara e inicia no Linux/macOS
.env.example        modelo de configuração (copiado para .env)
app.py              rotas, validação e regras
schema.sql          tabelas: produtos, pedidos, itens_pedido
templates/          páginas da loja e do painel (templates/admin/)
static/style.css    visual
static/carrinho.js  carrinho no navegador, catálogo e checkout
static/pedido.js    atualização automática da página do pedido
static/icones/      ícones da tela inicial do celular
```

## Antes de publicar na internet

Defina uma senha forte no `.env` e coloque o sistema atrás de HTTPS (por exemplo com um proxy reverso como Caddy ou Nginx). O login do painel não limita tentativas, então vale adicionar isso se o painel ficar exposto.
