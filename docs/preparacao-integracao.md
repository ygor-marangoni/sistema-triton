# Preparação para a integração do Sistema Triton

Esta revisão registra o estado do repositório e os pontos que ainda precisam de implementação ou validação antes de conectar fontes externas. Os exemplos e a conta de demonstração são sintéticos; não representam medições, outorgas ou tarifas reais.

## O que já está disponível

- FastAPI, autenticação por sessão, PostgreSQL e associação de dados às propriedades autorizadas.
- Cadastro de propriedade, reservatório, estação de nível, hidrômetro, outorga e tarifa manual. Leituras manuais e simuladas são identificadas pela origem, com horários observados e de recebimento.
- Estações podem ser editadas e, se não tiverem leituras ou imagens, excluídas. O backend bloqueia alterações de faixa ou exclusão quando há histórico.
- A comparação de outorga mantém as sobras diárias separadas e informa cobertura incompleta. Tarifas manuais são distintas de eventual cobrança pelo uso da água.
- A revisão de fotos mantém o original, exige calibração ou leitura manual e confirmação humana; não é leitura automática validada de campo.

## Pendências para os dados externos

| Área | Situação e trabalho restante |
| --- | --- |
| INMET | Existe importação sob demanda de ZIP anual histórico, mas o mapeamento precisa ser conferido com arquivo oficial real. Não é coleta horária recente e ainda não alimenta o balanço. |
| CEMIG | Há cadastro manual; falta implementar e validar coleta oficial, vigência e enquadramento da unidade consumidora. A estimativa atual não reproduz toda a fatura. |
| Telemetria | Não há receptor de equipamentos verificado nem broker MQTT configurado. É necessário conhecer o protocolo real, autenticar o dispositivo, associá-lo explicitamente à propriedade e testar duplicidade, atrasos e totalizador. |
| Balanço hídrico | A função de cálculo existe, mas `/evaporation/estimate/{property_id}` ainda entrega dados insuficientes: faltam entradas compatíveis por reservatório e intervalo, cobertura e persistência de resultados. Não há série mensal real. |
| Série de perda residual | O gráfico da interface aguarda `history` no resultado do balanço. Cada item deve conter `reservoir_id`, `period_start`, `period_end`, `status`, `coverage`, `origin` e `loss_residual_mm_day`; só meses calendários completos de um mesmo reservatório com `status` igual a `perda residual estimada pelo balanço hídrico`, `coverage` igual a `completa` e `origin` em `manual`, `medida`, `simulada` ou `mista` são exibidos. A origem identifica os dados usados no cálculo, que continua sendo estimado. Os dados precisam ser calculados e rastreáveis, não preenchidos pelo scraper. Valores ausentes, inválidos, negativos ou meses duplicados não viram zero. A API atual ainda não fornece esse histórico. |
| Documentos de outorga | Upload do PDF original, extração/OCR, revisão e histórico de correções não estão implementados. Não ativar dados extraídos sem conferência. |
| Alertas e coleta | A avaliação atual é acionada manualmente. Agendamento, monitoramento de falhas e eventual notificação dependem de implementação e configuração próprias. |
| Manutenção de cadastros | A estação tem edição/exclusão protegidas. Hidrômetros e outorgas ainda não têm edição/exclusão completas; qualquer implementação deve preservar vínculos, leituras, documentos e revisões. |
| Resiliência da interface | O carregamento do painel da propriedade usa requisições em conjunto: a falha de uma delas ainda impede a exibição do conjunto. Avaliar carregamento parcial com estados de erro separados, sem apresentar dados ausentes como zero. A listagem de alertas possui limite da API e o resumo não deve ser interpretado como contagem global quando houver mais registros que o limite. |

Para cada fonte, preservar origem, equipamento/estação, unidade, instante observado, instante coletado, estado de qualidade e histórico das correções. Não substituir medições ausentes por zero, nem estimativas por medições reais. Não transmitir dados para órgãos externos sem uma integração específica e seus requisitos verificados.

## Dados de demonstração locais

A conta `demo@example.com` usa registros sintéticos em uma conta separada no banco local atualmente configurado. Sua posição no mapa e o perímetro do reservatório são fictícios, independentes e identificados como demonstração; não representam imóveis reais. A outorga, a tarifa, o alerta e as leituras também são exemplos. Para propriedades pertencentes a essa conta, somente em ambiente local/de desenvolvimento/teste, a API também gera meteorologia simulada, seis balanços mensais e uma comparação de outorga sintética até a data atual. Esta comparação é independente das leituras salvas; essas respostas não são coletas oficiais nem são persistidas como medições. As outras contas continuam usando os fluxos reais e seus respectivos estados de configuração. O script `backend/scripts/load_demo.py` também pode ser usado em um banco local de demonstração separado, conforme o README, sem substituir uma conta existente.

## Validação antes de conectar

1. Reiniciar a API para carregar as rotas atuais e verificar `/health` e `/docs`; aplicar migrações existentes ao banco escolhido quando necessário.
2. Testar cada adaptador com fixtures identificadas, incluindo respostas incompletas, repetidas, inválidas e indisponibilidade. Validar contra material oficial ou equipamento real antes de ativar coleta.
3. Confirmar isolamento por usuário/propriedade e vínculo explícito do equipamento antes de persistir registros.
4. Definir os intervalos, a cobertura e as unidades antes de produzir resultados do balanço; só publicar séries com dados suficientes e premissas verificáveis.
