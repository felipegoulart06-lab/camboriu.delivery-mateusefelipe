"""Manual operacional das entregas de alto padrão.

A tela Integração e o PDF baixam o mesmo conteúdo, para a empresa e o
entregador receberem a mesma regra — sem versão resumida.
"""

TITLE = "Manual de integração — entregas de alto padrão"
SUBTITLE = (
    "Como a Camboriú Delivery executa coleta, transporte e entrega de itens "
    "sensíveis, com cadeia de custódia, rastreio e prova fotográfica."
)
VERSION = "1.0"
AUDIENCE = "Empresas contratantes · Entregadores · Equipe da central"

SECTIONS = (
    {
        "id": "proposito",
        "title": "1. Para que serve este documento",
        "blocks": (
            {
                "type": "p",
                "text": (
                    "Este manual descreve, passo a passo, o jeito único de trabalhar da Camboriú Delivery. "
                    "Não é um resumo comercial: é o procedimento que a empresa, o entregador e a central "
                    "devem seguir em toda corrida. Imprima ou envie o PDF antes da primeira operação."
                ),
            },
            {
                "type": "rules",
                "items": (
                    "Toda corrida nasce de uma solicitação da empresa no painel. Não existe coleta combinada só por WhatsApp.",
                    "O entregador só entra em trânsito depois de concluir o checklist antifraude com as 12 fotos obrigatórias.",
                    "Solicitações não são apagadas. Cancelar encerra o atendimento; o histórico permanece.",
                    "Fotos, documentos e posições GPS não ficam em pasta pública: só saem por tela com acesso conferido.",
                ),
            },
        ),
    },
    {
        "id": "padrao",
        "title": "2. O que é uma entrega de alto padrão",
        "blocks": (
            {
                "type": "p",
                "text": (
                    "Alto padrão, neste serviço, significa cadeia de custódia fechada: quem pediu, quem coletou, "
                    "quem recebeu, em que veículo, com quais fotos e em que coordenadas. Serve para documento, "
                    "item de alto valor, medicamento, amostra e qualquer carga que a empresa marque como sigilosa."
                ),
            },
            {
                "type": "steps",
                "items": (
                    "A empresa descreve o item, o valor declarado, a coleta e todos os destinos.",
                    "A central aciona um entregador com login, CNH com EAR e veículo regular.",
                    "O aparelho do entregador publica a posição enquanto a corrida está ativa.",
                    "Na coleta, o entregador identifica quem entrega o item, lacra, fotografa 12 etapas e declara a conferência.",
                    "No destino, registra quem recebeu. A empresa e a central leem o termo com as fotos.",
                ),
            },
        ),
    },
    {
        "id": "papeis",
        "title": "3. Os três papéis — e o que cada um faz",
        "blocks": (
            {
                "type": "p",
                "text": "Ninguém atravessa o papel do outro. A empresa pede; a central despacha; o entregador executa.",
            },
            {
                "type": "roles",
                "items": (
                    (
                        "Empresa contratante",
                        "Conclui o cadastro (CNPJ, MEI ou CPF) com documentos. Pede a retirada no painel, acompanha o mapa, lê o termo de coleta e, se for CNPJ/MEI, fatura em boleto.",
                    ),
                    (
                        "Admin master e central",
                        "Cadastram empresas, entregadores e frota. Recebem a notificação da solicitação, acionam o entregador, confirmam o aceite, cancelam com dupla confirmação e guardam o histórico financeiro.",
                    ),
                    (
                        "Entregador",
                        "Entra só no app dele. Aceita a corrida atribuída, liga o GPS, preenche o checklist no local, não sai com a carga sem as 12 fotos e registra o recebedor no destino.",
                    ),
                ),
            },
        ),
    },
    {
        "id": "empresa",
        "title": "4. Integração da empresa — o que precisa estar pronto",
        "blocks": (
            {
                "type": "p",
                "text": (
                    "Antes de pedir a primeira retirada, a empresa preenche o cadastro em Configurações. "
                    "Enquanto isso não estiver concluído, o restante do painel fica bloqueado."
                ),
            },
            {
                "type": "steps",
                "items": (
                    "Identificação: nome fantasia, razão social, tipo de documento (CNPJ, MEI ou CPF) com dígito verificador, inscrição estadual (ou ISENTO), inscrição municipal, regime tributário, data de abertura e ramo.",
                    "Responsável: nome, CPF, cargo, e-mail e telefone de quem responde pela empresa na plataforma.",
                    "Endereço oficial: CEP, logradouro e número, complemento, bairro, cidade e UF — o mesmo do comprovante.",
                    "Financeiro: e-mail e telefone de cobrança e o dia de vencimento preferido do boleto (1 a 28).",
                    "Anexos obrigatórios para CNPJ/MEI: cartão CNPJ, contrato social ou certificado MEI, comprovante de endereço e documento com foto do responsável. Cadastro em CPF dispensa contrato social.",
                ),
            },
            {
                "type": "rules",
                "items": (
                    "CNPJ e MEI faturam entregas em boleto, com o vencimento escolhido no painel.",
                    "Cadastro em CPF paga por entrega (Pix ou dinheiro). Não gera boleto.",
                    "Os dados cadastrais saem no cabeçalho de cada solicitação, da notificação do master e dos PDFs.",
                ),
            },
        ),
    },
    {
        "id": "entregador",
        "title": "5. Integração do entregador — quem pode ser acionado",
        "blocks": (
            {
                "type": "p",
                "text": (
                    "O admin master cadastra o entregador e o login do celular na mesma ficha. "
                    "Entregador sem login, sem EAR ou com CNH vencida não entra em operação."
                ),
            },
            {
                "type": "steps",
                "items": (
                    "Dados pessoais: nome completo, CPF válido, data de nascimento (mínimo 18 anos), RG, órgão emissor e nome da mãe.",
                    "Contato: telefone principal e um contato de emergência com telefone.",
                    "Endereço completo, batendo com o comprovante de residência.",
                    "Habilitação: número da CNH, categoria, registro, UF, emissão, primeira habilitação, vencimento e exame médico em dia.",
                    "EAR obrigatória (exerce atividade remunerada). Sem essa observação a CNH não autoriza transportar carga de terceiros.",
                    "Repasse: chave Pix ou banco, agência e conta completos.",
                    "Anexos obrigatórios: CNH (frente ou digital), comprovante de residência e foto do entregador. Opcionais: verso da CNH, antecedentes, ASO e comprovante bancário.",
                ),
            },
            {
                "type": "rules",
                "items": (
                    "O e-mail e a senha da ficha são o login do app. Sem eles a central não consegue acionar.",
                    "CNH ou exame médico vencidos travam o cadastro. A lista avisa o que vence em 30 dias.",
                    "O entregador só vê as corridas atribuídas a ele. Não acessa o painel da empresa nem o da central.",
                ),
            },
        ),
    },
    {
        "id": "frota",
        "title": "6. Integração da frota — moto, carro e utilitário",
        "blocks": (
            {
                "type": "p",
                "text": (
                    "O veículo precisa bater com o CRLV. Cada tipo cobra o que faz sentido para a carga. "
                    "Licenciamento vencido não entra na rua."
                ),
            },
            {
                "type": "roles",
                "items": (
                    ("Moto", "Placa, UF, RENAVAM, chassi, marca, modelo, anos, cor, combustível, proprietário, quilometragem, capacidade em kg e litragem do baú. Anexos: CRLV, foto frontal e foto da placa."),
                    ("Carro", "Tudo da identificação mais número de portas e seguro completo (seguradora, apólice, vencimento e PDF da apólice)."),
                    ("Utilitário", "Tudo do carro mais tipo de carroceria, PBT, comprimento, largura e altura do compartimento, e foto da carga."),
                ),
            },
            {
                "type": "rules",
                "items": (
                    "Placa no padrão antigo (ABC1234) ou Mercosul (ABC1D23). RENAVAM e chassi são conferidos.",
                    "Se marcar rastreador, informe a empresa do rastreador.",
                    "A central escolhe o veículo na hora do acionamento. A empresa vê a frota disponível, mas não altera a da plataforma.",
                ),
            },
        ),
    },
    {
        "id": "pedido",
        "title": "7. Como a empresa pede a retirada",
        "blocks": (
            {
                "type": "p",
                "text": (
                    "No painel da empresa: Minhas entregas → Pedir retirada. A empresa não escolhe o entregador "
                    "nem muda o status. Isso é da central."
                ),
            },
            {
                "type": "steps",
                "items": (
                    "Informe quem solicita internamente (setor, clínica, escritório) e o tipo de item: documento, alto valor, medicamento, amostra ou outro.",
                    "Descreva o que será transportado. Declare o valor. Marque sigiloso se o conteúdo não deve aparecer em texto aberto.",
                    "Endereço e contato da coleta, com janela de horário se houver.",
                    "1º destino com endereço e contato. Inclua destinos extras no mesmo formulário (até nove além do primeiro).",
                    "Prioridade: normal, urgente ou crítica. O preço já nasce com a tabela vigente (base + destinos extras + acréscimo de urgência).",
                    "Salve. O sistema gera o código da solicitação, o PDF com o cabeçalho da empresa e a notificação para o admin master.",
                ),
            },
            {
                "type": "rules",
                "items": (
                    "Não combine coleta por fora e depois “só registra”. Sem solicitação no sistema não há contrato, rastreio nem termo.",
                    "Vários destinos na mesma viagem são a regra, não a exceção. Cada destino extra entra no preço.",
                    "A empresa acompanha a corrida em tempo real assim que o entregador aceitar e ligar o GPS.",
                ),
            },
        ),
    },
    {
        "id": "central",
        "title": "8. O que a central faz ao receber o pedido",
        "blocks": (
            {
                "type": "p",
                "text": (
                    "A notificação chega com os dados cadastrais da empresa (documento, endereço, responsável). "
                    "O admin master abre a solicitação, lê o PDF e aciona um entregador disponível."
                ),
            },
            {
                "type": "steps",
                "items": (
                    "Conferir tipo de item, prioridade, valor declarado e se é sigiloso.",
                    "Escolher entregador com login ativo, CNH com EAR e documentos em dia.",
                    "Escolher o veículo adequado (baú da moto, carro com seguro, utilitário com medidas).",
                    "Acionar. A corrida passa a “Acionando entregador”. O entregador vê no app dele.",
                    "Quando ele aceita, a central pode confirmar o aceite. A empresa já enxerga o mapa.",
                    "Cancelar só com motivo e segunda confirmação na tela. O registro não some.",
                ),
            },
        ),
    },
    {
        "id": "aceite",
        "title": "9. Aceite da corrida pelo entregador",
        "blocks": (
            {
                "type": "steps",
                "items": (
                    "Abra o app → Corridas. Toque na solicitação atribuída.",
                    "Leia coleta, destinos, tipo de item e prazo. Se não puder cumprir, recuse pela central — não aceite para depois abandonar.",
                    "Aceite. O status vira “Aceita pelo entregador”. O GPS precisa estar autorizado no aparelho.",
                    "Siga para a coleta. A empresa vê você no mapa enquanto a corrida estiver ativa (aceita, em coleta ou em trânsito).",
                    "Ao chegar, inicie a coleta no app. Só então abre o checklist. Sem ele o sistema não libera “em trânsito”.",
                ),
            },
            {
                "type": "rules",
                "items": (
                    "Fora de localhost o GPS exige HTTPS. Sem posição, a empresa não acompanha a chegada.",
                    "Depois de entregue ou cancelada o rastreio fecha. A trilha permanece no histórico da corrida.",
                ),
            },
        ),
    },
    {
        "id": "coleta",
        "title": "10. Procedimento de coleta — o que não pode faltar",
        "blocks": (
            {
                "type": "p",
                "text": (
                    "Este é o coração da operação. O entregador preenche o checklist no local, na hora, "
                    "com o item à vista. As fotos são prova para os dois lados e anexam-se ao contrato de prestação de serviço."
                ),
            },
            {
                "type": "steps",
                "items": (
                    "Apresente-se na recepção com o código da solicitação. Peça a pessoa responsável pela entrega do item.",
                    "Confira o documento dessa pessoa (RG ou CPF) e anote nome e número no formulário.",
                    "Confronte o item com a descrição da solicitação: quantidade de volumes, etiqueta, lacre, temperatura se for o caso.",
                    "Aplique o lacre/selo de segurança se a empresa usar. Anote o número.",
                    "Tire as 12 fotos na ordem do app, no local, com a câmera traseira. Não reaproveite foto antiga, print ou galeria.",
                    "Marque todas as declarações. Envie. Só então o sistema autoriza sair com a carga.",
                ),
            },
            {
                "type": "rules",
                "items": (
                    "As 12 fotos são obrigatórias. Falta uma, o envio não passa.",
                    "Cada arquivo tem limite de tamanho (padrão 12 MB). Use a câmera do celular, não um scanner de mesa.",
                    "O app grava latitude, longitude, precisão e o dispositivo no momento do envio.",
                    "A empresa e a central leem o termo depois. O entregador não edita o checklist enviado.",
                ),
            },
        ),
    },
    {
        "id": "fotos",
        "title": "11. As 12 fotos — exatamente como tirar cada uma",
        "blocks": (
            {
                "type": "p",
                "text": (
                    "Siga a ordem. Enquadre com luz, sem tremer, sem dedo na lente. O texto da etiqueta e o número do lacre "
                    "precisam ser legíveis. Se a foto sair escura, apague e tire de novo antes de enviar."
                ),
            },
            {
                "type": "photos",
                "items": (
                    ("1", "Fachada ou recepção do local de coleta", "Mostre que você está no endereço certo: placa, número, recepção ou portaria. Não fotografe só o chão ou o céu."),
                    ("2", "Nota fiscal ou documento de acompanhamento", "Papel ou tela da NF, romaneio ou protocolo. Números e nome do destinatário visíveis."),
                    ("3", "Item — visão geral", "O volume inteiro sobre uma superfície, de cima ou de frente, para contar quantos volumes são."),
                    ("4", "Item — etiqueta ou identificação", "Aproxime na etiqueta, código de barras, nome do paciente/cliente ou lacre de origem da empresa."),
                    ("5", "Item — lado A", "Primeira face lateral. Se for envelope, mostre a frente fechada."),
                    ("6", "Item — lado B", "Face oposta. Se for caixa, vire 180°. O objetivo é provar que não havia rasgo escondido."),
                    ("7", "Embalagem fechada", "Fita, lacre de fábrica ou envelope lacrado. Sem aba aberta."),
                    ("8", "Lacre ou selo de segurança", "Número do lacre nítido. Se a empresa não usa lacre, fotografe o selo adesivo ou a fita de segurança aplicada na hora."),
                    ("9", "Item acomodado no veículo", "Já no baú, no compartimento ou no suporte da moto, com a tampa/trava visível."),
                    ("10", "Placa do veículo", "Placa inteira, no veículo da corrida, no local da coleta. Não use foto de outro dia."),
                    ("11", "Odômetro no início da corrida", "Painel com a quilometragem atual. Em moto, o hodômetro digital ou analógico nítido."),
                    ("12", "Responsável pela entrega com o item", "A pessoa que passou o item, ao lado do volume. Rosto reconhecível. Peça autorização verbal antes."),
                ),
            },
        ),
    },
    {
        "id": "declaracoes",
        "title": "12. Declarações que o entregador assinala no local",
        "blocks": (
            {
                "type": "p",
                "text": "Todas as caixas abaixo precisam estar marcadas. São declaração formal, não “ok” de tela.",
            },
            {
                "type": "rules",
                "items": (
                    "Confirmei a identidade do responsável pela entrega.",
                    "O item confere com a solicitação da empresa.",
                    "Embalagem íntegra, sem sinal de violação.",
                    "Lacre/selo aplicado e fotografado.",
                    "Nota fiscal ou documento de acompanhamento conferido.",
                    "Declaro que as fotos foram tiradas agora, neste local.",
                    "Acondicionamento térmico adequado — marque quando o item exigir (medicamento, amostra, baú térmico).",
                ),
            },
            {
                "type": "p",
                "text": (
                    "No formulário também entram: nome e documento de quem entregou o item, quantidade de volumes, "
                    "número do lacre e observações (atraso da recepção, item gelado, volume extra, recusa parcial)."
                ),
            },
        ),
    },
    {
        "id": "transito",
        "title": "13. Em trânsito e destinos múltiplos",
        "blocks": (
            {
                "type": "steps",
                "items": (
                    "Com o checklist enviado, o status passa a “Em trânsito”. O baú/compartimento permanece lacrado até o destino.",
                    "Siga a ordem dos destinos (1, 2, 3…). O app lista cada endereço com botão de rota no mapa.",
                    "Não abra o volume no caminho, não desvie para corrida particular e não deixe a carga sem vigilância.",
                    "Se um destino recusar, anote no app e avise a central. Não devolva por conta própria sem registro.",
                    "Em cada parada, confirme o recebedor. No último destino, finalize a corrida com o nome de quem recebeu e o protocolo, se houver.",
                ),
            },
            {
                "type": "rules",
                "items": (
                    "O rastreio continua publicado até a entrega ou o cancelamento.",
                    "A empresa vê a trilha no mapa dela. Depois de encerrada, o mapa fecha; o histórico fica.",
                ),
            },
        ),
    },
    {
        "id": "destino",
        "title": "14. Entrega no destino — encerramento",
        "blocks": (
            {
                "type": "steps",
                "items": (
                    "Identifique quem vai receber. Confira o nome com o contato do destino.",
                    "Entregue o volume com o lacre intacto. Se o recebedor quiser abrir na sua frente, aguarde e anote.",
                    "No app, informe o nome de quem recebeu, documento ou protocolo e observações.",
                    "Envie. O status vira “Entregue”. Sem o checklist de coleta o sistema não deixa finalizar.",
                ),
            },
        ),
    },
    {
        "id": "itens",
        "title": "15. Regras extras por tipo de item",
        "blocks": (
            {
                "type": "roles",
                "items": (
                    ("Documento", "Envelope lacrado. Não dobre, não grampeie por cima do lacre, não fotografe o conteúdo interno se estiver marcado como sigiloso — fotografe o envelope fechado."),
                    ("Alto valor", "Valor declarado obrigatório. Preferir carro ou utilitário com seguro e rastreador. Não anuncie o conteúdo em voz alta na recepção."),
                    ("Medicamento", "Conferir acondicionamento térmico. Marque a declaração de temperatura. Baú térmico na moto quando a empresa exigir. Não deixe no sol no baú aberto."),
                    ("Amostra", "Tratar como material sensível. Não vire o tubo/caixa. Fotografe a etiqueta de origem. Se vazar, interrompa, fotografe e chame a central."),
                    ("Sigiloso", "A descrição no painel pode ser genérica. O entregador não comenta o conteúdo com terceiros. As fotos continuam obrigatórias, focadas na embalagem."),
                ),
            },
        ),
    },
    {
        "id": "conduta",
        "title": "16. Conduta no local — empresa e entregador",
        "blocks": (
            {
                "type": "p",
                "text": "A empresa também tem procedimento. A coleta só flui se os dois lados estiverem prontos.",
            },
            {
                "type": "roles",
                "items": (
                    ("A empresa no local", "Deixe o item embalado, identificado e, se usar, lacrado. Tenha um responsável com documento. Não peça para o entregador “já ir levando” sem abrir o app. Reserve um ponto de espera coberto."),
                    ("O entregador no local", "Uniforme ou identificação visível. Não entre em área restrita sem autorização. Não aceite envelope aberto. Não assine documento da empresa sem copiar o número no checklist."),
                    ("Os dois", "Qualquer divergência (volume a mais, lacre rompido, endereço errado) trava a saída. Registre na observação e avise a central antes de seguir."),
                ),
            },
        ),
    },
    {
        "id": "proibido",
        "title": "17. O que é proibido — sem exceção",
        "blocks": (
            {
                "type": "rules",
                "items": (
                    "Sair da coleta sem as 12 fotos enviadas.",
                    "Usar foto da galeria, print de WhatsApp ou foto de outra corrida.",
                    "Acionar entregador sem login no app.",
                    "Colocar na rua veículo com licenciamento vencido ou entregador com CNH/EAR irregular.",
                    "Apagar solicitação. Não existe lixeira para pedido de empresa. Cancele, se for o caso.",
                    "Cancelar fatura, desfazer repasse ou suspender empresa sem a segunda confirmação na tela.",
                    "Publicar pasta de mídia na internet. Fotos e documentos só saem pelas telas autenticadas.",
                    "Subcontratar a corrida para um terceiro que não está no cadastro.",
                ),
            },
        ),
    },
    {
        "id": "incidentes",
        "title": "18. Incidentes — o que fazer na hora",
        "blocks": (
            {
                "type": "roles",
                "items": (
                    ("Recusa no destino", "Não force. Anote o nome de quem recusou, fotografe o volume ainda lacrado se possível, avise a central e aguarde instrução (retorno à origem ou próximo destino)."),
                    ("Avaria ou lacre violado", "Não siga. Fotografe, descreva no checklist ou na observação da entrega, chame a central. A empresa lê o termo."),
                    ("Acidente ou pane", "Priorize segurança. Avise a central. Não transfira a carga para outro veículo sem novo acionamento no sistema."),
                    ("Cancelamento", "Só a central cancela, com motivo e confirmação dupla. A empresa vê o status cancelado; o pedido continua no histórico e no PDF."),
                    ("GPS recusado no celular", "A corrida até pode ser aceita, mas a empresa não vê a chegada. Autorize a localização ou a central orienta o cliente pelo telefone."),
                ),
            },
        ),
    },
    {
        "id": "financeiro",
        "title": "19. Depois da entrega — valores, fatura e repasse",
        "blocks": (
            {
                "type": "steps",
                "items": (
                    "Cada solicitação já nasce com o valor cobrado e o percentual do entregador, pela tabela de preços da plataforma.",
                    "Empresa com CNPJ ou MEI junta as entregas concluídas e pede fatura no painel, escolhendo o vencimento. O master cola a linha digitável do boleto.",
                    "Empresa com CPF não fatura em boleto: acerta por entrega.",
                    "O master fecha o repasse do entregador por período. O entregador vê ganhos do mês e o que ainda vai receber no Histórico.",
                    "Nada disso substitui o termo de coleta. Sem checklist, a corrida não fecha e não entra em fatura como entregue.",
                ),
            },
        ),
    },
    {
        "id": "apresentacao",
        "title": "20. Como apresentar este PDF",
        "blocks": (
            {
                "type": "p",
                "text": (
                    "Baixe o PDF neste menu e envie junto com o acesso da empresa ou na integração do entregador. "
                    "Peça a leitura antes do primeiro login. Na reunião de kickoff, percorra as seções 7 a 14 com a tela do sistema aberta."
                ),
            },
            {
                "type": "roles",
                "items": (
                    ("Para a empresa", "Destaque as seções 4, 7, 8, 10, 16 e 19. Mostre onde ela pede a retirada, onde vê o mapa e onde baixa o PDF da solicitação com o próprio CNPJ no cabeçalho."),
                    ("Para o entregador", "Destaque as seções 5, 9, 10, 11, 12, 13, 14 e 17. Faça um ensaio das 12 fotos com um volume de treino antes da primeira corrida real."),
                    ("Para a central", "Destaque as seções 8, 17 e 18. Ninguém aciona entregador irregular. Ninguém apaga pedido."),
                ),
            },
            {
                "type": "p",
                "text": (
                    "Documento interno da Camboriú Delivery. Descreve o procedimento vigente do sistema. "
                    "Alteração de regra só vale quando o painel for atualizado — não por combinado verbal."
                ),
            },
        ),
    },
)
