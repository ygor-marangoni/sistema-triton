# Integrações e verificação — 25/11/2026

**Registro histórico.** A etapa posterior está descrita em [integrações da etapa atual](integracoes-etapa-atual.md); as situações abaixo registram o início, não o resultado mais recente.

Este registro distingue implementação, testes sintéticos e evidência real. A Entrega 1 disponível é o PDF na raiz. `plano.txt`, slides do professor e ZIP oficial do INMET não foram encontrados nos arquivos acessíveis do repositório; documentos em diretórios sem permissão não puderam ser inspecionados. A matriz histórica cita uma consulta anterior à `Aula 10.pdf`, mas o arquivo não estava disponível para nova conferência nesta sessão. A Entrega 1 propõe Next.js, enquanto o código usa React/Vite; também propõe extração de PDF e coleta CEMIG que ainda não existem. Ela define o balanço residual, não uma medição direta de evaporação, e exige levantamento para a relação cota–volume.

| Fonte | Estado e evidência | Unidades, tempo, ausências e dependências |
|---|---|---|
| INMET anual | Adaptador e testes com ZIP/CSV sintéticos; **não validado com arquivo oficial**. Coleta é solicitada manualmente. | Cabeçalhos, unidades e timezone IANA são configuráveis, não confirmados. Horário sem offset exige `source_timezone`; instantes ambíguos são rejeitados. `9999`, `Null` e vazio são ausências, não zero. Faltam identificação do lote em cada observação, valores originais e contagens completas de linhas. Fonte recente separada não implementada. |
| Hidrômetros | Cadastro, leituras manuais/simuladas, proteção parcial contra duplicidade e totalizador; auditoria indicativa de registros anteriores. Testes sintéticos; sem equipamento real. | m³ e m³/h; instantes com fuso normalizados para UTC. Reinício é sinalizado sem volume inferido. Histórico de vínculo, revisão de reinício e receptor físico ainda não existem. Contrato interno isolado não recebe mensagens nem persiste dados. Faltam modelo, protocolo, exemplos, autenticação e broker, se houver. |
| Estação / imagens | Leituras e revisão humana de imagens disponíveis; testes usam imagens geradas. | Nível em m; captura e registro em UTC na gravação. Leituras fora da faixa são preservadas como inconsistentes. Não há validação de precisão automática com fotos reais. Precisam ser adicionados usuário em leituras comuns, idempotência de nível e cobertura de consultas mais ampla. |
| PDF de outorga | Apenas modelo de documento e revisão de demandas cadastradas manualmente; upload, armazenamento, extração, OCR e aprovação documental **não implementados**. | Não há OCR configurado ou validação de documentos. É necessário implementar fluxo privado e testá-lo com PDF real autorizado; campo ausente não pode ser inferido. |
| Balanço hídrico | Fórmula isolada testada com valores sintéticos. API para propriedade real retorna dados insuficientes; demonstração tem dados sintéticos. | m², dias, mm e m³. Falta persistência e montagem para intervalo completo, comprovação de cobertura, verificação de unidades e origens e histórico mensal real. Não interpretar como evaporação medida. |
| Curva cota–volume | Interpolador isolado testado com pontos sintéticos, sem extrapolação. | m e m³. Não há cadastro, versão, origem ou conexão com cálculos. KML é perímetro, não curva; geometria simplificada é estimativa a validar em campo. |
| CEMIG / energia | Cadastro manual de tarifa e estimativa existem; testes sintéticos. Coleta oficial e medição elétrica não implementadas ou validadas. | R$/kWh, com vigência e localidade cadastradas; estimativa de operação possui cobertura incompleta e não reproduz fatura. Falta responsável pelo cadastro e fonte oficial validada. Cobrança de água é separada. |
| Alertas | Avaliação manual, deduplicação e resolução/reabertura existentes; testes sintéticos. | Sem agendador ou coleta automática. Não há regra de aproximação arbitrária. Faltam trilha completa de avaliações e alertas para falhas de coleta; limiares precisam ser definidos. |

## Consultas e preservação

`GET /level-stations/{id}/readings` e `GET /hydrometers/{id}/readings` aceitam `start` inclusivo e `end` exclusivo, com offset, além de `skip` e `limit`. A propriedade é autorizada por meio do reservatório. `GET /hydrometers/{id}/totalizer-audit` sinaliza divergências de sequência sem modificar dados; não comprova que os intervalos ou vínculos históricos são corretos. A exclusão administrativa de propriedade está desativada para impedir exclusões em cascata; ainda não existe inativação. Cadastros editáveis e auditados de hidrômetros e outorgas, histórico dos vínculos, agregações diárias/mensais/anuais e paginação integral da interface permanecem pendentes.

O carregamento das seções usa resultados independentes, com erro por dependência; dados de uma propriedade anterior não são reutilizados. A contagem de alertas do resumo indica o limite da primeira página quando alcançado. A listagem de propriedades ainda é limitada pela API e não tem navegação por todas as páginas.

## Verificações locais

- Serviço PostgreSQL 18 ativo; conexão à base configurada bem-sucedida. A conta configurada não possui `CREATEDB`. `alembic current` leu `0006_nullable_interval_volume (head)`; não houve migração nem teste de escrita nesta sessão. Nenhuma migração nova foi criada para alterações que não modificam o esquema.
- Testes de API usam SQLite em memória e não validam PostgreSQL. Para executar as duas verificações de upload neste ambiente foi necessário substituir temporariamente a fixture `tmp_path`, pois o diretório padrão criado pelo pytest recebeu `PermissionError`; a fixture alternativa cria diretórios sob `backend/.tmp` e não contata serviços externos.
- Backend: `python -m pytest -q -p no:cacheprovider` inicialmente apresentou 2 erros na preparação de diretório temporário. Com a fixture alternativa descrita abaixo, `python -m pytest -q -p triton_temp_plugin -p no:cacheprovider` passou: **80 testes**, com um aviso de depreciação do Starlette/AnyIO. Os testes da API exercitam SQLite em memória, nunca PostgreSQL.
- Frontend: `npm test` passou **20 testes** e `npm run build` concluiu. `git diff --check` concluiu sem erros de whitespace (Git avisou sobre conversão futura de finais de linha).
- Não se usou ZIP oficial, PDF real de outorga, foto real, equipamento, CEMIG ou serviço remoto. O PDF da Entrega 1 foi lido como requisito, não usado como fixture de importação de outorga.
- Consulte o README para instalar PostgreSQL nativamente e configurar o ambiente. Para validar migrações, crie um **banco de teste separado**, execute `alembic upgrade head` apontando `DATABASE_URL` somente para ele, e exercite persistência e permissões; não use nem substitua a base atual.

Para reproduzir a alternativa temporária usada nesta máquina, a partir de `backend`, crie `.tmp/triton_temp_plugin.py` com o código abaixo, aponte `PYTHONPATH` para a pasta `.tmp` e rode o comando indicado acima. Os diretórios resultantes são de teste e contêm imagens sintéticas.

```python
from pathlib import Path
from uuid import uuid4
import pytest

@pytest.fixture
def tmp_path():
    path = Path.cwd() / '.tmp' / ('triton-image-test-' + uuid4().hex)
    path.mkdir(parents=True)
    return path
```

```powershell
$env:PYTHONPATH = (Resolve-Path '.tmp').Path
.\.venv\Scripts\python.exe -m pytest -q -p triton_temp_plugin -p no:cacheprovider
```

## Itens necessários para validação em campo

Arquivo anual oficial e estação/ano; PDF de outorga autorizado e exemplos para revisão; fotos reais identificadas com leituras conferidas e calibração; fabricante/modelo dos dispositivos, protocolo, mensagens, autenticação e eventual broker; curva cota–volume ou levantamento e área superficial do reservatório; medições de fluxos, precipitação e cobertura dos intervalos; enquadramento e vigência tarifários; limiares de alertas e banco PostgreSQL de teste separado. Materiais não substituem a implementação ainda pendente acima.
