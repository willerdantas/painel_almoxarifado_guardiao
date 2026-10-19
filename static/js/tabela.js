// busca dado na api e desenha tabela
async function carregarTabela(endpoint, containerId) {
  const container = document.getElementById(containerId);
  try {
    const resp = await fetch(endpoint);
    const dados = await resp.json();

    if (!Array.isArray(dados) || dados.length === 0) {
      container.innerHTML = '<p class="msg-vazio">Nenhum dado encontrado, homem.</p>';
      return [];
    }

    const colunas = Object.keys(dados[0]);
    const cabecalho = colunas.map((c) => `<th>${escaparHtml(c)}</th>`).join("");
    const linhas = dados
      .map((linha) => `<tr>${colunas.map((c) => `<td>${escaparHtml(linha[c])}</td>`).join("")}</tr>`)
      .join("");

    container.innerHTML = `
      <table class="tabela-dados">
        <thead><tr>${cabecalho}</tr></thead>
        <tbody>${linhas}</tbody>
      </table>`;
    return dados;
  } catch (erro) {
    container.innerHTML = `<p class="msg-vazio">Erro ao caçar dados: ${escaparHtml(erro)}</p>`;
    return [];
  }
}
