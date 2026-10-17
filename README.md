# INSYSTEM Almoxarifado

Sistema auxiliar de almoxarifado. Backend Flask + Postgres, frontend HTML/CSS/JS puro (sem build, sem React runtime — carrega direto no navegador, é o jeito mais leve pra você plugar as consultas reais no VS Code).

## Rodar
```
pip install flask psycopg2-binary
python app.py
```
Acesse `http://localhost:5000`.

## Banco de teste (dado fictício)
Enquanto as consultas reais não são coladas, o sistema roda contra um banco local
`almoxarifado_dev`, separado do banco de produção, com dado ficticio.
- `scripts/seed_dev.py` cria as tabelas (`usuario`, `pessoa`, `requisitante`, `armazem`,
  `requisicao`) e povoa com nomes fictícios. Roda de novo quando quiser resetar os dados:
  `python3 scripts/seed_dev.py`
- Login de teste: `admin` / `admin` (ou `joaosilva` / `1234`, etc.)
- Quando for a hora de ligar no banco real, troca `dbname` em `db.py` de volta pra
  `isivitaedb_hm` (ou o nome do banco de produção) — o resto do código não muda, já que o
  schema fictício foi desenhado pra bater com as tabelas/colunas reais.

## Ajustar
- `db.py` → credenciais reais do postgres (host/senha).
- `app.py` → em cada rota `/api/...` tem um `TODO homem:` — troca o `SELECT 1 placeholder` pela consulta real da tabela.
- `app.py /api/login` → se a senha no banco for hash (bcrypt/md5), troca a comparação direta pela verificação de hash.
- `static/js/sidebar.js` → lista `ITENS_MENU` controla os links do menu lateral.
- `static/css/style.css` → cores centralizadas nas variáveis `:root` (tema INSYSTEM: azul + vermelho).

## Estrutura
```
app.py                    # rotas flask + api
db.py                     # conexão postgres
scripts/seed_dev.py       # cria/povoa o banco de teste com dado ficticio
pages/                    # todas as telas html
  index.html               # login
  painel_pedidos.html
  pedidos.html
  separacao_pedidos.html
  distribuicao_pedidos.html
  vencidos.html
  estoque.html
  estoque_critico.html
  processos_aquisicao.html
  planejamento_aquisicao.html
  atas_contratos.html
  pagamentos.html
static/css/style.css      # css único do projeto
static/js/sidebar.js      # menu lateral + helpers compartilhados (data, select, registro de separação)
static/js/tabela.js       # renderiza tabela genérica vinda da api
```

**Banco fora do ar:** se o sistema não conseguir conectar no Postgres, o login aceita só o
usuário de teste (`teste` / `teste`, ou o que estiver nas variáveis de ambiente `USUARIO_TESTE` /
`SENHA_TESTE`), que entra direto na tela Configuração do Banco pra ajustar a conexão. Com o banco
conectando, esse usuário deixa de funcionar e o login volta ao normal.

Login usa `localStorage` pra guardar o usuário logado (troque por sessão/JWT se precisar de mais segurança).
