<?php
declare(strict_types=1);

require_once __DIR__ . '/includes/config.php';
require_once __DIR__ . '/includes/form-handler.php';

$form = handle_contact_form();

$segments = [
    'clinica' => 'Clínica / Hospital',
    'laboratorio' => 'Laboratório',
    'farmacia' => 'Farmácia',
    'juridico' => 'Escritório jurídico',
    'financeiro' => 'Instituição financeira',
    'varejo' => 'Varejo de alto valor',
    'outro' => 'Outro',
];

$services = [
    [
        'title' => 'Documentos',
        'text' => 'Contratos, processos, laudos e malotes com protocolo, rastreio e confirmação de recebimento.',
    ],
    [
        'title' => 'Itens de alto valor',
        'text' => 'Joias, eletrônicos, equipamentos e cargas sensíveis com cadeia de custódia e entrega assistida.',
    ],
    [
        'title' => 'Medicamentos',
        'text' => 'Remédios controlados e urgentes com prioridade operacional e registro completo da rota.',
    ],
    [
        'title' => 'Exames e amostras',
        'text' => 'Coletas, testes laboratoriais e materiais biológicos com cuidado térmico e prazo crítico.',
    ],
];

$steps = [
    [
        'num' => '01',
        'title' => 'Cadastro da empresa',
        'text' => 'Ativamos o acesso da sua operação com usuários, centros de custo e regras de aprovação.',
    ],
    [
        'num' => '02',
        'title' => 'Solicitação no app',
        'text' => 'Sua equipe cria a corrida, anexa observações e define nível de urgência e confidencialidade.',
    ],
    [
        'num' => '03',
        'title' => 'Execução monitorada',
        'text' => 'Acompanhamento em tempo real, prova de entrega e histórico auditável para compliance.',
    ],
];

$benefits = [
    [
        'title' => 'Operação sob controle',
        'text' => 'Painel com status, SLA, histórico e evidências — pronto para auditoria interna.',
    ],
    [
        'title' => 'Entregadores qualificados',
        'text' => 'Equipe treinada para cargas sensíveis, sigilo e protocolos de recebimento.',
    ],
    [
        'title' => 'Prioridade real',
        'text' => 'Filas inteligentes para urgências clínicas, jurídicas e financeiras.',
    ],
    [
        'title' => 'Integração simples',
        'text' => 'Fluxo pensado para recepção, laboratório, jurídico e backoffice sem atrito.',
    ],
];
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Camboriú Delivery — plataforma de entregas especializadas para documentos, itens de alto valor, medicamentos e exames laboratoriais.">
    <title><?= htmlspecialchars(SITE_TITLE, ENT_QUOTES, 'UTF-8') ?></title>
    <link rel="icon" href="assets/img/favicon.svg" type="image/svg+xml">
    <link rel="apple-touch-icon" href="assets/img/favicon.svg">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;500;600;700&family=Syne:wght@600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="assets/css/styles.css">
</head>
<body>
    <div class="page-glow" aria-hidden="true"></div>

    <header class="topbar">
        <div class="container topbar__inner">
            <a class="brand" href="#topo" aria-label="<?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?>">
                <span class="brand__mark" aria-hidden="true"></span>
                <span class="brand__text"><?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?></span>
            </a>
            <nav class="nav" aria-label="Principal">
                <a href="#servicos">Serviços</a>
                <a href="#fluxo">Fluxo</a>
                <a href="#vantagens">Vantagens</a>
                <a href="#contato">Contato</a>
            </nav>
            <a class="btn btn--ghost" href="#contato">Falar com comercial</a>
            <button class="nav-toggle" type="button" aria-label="Abrir menu" aria-expanded="false">
                <span></span><span></span>
            </button>
        </div>
    </header>

    <main id="topo">
        <section class="hero">
            <div class="hero__media" aria-hidden="true">
                <img
                    src="https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?auto=format&fit=crop&w=2000&q=80"
                    alt=""
                    width="2000"
                    height="1333"
                >
                <div class="hero__shade"></div>
            </div>

            <div class="container hero__content">
                <p class="brand-hero"><?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?></p>
                <h1>Entregas especializadas com precisão de sistema.</h1>
                <p class="hero__lead">
                    Plataforma B2B para documentos, itens de alto valor, medicamentos e exames laboratoriais — com rastreio, protocolo e responsabilidade ponta a ponta.
                </p>
                <div class="hero__actions">
                    <a class="btn btn--primary" href="#contato">Solicitar demonstração</a>
                    <a class="btn btn--line" href="#servicos">Ver o que entregamos</a>
                </div>
            </div>
        </section>

        <section class="strip" aria-label="Cobertura">
            <div class="container strip__inner">
                <p><strong>Foco operacional:</strong> <?= htmlspecialchars(SITE_CITY, ENT_QUOTES, 'UTF-8') ?></p>
                <p><strong>Modelo:</strong> aplicativo + painel para empresas</p>
                <p><strong>Perfil:</strong> cargas sensíveis e urgentes</p>
            </div>
        </section>

        <section id="servicos" class="section section--services">
            <div class="container">
                <header class="section__head reveal">
                    <h2>O que sua empresa pode enviar</h2>
                    <p>Não somos delivery de comida. Somos logística especializada para o que não pode falhar.</p>
                </header>

                <div class="service-grid">
                    <?php foreach ($services as $index => $service): ?>
                        <article class="service reveal" style="--delay: <?= $index * 80 ?>ms">
                            <span class="service__index">0<?= $index + 1 ?></span>
                            <h3><?= htmlspecialchars($service['title'], ENT_QUOTES, 'UTF-8') ?></h3>
                            <p><?= htmlspecialchars($service['text'], ENT_QUOTES, 'UTF-8') ?></p>
                        </article>
                    <?php endforeach; ?>
                </div>
            </div>
        </section>

        <section id="fluxo" class="section section--flow">
            <div class="container flow">
                <header class="section__head section__head--light reveal">
                    <h2>Como o sistema funciona</h2>
                    <p>Do pedido ao comprovante, tudo em um fluxo claro para o time da empresa.</p>
                </header>

                <ol class="flow__list">
                    <?php foreach ($steps as $index => $step): ?>
                        <li class="flow__item reveal" style="--delay: <?= $index * 100 ?>ms">
                            <span class="flow__num"><?= htmlspecialchars($step['num'], ENT_QUOTES, 'UTF-8') ?></span>
                            <div>
                                <h3><?= htmlspecialchars($step['title'], ENT_QUOTES, 'UTF-8') ?></h3>
                                <p><?= htmlspecialchars($step['text'], ENT_QUOTES, 'UTF-8') ?></p>
                            </div>
                        </li>
                    <?php endforeach; ?>
                </ol>
            </div>
        </section>

        <section id="vantagens" class="section section--benefits">
            <div class="container">
                <header class="section__head reveal">
                    <h2>Feito para operação corporativa</h2>
                    <p>Uma experiência com cara de sistema: objetiva, auditável e pronta para o dia a dia da empresa.</p>
                </header>

                <div class="benefit-rail">
                    <?php foreach ($benefits as $index => $benefit): ?>
                        <article class="benefit reveal" style="--delay: <?= $index * 70 ?>ms">
                            <h3><?= htmlspecialchars($benefit['title'], ENT_QUOTES, 'UTF-8') ?></h3>
                            <p><?= htmlspecialchars($benefit['text'], ENT_QUOTES, 'UTF-8') ?></p>
                        </article>
                    <?php endforeach; ?>
                </div>
            </div>
        </section>

        <section class="section section--trust">
            <div class="container trust reveal">
                <div class="trust__copy">
                    <h2>Confidencialidade e prova de entrega embutidas</h2>
                    <p>
                        Cada corrida gera trilha operacional: retirada, deslocamento, entrega e confirmação.
                        Ideal para clínicas, laboratórios, escritórios e operações que exigem responsabilidade formal.
                    </p>
                </div>
                <ul class="trust__list">
                    <li>Protocolo digital de retirada e entrega</li>
                    <li>Observações e instruções por corrida</li>
                    <li>Histórico exportável para compliance</li>
                    <li>Atendimento comercial dedicado</li>
                </ul>
            </div>
        </section>

        <section id="contato" class="section section--contact">
            <div class="container contact">
                <header class="section__head reveal">
                    <h2>Leve o Camboriú Delivery para a sua empresa</h2>
                    <p>Conte-nos sobre a operação. Retornamos com proposta e demonstração do aplicativo.</p>
                </header>

                <?php if ($form['message'] !== ''): ?>
                    <div class="alert <?= $form['success'] ? 'alert--ok' : 'alert--err' ?>" role="status">
                        <?= htmlspecialchars($form['message'], ENT_QUOTES, 'UTF-8') ?>
                    </div>
                <?php endif; ?>

                <form class="contact-form reveal" method="post" action="#contato" novalidate>
                    <div class="form-grid">
                        <label>
                            <span>Nome</span>
                            <input type="text" name="name" required maxlength="120" value="<?= htmlspecialchars($form['old']['name'], ENT_QUOTES, 'UTF-8') ?>">
                        </label>
                        <label>
                            <span>Empresa</span>
                            <input type="text" name="company" required maxlength="160" value="<?= htmlspecialchars($form['old']['company'], ENT_QUOTES, 'UTF-8') ?>">
                        </label>
                        <label>
                            <span>E-mail corporativo</span>
                            <input type="email" name="email" required maxlength="160" value="<?= htmlspecialchars($form['old']['email'], ENT_QUOTES, 'UTF-8') ?>">
                        </label>
                        <label>
                            <span>Telefone / WhatsApp</span>
                            <input type="tel" name="phone" required maxlength="40" value="<?= htmlspecialchars($form['old']['phone'], ENT_QUOTES, 'UTF-8') ?>">
                        </label>
                        <label class="form-grid__full">
                            <span>Segmento</span>
                            <select name="segment">
                                <option value="">Selecione</option>
                                <?php foreach ($segments as $value => $label): ?>
                                    <option value="<?= htmlspecialchars($value, ENT_QUOTES, 'UTF-8') ?>" <?= $form['old']['segment'] === $value ? 'selected' : '' ?>>
                                        <?= htmlspecialchars($label, ENT_QUOTES, 'UTF-8') ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                        </label>
                        <label class="form-grid__full">
                            <span>Como podemos ajudar?</span>
                            <textarea name="message" rows="4" maxlength="2000" placeholder="Volume mensal, tipos de entrega, horários críticos..."><?= htmlspecialchars($form['old']['message'], ENT_QUOTES, 'UTF-8') ?></textarea>
                        </label>
                    </div>
                    <button class="btn btn--primary" type="submit" name="contact_submit" value="1">
                        Enviar solicitação
                    </button>
                </form>
            </div>
        </section>
    </main>

    <footer class="footer">
        <div class="container footer__inner">
            <div>
                <p class="footer__brand"><?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?></p>
                <p><?= htmlspecialchars(SITE_TAGLINE, ENT_QUOTES, 'UTF-8') ?></p>
            </div>
            <div class="footer__meta">
                <a href="mailto:<?= htmlspecialchars(SITE_EMAIL, ENT_QUOTES, 'UTF-8') ?>"><?= htmlspecialchars(SITE_EMAIL, ENT_QUOTES, 'UTF-8') ?></a>
                <span><?= htmlspecialchars(SITE_PHONE, ENT_QUOTES, 'UTF-8') ?></span>
                <span><?= htmlspecialchars(SITE_CITY, ENT_QUOTES, 'UTF-8') ?></span>
            </div>
            <p class="footer__copy">&copy; <?= date('Y') ?> <?= htmlspecialchars(SITE_NAME, ENT_QUOTES, 'UTF-8') ?>. Todos os direitos reservados.</p>
        </div>
    </footer>

    <script src="assets/js/main.js" defer></script>
</body>
</html>
