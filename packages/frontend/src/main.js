import { criarChamado, listarChamados, lerApiKey, salvarApiKey } from "./api.js";

const form = document.getElementById("form-chamado");
const statusForm = document.getElementById("status-form");
const lista = document.getElementById("lista-chamados");
const btnAtualizar = document.getElementById("btn-atualizar");
const campoChave = document.getElementById("api-key");
const btnRevelar = document.getElementById("btn-revelar");

function formatarData(isoString) {
  if (!isoString) return "";
  return new Date(isoString).toLocaleString("pt-BR");
}

function mensagem(texto, tipo = "") {
  statusForm.textContent = texto;
  statusForm.className = tipo ? `status ${tipo}` : "status";
}

// Os campos vêm do que o usuário digitou, então montamos os nós com
// textContent em vez de innerHTML — senão um título com HTML dentro seria
// executado no navegador de quem abre a lista.
function criarItem(chamado) {
  const item = document.createElement("li");
  item.className = "chamado";

  const topo = document.createElement("div");
  topo.className = "chamado-topo";

  const titulo = document.createElement("span");
  titulo.className = "chamado-titulo";
  titulo.textContent = chamado.titulo ?? "";

  const badge = document.createElement("span");
  badge.className = `badge badge-${chamado.status ?? ""}`;
  badge.textContent = chamado.status ?? "";

  topo.append(titulo, badge);

  const descricao = document.createElement("p");
  descricao.className = "chamado-descricao";
  descricao.textContent = chamado.descricao ?? "";

  const data = document.createElement("time");
  data.textContent = formatarData(chamado.timestamp);

  item.append(topo, descricao, data);
  return item;
}

function renderizarChamados(chamados) {
  lista.replaceChildren();

  if (chamados.length === 0) {
    const vazio = document.createElement("li");
    vazio.className = "vazio";
    vazio.textContent = "Nenhum chamado ainda.";
    lista.append(vazio);
    return;
  }

  lista.append(...chamados.map(criarItem));
}

async function atualizarLista() {
  if (!lerApiKey()) {
    lista.replaceChildren();
    const vazio = document.createElement("li");
    vazio.className = "vazio";
    vazio.textContent = "Informe a chave de acesso para ver os chamados.";
    lista.append(vazio);
    return;
  }

  try {
    renderizarChamados(await listarChamados());
  } catch (erro) {
    lista.replaceChildren();
    const falha = document.createElement("li");
    falha.className = "vazio erro";
    falha.textContent = erro.message;
    lista.append(falha);
  }
}

form.addEventListener("submit", async (evento) => {
  evento.preventDefault();

  const titulo = document.getElementById("titulo").value.trim();
  const descricao = document.getElementById("descricao").value.trim();
  const botaoEnviar = form.querySelector("button[type=submit]");

  mensagem("Enviando...");
  botaoEnviar.disabled = true;

  try {
    await criarChamado(titulo, descricao);
    mensagem("Chamado criado! O agente de AI está processando.", "sucesso");
    form.reset();
    await atualizarLista();
  } catch (erro) {
    mensagem(erro.message, "erro");
  } finally {
    botaoEnviar.disabled = false;
  }
});

btnAtualizar.addEventListener("click", atualizarLista);

// chave: salva a cada tecla (não se perde ao recarregar a aba) e recarrega
// a lista quando a pessoa termina de digitar
campoChave.value = lerApiKey();
campoChave.addEventListener("input", () => salvarApiKey(campoChave.value.trim()));
campoChave.addEventListener("change", atualizarLista);

btnRevelar.addEventListener("click", () => {
  const revelada = campoChave.type === "text";
  campoChave.type = revelada ? "password" : "text";
  btnRevelar.setAttribute("aria-pressed", String(!revelada));
  btnRevelar.setAttribute("aria-label", revelada ? "Mostrar chave" : "Ocultar chave");
});

atualizarLista();
