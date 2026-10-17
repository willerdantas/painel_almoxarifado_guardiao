// icones simples em linha, brancos (herdam a cor do texto via currentColor)
const SVG_ABRE = (miolo) =>
  `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${miolo}</svg>`;

const ICONES = {
  dashboard: SVG_ABRE('<path d="M21.21 15.89A10 10 0 1 1 8 2.83"/><path d="M22 12A10 10 0 0 0 12 2v10z"/>'),
  painel_pedidos: SVG_ABRE('<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>'),
  pedidos: SVG_ABRE('<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/><line x1="12" y1="13" x2="12" y2="21"/>'),
  separacao_pedidos: SVG_ABRE('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 5 17 10"/><line x1="12" y1="5" x2="12" y2="15"/>'),
  distribuicao_pedidos: SVG_ABRE('<rect x="1" y="3" width="15" height="13"/><polygon points="16 8 20 8 23 11 23 16 16 16 16 8"/><circle cx="5.5" cy="18.5" r="2.5"/><circle cx="18.5" cy="18.5" r="2.5"/>'),
  produtos: SVG_ABRE('<path d="M20.59 13.41L11 3.83A2 2 0 0 0 9.59 3.24L3 3v6.59a2 2 0 0 0 .59 1.41l9.58 9.59a2 2 0 0 0 2.83 0l4.59-4.59a2 2 0 0 0 0-2.83z"/><circle cx="7.5" cy="7.5" r="1.5"/>'),
  estoque: SVG_ABRE('<rect x="2" y="3" width="20" height="5"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><line x1="10" y1="12" x2="14" y2="12"/>'),
  vencidos: SVG_ABRE('<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>'),
  estoque_critico: SVG_ABRE('<polyline points="23 18 13.5 8.5 8.5 13.5 1 6"/><polyline points="17 18 23 18 23 12"/>'),
  processos_aquisicao: SVG_ABRE('<path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="15" y2="16"/>'),
  planejamento_aquisicao: SVG_ABRE('<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><polyline points="9 16 11 18 15 14"/>'),
  atas_contratos: SVG_ABRE('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/>'),
  pagamentos: SVG_ABRE('<rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>'),
  cadastro: SVG_ABRE('<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>'),
  configuracao_banco: SVG_ABRE('<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>'),
  menu: SVG_ABRE('<line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>'),
  sair: SVG_ABRE('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>'),
};

// homem constroi menu uma vez so
const ITENS_MENU = [
  { href: "/pages/dashboard.html", icone: ICONES.dashboard, texto: "Dashboard", chave: "dashboard" },
  { href: "/pages/painel_pedidos.html", icone: ICONES.painel_pedidos, texto: "Painel de Pedidos", chave: "painel_pedidos" },
  { href: "/pages/pedidos.html", icone: ICONES.pedidos, texto: "Controle de Pedidos", chave: "pedidos" },
  { href: "/pages/separacao_pedidos.html", icone: ICONES.separacao_pedidos, texto: "Separação de Pedidos", chave: "separacao_pedidos" },
  { href: "/pages/distribuicao_pedidos.html", icone: ICONES.distribuicao_pedidos, texto: "Distribuição de Pedidos", chave: "distribuicao_pedidos" },
  { href: "/pages/produtos.html", icone: ICONES.produtos, texto: "Produtos", chave: "produtos" },
  { href: "/pages/estoque.html", icone: ICONES.estoque, texto: "Controle de Estoque", chave: "estoque" },
  { href: "/pages/vencidos.html", icone: ICONES.vencidos, texto: "Produtos Vencidos", chave: "vencidos" },
  { href: "/pages/estoque_critico.html", icone: ICONES.estoque_critico, texto: "Estoque Crítico", chave: "estoque_critico" },
  { href: "/pages/processos_aquisicao.html", icone: ICONES.processos_aquisicao, texto: "Processos de Aquisição", chave: "processos_aquisicao" },
  { href: "/pages/planejamento_aquisicao.html", icone: ICONES.planejamento_aquisicao, texto: "Planejamento de Aquisição", chave: "planejamento_aquisicao" },
  { href: "/pages/atas_contratos.html", icone: ICONES.atas_contratos, texto: "Atas e Contratos", chave: "atas_contratos" },
  { href: "/pages/pagamentos.html", icone: ICONES.pagamentos, texto: "Processos de Pagamento", chave: "pagamentos" },
  { href: "/pages/cadastro.html", icone: ICONES.cadastro, texto: "Cadastro", chave: "cadastro" },
  { href: "/pages/configuracao_banco.html", icone: ICONES.configuracao_banco, texto: "Configuração do Banco", chave: "configuracao_banco" },
];

// perfil de acesso (gravado no login) diz quais chaves de ITENS_MENU o usuario pode ver -
// administrador enxerga tudo; sem perfil gravado (login antigo) tambem libera tudo, pra nao
// quebrar sessao de quem logou antes dessa funcionalidade existir
function paginasPermitidas() {
  // usuario de teste (login com banco fora do ar) - so a tela de configurar a conexao
  if (localStorage.getItem("modo_configuracao") === "true") return ["configuracao_banco"];
  if (localStorage.getItem("administrador") === "true") return null;
  const bruto = localStorage.getItem("paginas");
  if (!bruto) return null;
  try {
    return JSON.parse(bruto);
  } catch (e) {
    return null;
  }
}

function montarMenu(paginaAtual) {
  // desenha esqueleto do menu - permitidas null = sem restricao (admin ou sessao antiga)
  const permitidas = paginasPermitidas();
  const itensVisiveis = permitidas ? ITENS_MENU.filter((item) => permitidas.includes(item.chave)) : ITENS_MENU;

  const links = itensVisiveis.map((item) => {
    const ativo = item.chave === paginaAtual ? "ativo" : "";
    return `<a href="${item.href}" class="${ativo}">
      <span class="icone">${item.icone}</span><span class="texto">${item.texto}</span>
    </a>`;
  }).join("");

  return `
    <aside class="menu-lateral" id="menuLateral">
      <div class="menu-cabecalho" id="toggleMenu">
        <span class="seta">▸</span>
        <span class="titulo-menu">
          <span class="icone">${ICONES.menu}</span><span class="texto">Menu</span>
        </span>
      </div>
      <nav>
        ${links}
        <a href="#" class="item-sair" id="botaoSairMenu">
          <span class="icone">${ICONES.sair}</span><span class="texto">Sair</span>
        </a>
      </nav>
    </aside>
  `;
}

function iniciarMenu(paginaAtual) {
  // se o perfil do usuario nao libera essa pagina, manda pra primeira que ele pode ver
  const permitidas = paginasPermitidas();
  if (permitidas && !permitidas.includes(paginaAtual)) {
    window.location.href = permitidas.length ? ITENS_MENU.find((item) => item.chave === permitidas[0]).href : "/";
    return;
  }

  // planta menu na tela
  document.getElementById("menuContainer").innerHTML = montarMenu(paginaAtual);
  document.getElementById("toggleMenu").addEventListener("click", () => {
    document.getElementById("menuLateral").classList.toggle("aberto");
  });

  const usuario = localStorage.getItem("usuario") || "visitante";
  const alvo = document.getElementById("usuarioLogado");
  if (alvo) alvo.textContent = usuario;

  document.getElementById("botaoSairMenu").addEventListener("click", (ev) => {
    ev.preventDefault();
    sair();
  });

  const botaoTopo = document.getElementById("botaoSairTopo");
  if (botaoTopo) botaoTopo.addEventListener("click", sair);
}

// se nao logado, manda de volta pra entrada
function protegerPagina() {
  if (!localStorage.getItem("usuario")) {
    window.location.href = "/";
  }
}

// tira o cracha e manda de volta pra entrada
function sair() {
  localStorage.removeItem("usuario");
  localStorage.removeItem("identificacao");
  localStorage.removeItem("administrador");
  localStorage.removeItem("paginas");
  localStorage.removeItem("modo_configuracao");
  window.location.href = "/";
}

// login (identificacao) de quem esta na tela, usado pra filtrar por armazem
function identificacaoLogada() {
  return localStorage.getItem("identificacao") || "";
}

// formata numero como moeda brasileira (R$ 1.234,56)
function formatarMoeda(valor) {
  if (valor === null || valor === undefined || valor === "") return "";
  const numero = Number(valor);
  if (Number.isNaN(numero)) return valor;
  return numero.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

// formata quantidade com separador de milhar/milhao (1.234.567) - toLocaleString ja agrupa
// corretamente em qualquer grandeza, sem limitar a milhar como uma formatacao manual faria
function formatarQuantidade(valor) {
  if (valor === null || valor === undefined || valor === "") return "";
  const numero = Number(valor);
  if (Number.isNaN(numero)) return valor;
  return numero.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

// mascara de cnpj: xx.xxx.xxx/xxxx-xx
function formatarCnpj(cnpj) {
  if (!cnpj) return "";
  const digitos = String(cnpj).replace(/\D/g, "");
  if (digitos.length !== 14) return cnpj;
  return digitos.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
}

// data de hoje no formato que o <input type="date"> entende
function dataHojeISO() {
  const hoje = new Date();
  const ano = hoje.getFullYear();
  const mes = String(hoje.getMonth() + 1).padStart(2, "0");
  const dia = String(hoje.getDate()).padStart(2, "0");
  return `${ano}-${mes}-${dia}`;
}


// poe as opcoes de uma consulta dentro de um <select> (campo "nome" por padrao)
async function preencherSelect(endpoint, selectId, campo = "nome") {
  const select = document.getElementById(selectId);
  try {
    const resp = await fetch(endpoint);
    const dados = await resp.json();
    dados.forEach((linha) => {
      const opcao = document.createElement("option");
      opcao.value = linha[campo];
      opcao.textContent = linha[campo];
      select.appendChild(opcao);
    });
  } catch (erro) {
    console.error(`Erro ao carregar ${endpoint}:`, erro);
  }
}

// campo de filtro de armazem (produtos/estoque/vencidos/estoque_critico) - so aparece pra
// administrador (enxerga todos os armazens) ou usuario com mais de um armazem em armazemfunc
// (pra quem tem so um, o filtro nao faria diferenca - ja esta implicito em usuario_logado)
async function iniciarFiltroArmazemCondicional(selectId, blocoId) {
  const administrador = localStorage.getItem("administrador") === "true";
  const bloco = document.getElementById(blocoId);
  const select = document.getElementById(selectId);

  try {
    let armazens = [];
    if (administrador) {
      const resp = await fetch("/api/armazens");
      armazens = await resp.json();
    } else if (identificacaoLogada()) {
      const resp = await fetch(`/api/usuario_armazens?usuario_logado=${encodeURIComponent(identificacaoLogada())}`);
      armazens = await resp.json();
    }

    if (!administrador && armazens.length <= 1) return;

    armazens.forEach((item) => {
      const opcao = document.createElement("option");
      opcao.value = item.nome;
      opcao.textContent = item.nome;
      select.appendChild(opcao);
    });
    bloco.classList.remove("oculto");
  } catch (erro) {
    console.error("Erro ao carregar armazéns do filtro:", erro);
  }
}
