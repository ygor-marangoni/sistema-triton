# Entrega 1: revisão para integração

Revisão do documento `entrega 1 sistema triton.pdf`, páginas 1 a 13, confrontada com os módulos do projeto. O documento descreve um planejamento; a tabela indica o que o código oferece atualmente, sem considerar os exemplos da conta de demonstração como integrações concluídas.

| Frente prevista na Entrega 1 | Estado atual | Próxima etapa para a equipe |
| --- | --- | --- |
| FastAPI, React, PostgreSQL, autenticação e separação por propriedade | Implementados em `backend/app` e `frontend/src`; migrações em `backend/migrations`. | Validar a instalação e as migrações no ambiente de cada desenvolvedor; estabelecer rotina de backup. A interface usa React com Vite, não Next.js. |
| Reservatórios, geometria, nível e hidrômetros | Cadastros e leituras manuais ou simuladas; modelo geométrico retangular com paredes planas. | Validar as hipóteses de geometria em campo e a vinculação dos equipamentos. O KML não fornece, sozinho, a relação cota–volume. KMZ ainda não é aceito. |
| Limites mensais, comparação de captação e alertas | Cadastro de demandas, vínculo explícito e comparação com cobertura identificada; avaliação de alertas manual. | Completar as agregações e cobertura dos períodos e validar os limites com documentos reais; agendamento automático ainda não foi implementado. |
| Meteorologia do INMET | Importação histórica anual configurável e consulta; estação deve ser informada. | Conferir mapeamento e unidades contra ZIP oficial real e implementar fonte recente caso seja necessária. Não é coleta em tempo real. |
| Tarifa CEMIG e custo energético | Tarifa manual e estimativa quando existem dados compatíveis. | Implementar e validar coleta oficial, vigência, enquadramento e eventual medição elétrica. Não reproduz a fatura completa. |
| PDF de outorga | Cadastro manual de campos e limites; extração não disponível. | Receber e preservar PDF, extrair campos e tabelas, revisar os resultados e manter histórico; OCR depende do documento. |
| Imagem da régua | Upload, preservação e fluxo assistido de calibração, revisão e confirmação humana. | Desenvolver e validar o reconhecimento automático com imagens reais e OpenCV; resultados inconclusivos exigem revisão. |
| Telemetria de hidrômetros | Leituras manuais e simuladas identificadas; tratamento de totalizadores. | Definir protocolo e autenticação com o equipamento físico antes de implementar recepção. HTTP ou MQTT dependem do dispositivo. |
| Balanço hídrico e histórico | Função de cálculo existente; a demonstração apresenta uma série sintética identificada. | Montar e persistir resultados reais com entradas, saídas, chuva e variação de volume compatíveis para o mesmo período. A conta comum não recebe a série demonstrativa. |
| Rastreabilidade e qualidade | Registros distinguem origem e horários em vários fluxos; a revisão de imagens preserva o original. | Completar histórico de correções e validação para cada coletor; testar falhas e dados incompletos com fixtures e fontes reais. |

As regras e limitações para integração e o contrato do gráfico estão em [preparacao-integracao.md](preparacao-integracao.md). O cenário simulado é restrito à conta `demo@example.com` e aos ambientes de desenvolvimento, local ou teste; uma conta comum não recebe os dados demonstrativos. Não há transmissão automática à ANA, ao IGAM ou ao MIRA.
