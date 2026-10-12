// Carrinho guardado no navegador do cliente: { "<produto_id>": quantidade }.
// O servidor recalcula preços e confere estoque ao finalizar, então isto é só conveniência.
const CHAVE_CARRINHO = "mercearia_carrinho";
const QTD_MAXIMA = 99;

function lerCarrinho() {
  try {
    const dados = JSON.parse(localStorage.getItem(CHAVE_CARRINHO));
    return dados && typeof dados === "object" ? dados : {};
  } catch {
    return {};
  }
}

function salvarCarrinho(carrinho) {
  try {
    localStorage.setItem(CHAVE_CARRINHO, JSON.stringify(carrinho));
  } catch {
    // Sem armazenamento disponível (modo privado restrito): o carrinho dura só nesta página.
  }
  atualizarBadge();
}

function limparCarrinho() {
  try {
    localStorage.removeItem(CHAVE_CARRINHO);
  } catch {}
  atualizarBadge();
}

function atualizarBadge() {
  const total = Object.values(lerCarrinho()).reduce((soma, qtd) => soma + qtd, 0);
  document.querySelectorAll("[data-badge-carrinho]").forEach((el) => {
    el.textContent = total;
    el.hidden = total === 0;
  });
}

function formatarBRL(centavos) {
  return (centavos / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function normalizar(texto) {
  return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

function alterarQuantidade(id, delta, maximo) {
  const carrinho = lerCarrinho();
  const nova = Math.min(maximo, (carrinho[id] || 0) + delta);
  if (nova <= 0) delete carrinho[id];
  else carrinho[id] = nova;
  salvarCarrinho(carrinho);
}

function criarBotao(texto, classe, aoClicar) {
  const botao = document.createElement("button");
  botao.type = "button";
  botao.className = classe;
  botao.textContent = texto;
  botao.addEventListener("click", aoClicar);
  return botao;
}

function criarStepper(id, qtd, maximo, aoMudar) {
  const caixa = document.createElement("div");
  caixa.className = "stepper";
  const menos = criarBotao(qtd === 1 ? "🗑" : "−", "botao-qtd", () => {
    alterarQuantidade(id, -1, maximo);
    aoMudar();
  });
  menos.setAttribute("aria-label", qtd === 1 ? "Remover" : "Diminuir");
  const valor = document.createElement("span");
  valor.className = "qtd";
  valor.textContent = qtd;
  const mais = criarBotao("+", "botao-qtd", () => {
    alterarQuantidade(id, 1, maximo);
    aoMudar();
  });
  mais.setAttribute("aria-label", "Aumentar");
  mais.disabled = qtd >= maximo;
  caixa.append(menos, valor, mais);
  return caixa;
}

// ------------------------------------------------------------------ catálogo

function renderizarControles(card) {
  const id = card.dataset.id;
  const maximo = Math.min(Number(card.dataset.estoque), QTD_MAXIMA);
  if (maximo <= 0) return;
  const caixa = card.querySelector("[data-controles]");
  const qtd = lerCarrinho()[id] || 0;
  card.classList.toggle("no-carrinho", qtd > 0);
  caixa.replaceChildren(
    qtd === 0
      ? criarBotao("Adicionar", "botao botao-primario", () => {
          alterarQuantidade(id, 1, maximo);
          renderizarControles(card);
        })
      : criarStepper(id, qtd, maximo, () => renderizarControles(card))
  );
}

function iniciarCatalogo() {
  const cards = [...document.querySelectorAll("[data-produto]")];
  cards.forEach((card) => {
    card.dataset.busca = normalizar(card.querySelector("h3").textContent);
    renderizarControles(card);
  });

  const busca = document.getElementById("busca");
  const semResultado = document.getElementById("busca-vazia");
  busca?.addEventListener("input", () => {
    const termo = normalizar(busca.value);
    cards.forEach((card) => (card.hidden = termo !== "" && !card.dataset.busca.includes(termo)));
    let algumVisivel = false;
    document.querySelectorAll("[data-categoria]").forEach((secao) => {
      secao.hidden = !secao.querySelector("[data-produto]:not([hidden])");
      algumVisivel ||= !secao.hidden;
    });
    semResultado.hidden = algumVisivel || cards.length === 0;
  });

  // Ao voltar para a página pelo histórico, o carrinho pode ter mudado.
  window.addEventListener("pageshow", () => {
    cards.forEach(renderizarControles);
    atualizarBadge();
  });
  atualizarBadge();
}

// ------------------------------------------------------------------ checkout

function iniciarCheckout(produtos, taxaEntrega) {
  const lista = document.getElementById("itens-carrinho");
  const form = document.getElementById("form-checkout");
  const botaoFinalizar = document.getElementById("botao-finalizar");
  const campoEndereco = document.getElementById("campo-endereco");
  const endereco = campoEndereco.querySelector("textarea");

  // Remove itens que saíram da loja e ajusta quantidades ao estoque atual.
  const carrinho = lerCarrinho();
  let mudou = false;
  for (const id of Object.keys(carrinho)) {
    const p = produtos[id];
    if (!p || p.estoque <= 0) {
      delete carrinho[id];
      mudou = true;
    } else if (carrinho[id] > p.estoque) {
      carrinho[id] = p.estoque;
      mudou = true;
    }
  }
  if (mudou) salvarCarrinho(carrinho);

  const tipoEntrega = () => form.querySelector("input[name=tipo_entrega]:checked")?.value;

  function renderizar() {
    const atual = lerCarrinho();
    const ids = Object.keys(atual).filter((id) => produtos[id]);
    let subtotal = 0;
    lista.replaceChildren(
      ...ids.map((id) => {
        const p = produtos[id];
        const qtd = atual[id];
        subtotal += p.preco * qtd;

        const linha = document.createElement("div");
        linha.className = "linha-item";
        const info = document.createElement("div");
        info.className = "info-item";
        const nome = document.createElement("strong");
        nome.textContent = p.nome;
        const detalhe = document.createElement("small");
        detalhe.textContent = `${formatarBRL(p.preco)} · ${p.unidade}`;
        info.append(nome, detalhe);
        const valor = document.createElement("span");
        valor.className = "valor-item";
        valor.textContent = formatarBRL(p.preco * qtd);
        linha.append(info, criarStepper(id, qtd, Math.min(p.estoque, QTD_MAXIMA), renderizar), valor);
        return linha;
      })
    );

    const vazio = ids.length === 0;
    const entrega = tipoEntrega() === "entrega";
    const taxa = !vazio && entrega ? taxaEntrega : 0;
    document.getElementById("carrinho-vazio").hidden = !vazio;
    document.getElementById("subtotal").textContent = formatarBRL(subtotal);
    document.getElementById("taxa").textContent = entrega ? formatarBRL(taxa) : "Retirada (grátis)";
    document.getElementById("total").textContent = formatarBRL(subtotal + taxa);
    botaoFinalizar.disabled = vazio;
    campoEndereco.hidden = !entrega;
    endereco.required = entrega;
  }

  const pagamento = form.querySelector("select[name=pagamento]");
  const dicaPix = document.getElementById("dica-pix");
  const mostrarDicaPix = () => dicaPix && (dicaPix.hidden = pagamento.value !== "pix");
  mostrarDicaPix();

  form.addEventListener("change", (e) => {
    if (e.target.name === "tipo_entrega") renderizar();
    if (e.target === pagamento) mostrarDicaPix();
  });
  form.addEventListener("submit", (e) => {
    const atual = lerCarrinho();
    if (Object.keys(atual).length === 0) {
      e.preventDefault();
      return;
    }
    document.getElementById("campo-carrinho").value = JSON.stringify(atual);
    botaoFinalizar.disabled = true;
    botaoFinalizar.textContent = "Enviando…";
  });
  window.addEventListener("pageshow", () => {
    botaoFinalizar.textContent = "Enviar pedido";
    renderizar();
  });

  renderizar();
  atualizarBadge();
}
