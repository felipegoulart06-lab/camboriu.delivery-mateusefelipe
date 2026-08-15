# SC Transporte Executivo

MVP SaaS multiempresa em Django para gestão de entregas especializadas. O Django é a aplicação oficial; os arquivos PHP na raiz foram preservados apenas como legado visual e não participam do fluxo.

## Os três tipos de conta

| Conta | Painel | O que faz |
| --- | --- | --- |
| **Admin master** do sistema | `/plataforma/` | Cadastra empresas contratantes e os acessos delas, cadastra entregadores com login, despacha corridas, cuida do financeiro e vê tudo |
| **Empresa contratante** | `/app/` | Faz o próprio cadastro, pede a retirada com um ou vários destinos, acompanha o rastreio, fatura em boleto e lê o termo de coleta |
| **Entregador** | `/motorista/` | Mini painel no celular com as corridas atribuídas, checklist antifraude, ganhos e disponibilidade |

O login é único (`/login/`): cada conta é levada ao painel dela depois de entrar, mesmo que alguém cole a URL de outro painel.

## Como o fluxo funciona

1. O **admin master** cadastra a empresa em `/plataforma/empresas/nova/` e cria o primeiro acesso dela.
2. Na primeira entrada, a **empresa preenche o próprio cadastro** em `/app/configuracoes/`: MEI, CNPJ ou CPF, endereço, contato e dia de vencimento preferido. Enquanto não concluir, todas as outras telas redirecionam para lá.
3. A empresa cria a solicitação em `/app/entregas/nova/`, com **um ou vários destinos**. Ela não escolhe motorista nem status, e o valor sai da tabela de preços.
4. A solicitação cai na **central de despacho** em `/plataforma/despacho/` e gera uma **notificação** com os dados cadastrais da empresa e o **PDF da solicitação** com esses dados no cabeçalho.
5. A central **aciona um entregador** e fala com ele na hora pelo link de WhatsApp. A empresa passa a ver o andamento.
6. O **entregador** entra em `/motorista/`, aceita a corrida e sai para a coleta. O aparelho dele envia a posição e a empresa acompanha no mapa.
7. Ao chegar, o entregador preenche o **checklist antifraude com 12 fotos obrigatórias**. Sem isso ele não libera o transporte.
8. Do checklist sai o **termo de coleta** imprimível, para anexar ao contrato de prestação de serviço.
9. Com a entrega concluída, a empresa com CNPJ ou MEI **fatura em boleto** escolhendo o vencimento, e o admin master acompanha recebimentos e repassa os entregadores no painel contábil.

## Executar no Windows

Requer Python 3.12+.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py reset_operation --yes
python manage.py runserver
```

Endereços: `http://127.0.0.1:8000/` (site), `/login/` (entrada única), `/app/` (empresa), `/plataforma/` (admin master e central), `/motorista/` (entregador) e `/admin/` (admin interno do Django).

Login inicial — o único acesso que existe depois do reset:

- **Admin master:** `master@camboriudelivery.local` / `Camboriu@123`

Empresas, entregadores, frota e o restante dos logins nascem pelo painel do admin master. Troque essa senha no primeiro acesso.

Para um banco local cheio de exemplos (só com `DEMO_MODE=True`):

```powershell
python manage.py seed_demo --master-email master@suaempresa.com --admin-email admin@suaempresa.com --password "OutraSenhaForte"
```

## Papéis

| Papel | Onde entra | O que faz |
| --- | --- | --- |
| `master` | `/plataforma/` | Tudo da central **mais** cadastro de empresas, de acessos de empresa, da equipe interna e de entregadores |
| `dispatcher` | `/plataforma/` | Aciona, confirma aceite e cancela corridas de todas as empresas; não cadastra empresas |
| `owner` / `admin` | `/app/` | Solicita entregas, acompanha rastreio, lê o termo de coleta, preenche o cadastro da empresa e fatura em boleto |
| `operator` | `/app/` | Solicita e acompanha entregas; não mexe no cadastro nem gera fatura |
| `viewer` | `/app/` | Somente consulta |
| `driver` | `/motorista/` | Aceita corridas, envia posição, preenche o checklist e ajusta a disponibilidade |

## O que o admin master administra

- **Empresas** (`/plataforma/empresas/`): cadastro, edição, suspensão e reativação. Empresa suspensa não entra no painel nem pede retirada, mesmo com a senha correta.
- **Acessos das empresas**: cria o login (o e-mail é o usuário), escolhe o papel e troca a senha quando o cliente esquece.
- **Entregadores** (`/plataforma/entregadores/`): a central consulta a frota; só o **admin master** cadastra o entregador e o login do app. Entregador sem login não pode ser acionado.
- **Equipe interna** (`/plataforma/equipe/`): outros admin masters e operadores da central.
- **Financeiro** (`/plataforma/financeiro/`): painel contábil, faturas, repasses e tabela de preços.
- **Notificações** (`/plataforma/financeiro/notificacoes/`): cada solicitação, faturamento e cadastro concluído, com os dados da empresa de origem.
- **Integração** (`/plataforma/integracao/`): manual operacional das entregas de alto padrão (cadastro, pedido, acionamento, as 12 fotos do checklist, destinos, incidentes e financeiro). O mesmo texto baixa em PDF em `/plataforma/integracao/manual.pdf` para apresentar à empresa e ao entregador.

Entregadores e veículos da operação ficam na empresa marcada como **transportadora da plataforma** (`is_platform`), criada pelo `bootstrap` (ou pelo `seed_demo`, em desenvolvimento). Só existe uma por banco. **Somente o admin master** cadastra entregadores e veículos; a empresa contratante e o próprio entregador não veem essas telas.

## Cadastro da empresa

O cadastro é a primeira coisa que a empresa faz. Em `/app/configuracoes/` o formulário vem dividido em blocos e cobra tudo o que a operação e o financeiro precisam. Só o proprietário ou o administrador da empresa mexe nessa tela.

| Bloco | Campos |
| --- | --- |
| Identificação | Nome fantasia, razão social, tipo de documento (CNPJ, MEI ou CPF), documento, inscrição estadual e municipal, regime tributário, data de abertura e ramo de atividade |
| Responsável | Nome, CPF, cargo, e-mail e telefone |
| Endereço | CEP, logradouro e número, complemento, bairro, cidade e UF |
| Financeiro | E-mail e telefone do financeiro e o dia de vencimento preferido |
| Documentos | Cartão CNPJ (ou documento do titular), contrato social/certificado MEI, comprovante de endereço e documento com foto do responsável |

- O documento passa por **conferência de dígito verificador**: CNPJ ou CPF errado não é aceito. CEP e telefone são normalizados na gravação.
- Inscrição estadual é obrigatória para CNPJ e MEI — quem não tem escreve `ISENTO`.
- Cadastro em CPF não precisa de contrato social nem de documento do responsável.
- Enquanto `registered_at` estiver vazio, `dashboard`, entregas e financeiro redirecionam para o cadastro.
- Ao concluir, o admin master recebe uma notificação com o documento e o endereço.
- O dossiê cadastral completo baixa em PDF nas configurações da empresa (`/app/configuracoes/dossie.pdf`) e na ficha da plataforma (`/plataforma/empresas/<id>/dossie.pdf`), com todos os dados e as fotos anexadas.
- Esses dados vão automaticamente no cabeçalho da notificação de cada solicitação, do PDF da solicitação e da fatura.
- **CNPJ e MEI faturam em boleto**; cadastros em **CPF** pagam por entrega (recibo em Pix ou dinheiro).

O admin master cria a empresa em `/plataforma/empresas/nova/` com os mesmos campos; os anexos ficam opcionais nessa tela porque quem envia os arquivos é a própria empresa. A ficha da empresa mostra o que ainda falta anexar.

## Cadastro do entregador

Somente o **admin master** cadastra. `/plataforma/entregadores/novo/` cria a ficha e o login do app na mesma tela, também em blocos: dados pessoais (nome, CPF, nascimento, RG e órgão emissor, nome da mãe), acesso ao app, contato e contato de emergência, endereço completo, habilitação e vínculo com a forma de repasse. O dossiê completo baixa em PDF na lista e na ficha (`/plataforma/entregadores/<id>/dossie.pdf`).

- CPF conferido por dígito verificador; nascimento precisa indicar 18 anos ou mais.
- CNH: número, categoria, registro, UF, emissão, primeira habilitação, vencimento e **EAR**. Sem a observação EAR o cadastro não passa, porque é o que autoriza transportar carga de terceiros.
- CNH e exame médico vencidos travam o cadastro; a lista de entregadores avisa o que vence nos próximos 30 dias.
- Repasse: chave Pix **ou** banco, agência e conta completos.
- Documentos obrigatórios: **CNH (frente ou CNH digital)**, **comprovante de residência** e **foto do entregador**. Opcionais: verso da CNH, antecedentes criminais, ASO/exame médico e comprovante bancário.

## Cadastro de veículo

Somente o **admin master** cadastra. `/app/veiculos/novo/` usa a mesma ficha para **moto, carro e utilitário**, cobrando de cada tipo o que faz sentido. O dossiê completo baixa em PDF na lista e na ficha (`/app/veiculos/<id>/dossie.pdf`).

| Bloco | Campos |
| --- | --- |
| Identificação | Tipo, placa e UF, RENAVAM, chassi, marca, modelo, ano de fabricação e do modelo, cor e combustível |
| Propriedade e uso | Proprietário do CRLV e documento, quilometragem, situação e vencimento do licenciamento |
| Seguro e rastreamento | Seguradora, apólice, vencimento, rastreador e empresa do rastreador |
| Carga | Capacidade em kg, litragem do baú, portas, carroceria, PBT, medidas do compartimento, refrigeração e trava |
| Documentos | CRLV digital, apólice e fotos frontal, traseira, da placa e do compartimento |

- **Moto** exige a litragem do baú. **Carro** exige portas e seguro completo. **Utilitário** exige portas, seguro, tipo de carroceria, PBT, as três medidas do compartimento e a foto da carga.
- Placa (padrão antigo ou Mercosul), RENAVAM e chassi são validados; licenciamento vencido não passa.
- Anexos obrigatórios em qualquer tipo: CRLV, foto frontal e foto da placa. Carro e utilitário somam a apólice.

Os anexos de empresas, entregadores e veículos **não ficam em URL pública**: saem por rotas que conferem o acesso antes de entregar o arquivo (`/plataforma/empresas/<id>/documento/<campo>/`, `/app/configuracoes/documento/<campo>/`, `/app/motoristas/<id>/documento/<campo>/` e `/app/veiculos/<id>/documento/<campo>/`). Valem fotos JPG, PNG, WEBP ou PDF, com o mesmo limite de `CHECKLIST_MAX_PHOTO_MB`.

## Entregas com vários destinos

Toda viagem tem o destino principal (o endereço de entrega) e pode ganhar até nove destinos adicionais no mesmo formulário. Os destinos são numerados em sequência (1, 2, 3…), aparecem no PDF, no despacho e no app do entregador — que abre a rota de cada um no mapa — e cada destino além do primeiro entra no preço.

## Financeiro e contabilidade

Tabela de preços (`/plataforma/financeiro/tabela-de-precos/`): valor base, valor por destino adicional, acréscimo de urgente e de crítica, e o percentual do entregador. Cada solicitação já nasce com o valor cobrado e o repasse calculados; o admin master pode ajustar entrega por entrega enquanto ela não estiver faturada.

O painel contábil (`/plataforma/financeiro/`) mostra:

- **Indicadores**: recebido no mês, a receber, vencido, repassado aos entregadores, a repassar e margem.
- **Gráfico** de receita contra repasse nos últimos seis meses, com o número de viagens de cada mês.
- **Tabela por entregador**: viagens, quanto gerou para a operação, ganhos, **já repassado**, repasse fechado a pagar e a repassar.
- **Tabela por empresa**: entregas, total das entregas, a faturar, recebido e em aberto.

**Faturas** (`/plataforma/financeiro/faturas/`): a empresa gera a fatura escolhendo as entregas e o vencimento em `/app/financeiro/faturar/`. O admin master gera o boleto no banco e cola a **linha digitável** (47 ou 48 dígitos) na fatura; ela aparece na hora no painel da empresa e no PDF. Depois é possível baixar como paga ou cancelar — no cancelamento as entregas voltam para a fila de faturamento. O sistema não se conecta a banco: a emissão do boleto continua sendo feita no internet banking.

**Repasses** (`/plataforma/financeiro/repasses/`): o admin master escolhe o entregador e o período, o sistema junta as entregas concluídas sem repasse, fecha o valor e registra o pagamento. O entregador vê os repasses e o saldo a receber no histórico dele.

## PDFs

Gerados com ReportLab, sempre com o cabeçalho cadastral da empresa solicitante (razão social, documento, inscrição estadual, endereço e contato):

- **Solicitação**: `/plataforma/financeiro/solicitacoes/<id>/pdf/` para o admin master e `/app/entregas/<id>/pdf/` para a empresa. Traz item, prioridade, coleta, todos os destinos, entregador, valor e situação do checklist.
- **Fatura**: `/plataforma/financeiro/faturas/<id>/pdf/` e `/app/financeiro/faturas/<id>/pdf/`, com as entregas do período, o total e a linha digitável quando o boleto já saiu.

## Mini painel do entregador

Mesmo casco dos outros painéis: **menu lateral esquerdo** com Início, Corridas, Histórico e Perfil, mais o status de disponibilidade e o botão de sair. No celular o menu vira uma gaveta (botão no topo); no tablet e no computador ele fica fixo à esquerda. O entregador vê apenas as corridas atribuídas a ele.

## Rastreio em tempo real

O mapa usa **Leaflet** com tiles do OpenStreetMap: é open source e não exige token nem chave de API. Para trocar por um provedor com chave, defina `MAP_TILE_URL` e `MAP_TILE_ATTRIBUTION`.

- O navegador do entregador envia a posição para `/motorista/corridas/<id>/posicao/` a cada `TRACKING_PING_SECONDS`.
- A empresa lê `/app/entregas/<id>/rastreio/dados/` no mesmo intervalo.
- A posição só é publicada enquanto a corrida está ativa (aceita, em coleta ou em trânsito). Depois de entregue ou cancelada o rastreio fecha.
- O GPS depende de permissão no aparelho e, fora do `localhost`, de HTTPS.

## Checklist antifraude da coleta

São 12 fotos obrigatórias, uma por etapa: local da coleta, documento, quatro ângulos do item, embalagem, lacre, item acomodado no veículo, placa, odômetro e responsável pela entrega. Junto vão a identificação de quem entregou o item, número do lacre, volumes, as declarações de conferência e a geolocalização do momento.

- O entregador não avança para "em trânsito" sem enviar o checklist completo, e não finaliza a entrega sem ele.
- As fotos não ficam em URL pública: saem por `/app/entregas/<id>/termo-de-coleta/foto/<id>/`, que confere o acesso antes de entregar o arquivo.
- `CHECKLIST_MAX_PHOTO_MB` limita o tamanho de cada imagem.

## Configuração

As configurações leem variáveis do ambiente. Se existir um `.env` na raiz, ele é lido na subida (leitor próprio, sem dependência nova) e o que já estiver definido no sistema tem prioridade. O `.env` está no `.gitignore` porque guarda a senha do banco; use o `.env.example` como modelo. Também dá para exportar tudo no PowerShell:

```powershell
$env:SECRET_KEY="uma-chave-longa-e-secreta"
$env:DEBUG="False"
$env:ALLOWED_HOSTS="camboriudelivery.com.br,app.camboriudelivery.com.br"
$env:CSRF_TRUSTED_ORIGINS="https://camboriudelivery.com.br,https://app.camboriudelivery.com.br"
$env:MEDIA_ROOT="D:\camboriu\media"
```

Em desenvolvimento os anexos podem ficar em `MEDIA_ROOT`. Em produção (Vercel) eles vão para o **R2 da Cloudflare**: crie um bucket privado, um token S3 com leitura e escrita, e cadastre `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` e `R2_BUCKET_NAME`. O download nunca usa URL pública do bucket — só as views autenticadas.

SQLite é o padrão apenas em desenvolvimento — com `DEBUG=False` e sem banco configurado o projeto se recusa a subir. Para PostgreSQL fora do Supabase seguem valendo `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST` e `POSTGRES_PORT`.

## Banco no Supabase

O banco de produção é o PostgreSQL do projeto Supabase. A conexão sai de `DATABASE_URL` (Project Settings › Database › Connection string › URI):

```powershell
$env:DATABASE_URL="postgresql://postgres.<ref>:<SENHA>@aws-0-<regiao>.pooler.supabase.com:5432/postgres"
python manage.py migrate
python manage.py harden_database --check
python manage.py bootstrap --nome "SC Transporte Executivo" --cnpj "00.000.000/0001-00" --master-email diretoria@suaempresa.com.br
```

- **Porta 5432** (conexão de sessão ou direta) para rodar `migrate`. **Porta 6543** é o pooler em modo transação: serve para a aplicação no dia a dia e o Django se ajusta sozinho a ele (sem conexão persistente e sem cursor no servidor).
- `sslmode=require` é aplicado sempre; o Supabase não aceita conexão em claro.
- Conexões são reaproveitadas por `CONN_MAX_AGE` (600s por padrão) com checagem de saúde antes do uso.
- Cada `migrate` termina blindando o banco (veja abaixo). Para rodar por fora: `python manage.py harden_database`.

### Por que a blindagem é obrigatória

O Supabase publica o schema `public` numa API REST e entrega a chave pública junto com o projeto. Sem tratamento, CPF, CNH, contrato social e fotos do checklist ficariam legíveis por qualquer um com essa chave, sem passar pelo Django. Por isso `core/db_security.py`:

- liga **RLS em todas as tabelas** (sem policy nenhuma, o que fecha a leitura para todo mundo que não tenha BYPASSRLS);
- **revoga** tabelas, sequências, funções e o próprio schema dos papéis `anon` e `authenticated`;
- repete a revogação em `DEFAULT PRIVILEGES`, para as tabelas que as próximas migrações criarem.

Quem fala com o banco é só o Django, com o usuário do `DATABASE_URL`. Se um dia o projeto passar a usar a API do Supabase direto do navegador, será preciso criar policies explícitas para cada tabela exposta.

## Primeira carga com dados reais

```powershell
python manage.py reset_operation --yes
```

Isso apaga empresas, entregadores, frota, entregas e todos os logins, e recria só a transportadora com o admin master (`master@camboriudelivery.local` / `Camboriu@123`). O cadastro de clientes e da frota é feito em `/plataforma/`.

- `bootstrap` cria (ou atualiza) a transportadora e o admin master sem apagar o resto. Documento passa pelo dígito verificador; senha pelos validadores. Sem `--senha`, sorteia uma senha forte e a exibe uma única vez.
- `seed_demo` só funciona com `DEMO_MODE=True`; em produção ele se recusa a rodar.
- Com `DEMO_MODE=False` a tela de login não lista contas nem senhas.

## Deploy na Vercel

O Django sobe como função serverless em São Paulo (`gru1`), no mesmo continente do Supabase. A Vercel detecta o `manage.py` e usa `config/wsgi.py`. Arquivos: `vercel.json`, `.python-version` (3.12) e `config/wsgi.py`.

1. Publique o repositório no GitHub e importe o projeto em [vercel.com/new](https://vercel.com/new). Framework: **Django** (ou deixe a detecção automática).
2. Em **Settings → Environment Variables**, cadastre pelo menos `SECRET_KEY`, `DATABASE_URL` e as chaves do R2. No **runtime** elas são obrigatórias; no **build** o Django aceita ficar sem elas (a Vercel lê o `manage.py` antes de injetar segredo de runtime). Marque como disponíveis em Production e Preview:

| Variável | Valor |
| --- | --- |
| `SECRET_KEY` | a mesma chave longa do `.env` local |
| `DEBUG` | `False` |
| `DEMO_MODE` | `False` |
| `DATABASE_URL` | URI do pooler **porta 6543** (`...pooler.supabase.com:6543/postgres`) |
| `PGSSLMODE` | `require` |
| `ALLOWED_HOSTS` | `.vercel.app` e, depois, o domínio próprio |
| `CSRF_TRUSTED_ORIGINS` | `https://*.vercel.app` e `https://seudominio.com` |
| `R2_ACCOUNT_ID` | Cloudflare → R2 → Account ID (barra lateral) |
| `R2_ACCESS_KEY_ID` | token da API S3 do R2 (Object Read & Write) |
| `R2_SECRET_ACCESS_KEY` | o segredo desse token |
| `R2_BUCKET_NAME` | nome do bucket privado (ex.: `camboriu-media`) |

A Vercel injeta `VERCEL`, `VERCEL_URL` e `VERCEL_PROJECT_PRODUCTION_URL`. O Django acrescenta esses hosts sozinho e, na Vercel, troca a porta 5432 do pooler pela 6543 (modo transação) e desliga conexão persistente.

3. Deploy. O `collectstatic` e a inspeção do `manage.py` rodam no build sem Postgres. No request, sem `SECRET_KEY`, `DATABASE_URL` ou R2 a aplicação não sobe.
4. Domínio próprio: Settings → Domains, depois some o host em `ALLOWED_HOSTS` e a origem `https://...` em `CSRF_TRUSTED_ORIGINS`.

A Vercel **não guarda arquivo em disco**. Fotos do checklist, CNH e contrato social vão para um **bucket privado no R2 da Cloudflare**. Sem as chaves do R2 a função responde 503. O download continua passando pelas views autenticadas — o bucket não é público.

O plano Hobby limita a função a 10 segundos; checklist com 12 fotos pede o plano Pro (`maxDuration` 60 em `vercel.json`). HTTPS já vem na Vercel, então a geolocalização do entregador funciona.

## Segurança e permissões

- Todo acesso operacional das views é filtrado pela empresa do usuário; superusuários e a equipe da plataforma são globais.
- `viewer` consulta; `operator` gerencia entregas; `admin` e `owner` gerenciam entregas, o cadastro da empresa e o faturamento; `dispatcher` despacha e lê o financeiro; `master` cadastra empresas, entregadores, veículos, acessos, tabela de preços, boletos e repasses; `driver` só vê as corridas dele e baixa o PDF da solicitação **sem** valor do produto nem preço da entrega.
- Faturas e PDFs são filtrados pela empresa: uma empresa não abre a fatura nem a solicitação de outra.
- Senhas criadas pelo painel passam pelos validadores do Django (mínimo de 10 caracteres, senha comum, só números, semelhança com o usuário) e são guardadas com **Argon2** quando a biblioteca está instalada.
- **Tentativas de login** são contadas por conta e por origem: passando de `LOGIN_ATTEMPT_LIMIT` (8) dentro de `LOGIN_ATTEMPT_WINDOW_SECONDS` (15 min), o login responde 429 até a janela virar. Acerto zera o contador. Com mais de um processo web, configure `REDIS_URL` para o contador ser compartilhado.
- Acertos e recusas de login vão para o log (`camboriu.auth`), junto com os avisos de `django.security`.
- Cookies de sessão e CSRF são HttpOnly, SameSite=Lax e, fora do modo de desenvolvimento, Secure. A sessão expira em 12 horas.
- Cabeçalhos: HSTS com preload, `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin` e COOP `same-origin`. `python manage.py check --deploy` passa sem avisos.
- No banco, RLS ligada em tudo e a API pública do Supabase sem acesso ao schema (veja "Banco no Supabase").
- Alterações usam POST com CSRF. Solicitações de entrega **não podem ser excluídas**: o registro permanece e, se a corrida for encerrada, só o status muda para cancelada. Cancelar fatura, desfazer repasse e suspender empresa pedem uma segunda confirmação na tela.
- O admin Django é uma interface interna da plataforma e tem visão global; não deve ser entregue aos clientes.
- CNPJ, CPF, CNH, contatos, endereços, coordenadas, fotos do checklist e os documentos anexados aos cadastros são dados sensíveis. O MVP não os criptografa em repouso; restrinja backups e acesso ao banco e ao `MEDIA_ROOT`.
- Documento de entregador, de veículo e de empresa só é baixado por quem pertence à mesma empresa (ou pela equipe da plataforma), sempre por view — nunca pela pasta de mídia.

## Performance

- Conexões PostgreSQL reaproveitadas (`CONN_MAX_AGE`) com checagem de saúde; no pooler em modo transação o Django desliga sozinho o que não funciona lá.
- Sessões lidas do cache e gravadas no banco (`cached_db`), o que tira uma consulta de cada clique.
- Índices para as telas que mais rodam: fila do despacho (`status` + data), corridas do entregador (`driver` + `status`), linha do tempo da entrega, faturas por empresa e repasses por entregador.
- Estáticos com hash no nome em produção (`ManifestStaticFilesStorage`), o que permite cache longo no navegador. Rode `collectstatic` no deploy.

## Verificações

```powershell
python manage.py test                      # 205 testes
python manage.py check
python manage.py check --deploy
python manage.py harden_database --check   # RLS e permissões no Supabase
python manage.py verify_database           # ciclo completo no banco configurado, com rollback
python smoke_check.py                      # abre as telas dos painéis no banco configurado
```

A suíte cobre, além dos testes de cada app:

| Arquivo | O que garante |
| --- | --- |
| `core/test_access_matrix.py` | Cada uma das 78 rotas aberta pelos 9 tipos de conta, com guarda que falha se alguma URL do projeto ficar fora da matriz. |
| `core/test_journey.py` | Jornada completa em um banco zerado: master cria empresa e equipe, empresa cadastra e solicita, central despacha, entregador coleta com checklist e entrega, faturamento, boleto, pagamento e repasse. |
| `core/test_business_rules.py` | Regras que protegem a operação: transições de status, ação repetida, dado de outra empresa, foto pesada, prazo antes da coleta, placa repetida. |
| `core/test_operation_screens.py` | Filtros, buscas e indicadores das listas e dos painéis, incluindo rastreamento em tempo real e isolamento entre empresas. |
| `core/test_configuration.py` | Validadores de documento, limites de anexo, leitura do `.env`, banco serverless e ajustes de segurança e sessão. |
| `core/test_pdf_documents.py` | Geração dos PDFs (solicitação, fatura, recibo e manual) inclusive com texto hostil e entrega com dez destinos. |
| `core/test_empty_operation.py` | Todas as telas dos três painéis e o admin Django abertos com o banco recém-zerado, sem quebrar. |

`manage.py test` roda sempre em SQLite, mesmo com `DATABASE_URL` apontando para o Supabase: a suíte cria e destrói um banco próprio, e o pooler sempre devolve o banco do projeto. Para exercitar o PostgreSQL de verdade existe o `verify_database`, que grava um ciclo inteiro da operação (empresa, entregador, veículo, entrega com destino extra, checklist, fatura, repasse e notificação), confere as consultas dos três painéis, verifica que a entrega continua impossível de excluir e desfaz tudo — no fim ele compara as contagens de antes e depois e reclama se sobrou qualquer registro.
