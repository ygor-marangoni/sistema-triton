# Sistema Triton

Aplicação web para acompanhar propriedades rurais, reservatórios, outorgas, hidrômetros e dados de nível, meteorologia, energia e alertas. O front-end usa React/Vite, a API usa FastAPI e os dados persistem em PostgreSQL. Leituras e estimativas mantêm origem e qualidade identificadas; quando faltam dados compatíveis, o sistema informa essa limitação.

Para começar a integração, consulte a [revisão da Entrega 1](docs/revisao-entrega-1.md), o [guia de preparação para integração](docs/preparacao-integracao.md) e a [referência visual](docs/referencia-visual-abacatepay.md). A matriz de requisitos também está em [docs/matriz-requisitos.md](docs/matriz-requisitos.md).

## Fontes consultadas e decisões

- O PDF da Entrega 1 está na raiz do repositório. A matriz de requisitos e as decisões de implementação estão em [docs/matriz-requisitos.md](docs/matriz-requisitos.md) e [docs/matriz-escopo-2026-11-24.md](docs/matriz-escopo-2026-11-24.md).
- A Entrega 1 descreve FastAPI, React, coleta INMET/CEMIG, documentos de outorga, leituras e estimativas de energia e perdas. Ela destaca que o balanço é residual, ET₀ não é evaporação de água livre e estimativas dependem das premissas e da qualidade dos registros.
- A integração meteorológica ao vivo permanece sem validação de ZIP oficial; tarifa CEMIG automática, PDF/OCR e telemetria física não estão implementados. Fotos da régua têm agora fluxo assistido e aguardam calibração e confirmação humanas. A tarifa cadastrada é manual e a energia é estimada somente quando há dados compatíveis.
- O modelo de reservatório assume paredes planas e planta retangular com laterais lineares. KML é validado e armazenado, mas o perímetro não determina a curva cota–volume. KMZ não é extraído.
- Leituras não têm registro de cobertura diária contínua; por isso a comparação de outorga sempre informa cobertura incompleta. Sobra de um dia não compensa excesso de outro; após os dias de operação autorizados, todo volume do dia adicional conta como extrapolado.

## Pré-requisitos

- Python 3.11 ou 3.12
- Node.js 20.19+ (ou 22.12+)
- PostgreSQL 16/17 instalado diretamente no Windows e em execução.
- pgAdmin 4 (incluído no instalador PostgreSQL do Windows) ou outro cliente PostgreSQL para criar usuário e banco.

## Configurar PostgreSQL local pelo pgAdmin (Windows)

Instale o PostgreSQL para Windows, definindo a senha do usuário administrador `postgres` e a porta durante a instalação. Guarde essa senha. O pgAdmin é o cliente de administração; a API conecta ao serviço PostgreSQL, normalmente em `localhost:5432`.

No PowerShell, consulte o nome e o estado do serviço instalado:

```powershell
Get-Service -Name '*postgres*' | Select-Object Name, DisplayName, Status
```

Se o estado for `Stopped`, abra `services.msc`, encontre o serviço PostgreSQL e clique em **Iniciar**. Alternativamente, em um PowerShell aberto como administrador, execute `Start-Service -Name 'NOME_DO_SERVICO'`, substituindo pelo nome exibido no comando anterior. Se a lista estiver vazia, confira a instalação e o registro do serviço. Para iniciar junto com o Windows, configure o tipo de inicialização como **Automático** nas propriedades do serviço.

No pgAdmin, conecte-se ao servidor local como administrador (normalmente `postgres`) e abra o **Query Tool** conectado ao banco `postgres`. Execute esta instrução:

```sql
CREATE ROLE triton WITH LOGIN PASSWORD 'triton_dev';
```

Se o role `triton` já existir, não repita o `CREATE ROLE`; atualize a senha, se necessário, com `ALTER ROLE triton WITH LOGIN PASSWORD 'triton_dev';`.

Em uma execução separada do Query Tool, crie o banco:

```sql
CREATE DATABASE triton OWNER triton;
```

Se o banco já existir, mantenha-o e ajuste `DATABASE_URL` em `backend/.env` para os dados reais da sua instalação. A URL usada pelo projeto tem o formato SQLAlchemy `postgresql+psycopg://usuario:senha@host:porta/banco`; o driver é Psycopg 3, instalado pelo pacote `psycopg[binary]` em `backend/requirements.txt`.

## Subir pela primeira vez (Windows PowerShell, sem Docker)

Na raiz do repositório:

```powershell
if (!(Test-Path backend\.env)) { Copy-Item backend\.env.example backend\.env }
python -m venv backend/.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
Set-Location backend
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload
```

Em outro terminal:

```powershell
Set-Location frontend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm ci
npm run dev
```

Abra `http://localhost:5173`; documentação da API em `http://localhost:8000/docs` e verificação em `http://localhost:8000/health`.

## Linux/macOS com PostgreSQL instalado

```bash
test -f backend/.env || cp backend/.env.example backend/.env
python3 -m venv backend/.venv
. backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend && alembic upgrade head
uvicorn app.main:app --reload
```

Em outro terminal:

```bash
cd frontend
test -f .env || cp .env.example .env
npm ci
npm run dev
```

Antes da migração, confirme que o serviço PostgreSQL está ativo, que o banco/role indicados em `DATABASE_URL` existem e que o role pode criar tabelas. `alembic upgrade head` aplica as migrações no PostgreSQL configurado; a inicialização da API não cria nem apaga tabelas.

Configure `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS` e `COOKIE_SECURE` nos arquivos `.env`. O segredo de desenvolvimento do exemplo deve ser trocado em qualquer ambiente compartilhado; em produção, configure `COOKIE_SECURE=true` sob HTTPS. A aplicação não cria nem apaga tabelas ao iniciar. Mudanças futuras devem ser novas revisões Alembic.

## Conta e dados demonstrativos

Crie uma conta pela tela inicial. O CPF é validado e armazenado cifrado; a API devolve somente a versão mascarada. Senhas são armazenadas com Argon2id. A sessão usa cookie HttpOnly, SameSite=Lax e expiração em 12 horas. Para criar a primeira conta administrativa, rode `python scripts/create_admin.py` em `backend`; o comando solicita os dados sem deixar senha padrão e permite promover uma conta existente sem mudar sua senha.

Para manter dados sintéticos separados do banco principal, crie no pgAdmin, conectado ao banco `postgres`, um banco de demonstração com o mesmo proprietário já criado:

```sql
CREATE DATABASE triton_demo OWNER triton;
```

Se ele já existir, mantenha os dados existentes. Em um terminal PowerShell, a partir da raiz do projeto, selecione temporariamente esse banco para a migração e para o script. Ajuste a senha e a porta se forem diferentes das usadas no exemplo:

```powershell
Set-Location backend
$env:DATABASE_URL = 'postgresql+psycopg://triton:triton_dev@localhost:5432/triton_demo'
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe scripts/load_demo.py
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Conta criada: `demo@example.com` / `Triton-Demo-2026!`. Use essas credenciais somente no banco local de demonstração. A tarifa é fictícia e marcada como manual; os registros são de demonstração. O carregador recusa `APP_ENV` fora de `development`, `local` ou `test`, não substitui registros existentes e não roda junto com a aplicação. A variável de banco definida acima vale somente para aquele terminal. Para voltar ao banco principal, encerre a API e execute `Remove-Item Env:DATABASE_URL` nesse terminal, ou abra outro terminal; a API voltará a ler `backend/.env`.

## Rotas principais

- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `GET/POST /properties`, `GET/PATCH /properties/{id}`
- `GET/POST /properties/{id}/reservoirs`, `GET /reservoirs/{id}`
- `GET/POST /outorgas`, `GET /outorgas/{id}/monthly-demands`, `PATCH /outorgas/{id}/monthly-demands/{month}`
- `GET/POST /hydrometers`, `POST /hydrometers/{id}/readings`, `PATCH /hydrometers/{id}/outorga/{outorga_id}`
- `GET/POST /level-stations`, `POST /level-stations/{id}/readings`
- `POST/GET /level-stations/{id}/image-reviews`, `GET /level-image-reviews/{id}`, `GET /level-image-reviews/{id}/image`, `POST /level-image-reviews/{id}/suggestion|calibrate|confirm`, `GET /level-image-reviews/{id}/history`
- `PUT /properties/{id}/meteorology/station`, `GET /properties/{id}/meteorology`, `POST /properties/{id}/meteorology/sync`
- `POST /energy/tariffs`, `GET /energy/estimate/{property_id}`, `GET /evaporation/estimate/{property_id}`
- `GET /dashboard/{property_id}`, `GET /alerts/{property_id}`
- `POST /alerts/{property_id}/evaluate`, `POST /alerts/{alert_id}/resolve`
- `GET /reservoirs/{reservoir_id}/map-geometry` (perímetro privado do reservatório, com autorização)

Rotas de recursos exigem sessão. Usuário comum só vê a propriedade própria; IDs de outra pessoa retornam 404. Admin pode manter contas e cadastrar propriedade para um usuário pela API. Hidrômetro de entrada sem vínculo ou fora da vigência conserva a leitura como pendente. Medidores de saída não são comparados à outorga. A avaliação de alertas é explícita pela interface/API; `ALERT_STALE_AFTER_HOURS` configura a idade para apontar equipamento sem leitura. Alertas mostram dados registrados, não uma confirmação de conformidade oficial.

## Mapa de propriedades

Depois do login, **Início** é a página inicial: o mapa e a lista de propriedades ficam juntos nessa área, sem uma entrada de mapa separada na navegação. O usuário escolhe o marcador, confere uma prévia e seleciona **Abrir painel**. O Triton não seleciona automaticamente a primeira propriedade. A página usa Leaflet e os tiles públicos `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, com atribuição visível a OpenStreetMap contributors. A URL pode ser alterada em `frontend/.env` por `VITE_OSM_TILE_URL`. O serviço público do OpenStreetMap tem regras de uso e disponibilidade próprias e não oferece garantia para produção; a aplicação não pré-carrega tiles nem oferece modo offline.

Latitude e longitude são campos próprios e opcionais da propriedade, em graus decimais (até seis casas). Preencha ambas com coordenadas conferidas; cidade, coordenadas da outorga e perímetro do reservatório não são usados como substitutos. A tela mostra propriedades sem posição em **Localização pendente**. Selecionar uma delas abre a prévia e permite entrar no painel mesmo sem coordenadas; definir a posição é uma ação separada, pelo botão correspondente, digitando os valores ou clicando no mapa. A API valida faixa e par de coordenadas e aplica o isolamento da propriedade autenticada. Se houver reservatório cadastrado, seu perímetro KML pode ser ligado como camada separada, identificado como reservatório.

No `.env.example` do front-end, `VITE_OSM_TILE_URL` aponta para o padrão HTTPS do OSM. Se a camada base estiver indisponível, a aplicação mantém a lista, os filtros e as posições pendentes utilizáveis. Em telas pequenas, a lista pode ser aberta ou recolhida abaixo do mapa.

O painel da propriedade resume a última leitura observada, a atividade recente, alertas registrados e comparações de outorga somente quando há dias com medições elegíveis. Um mês sem leitura aparece como ausência de volume medido; não é exibido como consumo zero. O estado inicial orienta o cadastro de reservatório, estação e outorga sem preencher campos com medições inventadas.

## Integração meteorológica INMET

A implementação consulta, no servidor, o arquivo ZIP anual publicado pelo próprio INMET (`https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip`). Essa escolha usa o catálogo oficial de dados históricos; não raspa a página dinâmica nem depende de um endpoint interno sem contrato público. É uma importação histórica sob demanda, não um feed em tempo real; a página de serviço em tempo real informa atualização horária para os últimos 90 dias, mas não publica ali um esquema técnico de API consumível pelo Triton. O serviço oficial informa que os dados automáticos são horários, disponibiliza os arquivos históricos e explica que horários estão em UTC, que marcadores como `9999`, `Null` e campos vazios representam ausência e que observações automáticas são dados brutos sem validação de consistência ([estações automáticas](https://portal.inmet.gov.br/servicos/esta%C3%A7%C3%B5es-autom%C3%A1ticas), [acesso e qualidade dos dados](https://portal.inmet.gov.br/noticias/saiba-como-acessar-os-dados-meteorol%C3%B3gicos-dispon%C3%ADveis-no-site-do-inmet), [arquivos históricos](https://portal.inmet.gov.br/dadoshistoricos/)). A página do catálogo de estações do INMET também pode ajudar a identificar o código a ser informado ([catálogo](https://portal.inmet.gov.br/paginas/catalogoaut)).

O INMET não publica nessa documentação um contrato estável de cabeçalhos/unidades dos ZIPs. Por isso, a integração fica desabilitada até que a equipe confira um ZIP oficial e preencha `INMET_CSV_SCHEMA_JSON` no `backend/.env`. Não copie nomes de coluna ou unidades de um exemplo sintético: configure os valores exatamente como aparecem no arquivo da estação/ano escolhido. Exemplo de formato (todos os textos entre `<...>` são marcadores que precisam ser substituídos):

```text
INMET_CSV_SCHEMA_JSON={"encoding":"<codificacao do arquivo>","delimiter":"<separador de um caractere>","header_row":0,"station_code_column":"<cabecalho exato do codigo>","date_column":"<cabecalho exato da data>","time_column":"<cabecalho exato da hora>","date_format":"<formato observado da data>","time_format":"<formato observado da hora>","decimal_separator":"<. ou ,>","thousands_separator":"","variables":{"temperature_air":{"column":"<cabecalho exato da temperatura>","unit":"<unidade do arquivo>"},"relative_humidity":{"column":"<cabecalho exato da umidade>","unit":"<unidade do arquivo>"},"wind_speed":{"column":"<cabecalho exato da velocidade do vento>","unit":"<unidade do arquivo>"},"wind_direction":{"column":"<cabecalho exato da direcao do vento>","unit":"<unidade do arquivo>"},"precipitation":{"column":"<cabecalho exato da precipitacao>","unit":"<unidade do arquivo>"},"solar_radiation":{"column":"<cabecalho exato da radiacao, se disponivel>","unit":"<unidade do arquivo>"}}}
```

Se o CSV mostrar data e hora em uma coluna única, substitua `date_column`, `time_column`, `date_format` e `time_format` por `datetime_column` e `datetime_format` com os nomes e formato observados. Configure um modo só. A interpretação de horário segue a documentação do INMET e é armazenada em UTC.

As cinco variáveis centrais são temperatura, umidade relativa, velocidade/direção do vento e precipitação; radiação solar é opcional se a fonte daquele arquivo não a oferecer. Índice UV e lux não são usados como substitutos. Configure manualmente o código e o nome para exibição na página **Meteorologia** de cada propriedade. O nome/localização são rótulos informados pelo usuário; só a correspondência exata do código no arquivo confirma que aquele arquivo contém registros para a estação. O Triton não procura nem seleciona estação vizinha.

Depois de conferir e salvar o mapeamento, reinicie a API e use **Sincronizar arquivo oficial**. A chamada é manual, usa timeout, uma tentativa limitada de repetição, limites configuráveis de 512 MiB para o ZIP e 4 GiB descomprimidos (`INMET_MAX_ARCHIVE_BYTES` e `INMET_MAX_UNCOMPRESSED_BYTES`) e cache local de uma hora; não ocorre na inicialização. Registros são associados à propriedade e estação, idempotentes por estação/variável/horário, e marcados `raw_unvalidated`. Horário e valor ausentes são omitidos, nunca convertidos em zero. Cabeçalho ou resposta incompatíveis registram uma execução com falha, não importam parte do arquivo e preservam os registros já gravados. O estado da página distingue erro, ausência de observações e atualização anterior. `is_valid` indica que o registro passou pelo parsing estrutural; não significa validação meteorológica ou oficial do sensor.

Os dados INMET aparecem somente na página meteorológica nesta etapa. Eles não alimentam o balanço hídrico, evaporação ou estimativas de energia. Coletas externas reais não foram executadas nesta entrega; as verificações usam apenas o arquivo de fixture sintético `backend/tests/fixtures/inmet/weather_fixture.csv`. A disponibilidade e o contrato binário/CSV do ZIP precisam ser conferidos no ambiente que configurará a integração.

Importe `postman/Sistema-Triton.postman_collection.json` no Postman. Use `POST /auth/login` primeiro e habilite o cookie jar. A coleção salva os IDs de propriedade, reservatório, outorga, hidrômetro e estação criados; todos os valores são sintéticos.

## Verificações locais

Com as dependências instaladas, no PowerShell e na raiz do projeto:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests
```

Em `frontend`:

```bash
npm run build
npm test
```

Os testes de domínio cobrem volumes vazio/intermediário/total, sobra diária sem compensação, excesso de dias, KML, alertas e dados insuficientes. O fixture de `tests/test_api.py` usa um SQLite **em memória**, isolado por execução; ele testa rotas, sessão e isolamento sem alterar seu PostgreSQL local. Isso não valida o driver Psycopg, as migrações Alembic nem a persistência PostgreSQL. Para essas verificações, mantenha o PostgreSQL iniciado, execute `alembic upgrade head` e teste a API contra ele. As limitações conhecidas das integrações estão em [docs/preparacao-integracao.md](docs/preparacao-integracao.md).

## Imagens da régua linimétrica

Na aba **Estação / nível**, envie uma fotografia vinculada à estação e ao horário observado. O Triton valida assinatura/formato real (PNG, JPEG ou WebP estático), decodificação, limite de tamanho e pixels, preserva os bytes originais em `MEDIA_STORAGE_DIRECTORY` e serve a pré-visualização somente por rota autenticada. O diretório padrão relativo à pasta `backend` é `backend/private_uploads`, independentemente do diretório atual do processo; mantenha-o fora de hospedagem estática. Configure `RULER_IMAGE_MAX_BYTES` e `RULER_IMAGE_MAX_PIXELS` para os limites da implantação.

Cada foto começa como **inconclusiva**. OpenCV/Canny avalia contornos como diagnóstico, mas não afirma identificar sozinho a escala ou a linha d'água. Na interface, marque duas graduações legíveis e informe os valores conhecidos em metros para aquela foto; marque também a linha d'água. A interpolação só é aceita entre as duas referências e dentro da faixa da estação. Se a foto não ajudar, informe manualmente a leitura, que continua pendente. Confirme explicitamente para gravar a leitura com origem `imagem_revisada`; o sistema guarda ator, horário, método, sugestão, confirmação e histórico de revisões. Uma correção reabre a medição como inconclusiva até ser confirmada novamente. O balanço/evaporação não consome uma sugestão ou revisão pendente.

Instale as novas dependências por `python -m pip install -r requirements.txt` dentro do ambiente virtual do backend: `python-multipart` para upload FastAPI, Pillow para validação/decodificação e OpenCV headless para análise de contornos sem dependência de GUI. O caminho completo API + migração depende de FastAPI/SQLAlchemy/Alembic e PostgreSQL; nesta máquina os testes HTTP e a migração ainda não puderam rodar. Os testes unitários offline usam imagens sintéticas geradas em memória, sem evidências de medição real. A validação com fotos de campo e a revisão humana permanecem necessárias.

No Postman, faça login, envie uma foto de teste em `POST /level-stations/{station_id}/image-reviews`, confira a imagem e use calibração/sugestão/confirmação separadamente. Os valores da coleção para coordenadas e metros são exemplos de requisição e devem ser substituídos por marcas verificadas na foto; nenhum valor de exemplo é leitura de campo.

## Próximos marcos

1. Incluir cobertura diária explícita, eventos de operação, alertas de aproximação configuráveis e execução agendada da avaliação.
2. Validar o mapeamento de variáveis/unidades do INMET contra um ZIP histórico oficial no ambiente habilitado, sem exibir fixtures como clima real.
3. Implementar PDF de outorga com armazenamento privado, extração, conferência humana e histórico antes de ativar campos extraídos.
4. Avaliar a coleta CEMIG somente após confirmar fonte, período de vigência e dados da unidade consumidora; depois habilitar telemetria se houver dispositivo/protocolo.
5. Ampliar CRUD administrativo, KMZ/armazenamento privado, testes PostgreSQL e percurso visual desktop/mobile no ambiente completo.
