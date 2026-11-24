# Referência visual: AbacatePay

## Objetivo

Este documento analisa as telas de referência da AbacatePay enviadas na conversa e transforma seus padrões visuais em orientações para uma futura reformulação tela a tela do Sistema Triton.

A referência deve orientar **composição, hierarquia, espaçamento, densidade, componentes e tratamento de dados**. A paleta e a tipografia do Triton permanecem como estão: a intenção não é copiar a identidade verde-limão da AbacatePay.

## Escopo e precisão

A análise se baseia somente nas capturas de tela fornecidas (dashboard, navegação, produto, clientes, plugins, roadmap, financeiro, saques, perfil e estados de sucesso). As imagens não dão acesso ao arquivo de design, ao CSS, aos nomes oficiais das fontes ou aos tokens da AbacatePay.

Por isso:

- Medidas e cores atribuídas à referência são **estimativas visuais**, úteis como proporção e direção, não como especificação oficial.
- A família exata da fonte e dos ícones da AbacatePay não pode ser confirmada pelas imagens.
- As capturas não mostram uma tela de mapa. A seção de mapa abaixo descreve uma adaptação coerente com a linguagem visual observada e com o mapa já existente no Triton.
- Há capturas em diferentes escalas e recortes; medidas em pixels são aproximadas e pensadas para desktop largo.

## Leitura geral da linguagem visual

A interface combina uma navegação lateral persistente com uma área de trabalho ampla, clara e modular. Ela usa bastante espaço em branco, texto azul-petróleo escuro, bordas frias discretas, cartões brancos e um verde-limão intenso para indicar foco, progresso ou ação principal.

A organização é densa em dados, mas evita a aparência de uma tabela contínua: métricas ficam em grupos, gráficos têm seus próprios contêineres e áreas administrativas são divididas em seções reconhecíveis. A decoração aparece em pontos de destaque — principalmente nas ilustrações 3D — e não substitui as informações nem compete com os controles.

### Princípios visuais observados

1. **Uma navegação constante:** o menu lateral mantém a orientação entre áreas do produto.
2. **Hierarquia por escala e posição:** nome da página, título da seção, rótulos e valores têm níveis fáceis de distinguir.
3. **Superfícies simples:** branco, cinza azulado muito claro, borda fina e sombra contida.
4. **Cor forte reservada:** o verde mais vivo destaca seleção, ação, resultado positivo e séries de dados.
5. **Dados agrupados por leitura:** resumo primeiro, detalhamento depois; gráficos e tabelas seguem essa mesma sequência.
6. **Controles compactos e arredondados:** filtros, seletores e ações ocupam pouco espaço sem ficarem apertados.
7. **Ilustração como acento:** objetos 3D aparecem em locais específicos, como indicadores de faturamento, saque e conclusão de onboarding.

## Estrutura do aplicativo

### Navegação lateral

Nas capturas de desktop, a barra lateral aberta ocupa aproximadamente **250–260 px**. Ela tem fundo branco, marca no topo, seletor da empresa/loja logo abaixo e navegação vertical agrupada por área.

- **Marca e seletor:** ficam no topo, alinhados à mesma margem. O seletor tem aparência de controle, com ícone em uma pequena caixa, nome e chevrons.
- **Item selecionado:** retângulo verde claro e saturado, altura aproximada de 44 px, raio de 8–10 px, ícone e texto escuros.
- **Itens inativos:** fundo transparente, texto azul acinzentado, ícone de contorno e chevron quando o grupo expande.
- **Grupos:** seções como “Sua Loja”, “Financeiro” e “Integração” podem ser expandidas. Os subitens ficam recuados e mantêm o mesmo alinhamento de ícones.
- **Rodapé:** elementos secundários, suporte e perfil permanecem próximos à base da barra. A separação por uma linha fina cria um fechamento visual.
- **Recolhida:** a referência também mostra navegação em modo estreito, com os ícones centralizados e os rótulos ocultos. O menu continua reconhecível pela ordem e pelos símbolos.

O seletor aberto (imagem 2) usa um popover branco sobreposto ao conteúdo, com borda leve, cantos arredondados, sombra perceptível e divisores entre a loja atual e as ações de convidar/criar. A lista não altera a estrutura da navegação ao redor.

### Cabeçalho e área de trabalho

O cabeçalho superior é baixo, com breadcrumb ou nome da tela à esquerda e ações globais à direita (tema e notificações nas capturas). Ele usa o mesmo plano claro da área principal, sem uma barra colorida pesada.

No dashboard, o conteúdo fica dentro de uma grande superfície branca, recuada em relação ao fundo cinza-azulado da aplicação. O painel tem cantos bem amplos — em torno de 28–34 px na captura — e padding interno de aproximadamente 24 px. Essa camada externa separa a navegação global do espaço de trabalho da página.

Em outras telas, a superfície branca pode ocupar quase toda a largura útil. O título permanece próximo ao topo, com as ações da página alinhadas à direita, como “Novo produto”, “Exportar” ou “Criar task”.

## Grid, proporções e espaçamento

A AbacatePay parece seguir uma escala visual próxima a múltiplos de **4 e 8 px**. Abaixo estão referências úteis para reproduzir as proporções, arredondadas a partir das capturas.

| Uso | Proporção/medida observada ou sugerida |
|---|---:|
| Barra lateral aberta | 250–260 px |
| Barra lateral recolhida | 60–70 px |
| Cabeçalho superior | 64–76 px |
| Recuo do conteúdo em desktop | 24–40 px |
| Espaço entre cartões | 20–24 px |
| Padding de cartão | 20–26 px |
| Altura de controle comum | 40–48 px |
| Altura de item de navegação | 42–46 px |
| Raio de campo/botão | 8–12 px |
| Raio de cartão | 16–20 px |
| Raio do painel principal do dashboard | 28–34 px |

Os valores servem como uma escala de referência, não como uma medição exata. A densidade muda de acordo com a tela: o dashboard aproxima indicadores relacionados; formulários e páginas de perfil usam intervalos maiores entre blocos.

### Padrões de grid

- **Dashboard:** uma área superior de indicadores em duas colunas, uma faixa de métricas compactas e gráficos organizados abaixo.
- **Analytics:** grade de duas colunas com cartões de largura equivalente; em telas mais estreitas, a leitura natural é empilhar os módulos.
- **KPIs:** faixa horizontal em quatro ou cinco divisões, com linhas verticais finas entre métricas.
- **Produto:** listagem em grade de cartões; a página de edição usa duas colunas, formulário largo à esquerda e imagem/configuração auxiliar à direita.
- **Perfil:** conteúdo em seções e grades simples. Nem todo campo precisa virar um cartão próprio.
- **Tabelas:** ocupam a largura disponível, com cabeçalho em tom claro e linhas contidas em um contêiner com borda.

## Cor e superfície na referência

O contraste mais característico é entre o verde-limão dos estados ativos e o azul-petróleo escuro da tipografia. O cinza azulado aparece nos fundos, bordas e textos secundários. A estimativa dos tons vistos nas capturas não representa os tokens oficiais da marca.

| Papel visual na referência | Aparência aproximada | Uso observado |
|---|---|---|
| Fundo geral | Cinza azulado muito claro | Área atrás dos painéis |
| Superfície | Branco | Cartões, formulários e painéis |
| Texto principal | Azul-petróleo profundo | Títulos e valores |
| Texto secundário | Azul/cinza médio | Descrições, datas e eixos |
| Borda | Cinza azulado claro | Contornos, divisores e grades |
| Acento ativo | Verde-limão vivo | Navegação ativa, CTA e barras |
| Acento suave | Verde muito claro | Filtro selecionado e fundos de estado |
| Aviso/risco em gráfico | Azul e vermelho fortes | Segmentos de conversão e perdas |

### Aplicação ao Triton

Na implementação futura, mapear os papéis visuais da AbacatePay para os tokens já existentes do Triton. **Não substituir o teal do Triton pelo verde-limão da referência.**

| Token atual do Triton (frontend/src/styles.css) | Valor atual | Papel a manter |
|---|---|---|
| --ink | #172b27 | Texto principal e títulos |
| --muted | #60716b | Texto secundário |
| --line | #dce7e2 | Bordas e divisores |
| --surface | #ffffff | Cartões e superfícies |
| --soft / fundo | #f3f7f5 | Fundo suave da aplicação |
| --teal | #08786e | Ação primária, série principal e foco |
| --teal-dark | #075e56 | Texto de ação e estados selecionados |
| --teal-pale | #e4f3ef | Realce suave e seleção |

O Triton já tem tokens semânticos de âmbar, vermelho e verde para estados. Eles devem continuar distinguindo avisos, erros e sucesso. A referência serve para emprestar a **distribuição** da cor: usar o acento em pontos claros, sem pintar todos os cartões ou transformar todos os dados em verde.

## Tipografia

As capturas mostram uma sans-serif moderna, com formas abertas, boa leitura em tamanhos pequenos e aparência levemente geométrica. A identificação exata da fonte não é possível pela imagem. A hierarquia observável é mais importante que tentar adivinhar o nome da família:

| Nível | Faixa visual aproximada | Tratamento |
|---|---:|---|
| Título da página | 24–28 px | Peso semibold/bold, cor principal |
| Título de seção/cartão | 15–18 px | Peso regular a semibold |
| Valor de KPI principal | 36–42 px | Peso semibold, alto contraste |
| Métrica secundária | 22–26 px | Peso semibold |
| Corpo e navegação | 13–15 px | Peso regular/medium |
| Rótulo, eixo e legenda | 11–13 px | Cor secundária, sem competir com o dado |

Para o Triton, manter **Fustat** como família. Reproduzir a hierarquia com tamanho, peso, cor e espaçamento, sem misturar outra fonte só para imitar a referência. Valores financeiros e medidas podem usar números tabulares, quando fizer sentido, para facilitar a comparação vertical.

## Ícones e linguagem gráfica

Os ícones da referência têm aparência de **contorno simples**, com poucos detalhes, espessura consistente e tamanho pequeno. Eles ficam alinhados ao rótulo, geralmente antes do texto, e funcionam como pista de reconhecimento, não como decoração. Não há evidência suficiente para afirmar qual família de ícones foi usada.

O Triton já usa lucide-react, que se encaixa bem nesse padrão. Para manter consistência:

- usar uma família única de ícones de linha;
- manter o mesmo peso de traço, em torno de 1,8–2 px;
- usar aproximadamente 16–20 px em navegação e títulos de cartão;
- reservar ícones maiores para estados vazios ou ações de destaque;
- evitar misturar pictogramas preenchidos, emojis e ícones 3D na navegação comum;
- não depender só da cor: o ícone, o rótulo e o estado devem comunicar juntos.

## Ilustrações 3D

As ilustrações 3D da referência têm aparência de pequenos objetos isométricos ou quase isométricos: dinheiro, calendário, saque e troféu. Em geral combinam material brilhante, verde vivo, base branca/cinza clara, luz difusa e sombra macia. São recortes visuais com volume, diferentes dos ícones de interface.

### Onde funcionam

- Ao lado de um KPI de alto nível, como apoio visual e sem roubar o lugar do valor.
- Em estado vazio ou confirmação de uma etapa importante.
- Em onboarding ou celebração de uma conquista, como na janela “primeiro produto”.

### Regras para o Triton

- Usar com parcimônia; não colocar uma ilustração em cada cartão ou seção.
- Criar ou escolher objetos relacionados a água, reservatórios, nível, medição ou energia.
- Preservar o estilo de objeto 3D com volume e sombra suave, mas usar a paleta Triton (teal, verdes existentes e neutros), sem importar automaticamente o verde-limão da AbacatePay.
- Manter o objeto pequeno em relação ao dado. Nas capturas, o 3D ocupa uma área lateral e não interrompe a leitura do KPI.
- Para dados técnicos que exigem precisão, priorizar gráfico, mapa ou ícone linear; a ilustração serve como acento emocional.

## Cartões e métricas

Os cartões são contêineres brancos com borda fina, raio médio e sombra mínima ou inexistente. O contraste entre módulos vem principalmente da borda e do espaço entre eles, não de grandes sombras ou fundos coloridos.

### Cartão de KPI

Padrão visto no topo do dashboard e em telas financeiras:

1. Rótulo curto, em corpo pequeno e cor secundária.
2. Valor dominante, em corpo grande e cor principal.
3. Comparação ou tendência ao lado, com ícone/seta e percentual.
4. Ilustração opcional, posicionada na extremidade oposta ao texto.
5. Em faixas de KPIs, divisores verticais discretos separam as métricas.

O número deve ser o primeiro elemento percebido; rótulo, unidade, período e comparação explicam o valor depois. Para o Triton, isso vale para volume captado, nível, consumo, outorga e leituras, mantendo unidades explícitas.

### Cartão analítico

Um cartão maior contém título com ícone, uma descrição curta quando necessária e visualização. Os exemplos incluem funil com barras horizontais, conversão segmentada, evolução mensal e série de assinantes.

O padrão evita enfeites: grade leve, legenda compacta, rótulos alinhados e cores de série bem separadas. Contexto ou observação importante pode aparecer numa faixa suave dentro do cartão, sem criar outro cartão concorrente.

## Gráficos

### Gráficos de barras e séries temporais

Nas imagens 1, 3 e 4, os gráficos usam linhas de grade horizontais finas, rótulos de eixo discretos e séries coloridas com alto contraste em relação ao fundo branco. As barras têm largura generosa, espaços regulares e cantos superiores levemente arredondados. A legenda fica no cabeçalho ou próxima da série; não há moldura pesada em torno da área de plotagem.

### Funil e conversão

O funil da imagem 3 usa uma lista de etapas, cada qual com uma barra horizontal de trilho cinza claro, preenchimento proporcional e valores alinhados na coluna direita. A etapa final recebe preenchimento mais saturado. No gráfico de conversão de cartão, uma barra horizontal segmentada mostra a participação de cada resultado; legenda, contagem e taxa do banco ficam próximas da barra.

### Tradução para métricas ambientais

- Reservar o teal principal para a série ou valor que deve receber mais atenção.
- Usar tons suaves da mesma família para referências ou séries secundárias.
- Usar âmbar e vermelho existentes apenas quando representarem limiar, risco ou exceção.
- Manter grade e rótulos no neutro, para não competir com os dados.
- Mostrar unidade, intervalo de tempo, legenda e estado sem dados de forma explícita.
- Preferir tooltip e legenda para detalhes, sem sobrecarregar o gráfico com texto permanente.
- Em comparações, não depender exclusivamente de cores parecidas: combinar cor, legenda e marcador/estilo.

## Tabelas, formulários e páginas de detalhe

### Tabelas

Cabeçalho em fundo cinza azulado claro, texto pequeno e discreto, divisores horizontais finos e linhas com espaço vertical suficiente. A borda arredondada pertence ao contêiner da tabela. Ações ficam alinhadas na extremidade da linha, muitas vezes sob menu de três pontos.

### Formulários

Campos de altura média, borda leve, fundo branco e rótulo acima. Descrições e ajuda aparecem próximas ao campo, em texto secundário. A tela de produto usa formulário em uma coluna ampla e uma coluna auxiliar com imagem; a edição de dados do perfil se organiza em seções, não em um cartão por campo.

### Ações

O botão principal é preenchido e arredondado; secundários costumam usar fundo branco ou cinza muito claro, com contorno discreto. A ação mais importante da tela aparece perto do título ou no fim do formulário. O estado desabilitado tem contraste reduzido, mas continua legível.

## Estados vazios, sucesso e overlays

A imagem 5 apresenta uma confirmação de onboarding em modal dividido: texto e ações à esquerda, ilustração 3D à direita. O fundo fica escurecido e desfocado, o modal tem cantos largos, sombra suave e uma ação principal mais uma opção secundária.

Nas telas sem dados (imagens 11 e 18), a mensagem central explica a condição e sugere a próxima ação. A ilustração fica acima do título e é menor que a mensagem. A tela de visão financeira vazia usa uma frase simples no centro do gráfico, sem inventar valores ou manter um eixo sem contexto.

Para o Triton, preservar estados honestos: dado ausente deve aparecer como pendente/sem registro, nunca como zero presumido. O desenho pode ser leve, mas a ação seguinte precisa ser clara.

## Mapas no contexto do Triton

Não há mapa nas imagens da AbacatePay; portanto, não há um padrão cartográfico a copiar. O mapa de propriedades do Triton deve continuar usando a cartografia e os controles funcionais atuais. A referência pode orientar apenas os elementos ao redor:

- tratar mapa e lista de propriedades como módulos irmãos, com borda leve e cantos arredondados;
- usar fundo neutro e cartões brancos para filtros, pesquisa e prévia da propriedade;
- manter controles do mapa compactos, em superfícies brancas com sombra leve, sem cobrir áreas importantes;
- preservar o teal do Triton para propriedade selecionada e elementos ativos; usar estados semânticos existentes para localização pendente e alertas;
- destacar o marcador selecionado por contorno/tamanho além da cor;
- usar sobreposições de reservatório com preenchimento translúcido para não esconder o mapa;
- em telas estreitas, permitir alternância clara entre mapa e lista, mantendo busca e seleção acessíveis.

O mapa precisa continuar visualmente legível como mapa. A aproximação com o dashboard ocorre na moldura, nos filtros, nos estados e na hierarquia — não por substituir tiles, limites ou marcadores por ilustrações decorativas.

## Responsividade

As referências fornecidas são predominantemente desktop; não permitem confirmar os breakpoints ou a solução móvel oficial. Como direção para implementação:

- abaixo da largura de tablet, empilhar grades analíticas e KPIs;
- reduzir margens externas antes de reduzir demais o texto;
- transformar a navegação lateral em menu recolhível ou navegação adaptada ao mobile;
- permitir rolagem horizontal em tabelas densas, com colunas prioritárias visíveis;
- converter gráficos em largura total, preservando rótulos e controles de período;
- reorganizar modais divididos em uma coluna, posicionando o texto e a ação antes da ilustração;
- evitar controles de mapa muito próximos entre si e conservar área útil para interação por toque.

Esses itens são recomendações de adaptação, não características mobile confirmadas da referência.

## Inventário de padrões para reutilizar

| Padrão | Uso futuro no Triton |
|---|---|
| Sidebar com grupos e estado ativo | Navegação entre início, propriedade, leituras, outorga, energia e alertas |
| Seletor de contexto no topo do menu | Escolha da propriedade ativa |
| Cabeçalho com breadcrumb/título e ação | Páginas de listagem e detalhe |
| Pills de período | Filtros de séries temporais e histórico |
| Faixa de KPIs | Resumo de propriedade e indicadores de energia/água |
| Cartão analítico | Séries de nível, consumo, captação e comparação de outorga |
| Tabela com cabeçalho suave | Leituras, componentes, reservatórios e registros |
| Estado vazio com orientação | Propriedade sem dados, ausência de leitura ou histórico |
| Popover de seleção | Troca de propriedade e opções de contexto |
| Ícones de linha consistentes | Navegação e cabeçalhos, usando lucide-react |
| Ilustração 3D ocasional | Onboarding e estados vazios escolhidos com critério |
| Painel do mapa + filtros + prévia | Lista e mapa de propriedades, sem alterar a cartografia |

## Direção recomendada para as próximas etapas

Ao refazer cada tela, usar este roteiro:

1. Identificar a finalidade e os dados que a tela do Triton já apresenta.
2. Escolher o padrão estrutural correspondente (dashboard, tabela, formulário, mapa ou detalhe).
3. Aplicar a hierarquia e o espaçamento inspirados na AbacatePay.
4. Aplicar os tokens e a fonte atuais do Triton, sem importar a paleta de marca da referência.
5. Manter comportamento, regras e estados reais dos dados.
6. Em gráficos e mapas, preservar unidade, legenda, seleção, acessibilidade e estados sem dados.
7. Revisar desktop e mobile para que a densidade se reorganize sem esconder informação importante.

O resultado desejado é um Triton mais consistente, arejado e fácil de percorrer, com a disciplina visual da referência e identidade própria do produto.
