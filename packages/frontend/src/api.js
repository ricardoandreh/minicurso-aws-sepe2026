// A URL da API vem do build (não é segredo). A chave NÃO vem: ela é digitada
// pela pessoa e guardada só no sessionStorage desta aba. Embutir a chave no
// bundle via VITE_* deixaria ela visível no DevTools de qualquer visitante.
const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");
const STORAGE_KEY = "central-chamados:api-key";

export function lerApiKey() {
  try {
    return sessionStorage.getItem(STORAGE_KEY) ?? "";
  } catch {
    return "";
  }
}

export function salvarApiKey(valor) {
  try {
    sessionStorage.setItem(STORAGE_KEY, valor);
  } catch {
    /* modo privado / storage bloqueado — a chave vale só para esta sessão */
  }
}

function headers() {
  return {
    "Content-Type": "application/json",
    "x-api-key": lerApiKey(),
  };
}

// 401 e 403 vêm do Lambda Authorizer e significam coisas diferentes:
// 401 = nenhuma credencial chegou ao authorizer
// 403 = a credencial chegou e foi recusada
function conferir(resposta) {
  if (resposta.status === 401) {
    throw new Error("Nenhuma chave enviada — preencha a chave de acesso.");
  }
  if (resposta.status === 403) {
    throw new Error("Chave de acesso incorreta.");
  }
  if (!resposta.ok) {
    throw new Error(`Falha na requisição (HTTP ${resposta.status})`);
  }
  return resposta;
}

export async function criarChamado(titulo, descricao) {
  const resposta = await fetch(`${API_URL}/chamados`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ titulo, descricao }),
  });

  return conferir(resposta).json();
}

export async function listarChamados() {
  const resposta = await fetch(`${API_URL}/chamados`, {
    headers: headers(),
  });

  const dados = await conferir(resposta).json();
  return dados.chamados ?? [];
}
