// Página de acompanhamento do pedido: consulta o status a cada poucos segundos e
// recarrega a página quando a mercearia muda o status no painel.
const INTERVALO_STATUS_MS = 5000;
const STATUS_FINAIS = ["concluido", "cancelado"];
const CHAVE_AVISO = "mercearia_status_atualizado";

// Botões "Copiar" (chave Pix). A API de área de transferência só existe em https ou
// localhost; acessando pelo IP da rede local, cai no método antigo.
document.addEventListener("click", async (evento) => {
  const botao = evento.target.closest("[data-copiar]");
  if (!botao) return;
  const texto = botao.dataset.copiar;
  let copiou = false;
  try {
    await navigator.clipboard.writeText(texto);
    copiou = true;
  } catch {
    const campo = document.createElement("textarea");
    campo.value = texto;
    campo.setAttribute("readonly", "");
    campo.style.position = "fixed";
    campo.style.opacity = "0";
    document.body.append(campo);
    campo.select();
    try {
      copiou = document.execCommand("copy");
    } catch {}
    campo.remove();
  }
  const original = botao.textContent;
  botao.textContent = copiou ? "Copiada!" : "Copie a chave acima";
  setTimeout(() => (botao.textContent = original), 2500);
});

function acompanharStatus(urlStatus, statusAtual) {
  // Tira o "?novo=1" da barra de endereço para o aviso de "Pedido enviado!" não voltar ao recarregar.
  if (location.search) history.replaceState(null, "", location.pathname);

  try {
    if (sessionStorage.getItem(CHAVE_AVISO) === location.pathname) {
      sessionStorage.removeItem(CHAVE_AVISO);
      document.getElementById("aviso-status").hidden = false;
    }
  } catch {}

  if (STATUS_FINAIS.includes(statusAtual)) return;

  let temporizador = null;

  async function verificar() {
    temporizador = null;
    try {
      const resposta = await fetch(urlStatus, { cache: "no-store" });
      if (resposta.ok) {
        const { status } = await resposta.json();
        if (status !== statusAtual) {
          try {
            sessionStorage.setItem(CHAVE_AVISO, location.pathname);
          } catch {}
          location.reload();
          return;
        }
      }
    } catch {
      // Sem conexão ou servidor reiniciando: tenta de novo no próximo ciclo.
    }
    agendar();
  }

  function agendar() {
    if (!document.hidden && temporizador === null) {
      temporizador = setTimeout(verificar, INTERVALO_STATUS_MS);
    }
  }

  // Com a aba em segundo plano não consulta; ao voltar, confere na hora.
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) {
      clearTimeout(temporizador);
      temporizador = null;
    } else if (temporizador === null) {
      verificar();
    }
  });

  agendar();
}
