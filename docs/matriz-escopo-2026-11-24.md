# Matriz inicial de escopo — 24/11/2026

Diagnóstico anterior às alterações desta tarefa. Fontes: P = plano.txt; E1 = Entrega 1; A = aulas 1–6 e 9 (aula 10 somente persistência); U = pedido nesta conversa. A situação representa leitura do código, não uma certificação de execução.

## Requisitos documentados

| Requisito | Origem | Situação inicial | Pendente / limite |
|---|---|---|---|
| Conta, vínculo de propriedade, administração e autenticação | P, E1, A | Sessão, hash, isolamento e rotas administrativas | Conferir todos os fluxos e administração de componentes |
| Propriedade e arquivos KML/KMZ | P | CRUD e KML | KMZ não aceito |
| Reservatório e geometria | P, E1 | Cadastro, KML e modelo de tronco retangular | KMZ e validação com dados reais |
| Outorgas, doze demandas, comparações e histórico | P, E1 | Cadastro, cálculos diários e revisão de demandas | Cobertura integral, séries e agregação anual exigem conferência |
| Hidrômetros e leituras | P, E1 | Cadastro, leituras manuais/simuladas, totalizador e vínculo explícito | Revisar duplicidade, reinício e qualidade; equipamento real depende de protocolo |
| Estações, nível e histórico | P, E1 | Cadastro, leituras e revisão de imagem | Histórico por período e validação de campo |
| PDF da outorga e revisão | E1 | Modelo de documento, sem fluxo de upload e extração | Implementar preservação, extração, revisão e histórico; OCR depende de ferramenta e documentos reais |
| Régua por imagem | E1 | Upload, diagnóstico, calibração e confirmação humana | Reconhecimento automático e validação em fotos reais |
| Meteorologia INMET | P, E1 | Importação anual configurável e rastreio de coleta | Validação com ZIP oficial real e fonte recente |
| Balanço hídrico | E1 | Serviço de cálculo com entradas explícitas | Integração persistida para períodos compatíveis |
| Energia CEMIG | P, E1 | Tarifa manual e estimativa | Medições elétricas e conferência do enquadramento |
| Alertas e rastreabilidade | E1 | Avaliação manual e histórico | Aproximação de limite, coletas falhas e imagens pendentes |
| FastAPI, React, Postman, PostgreSQL e migrações | A, E1 | Estrutura e migrações presentes | Validar ambiente e integrações atuais |

## Pedidos e restrições desta conversa

| Requisito | Origem | Situação inicial | Pendente / limite |
|---|---|---|---|
| Seleção de propriedade no mapa após login | U | Leaflet, lista e seleção explícita | Verificar fluxo e localização real |
| Separar perda residual de evaporação, preservar ausências e proveniência | U, compatível com E1 | Parcial em serviços | Garantir em todas as rotas e interfaces |
| Não implementar Telegram, integrações oficiais sem autorização, notificações ou exportação | U | Fora do fluxo principal | Preservar restrição |
| Aplicar o visual de referência | U anterior | Relatório visual existente | Usuário explicitou que não é para redesenhar telas nesta tarefa |

## Decisões e dependências

- Fonte horária recente do INMET, formato real de PDF/outorga, protocolo físico de equipamentos e configurações tarifárias dependem de evidências e não serão presumidos.
- Nenhuma localização exata será inferida pelo centro municipal.
- A documentação existente de verificações anteriores é histórica e precisa ser atualizada com resultados efetivamente obtidos nesta tarefa.

## Resultado desta etapa

Esta tabela registra o estado após as alterações realizadas nesta sessão. Parcial indica que existem funções úteis, mas o requisito completo ainda não foi entregue.

| Requisito / origem | Situação | Arquivos principais | Dependência ou trabalho pendente |
|---|---|---|---|
| Autenticação, usuários e propriedades / P, E1 | Parcial | `backend/app/main.py`, `models.py`, `schemas.py` | Administração e todos os fluxos de componentes ainda precisam de revisão completa |
| Mapa de seleção / U | Parcial | `frontend/src/components/PropertyMapPage.jsx`, `frontend/src/map/mapUtils.js` | Verificação interativa de fluxo e tiles |
| KML/KMZ / P | Parcial | `backend/app/services/geometry.py` | KML implementado; KMZ não implementado |
| Reservatório e volume / P, E1 | Parcial | `backend/app/services/domain.py`, `models.py` | Modelo geométrico específico; calibração e geometria real dependem de levantamento |
| Outorga e limites / P, E1 | Parcial | `backend/app/services/domain.py`, `main.py` | Comparações e cobertura anual completas ainda pendentes; somas permanecem parciais |
| Hidrômetros e qualidade / P, E1, U | Parcial | `backend/app/main.py`, `models.py`, `services/domain.py`, migração `0006_nullable_interval_volume.py` | Novas leituras de linha de base/reinício têm volume desconhecido; rejeita duplicatas conflitantes e inserção histórica que invalidaria deltas posteriores. Não há fluxo de revisão para restabelecer uma sequência após reinício. Registros antigos não foram reescritos; requerem auditoria. Equipamento real requer protocolo verificado |
| Régua e estação / P, E1 | Parcial | `backend/app/services/ruler_images.py`, `main.py` | Revisão humana existente; reconhecimento automático e precisão dependem de fotos reais |
| PDF de outorga / E1 | Pendente | `backend/app/models.py` (`ManagedDocument`) | Upload, extração, revisão, histórico e OCR ainda não implementados |
| INMET / P, E1 | Parcial | `backend/app/integrations/inmet.py` | Arquivos anuais; falta validação com ZIP oficial real e fonte recente |
| Balanço hídrico / E1 | Parcial | `backend/app/services/domain.py`, `main.py` | Função isolada existe; montagem dos dados para um período completo ainda não foi implementada |
| Energia / P, E1 | Parcial | `backend/app/services/domain.py`, `main.py` | Tarifa manual e estimativa existem; medição elétrica, cálculo completo de entrada e saída e enquadramento precisam de trabalho |
| Alertas / E1, U | Parcial | `backend/app/services/alerts.py`, `main.py` | Avaliação manual agora inclui imagens pendentes; faltam aproximação de limite e falhas de coleta externa |
| Persistência / A, U | Parcial | `backend/migrations`, `backend/app/db` | PostgreSQL configurado atualizado até `0006`; não equivale à validação funcional de todos os módulos |

### Verificações desta sessão

- Backend: 47 testes passaram com duas verificações de upload de imagem desmarcadas. As duas foram tentadas separadamente e falharam na preparação por `PermissionError` ao acessar o diretório temporário do pytest; não chegaram a testar o endpoint.
- Frontend: quatro testes de utilitários do mapa passaram e a compilação de produção passou.
- PostgreSQL: `alembic upgrade head` aplicou `0006_nullable_interval_volume`; `alembic current` confirmou a revisão `head`.
- Nenhuma chamada ao vivo ao INMET ou à CEMIG foi usada nos testes. Não foram conferidos documento real de outorga, equipamento físico ou percurso completo no navegador.
