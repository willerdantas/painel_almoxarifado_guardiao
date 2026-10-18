# INSYSTEM Almoxarifado

Sistema auxiliar de almoxarifado. Backend Flask + Postgres, frontend HTML/CSS/JS puro (sem build, sem React runtime — carrega direto no navegador, é o jeito mais leve pra você plugar as consultas reais no VS Code).

## Rodar
```
pip install -r requirements.txt
export DB_PASSWORD='...'      # senha do Postgres (nunca no código)
python app.py                 # desenvolvimento (APP_RELOAD=1 recarrega ao salvar)
gunicorn --bind 0.0.0.0:5000 --workers 2 --preload app:app   # produção
```
Acesse `http://localhost:5000`. Com Docker: `docker compose up -d --build` (o compose sobe em modo
desenvolvimento; tire o `command:` dele pra usar o gunicorn do Dockerfile).

## Configuração (variáveis de ambiente)
| Variável | Para quê |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Conexão padrão do Postgres. A tela Configuração do Banco grava por cima em `db_config.json` (fora do git). |
| `APP_SECRET_KEY` | Assina o cookie de sessão. Sem ela, o sistema gera uma e guarda em `secret_key` (fora do git). |
| `APP_COOKIE_SECURE=1` | Só manda o cookie de sessão por HTTPS (use quando estiver atrás de HTTPS). |
| `USUARIO_TESTE`, `SENHA_TESTE` | Usuário de emergência que só entra com o banco fora do ar, direto na Configuração do Banco. Sem as duas variáveis, ele não existe. |
| `APP_DEBUG=1` | Depurador interativo do Flask. **Nunca em produção** (executa código pelo navegador). |
| `APP_RELOAD=1` | Recarrega o servidor ao salvar arquivo, sem o depurador. |

## Segurança
- O login cria uma sessão no servidor (cookie assinado, expira em 12h). Toda rota `/api/` exige
  essa sessão, e o usuário logado sempre vem dela — o `localStorage` só guarda nome e menu pra
  desenhar a tela.
- Cadastro e Configuração do Banco (`/api/perfis`, `/api/usuarios_sistema`,
  `/api/calendario_distribuicao`, `/api/configuracao_banco`...) são só de administrador.
- Login: mesma mensagem pra usuário inexistente e senha errada; 5 tentativas erradas bloqueiam
  por 5 minutos.
- Definir senha só funciona pra quem ainda não tem senha (primeiro acesso ou senha resetada).
- Todo dado que vai pra tela passa por `escaparHtml` (`static/js/sidebar.js`).

## Testes
```
python3 -m unittest discover -s tests -v
```
Rodam sem banco (acesso ao banco simulado).

## Banco de teste (dado fictício)
Enquanto as consultas reais não são coladas, o sistema roda contra um banco local
`almoxarifado_dev`, separado do banco de produção, com dado ficticio.
- `scripts/seed_dev.py` cria as tabelas (`usuario`, `pessoa`, `requisitante`, `armazem`,
  `requisicao`) e povoa com nomes fictícios. Roda de novo quando quiser resetar os dados:
  `python3 scripts/seed_dev.py`
- Login de teste: `admin` / `admin` (ou `joaosilva` / `1234`, etc.)
- O script usa as mesmas variáveis `DB_HOST`/`DB_USER`/`DB_PASSWORD` (e `DB_NAME_DEV`, padrão
  `almoxarifado_dev`).

## Ajustar
- Conexão do banco → variáveis de ambiente acima ou tela Configuração do Banco.
- `app.py` → onde tiver `TODO homem:` ainda falta definição de negócio (consulta de pagamentos,
  significado dos códigos de status/modalidade).
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
tests/                    # testes automatizados (python3 -m unittest discover -s tests)
```

**Banco fora do ar:** se o sistema não conseguir conectar no Postgres, o login aceita só o
usuário de emergência das variáveis `USUARIO_TESTE` / `SENHA_TESTE` (se estiverem definidas), que
entra direto na tela Configuração do Banco pra ajustar a conexão. Com o banco conectando, esse
usuário deixa de funcionar e o login volta ao normal.
