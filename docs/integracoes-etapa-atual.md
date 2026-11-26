# Integrações — estado verificado em 25/11/2026

Este documento substitui os estados antigos da [matriz](matriz-requisitos.md) e do [registro inicial](integracoes-verificacao-2026-11-25.md) quando descreve o código atual. A Entrega 1 define o balanço como **perda residual estimada** e exige entradas do mesmo intervalo. A área média deve corresponder ao reservatório; o KML representa somente o perímetro e não fornece curva cota–volume. O código continua em React/Vite: a Entrega 1 cita Next.js, mas não foi encontrada exigência expressa do professor para migração.

## Estado das integrações

| Fonte/fluxo | Estado e evidência | Unidade, fuso, qualidade, configuração e limite |
|---|---|---|
| INMET anual | Importador e testes com fixture sintética implementados; **não validado com ZIP oficial**. Não é tempo real. | Cabeçalhos, formato, unidades e timezone dependem de `INMET_CSV_SCHEMA_JSON` configurado após examinar o ZIP oficial. `9999`, `Null` e vazio permanecem ausentes. Registros do importador continuam brutos e não comprovam precipitação revisada do balanço. Não há fonte recente/operacional escolhida. |
| Comparação de hidrômetros | Intervalos explícitos, ordenação, duplicidade, unidade, atraso e elegibilidade implementados; testes sintéticos de domínio/API. | Volume em m³, vazão em m³/h, horários em UTC. Sem leitura elegível o total é `null`/insuficiente. Intervalos que atravessam dias preservam início/fim e não são distribuídos por dia; ficam marcados para revisão e não entram em totais diários. Intervalos sem início confiável não viram volume diário. |
| Vínculo hidrômetro–outorga | Histórico temporal meia-aberto `[início, fim)`, auditoria, rejeição de sobreposição, resolução por intervalo e isolamento de propriedade implementados; testes sintéticos. | O vínculo atual é apenas compatibilidade de exibição. Leituras antigas não recebem o vínculo atual. Intervalo sem cobertura histórica fica pendente. Vigências legais não podem ser alteradas após existir leitura/vínculo que dependa delas. Não foram preenchidos vínculos retroativos. |
| PDF de outorga | Upload privado, acesso por propriedade/usuário, limite de 10 MiB e 50 páginas, hash SHA-256, extração local de texto, seleção literal, estados, revisão e histórico implementados; testes com PDFs sintéticos. | Campo ausente fica `não localizado`; nenhuma inferência semântica preenche campos. Correções continuam auditadas e não alimentam demandas automaticamente. Nenhum PDF real autorizado foi usado. Nenhum arquivo é enviado a serviços externos. |
| OCR de PDF | Adaptador local configurável implementado; fixtures sintéticas verificam PDF digitalizado e ausência de ferramenta. | Requer `OCR_ENABLED=true`, Tesseract com idioma `por` instalado e Poppler `pdftoppm`; configurar `OCR_TESSERACT_COMMAND`, `OCR_PDF_RENDERER_COMMAND`, `OCR_LANGUAGES` e `OCR_TIMEOUT_SECONDS`. Neste ambiente `pdftoppm` existe e Tesseract não foi encontrado; OCR está desativado e retorna `ocr_unavailable` para páginas escaneadas. PDF vazio sem imagem retorna `no_text_found`. Não há precisão validada com documento real. |
| Leituras de nível/imagens | Leitura manual ou imagem confirmada pode ser revisada; tela do balanço lista e revisa níveis do período. Testes sintéticos. | Nível em m e horário UTC. Faixa incompatível não pode ser aprovada como válida sem correção. Sugestões de imagem não viram leituras automaticamente; não há precisão de reconhecimento comprovada com fotos reais. |
| Curva cota–volume | Cadastro de versões, aprovação com vigência, interpolação e seleção no balanço implementados; testes sintéticos de pontos, faixa, ambiguidade e isolamento. | Cota em m, volume em m³, sem extrapolação. O balanço exige uma única versão aprovada válida no mês e grava a versão usada. A área média é derivada pela variação de volume interpolado dividida pela variação de nível; nível sem variação não permite derivá-la. Correção dos pontos exige nova versão. Curva e vigência reais dependem de levantamento/responsável. |
| Balanço automático/histórico mensal | Montagem automática, histórico por propriedade/reservatório/mês, estado insuficiente, fontes e interface implementados; testes sintéticos. | Período civil `America/Sao_Paulo`, fim exclusivo em UTC. Exige chuva e cada hidrômetro ativo com intervalos revisados contínuos cobrindo o mês, vínculo histórico comprovado para cada hidrômetro de entrada, outras saídas quantificadas/revisadas, níveis revisados nos limites exatos e curva única vigente. Unidade/horário/origem e IDs dos registros são devolvidos. Lacunas, sobreposições, intervalos incompatíveis, mês aberto ou curva fora da faixa não viram zero nem total completo. O gráfico usa só `coverage=comprovada`. Avaliações manuais ficam separadas como cobertura declarada. |
| Cobertura do balanço | Cobertura é derivada da união exata dos intervalos armazenados, não de checkbox do usuário. Registros podem ser cadastrados e revisados na interface do balanço. | É necessária cobertura sem lacunas/sobreposições por cada grandeza requerida. Volumes de início/fim são leituras nos limites exatos do mês. A chuva anual importada do INMET ainda precisa ganhar intervalos e revisão apropriados; dados brutos não são considerados. Resultado: perda residual estimada pelo balanço, nunca evaporação medida. |
| Outras saídas | Evidência com valor, intervalo, unidade, origem, referência, usuário e revisão; API e UI implementadas. | m³ e horários UTC. Evidência sobreposta é rejeitada; cobertura incompleta ou não revisada não entra no cálculo. |
| Telemetria física | Envelope interno e persistência de eventos normalizados manual/de teste implementados; testes sintéticos. Entrada `equipment` segue bloqueada. | Nível em m, totalizador em m³, recebido/observado/registrado em UTC. Eventos brutos não criam medições nem corrigem totalizadores. Faltam modelo/fabricante, protocolo, mensagem real, autenticação e configuração do broker; não foi testado equipamento. |
| CEMIG/ANEEL | Consulta oficial sob demanda, seleção de classe/vigência, importação por propriedade, proveniência da linha e deduplicação implementadas; parser e rotas testados com fixture sintética. | Consulta o [conjunto de tarifas homologadas da ANEEL](https://dadosabertos.aneel.gov.br/dataset/tarifas-distribuidoras-energia-eletrica/resource/fcf2906c-7c32-4b9b-a637-054e7a5234f4) via API CKAN. Aceita apenas linhas de aplicação CEMIG, grupo B, modalidade convencional e unidade conversível publicada; usa TUSD + TE em R$/kWh antes de tributos/bandeiras. A classe da unidade consumidora precisa ser selecionada; custo estimado não reproduz fatura. Uma consulta manual à fonte terminou em `WinError 10061` antes de receber resposta; a validação real permanece pendente. Tarifa manual segue identificada como manual. |
| Alertas/coletas | Avaliação e histórico, deduplicação, resolução/reabertura e falha de coleta preservando o último dado válido; testes sintéticos. | Sem agendador. Limiares de aproximação/extrapolação seguem desligados até decisão do responsável. Falha registrada não substitui leitura existente por vazio/zero. |

## Interface e proveniência

O fluxo novo de balanço usa os estilos, campos, espaçamento e cores já presentes no Triton. Com um período selecionado, a interface permite registrar e revisar chuva e outras saídas, revisar níveis, executar o cálculo automático e inspecionar pendências/fontes. A cobertura declarada da avaliação manual não é rotulada como comprovada. As evidências usam paginação e mostram quando há mais itens. Nesta etapa, os estados repetitivos em badges de cabeçalho foram removidos, o texto de energia foi reduzido e erros de integração passaram a usar vermelho escuro. A lista de propriedades tem lápis para abrir o acordeão de edição; excluir arquiva e preserva o histórico, com restauração pela lista **Arquivadas**. Selects usam chevron explícito. Build e testes de renderização passaram; inspeção visual final em navegador não foi executada.

Os resultados automáticos retornam período, unidade, origem, horário observado, referência, IDs das leituras e ID da curva. Revisões registram usuário e momento. Registros antigos sem intervalo, autor ou vínculo temporal continuam sem esses dados, sem preenchimento retroativo.

## Migrações, API local e verificações

`0007_integration_history` permanece inalterada. `0008_proven_intervals` acrescenta os intervalos, estados de curva, vínculos temporais e evidências. A migração aditiva `0009_property_archive_tariff_source` acrescenta arquivamento e proveniência de tarifa. `alembic heads` confirmou `0009_property_archive_tariff_source` como head. `alembic upgrade 0006_nullable_interval_volume:head --sql` gerou SQL PostgreSQL offline até `0009`; isso não é aplicação nem prova de persistência PostgreSQL.

PostgreSQL nativo 18.6 está ativo em `localhost:5432`. A configuração efetiva (sem registrar credenciais) aponta para o banco `triton`, ambiente `development`; `alembic current` confirmou `0006_nullable_interval_volume`. A role conectada não tem privilégio `CREATEDB`. O catálogo contém outros bancos, mas nenhum foi confirmado como banco de teste isolado e autorizado. Não alterei nenhum banco nem apliquei migrações. `pg_isready`, `psql` e `createdb` não estão disponíveis no `PATH`. A consulta de identidade/revisão foi somente leitura. Testes da API usam SQLite em memória apenas para regras/rotas; não contam como validação PostgreSQL.

A causa do `Not Found` das rotas novas foi localizada: a API que já ocupava `127.0.0.1:8000` responde como Triton, mas seu OpenAPI não contém nenhuma das três rotas solicitadas. O processo proprietário (PID 1252) não expôs metadados acessíveis; não o encerrei. O `.env` do front-end aponta para essa porta. Para não tocar nesse processo, iniciei o código atual em `127.0.0.1:8012` e o Vite em `127.0.0.1:5175`, com sobrescritas de ambiente apenas nesses processos. A rota automática é POST; suas chamadas sem sessão retornam `401` (ou `405` no método GET), nunca `404`. As outras duas chamadas GET sem sessão retornam `401`.

```powershell
$env:CORS_ORIGINS = 'http://127.0.0.1:5175'; .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8012
```

A instância acima não executa migrações automaticamente. O front-end temporário recebeu `VITE_API_URL` como `http://127.0.0.1:8012`; confirme as rotas da API atual:

```powershell
$openapi = Invoke-RestMethod http://127.0.0.1:8012/openapi.json
$paths = $openapi.paths.PSObject.Properties.Name
$paths -contains '/reservoirs/{reservoir_id}/water-balance/monthly/automatic'
$paths -contains '/reservoirs/{reservoir_id}/water-balance/source-evidence'
$paths -contains '/hydrometers/{meter_id}/outorga-links'
```

O servidor Vite temporário usou este comando, sem editar `frontend/.env`:

```powershell
$env:VITE_API_URL = 'http://127.0.0.1:8012'
npm.cmd run dev -- --host 127.0.0.1 --port 5175 --strictPort
```

Resultado da validação local:

- Backend: a suíte anterior registrou `121 passed, 3 deselected`. Investiguei os três testes: o plugin `tmp_path` cria diretórios com modo `0o700`, inacessíveis neste sandbox Windows. Executei os três (`synthetic_permit_document_private_review_and_integrity`, `ruler_image_review_manual_confirmation_and_correction_history`, `ruler_image_upload_validation_and_property_isolation`) com fixture temporário de diretório permissivo e sem o plugin `tmpdir`: `3 passed, 26 deselected`. Assim, 124 testes distintos passaram em execuções separadas. PDFs/imagens dessas provas são sintéticos e os testes de API usam SQLite em memória. Nenhum teste chama serviços externos.
- Duas tentativas com o `tmp_path` padrão falharam ao listar diretórios que o pytest criou com permissões `0o700`. Restaram `.pytest-run-temp-20261125-2` na raiz do projeto e `%TEMP%\triton-pytest-verified-20261125`; a remoção direta também foi negada. Não alterei ACL; o diretório da raiz causa um aviso de acesso negado no `git status`.
- Front-end nesta etapa: `npm test` — `21 passed`.
- Front-end nesta etapa: `npm run build` — concluído.
- Alembic: `0009_property_archive_tariff_source` é head; SQL PostgreSQL offline gerado de `0006` a `0009`; nada foi aplicado a banco.
- API atual em `8012`: `/openapi.json` retornou HTTP 200 e as três rotas aparecem. Sem sessão, GET em `source-evidence` e `outorga-links`, e POST em `monthly/automatic`, retornaram `401`; GET na rota POST retornou `405`. `/auth/session` retornou `200` com sessão ausente. Nenhuma operação protegida de leitura/escrita foi feita no banco.
- API já existente em `8000`: OpenAPI HTTP 200, mas as três rotas novas estão ausentes. O `.env` ainda aponta para `localhost:8000`; não o alterei porque o processo proprietário não é controlado por esta sessão.
- Front-end atual em `5175`: `/`, `/src/api/client.js` e `/src/App.jsx` retornaram HTTP 200; o módulo transformado confirma `VITE_API_URL=http://127.0.0.1:8012`. Preflight CORS de `5175` para `8012` retornou HTTP 200. Não testei sessão autenticada nem operações de dados: o banco configurado ainda está na revisão `0006`.
- Fontes reais, PDFs/fotos reais, hardware/broker e banco PostgreSQL não foram usados nos testes. Testes automatizados não chamam serviços externos.

## Bloqueios reais e próximos passos

- **INMET:** fornecer um ZIP oficial anual, ano e código de estação; conferir cabeçalhos/unidades/fuso para configurar o mapeamento. A importação não é feed ao vivo.
- **OCR:** instalar Tesseract com idioma português e Poppler no host que executa a API e configurar as variáveis locais do `.env`; depois validar com PDF digitalizado autorizado. Não enviar documento a serviço externo.
- **Curva/área:** fornecer levantamento cota–volume real, unidade, pontos, data, origem/responsável e regra de validade; revisar áreas do reservatório.
- **Balanço:** fornecer leituras reais/revisadas que cubram os mesmos limites de mês, com origem, intervalos e referências. A cobertura não pode ser declarada em substituição aos registros.
- **Equipamento:** fabricante/modelo, protocolo, exemplo real de mensagem, autenticação, broker e uma decisão sobre eventos de reinício/troca do totalizador.
- **Fotos:** fotos reais identificadas com horário, estação, unidade e leituras/calibração conferidas, para validar a revisão humana.
- **PostgreSQL:** a role atual não pode criar bancos (`CREATEDB=false`) e `triton` está em `0006`. Para desbloquear, um administrador pode executar `CREATE DATABASE triton_integration_test OWNER <role_de_teste>;` e conceder DDL à role. Depois, no terminal `backend`, definir `$env:DATABASE_URL = 'postgresql+psycopg://<role>:<senha>@localhost:5432/triton_integration_test'` sem gravar a senha no histórico, executar `alembic upgrade 0006_nullable_interval_volume`, confirmar `alembic current`, executar `alembic upgrade 0009_property_archive_tariff_source` e confirmar a revisão final. Não execute as migrações com o `.env` atual apontando para `triton`.
- **CEMIG:** informar a classe/subclasse, modalidade e unidade consumidora que aparecem na conta; selecionar a linha oficial correspondente e conferir sua vigência. A fonte está conectada, mas a resposta da API oficial não foi validada nesta execução.
- **Alertas:** definir os limiares de aproximação/extrapolação antes de habilitar essas regras.

Não foi usado Docker nem Docker Compose.

## Execução adicional em 25/11/2026

Esta seção complementa os resultados acima. Nenhuma configuração de produção ou arquivo `.env` foi alterado.

### PostgreSQL nativo isolado

- Os executáveis `initdb`, `pg_ctl`, `psql` e `createdb` existem na instalação PostgreSQL 18.6. A porta temporária `55439` estava livre; o cluster foi configurado para escutar somente em `127.0.0.1`, com role e diretório próprios.
- `initdb -D %TEMP%\triton-pg-isolated-20261125-01 -U triton_cluster_admin --no-locale --encoding=UTF8 --auth-host=trust --auth-local=trust` terminou com exit code 0 e criou o cluster descartável. O executável emitiu avisos de criação de token restrito (`error code 87` e `error code 3`) antes de continuar.
- A tentativa `pg_ctl -D %TEMP%\triton-pg-isolated-20261125-01 -l ... -o '-h 127.0.0.1 -p 55439 -c listen_addresses=127.0.0.1' -w start` falhou: `could not create restricted token: error code 87` e `could not start server: error code 3`. `pg_ctl status` confirmou `no server running`, não havia `postmaster.pid` e a porta 55439 continuou sem listener. Não tentei elevar privilégios nem iniciar `postgres.exe` por outro meio.
- Removi somente o diretório de cluster criado nesta execução, após confirmar que nenhum servidor havia iniciado. Os diretórios antigos de pytest mencionados acima não foram listados, alterados ou removidos.
- Nenhuma migração, seed ou operação de API foi executada em PostgreSQL. O banco configurado `triton` permaneceu na revisão `0006_nullable_interval_volume`. A geração `alembic upgrade 0006_nullable_interval_volume:head --sql` terminou com exit code 0; isso gera SQL offline e não valida aplicação nem persistência PostgreSQL.

### API e front-end em execução

- O OpenAPI em `127.0.0.1:8012` continua contendo `/reservoirs/{reservoir_id}/water-balance/monthly/automatic`, `/reservoirs/{reservoir_id}/water-balance/source-evidence` e `/hydrometers/{meter_id}/outorga-links`. Chamadas sem sessão retornam `401`; não foram feitas operações protegidas no banco.
- O Vite em `127.0.0.1:5175` retorna `200` para `/`, `/src/api/client.js` e `/src/App.jsx`; o módulo transformado aponta para `http://127.0.0.1:8012`. A configuração local `frontend/.env` continua apontando para `http://localhost:8000`, sem alteração. O processo que já ocupa 8000 continua sem as três rotas e não foi encerrado.
- Isso confirma presença das rotas no código e conexão configurada no Vite temporário, mas não valida uma sessão autenticada, leitura/gravação de dados nem integração front-end com PostgreSQL.

### Testes e fontes

- Reexecutei os três testes antes desmarcados com um novo diretório temporário permissivo e fixture `tmp_path` temporária, sem alterar ACL: `3 passed, 26 deselected`. As provas de PDF e imagem usaram fixtures sintéticas e o fixture de API usou SQLite em memória; nenhum teste usou PostgreSQL.
- `pytest tests/test_permit_pdf_ocr.py tests/test_aneel_tariffs.py tests/test_inmet.py tests/test_balance_auto.py tests/test_balance_period.py tests/test_integration_contracts.py tests/test_temporal_permit_links.py tests/test_domain.py tests/test_alerts.py tests/test_ruler_images.py -p no:cacheprovider -p no:tmpdir -r a` terminou com `85 passed`. Esses testes usam regras/fixtures sintéticas e não chamam fontes externas.
- O OCR continua desativado: `OCR_ENABLED=false`, Tesseract não encontrado e `pdftoppm` disponível. Os testes de PDF digitalizado verificam `ocr_unavailable`, sem simular texto reconhecido.
- A busca local não encontrou ZIP oficial do INMET nos diretórios acessíveis; encontrou apenas `tests/fixtures/inmet/weather_fixture.csv`, usado como fixture. A busca reportou acesso negado a um diretório temporário antigo, que não foi inspecionado.
- Nenhuma chamada real à ANEEL/CEMIG foi feita. Os testes do catálogo usam respostas CKAN sintéticas; não há validação real de tarifa nesta execução.
- Os testes de balanço e vínculo confirmam comportamento com dados sintéticos. Nenhum período real ficou comprovado por estas execuções; cobertura declarada/manual permanece distinta de cobertura comprovada. Telemetria física segue bloqueada pelo equipamento/protocolo não confirmado.

### Bloqueio e próximo passo PostgreSQL

O impedimento desta tentativa não foi apenas `CREATEDB`: o cluster foi inicializado, mas o processo PostgreSQL nativo não iniciou porque `pg_ctl` não conseguiu criar o token restrito no sandbox. Para prosseguir sem contornar permissões, o administrador do ambiente precisa habilitar a criação desse processo por `pg_ctl` para a sessão local não elevada, ou fornecer um servidor/banco PostgreSQL separado já autorizado, com role de teste própria e permissões de DDL. Nesse servidor isolado, o comando seguro é `CREATE DATABASE triton_integration_test OWNER <role_de_teste>;`; depois, configure `DATABASE_URL` somente no processo de teste e aplique a sequência de `0006` até `0009`. Não use o `.env` atual nem migre `triton`.

Docker e Docker Compose não foram usados.

## Preparação local e revisão de migrações — 25/11/2026

### Configuração Vite/API

- Confirmei que `frontend/.env` era ignorado pelo Git e continha somente `VITE_API_URL=http://localhost:8000`; não havia outras variáveis nem credenciais nesse arquivo. Ajustei apenas essa chave para `http://127.0.0.1:8012`. `frontend/.env.example` e o fallback em `frontend/src/api/client.js` agora usam o mesmo endereço.
- A API atual já atendia em 8012 e o Vite em 5175. A instância antiga em 8000 não foi encerrada nem alterada. A configuração anterior por variável de ambiente do processo Vite já produzia um módulo apontando a 8012; o arquivo local e o fallback agora deixam esse destino persistente em novas inicializações.
- O código local servido expõe as três rotas novas no OpenAPI. Chamadas sem sessão continuam respondendo 401 (e o método incorreto 405), não 404. Isso confirma roteamento e contrato HTTP; não confirma leitura/gravação no banco, que segue em 0006.

### PostgreSQL de teste

- Não repeti `initdb` ou `pg_ctl`. A tentativa anterior foi bloqueada pelo Windows ao criar token restrito (`error code 87`); não elevei privilégios, alterei ACLs nem toquei no banco `triton`. Os diretórios temporários antigos inacessíveis foram preservados.
- Criei `backend/sql/create_integration_test_db.sql` com comandos para a role dedicada e `triton_integration_test`. A senha é definida localmente pelo administrador no pgAdmin ou com `\password triton_integration_test`; o arquivo e o Git não contêm senha.
- `backend/postgres-test.example.psd1` é o exemplo de configuração sem senha. A cópia `backend/postgres-test.local.psd1` é ignorada pelo Git; `backend/scripts/validate_postgres_test.ps1` pede a senha interativamente, valida loopback e nome exato do banco, e recusa `triton`. `backend/scripts/postgres_test_support.py` confirma a identidade PostgreSQL, insere uma fixture sintética de propriedade, reservatório, outorga, hidrômetro e leitura antes de 0007, verifica a preservação após 0009 e exige objetos/revisão esperados.
- A fixture de API pode usar a URL PostgreSQL separada por `TRITON_TEST_DATABASE_URL`; exige banco loopback `triton_integration_test` na revisão 0009 e isola cada teste numa transação revertida. Sem essa variável, o fixture continua usando SQLite em memória. O script ainda não foi executado: falta o administrador criar a role e o banco.

### Revisão técnica de 0007–0009

- As revisões são aditivas: acrescentam colunas, tabelas, índices e restrições; não removem nem reescrevem registros existentes. Revisei as dependências entre histórico/documentos (0007), vínculos temporais/evidências (0008) e arquivamento/proveniência de tarifa (0009).
- Tornei as operações de 0007–0009 condicionais quando colunas, tabelas, restrições e índices já existem. Isso atende tanto ao schema legado quanto a bancos criados pelo `0001` dinâmico com os modelos atuais, sem duplicar objetos. A geração offline assume que a revisão inicial é exatamente 0006 e inclui DDL para as alterações ainda não aplicadas.
- Verificação executada: no diretório `backend`, `alembic upgrade 0006_nullable_interval_volume:head --sql`, com URL offline apontando nominalmente para o banco de teste, terminou com código 0 e gerou DDL PostgreSQL para 0007, 0008 e 0009. `python -m py_compile` das três revisões e dos scripts de suporte também passou.
- `alembic upgrade head --sql` desde a base não é suportado pelas revisões anteriores: 0002–0004 usam reflexão do schema e a geração offline falha em `sqlalchemy.exc.NoInspectionAvailable`. Isso não é erro do DDL de 0007–0009; a faixa solicitada a partir de 0006 gera SQL. Nenhum SQL foi aplicado e nenhuma persistência PostgreSQL foi validada.

### Limites desta execução

- Vite/API foram configurados para o mesmo endereço local. Testes autenticados usando PostgreSQL e verificação ponta a ponta ainda não rodaram; a API em 8012 continua ligada à configuração local antiga (`triton`, revisão 0006) e não foi usada para operações protegidas.
- Executei no backend `python -m pytest tests/test_api.py tests/test_permit_pdf_ocr.py tests/test_aneel_tariffs.py tests/test_inmet.py tests/test_balance_auto.py tests/test_balance_period.py tests/test_integration_contracts.py tests/test_temporal_permit_links.py tests/test_domain.py tests/test_alerts.py tests/test_ruler_images.py -p no:cacheprovider -p no:tmpdir -r a --tb=short`, com uma pasta nova de fixtures dentro de `backend/.tmp`: `114 passed`. Os dados são sintéticos; o fixture da API usa SQLite em memória nesta execução. A primeira tentativa com a pasta temporária padrão teve três falhas de permissão ao gravar PDFs/imagens; repeti sem alterar ACLs, apontando os testes para a pasta temporária do workspace. As pastas antigas inacessíveis não foram removidas.
- `npm run build` no frontend terminou com código 0. A análise sintática do script PowerShell e `py_compile` dos scripts, fixture e migrações também passaram.
- O SQL offline, os testes unitários e a geração OpenAPI não comprovam aplicação de migração nem persistência PostgreSQL.
- Para desbloquear: um administrador local deve executar separadamente `CREATE ROLE triton_integration_test LOGIN;`, definir a senha localmente, depois executar `CREATE DATABASE triton_integration_test OWNER triton_integration_test;` no banco `postgres`. Em seguida copie o `.psd1` de exemplo e rode `& ./backend/scripts/validate_postgres_test.ps1` no PowerShell a partir da raiz. Não envie credenciais pelo chat.

Não usei Docker, não alterei `triton`, não elevei privilégios e não alterei ACLs.

## Correção do login local e CORS — 25/11/2026

- A captura do navegador mostrava `localhost:5173` chamando a API `127.0.0.1:8012`. O navegador bloqueava `/auth/session` e `/auth/login` porque a instância em 8012 não autorizava essa origem. A falha era CORS; as rotas existiam.
- Mantive a instância 8012 sem alterações. A tentativa de reutilizar a porta confirmou que ela já estava ocupada (bind `10048`), então iniciei o código atual em `127.0.0.1:8013`, sem migração nem operação autenticada. Essa instância permite `http://localhost:5173`, `http://127.0.0.1:5173` e `http://127.0.0.1:5175`, com credenciais.
- O processo Vite existente em 5175 mantinha `VITE_API_URL=8012` no ambiente herdado. Renomeei a configuração suportada para `VITE_API_BASE_URL` no `.env` local, exemplo e cliente; o cliente também tem fallback para 8013. O módulo servido em 5175 agora aponta para 8013. O exemplo de inicialização local no README define explicitamente o conjunto CORS correspondente.
- Verificação: OPTIONS de `/auth/session` (GET) e `/auth/login` (POST), com `Origin: http://localhost:5173` e `content-type`, retornou 200, `Access-Control-Allow-Origin` igual à origem e `Access-Control-Allow-Credentials: true`. GET `/auth/session` retornou 200 com sessão ausente e o cabeçalho correto. As três rotas de integração aparecem no OpenAPI; sem sessão, respondem 401 com o cabeçalho CORS, sem 404.
- O Vite acessível nesta sessão continua em 5175 (página e módulo 200). `localhost:5173` não estava acessível pelo terminal. Tentei iniciar o Vite nesse endereço, mas o sandbox bloqueou o subprocesso do esbuild com `spawn EPERM`; não encerrei processos nem alterei permissões. A origem 5173 está autorizada na API 8013, mas não pude validar uma página ativa nessa porta nesta sessão.
- `npm run build` após a mudança terminou com código 0. Os 114 testes backend aprovados anteriormente usam fixtures sintéticas e SQLite em memória para rotas/API; não testam o login da conta mostrada na captura nem confirmam acesso autenticado ao PostgreSQL. Não usei nem registrei as credenciais visíveis na imagem.
- O backend `.env` continua sem alteração e aponta para o banco local `triton` na revisão 0006. Nenhuma migração ou operação autenticada foi feita nele. Portanto, o CORS está corrigido para a nova instância, mas a autenticação real da conta e a persistência PostgreSQL seguem sem validação até existir o banco de teste isolado e a interface ser recarregada para usar `VITE_API_BASE_URL`.

A instância 8013 permanece em execução nesta sessão. Para uso após reiniciar, o comando Windows e as origens CORS estão documentados na seção de configuração local do README.
- A auditoria do cookie confirmou `SameSite=Lax`; o cliente agora usa `http://localhost:8013` (e não o IP 127.0.0.1) para manter página e API no mesmo site. `localhost:8013/openapi.json` e o módulo Vite em 5175 responderam 200. O preflight de `/auth/login` como POST e GET `/auth/session` funcionaram com origem `http://localhost:5173` e `Access-Control-Allow-Credentials: true.
- Executei novamente `npm run build` após a alteração final de host; terminou com código 0. O login real ainda não foi testado: as credenciais da captura não foram usadas, e não usei a conta/dados de `triton`.

## Revalidação do erro CORS do login — 25/11/2026

- A configuração local `frontend/.env` usa `VITE_API_BASE_URL=http://localhost:8013`; o cliente e o exemplo usam a mesma variável. O bundle atual do build contém `http://localhost:8013` e não contém `8012`. O `.env` local continua ignorado pelo Git e não contém credenciais.
- A API atual em `localhost:8013` respondeu `GET /health` com 200. `GET /auth/session` respondeu 200 com `authenticated:false`. Os preflights de `GET /auth/session` e `POST /auth/login`, vindos de `http://localhost:5173`, responderam 200 com `Access-Control-Allow-Origin` exato e `Access-Control-Allow-Credentials:true`.
- O OpenAPI atual inclui as três rotas de balanço automático, evidência e vínculo temporal. Chamadas sem sessão às duas rotas GET protegidas e ao POST de balanço retornaram 401 com CORS, confirmando que a instância atual não responde `Not Found` nessas rotas. Não foi feita gravação nem login autenticado no banco `triton`.
- `npm run build` terminou com código 0; `npm test` passou 21 testes. O teste `test_session_probe_is_clean_for_guests_and_logged_in_users` passou 1 teste com fixture sintética e SQLite em memória. Isso valida a lógica local da rota de sessão/login, não uma conta real nem PostgreSQL.
- A tentativa de iniciar Vite em 5173 com o carregador padrão falhou em `spawn EPERM` no esbuild; o carregador experimental também falhou ao executar `net use`. Servir o build estático em 5173 e 5175 falhou com `WinError 10013` ao vincular o socket. Não alterei permissões, ACLs ou processos alheios. O bundle e o build foram verificados, mas não pude atualizar uma página ativa no navegador nesta sessão.
- O Chrome DevTools informou que o perfil do navegador já estava em uso; não encerrei nem reabri esse navegador. A tela da captura deve ser recarregada e o Vite do terminal do usuário reiniciado caso o Network ainda mostre `127.0.0.1:8012`.
- Continua pendente confirmar o login com a conta real autorizada na interface. O backend `.env` aponta para `triton` na revisão 0006; não migrei esse banco nem usei a conta exibida na captura. A autenticação real e persistência PostgreSQL aguardam banco isolado em revisão atual e teste do usuário.
### Confirmação do bundle servido em 5173 — 25/11/2026

- Na rechecagem, `GET http://localhost:5173/` respondeu 200 e apontou para o bundle `index-DhROP5a9.js`; esse mesmo bundle foi gerado pelo build executado nesta etapa. O JavaScript servido contém `http://localhost:8013` e não contém `8012`. O módulo de origem `/src/api/client.js` retorna 404, indicando que a porta publica o build estático, não o servidor de desenvolvimento Vite.
- Uma nova tentativa de iniciar Vite em 5173 falhou porque a porta já está em uso. O proprietário não ficou visível por `Get-NetTCPConnection`; preservei o servidor e não tentei encerrá-lo. A tentativa anterior de servir Python nessa porta falhou ao vincular o socket. O build já servido é a versão atual, então a página deve ser recarregada com `Ctrl+F5` se a aba mantiver recursos em cache.
- Com a origem real `http://localhost:5173`, os preflights de sessão e login em `localhost:8013` retornam 200 com credenciais habilitadas; a sessão sem cookie retorna 200 como visitante. As rotas protegidas de integração retornam 401 sem sessão, com cabeçalho CORS, sem `404`.
- Isso resolve o endereço incorreto e o bloqueio CORS no bundle atualmente servido. O login com a conta real ainda depende de a pessoa usuária recarregar e autenticar na interface; não usei as credenciais da captura nem fiz autenticação ou gravação no banco `triton`.
## Erro ao carregar propriedades — 25/11/2026

A confirmação anterior de CORS cobria apenas respostas sem sessão e não validava o carregamento autenticado de propriedades. A consulta somente de leitura ao catálogo do PostgreSQL confirmou `0006_nullable_interval_volume` e ausência de `properties.is_archived` e `properties.archived_at`, exigidas pelo modelo atual e acrescentadas pela migração 0009. Portanto, GET e POST de propriedades podem falhar com SQLSTATE 42703; CORS mascarava o corpo do erro 500.

A API agora trata erros PostgreSQL 42703 e 42P01 como 503, com mensagem de estrutura incompatível, sem divulgar SQL ou parâmetros. O teste sintético com SQLSTATE 42703 confirmou 503 e o cabeçalho CORS; o teste existente de cadastro e isolamento também passou em SQLite (2 testes). Essa alteração só terá efeito após reiniciar a instância da API com o código atual. Não corrige o esquema do banco.

A recuperação completa segue bloqueada até validar 0006 → 0009 em PostgreSQL isolado. Nenhuma migração foi aplicada ao banco `triton`; nenhuma conta ou propriedade foi alterada nesta verificação. Para preparar o banco isolado, o administrador deve executar separadamente `CREATE ROLE triton_integration_test LOGIN;` e `CREATE DATABASE triton_integration_test OWNER triton_integration_test;`, definir a senha localmente e seguir `backend/scripts/validate_postgres_test.ps1`. A aplicação de migrações a `triton` continua proibida pela instrução do usuário.
## Correção do limite da revisão 0009

A execução informada pelo usuário no PostgreSQL de teste falhou ao registrar a revisão `0009_property_archive_tariff_source`: o campo `alembic_version.version_num` tinha limite de 32 caracteres, insuficiente para o identificador. Ajustei a migração 0009 para ampliar esse campo para `TEXT` em PostgreSQL antes de o Alembic registrar a revisão. O identificador foi preservado e a alteração não apaga registros. A revisão 0009 falhou na execução relatada; o banco de teste foi mantido para inspeção e o script verifica a revisão ao retomar.

A geração offline de `0006_nullable_interval_volume:head` terminou com código 0 e confirmou a alteração de tipo antes do registro da revisão; `py_compile` também passou. A migração corrigida ainda precisa ser executada no PostgreSQL de teste com o script e a senha digitada localmente pelo usuário. Não foi feita alteração no banco `triton`.
## Verificação após migração no banco de teste

O usuário informou que o banco de teste chegou a `0009_property_archive_tariff_source`, mas a verificação de esquema falhou com detalhe suprimido. O script agora disponibiliza `-VerifyOnly`, que consulta o estado e verifica o esquema sem executar migrações nem inserir a fixture; o verificador reúne e exibe nomes conhecidos dos objetos ausentes, sem expor mensagens do driver ou credenciais. Foi identificada uma possível diferença entre tabelas criadas pelo modelo em 0001 e as restrições esperadas por 0008; aguardamos o diagnóstico para confirmá-la. Python compilou e a sintaxe PowerShell foi verificada. A persistência e a preservação não foram declaradas validadas, e o banco `triton` não foi alterado.
## Revisão 0010: restrições de período

A verificação informada pelo usuário confirmou ausência de `ck_hydrometer_outorga_link_period` e `ck_balance_flow_evidence_period` no banco de teste em 0009. A revisão aditiva `0010_period_constraints` acrescenta as duas quando ausentes; não altera nem apaga registros. Se houver dados incompatíveis, a criação da restrição falha e a migração para, exigindo análise. Os modelos também foram alinhados para novas instalações. O script agora aceita 0009 e atualiza o banco isolado até 0010; a fixture PostgreSQL da API não força IDs de usuário que poderiam colidir com a fixture legada.

A sequência de SQL offline até 0010 e a sintaxe PowerShell passaram; 13 testes de regras e API e dois testes focados na fixture passaram com dados sintéticos, usando SQLite nas verificações da API. A aplicação da 0010, a preservação e os testes autenticados PostgreSQL aguardam execução do script pelo usuário. O banco `triton` não foi alterado.
## PostgreSQL de teste: migração 0010 aplicada

Na execução apresentada pelo usuário, o script confirmou o banco `triton_integration_test` na revisão inicial 0009 e aplicou `0010_period_constraints`. A verificação do script informou revisão 0010, 27 tabelas e leitura sintética legada preservada; as conferências de colunas, índices, restrições e chaves estrangeiras do verificador passaram. A captura foi feita antes da saída dos testes de API, portanto o resultado desses testes e a validação autenticada de persistência ainda não estão confirmados. A instalação limpa desde um banco vazio até 0010 ainda precisa ser verificada integralmente. O banco principal `triton` não foi migrado nesta etapa.
## Preparação de demonstração separada

O usuário solicitou uma conta e uma aplicação utilizável para apresentação. Foi criado `backend/scripts/start_demo_test.ps1`: usa exclusivamente `triton_integration_test` e sua role local, verifica esquema na revisão 0010, executa os testes de API em PostgreSQL, carrega os registros sintéticos existentes, compila o front-end numa pasta temporária nova e inicia API e interface próprias nas portas 8014 e 5176. Verifica preflight CORS, login e consulta de propriedades antes de informar sucesso. A senha PostgreSQL é solicitada localmente. Cookie e diretório de arquivos da demonstração são separados; nenhum processo anterior é encerrado e `.env` não é modificado.

O carregador de demonstração agora recusa outros bancos e verifica o nome real do banco e a revisão. A proteção recusou o banco `triton` sem consulta. A suíte `tests/test_api.py` passou 30 testes usando SQLite e dados sintéticos; o teste específico da carga passou após o ajuste. A sintaxe do PowerShell e a compilação Python passaram. A tentativa do build isolado nesta sessão falhou em `spawn EPERM` ao iniciar esbuild; a execução no terminal do usuário ainda precisa ser verificada. O comando completo da demonstração não foi executado aqui porque a senha da role de teste é informada apenas pelo usuário. Não houve validação de fontes externas reais, teste ponta a ponta ou escrita no banco `triton`.
## Demonstração com PostgreSQL isolado — verificação de ponta a ponta parcial

O usuário autorizou o uso da credencial da role de teste nesta sessão. O PostgreSQL `triton_integration_test` está na revisão 0010 e o verificador confirmou esquema e preservação da leitura legada. Foram corrigidos os testes que presumiam ID 1 ou representação UTC textual fixa, e o teste CORS passou a usar a origem configurada. Na importação INMET sintética, a contagem de inserções foi corrigida para contar IDs de `INSERT ... RETURNING`, pois psycopg pode retornar rowcount -1. Os 30 testes de API passaram no PostgreSQL com fixtures sintéticas; em execução posterior, 29 passaram e um foi pulado porque a conta demo persistente já existia. A execução anterior validou esse teste antes da criação persistente.

A demonstração foi iniciada em `http://localhost:5176`, com API em `http://localhost:8014` e banco isolado de teste. O build novo falhou com `spawn EPERM`; foi usada uma cópia do build existente, posterior aos arquivos de origem, com a URL da API alterada apenas na cópia. O script valida login e consulta de propriedades. Foi criada e relida uma propriedade sintética via API; as consultas autenticadas de dashboard, reservatórios, outorgas, hidrômetros, estações, meteorologia, energia, evaporação, alertas, documentos e histórico mensal retornaram 200. O HTML e o JavaScript da interface retornaram 200 e o JavaScript aponta para a API de demonstração. A inspeção do navegador não foi possível: o perfil DevTools estava em uso; a interação visual completa não foi validada.

As medições e tarifas demonstrativas são sintéticas. A execução não valida ZIP oficial INMET, tarifas por resposta real, OCR com documentos reais, fotos, equipamento nem telemetria física. O banco `triton` não foi alterado, nenhum processo preexistente foi encerrado e Docker não foi usado. A instalação limpa desde banco vazio até 0010 permanece pendente.
## Inicialização local e conservação de arquivos

A demonstração padrão deste computador pode ser aberta com `iniciar-triton.bat`; o atalho chama `iniciar-triton.ps1` e usa o PostgreSQL isolado `triton_integration_test` nas portas locais 8014 e 5176. A credencial da role foi protegida para o usuário Windows atual em arquivo ignorado pelo Git. Não foi incluída no repositório; em outro usuário Windows o inicializador solicita a senha localmente. Ao encontrar a demonstração já ativa, o inicializador confere login, propriedades e URL da interface antes de reutilizá-la. Em nova inicialização, verifica o esquema e a conta demo; reutiliza uma cópia do build existente se estiver atual ou tenta gerar novo build.

O armazenamento permanente da demonstração é `backend/private_demo_uploads`, também ignorado pelo Git. Antes de uma nova inicialização, arquivos privados de pastas de demonstração anteriores são copiados sem apagar os originais; conflitos de conteúdo interrompem a cópia. A inicialização nova em portas alternativas foi testada com a credencial protegida, banco isolado, login, consulta de propriedades e interface HTTP. A verificação visual completa pelo navegador continua pendente.

Foram removidos nove diretórios `__pycache__` acessíveis que continham somente arquivos `.pyc`. Os diretórios temporários antigos inacessíveis, os arquivos privados, a cópia da interface em uso e dados no banco foram preservados. O PostgreSQL `triton` principal não recebeu migração. As pendências de fontes reais, OCR, telemetria e validação de instalação limpa permanecem as descritas no registro.
## Alterações solicitadas após reunião — 26/11/2026

A tela de outorga passou a apresentar indicadores e gráficos de volume diário, somas semanais parciais, participação no limite mensal e médias ponderadas das vazões disponíveis. A vazão de saída é identificada como dado da propriedade e limitada às últimas leituras revisadas; o volume por outorga exige vínculo temporal. Leitura ausente não vira zero e intervalos que cruzam dias não são distribuídos. A comparação simulada de outorga deixou de ser usada no painel; a outorga demonstrativa é omitida da tela, sem excluir seu registro. Corrigida a comparação para permitir intervalos simultâneos de hidrômetros distintos.

A tela de balanço recebeu mapa com perímetro de propriedade/reservatórios e posições disponíveis de hidrômetros e estação meteorológica. Cadastro e edição de hidrômetros aceitam coordenadas em pares; a migração aditiva `0011_meter_coordinates` foi aplicada somente ao PostgreSQL `triton_integration_test` e o verificador confirmou preservação da leitura sintética legada. O banco principal `triton` continua sem migração. O texto de interpretação foi simplificado e os botões secundários tornaram-se preenchidos. O acesso à lista de propriedades arquivadas foi removido da interface, sem apagar os dados arquivados.

A leitura assistida por imagem foi removida da interface; as quatro operações de envio/sugestão/calibração/confirmação respondem 410 e não são mais gerados novos alertas para essa regra. O histórico anterior e os acessos de consulta legados são preservados, assim como a leitura manual de nível.

Validações: `npm run build` passou; `npm test` passou 21 testes. Testes sintéticos de API, domínio e vínculos temporais no PostgreSQL de teste: 59 passaram e 1 foi pulado por já existir a conta demo persistente; o teste da carga demo foi executado separadamente em SQLite e passou. A interface atual foi iniciada em `http://localhost:5179`, API 8017; login, dashboard, geometria e meteorologia responderam pela API. A ferramenta de inspeção visual de navegador não ficou disponível (pipe ausente/perfil em uso), portanto a validação visual responsiva e dos tiles ainda precisa ser feita. Fontes externas e equipamentos reais continuam sem validação. O inicializador padrão foi ajustado para as novas portas sem encerrar os processos que já estavam em execução.
## Página de uso hídrico e painel na evaporação

O banner ilustrativo da tela de evaporação foi substituído pelo acompanhamento de outorga, mantendo o resultado de perda residual estimada em uma faixa compacta e preservando o mapa e o histórico. A seção Monitoramento recebeu a página Uso hídrico, com seleção de outorga, resumo, gráficos diários e semanais, limite mensal, vazões e histórico anual. Na ausência de outorga real cadastrada, o painel apresenta estados vazios e a ação de cadastro; a outorga sintética continua preservada e não é apresentada como dado real. Cobrança pelo uso da água permanece indisponível até haver fonte e critérios definidos.

Foi acrescentada a consulta autenticada `GET /outorgas/{id}/usage/annual`, com volumes mensais de leituras elegíveis e cobertura incompleta; meses sem dados não são convertidos em zero. Uma fixture sintética verificou lacunas, leitura vinculada e revisada, ano futuro e isolamento entre usuários, tanto em SQLite quanto no PostgreSQL isolado. `npm test`: 23 passaram; `npm run build`: passou. A aplicação foi iniciada em `http://localhost:5180` e API `localhost:8018`; login, página, bundle e consulta anual retornaram sucesso. O atalho padrão usa as novas portas e preserva os processos existentes. A inspeção visual e responsiva no navegador segue pendente porque o canal nativo do computador estava indisponível. Fontes reais, equipamentos, curvas e critérios de cobrança continuam pendentes de validação.

## Ajustes de apresentação e unidades

O estado vazio de outorga deixa de ser mostrado quando o formulário de cadastro está aberto; a ação de tentar novamente no bloco de erro usa vermelho escuro. A perda residual apresentada no resumo, gráfico mensal e avaliações usa agora m³ para o intervalo informado, preservando o estado de insuficiência e as avaliações declaradas. O painel de uso mostra espaços para gráficos mesmo sem outorga/leituras, sem gerar barras ou valores fictícios. A outorga demonstrativa anteriormente ocultada permanece preservada no banco e não é tratada como dado real.

`npm test` passou 24 testes e o build passou. O bundle atualizado foi publicado apenas na cópia local da interface em `http://localhost:5180`, usando a API `localhost:8018`; ambas responderam e o navegador foi solicitado para esse endereço. As instâncias antigas em outras portas permanecem sem alteração. A inspeção visual automatizada e as integrações com fontes reais continuam pendentes.