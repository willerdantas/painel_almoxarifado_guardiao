# INSYSTEM Almoxarifado

Painel de gestão de almoxarifado que roda sobre o banco do Guardião (Postgres): pedidos,
separação e distribuição, estoque, vencidos, estoque crítico, atas e contratos, processos e
planejamento de aquisição.

- **Backend:** Flask (`app.py`) consultando o Postgres com `psycopg2`.
- **Frontend:** HTML/CSS/JS puro, sem build. Cada tela é um arquivo em `pages/`.
- **Dados:** lê as tabelas do Guardião (schema `public`) e guarda o que é do próprio sistema
  (perfis, usuários, processos de aquisição…) no schema `sist_logistica`.

## Telas

| Menu | Arquivo | O que faz |
|---|---|---|
| Dashboard | `dashboard.html` | Indicadores de estoque, atas/contratos e ponto de ressuprimento. |
| Painel de Pedidos | `painel_pedidos.html` | Contagem de pedidos por etapa e chamadas. |
| Controle de Pedidos | `pedidos.html` | Lista de pedidos (requisições) e seus itens. |
| Separação de Pedidos | `separacao_pedidos.html` | Fila de separação com registro de itens separados. |
| Distribuição de Pedidos | `distribuicao_pedidos.html` | Fila de distribuição (até 10 pedidos por usuário). |
| Produtos | `produtos.html` | Catálogo de produtos com lotes e notas. |
| Controle de Estoque | `estoque.html` | Estoque por produto (CD e Hospital): lotes, abastecimento, movimentações, unidades, atas/contratos e processos de aquisição. Abre também `consumo.html` e `estoque_movimentacoes.html`. |
| Produtos Vencidos | `vencidos.html` | Lotes vencidos com estoque, relatório por armazém (PDF/CSV/planilha). |
| Estoque Crítico | `estoque_critico.html` | Produtos abaixo do ponto de ressuprimento, estoque mínimo ou de segurança. |
| Processos de Aquisição | `processos_aquisicao.html` | Processos SESA (importados da planilha) e Processos Hospital. Ver abaixo. |
| Planejamento de Aquisição | `planejamento_aquisicao.html` | Sugestão de compra pela média de consumo. Ver abaixo. |
| Atas e Contratos | `atas_contratos.html` | Atas e contratos vigentes, aditivos, itens e saldos. Os vencidos ficam em `atas_contratos_vencidos.html`. |
| Processos de Pagamento | `pagamentos.html` | Estrutura pronta; consulta ainda não definida (ver Pendências). |
| Cadastro | `cadastro.html` | Perfis de acesso, usuários e calendário de distribuição. **Só administrador.** |
| Configuração do Banco | `configuracao_banco.html` | Conexão com o Postgres, criação do schema e logo. **Só administrador.** |

O login fica em `index.html`. As páginas que cada perfil vê são escolhidas em **Cadastro**.

### Processos de Aquisição

- **Processos SESA:** vêm da planilha *CONTROLE GERAL POR ITENS* (botão **+ Importar Planilha**).
  - Cada aba vira um grupo: MED → Medicamento, MMH, OPME, ODONTO → Odontologia, NUT → Nutrição,
    GASES → Gases Medicinais, LAB → Laboratório, EQUIP → Equipamentos, SERV → Serviço. As demais
    abas são ignoradas.
  - A importação **só inclui e atualiza, nunca exclui**. Um item é identificado por
    grupo + processo + nº item + código SRP. Por isso, mudar um desses campos na planilha cria um
    item novo.
  - As tabelas são criadas sozinhas na primeira importação.
- **Processos Hospital:** um item vai para o Hospital automaticamente quando o código SRP bate com
  o Cód. Seplag de algum produto.
  - **Incluir** e **Remover** ajustam isso à mão; o ajuste vale também depois de reimportar a
    planilha.
  - **+ Novo Processo** cadastra processos fora da planilha, com busca de itens pelo Cód. Seplag.
  - **Editar** só aparece para os perfis Administrador e Compras (lista `PERFIS_EDITAM_PROCESSO_HOSPITAL`
    em `app.py`). Também é guardado à parte e sobrevive à reimportação.
  - Os itens do Hospital mostram estoque e saldo a entregar em atas e contratos vigentes.

### Planejamento de Aquisição

- **Gerar** lista os produtos com consumo nos últimos 6 meses nos armazéns do usuário. Classe,
  subgrupo e armazém filtram a lista.
- Consumo é toda saída do armazém (saídas estornadas não contam).
- **Qtde. Sugerida** = consumo dos 6 meses ÷ 6, arredondado para cima. É mensal e pode ser
  alterada na tabela. Qtde. e Valor Anual = 12 × mensal.
- **+ Inserir Itens** adiciona produtos pelo Cód. Seplag ou nome.
- A lista **não é salva**: use CSV, Planilha ou PDF.

## Rodar

```bash
pip install -r requirements.txt
export DB_PASSWORD='...'     # senha do Postgres (nunca no código)
python app.py                # desenvolvimento
```

Acesse `http://localhost:5000`.

**Produção:**

```bash
gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 --preload app:app
```

O `--preload` carrega o app uma vez só, para todos os processos usarem a mesma chave de sessão.

**Docker:**

```bash
docker compose up -d --build
```

O `docker-compose.yml` sobe em modo desenvolvimento: o servidor recarrega ao salvar um arquivo,
sem o depurador. Para usar o gunicorn do `Dockerfile`, tire o `command:` do compose. O container
roda com o usuário `app` (uid 1000); os arquivos `db_config.json` e `secret_key` precisam pertencer
a esse usuário.

## Configuração (variáveis de ambiente)

| Variável | Para quê |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Conexão padrão do Postgres. Se existir `db_config.json` (gravado pela tela Configuração do Banco, fora do git), ele vale no lugar. |
| `APP_SECRET_KEY` | Assina o cookie de sessão. Sem ela, o sistema gera uma e guarda em `secret_key` (fora do git). |
| `APP_COOKIE_SECURE=1` | Só manda o cookie de sessão por HTTPS. Use quando o sistema estiver atrás de HTTPS. |
| `USUARIO_TESTE`, `SENHA_TESTE` | Usuário de emergência: só entra com o banco fora do ar, e só na Configuração do Banco. Sem as duas variáveis, ele não existe. |
| `APP_DEBUG=1` | Depurador interativo do Flask. **Nunca em produção:** ele executa código pelo navegador. |
| `APP_RELOAD=1` | Recarrega o servidor ao salvar um arquivo, sem o depurador. |
| `APP_PORT` | Porta do servidor de desenvolvimento (padrão 5000). |

**Banco fora do ar:** o login só aceita o usuário de emergência (se configurado), que entra direto
na Configuração do Banco para corrigir a conexão. Com o banco de volta, o login volta ao normal.

**Banco novo:** em Configuração do Banco, **Criar schema e tabelas** cria o `sist_logistica` com os
perfis padrão, e **Criar administrador inicial** vincula o primeiro administrador. Isso só funciona
enquanto nenhum usuário estiver cadastrado.

## Segurança

- **Sessão no servidor.** O login cria um cookie de sessão assinado, que expira em 12 horas. Toda
  rota `/api/` exige essa sessão, e o usuário logado sempre vem dela. O `localStorage` do navegador
  só guarda nome e menu para desenhar a tela.
- **Rotas de administrador.** `/api/perfis`, `/api/paginas_sistema`, `/api/usuarios_sistema`,
  `/api/calendario_distribuicao` e `/api/configuracao_banco` exigem perfil administrador.
- **Login.** Usuário inexistente e senha errada recebem a mesma mensagem. Cinco tentativas erradas
  bloqueiam por 5 minutos.
- **Primeiro acesso.** Definir senha só funciona para quem ainda não tem senha (usuário novo ou
  senha resetada no Cadastro). Depois de resetar a senha de alguém, peça para a pessoa criar a
  nova logo em seguida.
- **Conexão do banco.** Ao trocar host, porta ou usuário, a senha precisa ser digitada de novo; a
  atual só é mantida quando o servidor continua o mesmo.
- **Tela.** Todo dado que vai para o HTML passa por `escaparHtml` (`static/js/sidebar.js`).
- **Uploads** acima de 32 MB são recusados antes de serem lidos.

## Testes

```bash
python3 -m unittest discover -s tests -v
```

Os testes rodam sem banco (o acesso ao banco é simulado). Cobrem sessão e permissões, login,
primeiro acesso, troca de conexão, limite de upload e a leitura da planilha SESA.

## Banco de teste (dado fictício)

`scripts/seed_dev.py` cria e povoa um banco local separado (`almoxarifado_dev`) com dados
fictícios. Rode de novo para resetar os dados:

```bash
python3 scripts/seed_dev.py
```

Ele usa as mesmas variáveis `DB_HOST`, `DB_USER` e `DB_PASSWORD`, e `DB_NAME_DEV` para o nome do
banco (padrão `almoxarifado_dev`). Para o sistema usar esse banco, aponte a conexão para ele
(`DB_NAME` ou tela Configuração do Banco).

## Estrutura

```
app.py                       # rotas Flask, API, relatórios e regras de negócio
db.py                        # conexão com o Postgres
requirements.txt
Dockerfile / docker-compose.yml
scripts/seed_dev.py          # cria/povoa o banco de teste
tests/test_seguranca.py      # testes automatizados
pages/                       # uma tela por arquivo (ver tabela acima)
static/css/style.css         # CSS único; cores nas variáveis :root
static/js/sidebar.js         # menu lateral, sessão no navegador, escaparHtml e formatadores
static/js/tabela.js          # tabela genérica a partir de uma API
static/js/chart.umd.min.js   # Chart.js (gráficos do dashboard)
static/logo_insystem.png     # logo (trocável pela Configuração do Banco)
```

**Schema `sist_logistica`** (do próprio sistema; o resto vem do Guardião):

| Tabela | Conteúdo |
|---|---|
| `sistemaperfil`, `sistemaperfilpagina`, `sistemausuario` | Perfis de acesso, páginas de cada perfil e usuários do sistema (senha com hash). |
| `calendariodistribuicao` | Dias de distribuição por armazém. |
| `armazemmovimentacao` | Registro de separação e distribuição. |
| `grupoaquisicao` | Os 9 grupos de aquisição (MED, MMH…). |
| `processosesaitem`, `processosesaimportacao` | Itens da planilha SESA e histórico de importações. |
| `processohospitalajuste` | Ajustes manuais Incluir/Remover. |
| `processohospitalmanual`, `processohospitalmanualitem` | Processos cadastrados à mão e seus itens. |
| `processohospitaledicao` | Edições feitas pelo botão Editar em processos da planilha. |

## Onde mexer

- **Menu lateral:** lista `ITENS_MENU` em `static/js/sidebar.js`. Página nova também precisa
  entrar em `PAGES` e `PAGINAS_SISTEMA` no `app.py`.
- **Cores e tema:** variáveis `:root` em `static/css/style.css`.
- **Perfis que editam processos do Hospital:** `PERFIS_EDITAM_PROCESSO_HOSPITAL` em `app.py`.
- **Perfis que veem todos os armazéns:** `PERFIS_SEM_RESTRICAO_ARMAZEM` em `app.py`.

## Pendências

- **Processos de Pagamento:** a consulta ainda não foi definida (`/api/pagamentos` em `app.py`).
- **Atas e Contratos:** os filtros de status e modalidade aguardam o significado dos códigos de
  1 letra (`statuspedido`, `modalidadelicitacao`).
- **Separação:** `/api/pedidos_separacao` ainda não filtra por status de separação/distribuição.
- **Permissões por página na API:** as rotas de administrador são protegidas, mas um usuário logado
  ainda consegue chamar a API de uma página que não está no perfil dele.
- **`app.py` com mais de 6.000 linhas:** dividir por área (Flask Blueprints) depois de ampliar os
  testes.
