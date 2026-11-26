# Sistema Triton

Aplicação web para acompanhar propriedades rurais, reservatórios, outorgas, hidrômetros e dados de nível, meteorologia, energia e alertas. O front-end usa React/Vite, a API usa FastAPI e os dados persistem em PostgreSQL. Leituras e estimativas mantêm origem e qualidade identificadas; quando faltam dados compatíveis, o sistema informa essa limitação.

Para começar a integração, consulte a [revisão da Entrega 1](docs/revisao-entrega-1.md), o [guia de preparação para integração](docs/preparacao-integracao.md) e a [referência visual](docs/referencia-visual-abacatepay.md). A matriz de requisitos também está em [docs/matriz-requisitos.md](docs/matriz-requisitos.md).

O [registro da etapa atual](docs/integracoes-etapa-atual.md) apresenta o estado das integrações, testes sintéticos e limites da verificação em PostgreSQL. O [registro anterior](docs/integracoes-verificacao-2026-11-25.md) conserva a evidência histórica. A revisão mais recente é `0011_meter_coordinates`, aplicada ao banco isolado de teste; o banco principal `triton` não foi migrado.

## Fontes consultadas e decisões

- O PDF da Entrega 1 está na raiz do repositório. A matriz de requisitos e as decisões de implementação estão em [docs/matriz-requisitos.md](docs/matriz-requisitos.md) e [docs/matriz-escopo-2026-11-24.md](docs/matriz-escopo-2026-11-24.md).
- A Entrega 1 descreve FastAPI, React, coleta INMET/CEMIG, documentos de outorga, leituras e estimativas de energia e perdas. Ela destaca que o balanço é residual, ET₀ não é evaporação de água livre e estimativas dependem das premissas e da qualidade dos registros.
- O importador INMET anual permanece sem validação com ZIP oficial e não é fonte ao vivo. A consulta de tarifas de aplicação CEMIG foi conectada ao conjunto oficial da ANEEL por solicitação do usuário; o parser e as rotas foram testados apenas com fixtures sintéticas, sem consulta real automatizada durante os testes. A telemetria física segue bloqueada pelo protocolo do equipamento. O PDF tem upload privado, extração local de texto, seleção de trechos e revisão; há um adaptador OCR local configurável, mas o Tesseract não está instalado/configurado neste ambiente. Documentos reais ainda não foram validados.
- O modelo de reservatório assume paredes planas e planta retangular com laterais lineares. KML é validado e armazenado, mas o perímetro não determina a curva cota–volume. KMZ não é extraído.
- Comparações de hidrômetro preservam o início e fim das leituras. Intervalos que cruzam dias entram como evidência mensal, mas ficam sem atribuição diária; sem leituras elegíveis o volume é ausente, não zero. Sobra de um dia não compensa excesso de outro.
- O balanço mensal tem montagem automática condicionada à cobertura verificada nos intervalos revisados, aos limites exatos das leituras de nível e a uma curva cota–volume aprovada. Avaliações manuais seguem separadas e exibem cobertura declarada. Nenhum resultado é uma medição de evaporação.

## Fluxos de integração desta etapa

- Curvas: `POST/GET /reservoirs/{id}/stage-volume-curves` cria e consulta versões; `POST /stage-volume-curves/{id}/approve` registra vigência; `GET /stage-volume-curves/{id}/volume?level=...&at=AAAA-MM-DD` interpola somente dentro da faixa e validade aprovada.
- Documentos: `POST/GET /properties/{id}/permit-documents`, arquivo privado em `GET /permit-documents/{id}/file`, seleção literal de trecho em `POST /permit-documents/{id}/extract` e revisão/aprovação em `POST /permit-documents/{id}/review`. Campos revisados não alimentam demandas. OCR local requer `OCR_ENABLED=true`, Tesseract e `pdftoppm`; não há envio externo.
- Balanço: `GET /properties/{id}/water-balance/monthly?year=AAAA` expõe o estado automático por mês; `POST /reservoirs/{id}/water-balance/monthly/automatic` salva uma avaliação automática, inclusive quando insuficiente. `GET /reservoirs/{id}/water-balance/source-evidence` lista chuva, níveis e outras saídas com paginação para revisar. A avaliação manual em `POST /reservoirs/{id}/water-balance/monthly` permanece identificada como declarada.
- Telemetria: `POST /telemetry/normalized` persiste somente origem manual/de teste como evento bruto; não integra equipamentos nem alimenta cálculos. `GET /properties/{id}/telemetry/normalized` lista eventos. O equipamento físico continua desabilitado.
- Tarifas: na aba **Energia**, **Consultar tarifas oficiais** busca registros de aplicação da CEMIG no conjunto público de tarifas homologadas da [ANEEL](https://dadosabertos.aneel.gov.br/dataset/tarifas-distribuidoras-energia-eletrica/resource/fcf2906c-7c32-4b9b-a637-054e7a5234f4). O usuário escolhe classe e vigência antes de importar para a propriedade. O cálculo usa TUSD + TE convertidos para R$/kWh quando a unidade publicada é compatível; não inclui tributos, bandeiras nem reproduz a fatura. Também é possível cadastrar a tarifa da conta como origem manual. O custo permanece uma estimativa separada da cobrança pelo uso da água. A consulta real não foi validada por teste automatizado.
- Hidrômetros e outorgas possuem edição, estado ativo/inativo e histórico; não há exclusão física. Vínculos por intervalo são registrados em `/hydrometers/{id}/outorga-links`, sem aplicar o vínculo atual a leituras anteriores; intervalos sem vínculo comprovado ficam pendentes. Após existir vínculo histórico, a vigência legal da outorga não pode ser editada. Eventos de totalizador são registros manuais e não recalculam leituras.
- O painel de outorga mostra os dias com leituras elegíveis, somas semanais parciais, limite e médias das vazões informadas. A saída é identificada como dado da propriedade, sem vínculo presumido com a outorga; lacunas não são zero. Hidrômetros aceitam coordenadas opcionais e aparecem no mapa do balanço com a estação meteorológica e os perímetros KML disponíveis.
- A página **Uso hídrico** e a seção de evaporação exibem o acompanhamento da outorga. `GET /outorgas/{id}/usage/annual?year=AAAA` apresenta os volumes mensais elegíveis como parciais; meses sem leitura permanecem ausentes. A cobrança pelo uso da água continua indisponível até haver fonte e critérios definidos.
- A leitura assistida por imagem foi descontinuada: a interface não a oferece e as operações de envio e revisão retornam `410`. As imagens, revisões e leituras já registradas permanecem preservadas; a leitura direta de nível continua disponível.
- Propriedades: **Excluir propriedade** arquiva o cadastro, preservando leituras, documentos, vínculos e revisões. A lista **Arquivadas** permite restauração; as ações de arquivar/restaurar ficam registradas no histórico.
- Alertas são avaliados sob demanda; `GET /properties/{id}/alert-evaluations` lista avaliações. A última falha de coleta é sinalizada sem substituir observações anteriores. Não há agendador.

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
$env:CORS_ORIGINS = 'http://localhost:5173,http://127.0.0.1:5173,http://127.0.0.1:5175'
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8013 --reload
```

Em outro terminal:

```powershell
Set-Location frontend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm ci
npm run dev
```

Abra `http://localhost:5173`; documentação da API em `http://localhost:8013/docs` e verificação em `http://localhost:8013/health`. O front-end usa `VITE_API_BASE_URL` de `frontend/.env`; o padrão e o exemplo apontam para `http://localhost:8013`. A URL mantém a API no mesmo site do front-end, para que a sessão `SameSite=Lax` seja enviada pelo navegador. A API local permite as origens Vite indicadas no comando acima. A configuração local existente foi conferida e contém somente a URL; o arquivo continua ignorado pelo Git.

Não execute `alembic upgrade head` contra `backend/.env` sem confirmar o banco de destino. Neste repositório, esse arquivo local aponta para `triton`, que está na revisão `0006`; não o use para esta validação. Para preparar um banco isolado de integração, siga [Validar PostgreSQL de teste](#validar-postgresql-de-teste-windows) e use o script fornecido.

## Linux/macOS com PostgreSQL instalado

```bash
test -f backend/.env || cp backend/.env.example backend/.env
python3 -m venv backend/.venv
. backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
cd backend
export CORS_ORIGINS='http://localhost:5173,http://127.0.0.1:5173'
uvicorn app.main:app --host 127.0.0.1 --port 8013 --reload
```

Em outro terminal:

```bash
cd frontend
test -f .env || cp .env.example .env
npm ci
npm run dev
```

Antes da migração, confirme que o serviço PostgreSQL está ativo, que o banco/role indicados em `DATABASE_URL` são um banco separado para testes e que o role pode criar tabelas. `alembic upgrade head` aplica as migrações no PostgreSQL configurado; a inicialização da API não cria nem apaga tabelas. Não use o comando contra banco principal sem confirmar o destino.

Configure `DATABASE_URL`, `SECRET_KEY`, `CORS_ORIGINS` e `COOKIE_SECURE` nos arquivos `.env`. O segredo de desenvolvimento do exemplo deve ser trocado em qualquer ambiente compartilhado; em produção, configure `COOKIE_SECURE=true` sob HTTPS. A aplicação não cria nem apaga tabelas ao iniciar. Mudanças futuras devem ser novas revisões Alembic.

## Validar PostgreSQL de teste (Windows)

Um administrador deve conectar ao banco administrativo `postgres` e executar as instruções de `backend/sql/create_integration_test_db.sql`. Crie a role e o banco em comandos separados; `CREATE DATABASE` não pode ser executado dentro de transação. Defina a senha da role localmente pelo pgAdmin ou pelo prompt interativo do `psql` (`\password triton_integration_test`); não grave senha no repositório nem a envie pelo chat.

Depois, copie `backend/postgres-test.example.psd1` para `backend/postgres-test.local.psd1` e ajuste somente host, porta, banco e nome da role. A cópia local é ignorada pelo Git; o script solicita a senha sem ecoá-la. A partir da raiz:

~~~powershell
& ./backend/scripts/validate_postgres_test.ps1
~~~

O script aceita apenas `triton_integration_test` em loopback, recusa `triton`, confere a identidade do servidor, migra um banco novo até `0006`, insere fixtures sintéticas legadas e segue até `0011`. Em seguida verifica esquema e preservação dos registros e executa `tests/test_api.py` usando PostgreSQL, com transação externa revertida por teste e sem limpar o banco. Estados/revisões inesperados são recusados.

## Conta e dados demonstrativos

Crie uma conta pela tela inicial. O CPF é validado e armazenado cifrado; a API devolve somente a versão mascarada. Senhas são armazenadas com Argon2id. A sessão usa cookie HttpOnly, SameSite=Lax e expiração em 12 horas. Para criar a primeira conta administrativa, rode `python scripts/create_admin.py` em `backend`; o comando solicita os dados sem deixar senha padrão e permite promover uma conta existente sem mudar sua senha.

Para abrir a versão local de apresentação neste computador, dê dois cliques em **iniciar-triton.bat** na raiz do projeto. Ela usa o PostgreSQL local `triton_integration_test`, abre `http://localhost:5180` e mantém os dados da demonstração. É necessário que o serviço PostgreSQL esteja em execução. A senha da role fica protegida para o usuário Windows atual em `backend/postgres-test.secret`, ignorado pelo Git; se esse arquivo não existir, o comando pede a senha ao iniciar. Em outro computador ou usuário Windows, prepare o banco de teste e informe a senha localmente.

Login de apresentação: `demo@example.com` / `Triton-Demo-2026!`. Essa conta e seus dados são sintéticos. Documentos e imagens novos ficam em `backend/private_demo_uploads`, fora do Git; arquivos privados de demonstrações anteriores são copiados para essa pasta sem sobrescrever conteúdo diferente. Preserve essa pasta junto com o banco ao fazer backup.

Para executar novamente a validação da API em PostgreSQL antes de iniciar, execute na raiz do projeto:

```powershell
& .\backend\scripts\start_demo_test.ps1
```

O script pede a senha da role de teste localmente, verifica o esquema, executa os testes de API em PostgreSQL, carrega dados sintéticos e abre a interface em `http://localhost:5180`, com API em `localhost:8018`. Login: `demo@example.com` / `Triton-Demo-2026!`. A tarifa e as medições são exemplos sintéticos; integrações externas não são validadas por esta carga. A demonstração usa cookie e arquivos privados separados. A conta existente não é substituída; nenhum processo preexistente é encerrado. O banco `triton` e os arquivos `.env` não são alterados.

O inicializador normal reutiliza um build existente somente quando ele é mais recente que os arquivos de origem; caso contrário tenta gerar um novo. A URL da API é ajustada somente na cópia destinada à demonstração. Se a compilação falhar com `spawn EPERM`, será necessário resolver a permissão de execução do esbuild no ambiente antes de iniciar com código de front-end modificado.

## Rotas principais

- `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`
- `GET/POST /properties`, `GET/PATCH /properties/{id}`
- `GET/POST /properties/{id}/reservoirs`, `GET /reservoirs/{id}`
- `GET/POST /outorgas`, `GET /outorgas/{id}/monthly-demands`, `PATCH /outorgas/{id}/monthly-demands/{month}`
- `GET/POST /hydrometers`, `POST /hydrometers/{id}/readings`, `GET/POST /hydrometers/{id}/outorga-links`, `POST /hydrometer-outorga-links/{link_id}/close`, `POST /hydrometer-readings/{id}/review`
- `GET/POST /level-stations`, `POST /level-stations/{id}/readings`
- `POST/GET /level-stations/{id}/image-reviews`, `GET /level-image-reviews/{id}`, `GET /level-image-reviews/{id}/image`, `POST /level-image-reviews/{id}/suggestion|calibrate|confirm`, `GET /level-image-reviews/{id}/history`
- `PUT /properties/{id}/meteorology/station`, `GET /properties/{id}/meteorology`, `POST /properties/{id}/meteorology/sync`
- `POST /energy/tariffs`, `GET /energy/estimate/{property_id}`, `GET /evaporation/estimate/{property_id}`
- `GET /dashboard/{property_id}`, `GET /alerts/{property_id}`
- `POST /alerts/{property_id}/evaluate`, `POST /alerts/{alert_id}/resolve`
- `GET /properties/{id}/water-balance/monthly`, `POST /reservoirs/{id}/water-balance/monthly/automatic`, `GET /reservoirs/{id}/water-balance/source-evidence`
- `POST /properties/{id}/rainfall-intervals`, `POST /meteorological-observations/{id}/review`, `POST /level-readings/{id}/review`
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
INMET_CSV_SCHEMA_JSON={"encoding":"<codificacao do arquivo>","delimiter":"<separador de um caractere>","header_row":0,"source_timezone":"<fuso IANA confirmado>","station_code_column":"<cabecalho exato do codigo>","date_column":"<cabecalho exato da data>","time_column":"<cabecalho exato da hora>","date_format":"<formato observado da data>","time_format":"<formato observado da hora>","decimal_separator":"<. ou ,>","thousands_separator":"","variables":{"temperature_air":{"column":"<cabecalho exato da temperatura>","unit":"<unidade do arquivo>"},"relative_humidity":{"column":"<cabecalho exato da umidade>","unit":"<unidade do arquivo>"},"wind_speed":{"column":"<cabecalho exato da velocidade do vento>","unit":"<unidade do arquivo>"},"wind_direction":{"column":"<cabecalho exato da direcao do vento>","unit":"<unidade do arquivo>"},"precipitation":{"column":"<cabecalho exato da precipitacao>","unit":"<unidade do arquivo>"},"solar_radiation":{"column":"<cabecalho exato da radiacao, se disponivel>","unit":"<unidade do arquivo>"}}}
```

Se o CSV mostrar data e hora em uma coluna única, substitua `date_column`, `time_column`, `date_format` e `time_format` por `datetime_column` e `datetime_format` com os nomes e formato observados. Configure um modo só. A interpretação de horário segue a documentação do INMET e é armazenada em UTC.

As cinco variáveis centrais são temperatura, umidade relativa, velocidade/direção do vento e precipitação; radiação solar é opcional se a fonte daquele arquivo não a oferecer. Índice UV e lux não são usados como substitutos. Configure manualmente o código e o nome para exibição na página **Meteorologia** de cada propriedade. O nome/localização são rótulos informados pelo usuário; só a correspondência exata do código no arquivo confirma que aquele arquivo contém registros para a estação. O Triton não procura nem seleciona estação vizinha.

Depois de conferir e salvar o mapeamento, reinicie a API e use **Sincronizar arquivo oficial**. A chamada é manual, usa timeout, uma tentativa limitada de repetição, limites configuráveis de 512 MiB para o ZIP e 4 GiB descomprimidos (`INMET_MAX_ARCHIVE_BYTES` e `INMET_MAX_UNCOMPRESSED_BYTES`) e cache local de uma hora; não ocorre na inicialização. Registros são associados à propriedade e estação, idempotentes por estação/variável/horário, e marcados `raw_unvalidated`. Horário e valor ausentes são omitidos, nunca convertidos em zero. Cabeçalho ou resposta incompatíveis registram uma execução com falha, não importam parte do arquivo e preservam os registros já gravados. O estado da página distingue erro, ausência de observações e atualização anterior. `is_valid` indica que o registro passou pelo parsing estrutural; não significa validação meteorológica ou oficial do sensor.

Os dados INMET aparecem somente na página meteorológica nesta etapa. Eles não alimentam o balanço hídrico, evaporação ou estimativas de energia. Coletas externas reais não foram executadas nesta entrega; as verificações usam apenas o arquivo de fixture sintético `backend/tests/fixtures/inmet/weather_fixture.csv`. A disponibilidade e o contrato binário/CSV do ZIP precisam ser conferidos no ambiente que configurará a integração.

## Experiência de edição e tarifas

Na visão inicial, o ícone de lápis de cada propriedade abre diretamente o acordeão **Editar dados da propriedade**. A ação **Excluir propriedade** arquiva e confirma antes de ocultar o cadastro; dados associados permanecem preservados e podem ser restaurados em **Arquivadas**. Os selects do sistema usam um chevron consistente. Estados informativos repetitivos foram retirados dos cabeçalhos; erros de integração permanecem visíveis em vermelho escuro com uma ação de recuperação quando disponível.

A CEMIG não oferece uma única tarifa que sirva a todas as unidades. O fluxo oficial consulta registros da ANEEL sob demanda e requer que a pessoa selecione a classe/modalidade e a vigência correspondentes à própria unidade consumidora. A [página de tarifas vigentes da CEMIG](https://www.cemig.com.br/valores-e-tarifas/tarifas-vigentes/) é referência para conferência. Nenhum valor oficial foi validado com resposta real do endpoint nesta etapa.

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

Os testes de domínio cobrem intervalos, ausência de leitura, duplicidade, vínculos temporais, cobertura automática, curva, PDF e isolamento. O fixture de `tests/test_api.py` usa um SQLite **em memória**, isolado por execução; isso não valida o driver Psycopg, as migrações Alembic nem a persistência PostgreSQL. As evidências e limitações atuais estão em [docs/integracoes-etapa-atual.md](docs/integracoes-etapa-atual.md).

## Imagens da régua linimétrica

Na aba **Estação / nível**, envie uma fotografia vinculada à estação e ao horário observado. O Triton valida assinatura/formato real (PNG, JPEG ou WebP estático), decodificação, limite de tamanho e pixels, preserva os bytes originais em `MEDIA_STORAGE_DIRECTORY` e serve a pré-visualização somente por rota autenticada. O diretório padrão relativo à pasta `backend` é `backend/private_uploads`, independentemente do diretório atual do processo; mantenha-o fora de hospedagem estática. Configure `RULER_IMAGE_MAX_BYTES` e `RULER_IMAGE_MAX_PIXELS` para os limites da implantação.

Cada foto começa como **inconclusiva**. OpenCV/Canny avalia contornos como diagnóstico, mas não afirma identificar sozinho a escala ou a linha d'água. Na interface, marque duas graduações legíveis e informe os valores conhecidos em metros para aquela foto; marque também a linha d'água. A interpolação só é aceita entre as duas referências e dentro da faixa da estação. Se a foto não ajudar, informe manualmente a leitura, que continua pendente. Confirme explicitamente para gravar a leitura com origem `imagem_revisada`; o sistema guarda ator, horário, método, sugestão, confirmação e histórico de revisões. Uma correção reabre a medição como inconclusiva até ser confirmada novamente. O balanço/evaporação não consome uma sugestão ou revisão pendente.

Instale as dependências por `python -m pip install -r requirements.txt` dentro do ambiente virtual do backend. O OCR usa programas locais: `OCR_ENABLED=true`, Tesseract e Poppler `pdftoppm`; sem ambos, a extração de PDF digitalizado retorna `ocr_unavailable`. Os testes usam PDFs e medições sintéticos, não evidências de leitura real. A validação com fotos e documentos autorizados permanece necessária.

No Postman, faça login, envie uma foto de teste em `POST /level-stations/{station_id}/image-reviews`, confira a imagem e use calibração/sugestão/confirmação separadamente. Os valores da coleção para coordenadas e metros são exemplos de requisição e devem ser substituídos por marcas verificadas na foto; nenhum valor de exemplo é leitura de campo.

## Próximos marcos

1. Incluir cobertura diária explícita, eventos de operação, alertas de aproximação configuráveis e execução agendada da avaliação.
2. Validar o mapeamento de variáveis/unidades do INMET contra um ZIP histórico oficial no ambiente habilitado, sem exibir fixtures como clima real.
3. Instalar/configurar OCR local caso seja necessário processar PDFs digitalizados; campos continuam pendentes de revisão humana.
4. Validar a consulta CEMIG em execução autorizada, conferir a classe/modalidade da unidade consumidora e confirmar a vigência antes de usar tarifas importadas; custo estimado não é uma reprodução da fatura.
5. Ampliar CRUD administrativo, KMZ/armazenamento privado, testes PostgreSQL e percurso visual desktop/mobile no ambiente completo.

## Diagnóstico do login local

Se o console ainda mostrar chamadas para `127.0.0.1:8012`, reinicie o servidor Vite iniciado no seu terminal para carregar o cliente atualizado. Confirme no Network que `/auth/session` e `/auth/login` vão para `http://localhost:8013`; mantenha `localhost` como host da página e da API para a sessão por cookie.
Depois de atualizar a configuração, faça uma recarga forçada da página (`Ctrl+F5`). Se o Network continuar apontando para `8012`, o servidor que atende a porta `5173` ainda publica um bundle antigo; reinicie somente esse servidor pelo terminal que o iniciou.
