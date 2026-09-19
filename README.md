# Corretor OPI

Sistema Flask mobile-first para a organização da Olimpíada Picuiense de Informática. Fotografa o cartão Fundamental de 30 questões, lê CPF e respostas, permite revisão humana e salva a quantidade de acertos no SQLite. Não há cadastro de usuários/alunos nem integração externa ativa.

## Iniciar

Python 3.10 ou superior. Na raiz do projeto:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
# Opcional, recomendado em máquinas sem GPU: evita baixar os pacotes CUDA.
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
python scripts/setup_local.py
python scripts/prepare_ocr.py
flask --app run.py init-db
python run.py
```

`setup_local.py` pede usuário e senha sem ecoar a senha, gera a chave de sessão e grava **somente o hash** em `.env`, com permissão 600. Não sobrescreve uma configuração existente. A senha nunca entra em argumentos de comandos.

Alternativamente, copie `.env.example` para `.env` e configure:

- `SECRET_KEY`: gere com `python -c "import secrets; print(secrets.token_hex(32))"`.
- `ADMIN_USERNAME`: usuário da organização.
- `ADMIN_PASSWORD_HASH`: gere com `python -c "from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass('Senha: ')))"`.
- `DEBUG_OMR=false`: habilite `true` apenas durante calibração/desenvolvimento.
- `COOKIE_SECURE=false`: para HTTP na rede local; use `true` quando disponibilizar via HTTPS.
- `PORT=5000`: porta do servidor.

Hashes com `$` podem ser colados diretamente no `.env`; não os passe sem proteção por um shell. O programa recusa iniciar com `SECRET_KEY=change-me`, chave ausente ou senha sem formato de hash Werkzeug. O servidor **não ativa debugger**, mesmo em desenvolvimento.

`prepare_ocr.py` baixa os modelos do EasyOCR uma vez em `instance/ocr-models/`. Depois, o reconhecimento funciona localmente, sem internet e sem enviar CPF ou imagens. Se os modelos estiverem ausentes, o sistema solicita preenchimento manual. O primeiro carregamento do OCR consome memória e pode levar alguns segundos.

Abra `http://localhost:5000`. SQLite é inicializado explicitamente pelo comando `init-db`, que não apaga os dados existentes. O banco fica em `instance/database.db`. Nenhum gabarito é criado automaticamente.

## Acessar pelo celular

Conecte computador e celular à mesma rede Wi-Fi. Execute `python run.py`; o servidor escuta em `0.0.0.0:5000`. Descubra o IP do computador (`hostname -I` no Linux) e abra, por exemplo, `http://192.168.1.20:5000` no celular. Libere a porta 5000 no firewall local, se necessário.

A captura usa `input type=file`, `accept=image/...` e `capture=environment`, indicando a câmera traseira. O navegador/sistema operacional pode oferecer também a galeria. Não depende de `getUserMedia`, portanto funciona no HTTP local. Envie JPEG, PNG ou WebP; HEIC não é aceito. O navegador preserva a proporção, limita o maior lado a 2000 pixels e converte para JPEG com qualidade entre 82% e 92%, buscando até 3,5 MB. O backend limita a requisição completa a 4 MB e a imagem a 25 megapixels; imagens são orientadas pelo EXIF, redimensionadas e regravadas sem metadados.

O servidor Flask embutido serve para desenvolvimento/rede de testes. Para exposição pública, use servidor WSGI, HTTPS e `COOKIE_SECURE=true`. Não exponha o debugger. Mantenha banco e temporários com acesso restrito e faça backup protegido do SQLite, pois ele contém CPF.

## Uso

1. Entre com as credenciais do `.env`.
2. Em **Gabaritos**, crie a prova e informe as 30 alternativas corretas A–E.
3. Toque em **Tirar foto de cartão**, escolha a prova e fotografe a folha inteira.
4. Confira a foto. Use **Tirar novamente** ou **Usar foto e processar cartão**.
5. Aguarde o indicador de processamento. O botão fica desabilitado enquanto a requisição está em andamento.
6. Confira o CPF e todas as respostas. A foto pode ser expandida na revisão. CPF reconhecido com segurança aparece mascarado; expanda a edição para conferi-lo por inteiro.
7. Ajuste as respostas. O contador muda imediatamente e identifica alterações manuais. Sem JavaScript, o servidor recalcula na etapa seguinte.
8. Revise CPF mascarado e quantidade de acertos, então confirme.
9. Consulte os resultados em **Histórico**. Datas são exibidas explicitamente em UTC.

CPF inválido impede a confirmação até ser corrigido. Uma leitura de CPF com lacunas usa `?`, nunca inventa dígitos. A interface indica `válido`, `inválido`, `incerto` ou `não detectado`. A validação matemática não prova a identidade da pessoa: confira a foto.

## Modelo e calibração

O **Frame 1.pdf fornecido** é a fonte de verdade. O arquivo foi copiado de Downloads para a raiz e inspecionado visualmente antes da implementação. A página tem **433 × 613 pontos** (proporção 0,70636); a imagem normalizada tem **1299 × 1839 pixels**.

- CPF: y=164–182 pt; nove células de 13 pt a partir de x=17, seguidas por duas em x=147 e x=160. Há um espaço entre o nono e o décimo dígito: a região não é dividida uniformemente.
- Questões: três blocos de dez, deslocamento horizontal de 129 pt. Bolhas com limites de 13 × 13 pt, iniciando em x=61, 77, 93, 109, 125 pt e y=373 pt; incremento vertical de 19 pt.
- Questões de exemplo nas instruções são excluídas.

Veja [a imagem de calibração](docs/template-validation.png), com as 11 células e as 150 alternativas sobre o cartão original. As posições foram medidas nos elementos vetoriais do PDF e verificadas visualmente. O JSON guarda coordenadas relativas, sem espalhar posições pelo código.

Arquivos:

- `app/omr/templates/opi_fundamental_2026.json`: regiões e thresholds.
- `app/omr/reference.png`: modelo vazio público usado para alinhamento (não é foto de participante).
- `docs/card-reference.png`: renderização de referência do PDF.
- `scripts/calibrate_template.py`: reproduz o JSON e a sobreposição a partir das medidas documentadas.

Para regenerar a renderização, instale a ferramenta de desenvolvimento `pymupdf` e execute:

```bash
python -c "import pymupdf; d=pymupdf.open('Frame 1.pdf'); d[0].get_pixmap(matrix=pymupdf.Matrix(3,3),alpha=False).save('docs/card-reference.png')"
python scripts/calibrate_template.py
cp docs/card-reference.png app/omr/reference.png
```

Alterar o modelo exige medir suas regiões, criar uma nova referência e revisar o carregador. Não basta renomear um arquivo. O primeiro modelo é deliberadamente o único autorizado no carregador atual.

## Reconhecimento

`image_processor.py` separa carregamento, busca de contorno, alinhamento, normalização, threshold e debug. Contornos quadrilaterais são procurados com grayscale, blur, Canny e `findContours`. Como o modelo não tem marcadores fiduciais, o alinhamento final usa correspondências ORB com a referência e homografia RANSAC. Isso também trata rotação e verifica a identidade do cartão. Exige quantidade e distribuição espacial mínimas de correspondências e rejeita bordas ausentes/perspectiva incompatível. Não usa a foto inteira como fallback silencioso.

Depois do alinhamento, normaliza iluminação e aplica Otsu. OMR mede a proporção de pixels escuros dentro de uma elipse interna de cada bolha, excluindo a borda impressa. As letras A–E já presentes geram aproximadamente 14–23% de tinta no modelo vazio; os limiares toleram esse fundo.

No JSON, `min_fill=0.60`, `multiple_mark=0.48`, `min_difference=0.18`, `blank_max=0.40`:

- duas alternativas acima de `multiple_mark`: `multiple`;
- máximo abaixo de `blank_max`: `blank`;
- máximo abaixo de `min_fill` ou diferença insuficiente: `ambiguous`;
- caso contrário: `detected`.

Só `detected` com alternativa igual ao gabarito soma acerto. Todos os outros estados são erro. Não há nota de 0 a 10. Os parâmetros precisam de avaliação com fotos reais antes de uso operacional.

`cpf_detector.py` recorta individualmente as 11 células, remove as bordas e usa EasyOCR com `allowlist=0123456789`. Como as células já estão localizadas, usa o reconhecedor diretamente, sem detector de texto. Só aceita exatamente um dígito com confiança mínima de 80%. `EasyOCRDigitRecognizer` é substituível; `detect_cpf` recebe o reconhecedor como dependência. A biblioteca não é treinada especificamente para manuscritos da OPI: letras ou dígitos mal escritos podem exigir revisão. `cpf_validator.py` centraliza normalização, cálculo dos dois verificadores e máscara.

## Dados, revisão e duplicidade

Modelos simples: `Exam`, `AnswerKey` e `Correction`, sem tabela User. Respostas e gabaritos são JSON. A correção guarda CPF normalizado (11 dígitos), contadores, alternativa/status original, alternativa/status revisado, indicação manual por questão, revisão manual geral e cópia do gabarito usado. Editar um gabarito não altera resultados históricos.

Duplicidade significa **mesma prova + mesmo CPF**. A abordagem é salvar uma **nova versão**, com confirmação explícita; nunca substituir silenciosamente a anterior. A tela mostra as correções existentes. Uma chave única de submissão impede que o reenvio da mesma confirmação crie uma segunda correção. Uma nova captura pode criar uma nova versão mediante aviso.

A revisão usa um rascunho JSON no servidor; CPF e respostas não entram no cookie de sessão. O cookie contém apenas autenticação, CSRF, identificadores e token aleatório de trabalho. Todas as páginas e fotos privadas exigem login; formulários POST têm proteção CSRF e respostas privadas usam `Cache-Control: no-store`. A sessão dura até oito horas. Recursos estáticos de estilo e JavaScript são públicos, sem dados pessoais.

As fotos não são armazenadas no banco nem no histórico. Temporários ficam em `instance/work/<token>/`, nunca em `static/`. Confirmação, descarte, nova captura e logout removem a pasta inteira. Trabalhos abandonados expiram após uma hora de inatividade e são removidos na próxima requisição ou com:

```bash
flask --app run.py cleanup-temp
```

Para garantir limpeza mesmo sem tráfego, agende esse comando no cron a cada 15 minutos. Sem requisições/agendamento, arquivos expirados persistem até a próxima execução da limpeza. O rascunho também contém CPF e é eliminado junto com a foto.

`DEBUG_OMR=true` cria somente temporários de desenvolvimento: `01_original.jpg`, `02_document.jpg`, `03_warped.jpg`, `04_threshold.jpg`, `05_cpf_cells.jpg`, `06_answer_regions.jpg`, `07_result.jpg`. A última inclui regiões e estados detectados. São apagados com o trabalho e não têm rota pública. Os PNGs de `docs/` usam apenas o cartão vazio e dados sintéticos de teste.

Logs indicam etapas e respostas das questões, sem CPF completo. Parâmetros SQL são ocultados em erros do SQLAlchemy. Não adicione logging de corpos de requisição, rascunhos ou objetos de correção.

## Integrações futuras

`StudentProvider.find_by_cpf(cpf)` encapsula consulta ao aluno. Hoje, `MockStudentProvider` devolve a mensagem de integração não configurada. A confirmação chama somente essa abstração.

`ResultIntegration.send_result(correction)` prepara o contrato de envio; `NoOpResultIntegration` não transmite nada e retorna `pending`. A confirmação salva no SQLite **sem disparar envio**. `external_sync_status` começa `pending`, `external_sync_id` é nulo. Uma futura implementação poderá usar `synced` e `failed`, quando conhecermos autenticação, payload, endpoint e política de repetição do sistema externo. As implementações são injetadas em `app.extensions`.

## Organização

```text
app/
  __init__.py          # fábrica, configuração, CSRF, limpeza e comandos
  routes/              # login, gabaritos, captura/revisão, histórico
  models/              # SQLite via Flask-SQLAlchemy
  services/            # imagem, CPF, OMR, correção
    integrations/      # contratos e implementações sem integração real
  omr/                 # template, referência e conversão de coordenadas
  templates/           # Jinja2
  static/              # CSS e JavaScript simples
scripts/               # configuração, modelos OCR e validação visual
instance/              # banco e arquivos privados, ignorados pelo Git
tests/                 # testes pytest
```

Flask/Jinja2, Flask-SQLAlchemy, python-dotenv, Werkzeug (dependência do Flask), OpenCV headless, NumPy, Pillow, EasyOCR e pytest. `opencv-python-headless` fornece `cv2` sem bibliotecas gráficas desnecessárias no servidor. Sem tarefas distribuídas: o processamento é síncrono, adequado ao fluxo pequeno da organização.

## Validação e testes

```bash
pytest -q
```

Testes cobrem CPF, template, coordenadas, fill ratio, quatro estados OMR, comparação, revisão, duplicidade, autenticação/CSRF, upload inválido, limite de arquivo, CPF inválido, fluxo de confirmação, snapshot do gabarito e limpeza. Testes de imagem usam o cartão real vazio, marcas sintéticas e transformação de perspectiva em quatro orientações.

Para o teste de navegador (dependência **somente de desenvolvimento**):

```bash
pip install playwright
python scripts/check_mobile.py
```

Usa Google Chrome em `/usr/bin/google-chrome`, banco temporário e credenciais fictícias internas ao teste. Verifica o fluxo completo, contador imediato e ausência de rolagem horizontal em **360×800, 390×844 e 412×915**. Salva capturas em `docs/mobile-*.png`. Nenhum banco operacional é modificado.

O teste real do EasyOCR pode ser repetido após baixar os modelos:

```bash
python scripts/check_ocr.py
```

Ele reconhece 11 dígitos impressos sintéticos dentro das células e verifica o CPF; não representa uma medição de acurácia em manuscritos.

## Limitações atuais

- O modelo foi calibrado no PDF e testado com imagens sintéticas. Ainda é necessário validar uma amostra representativa de fotos reais, impressoras, canetas, iluminação e manuscritos antes de confiar na automação em uma aplicação oficial.
- Não há garantia de leitura de todos os CPFs manuscritos. Dúvidas nunca são preenchidas com valores inventados; revisão humana é obrigatória antes de salvar.
- Sombras fortes, desfoque, papel curvo, cortes e perspectiva excessiva podem impedir alinhamento ou produzir ambiguidades. Fotografe novamente nesses casos.
- Não reconhece nome, escola, assinatura ou nota manuscrita; não envia resultados externos.
- O SQLite atende uso pequeno. Não há múltiplos usuários, filas, dashboard ou banco de alunos.
# corrigiAi
# corrigiAi


## Deploy na Vercel

1. Conecte o repositório GitHub à Vercel e selecione a raiz do projeto.
2. Use a detecção Flask, sem Build Command customizado. O link `public/static` expõe os arquivos existentes de `app/static` no caminho `/static` para a CDN, sem duplicar CSS/JavaScript nem mudar o layout. Preserve esse link simbólico no Git. `index.py` exporta `app = create_app()`; `run.py` continua disponível para execução local, sem debugger.
3. Configure Environment Variables antes do deploy:

   ```dotenv
   SECRET_KEY=<chave aleatória forte>
   ADMIN_USERNAME=admin
   ADMIN_PASSWORD_HASH=<hash Werkzeug scrypt: ou pbkdf2:>
   DATABASE_URL=<URL do banco>
   COOKIE_SECURE=true
   DEBUG_OMR=false
   ```

   Gere o hash conforme a seção Iniciar; não configure senha em texto puro. `.env.example` não contém segredos e `.env` está ignorado pelo Git. Localmente, `DATABASE_URL` vazio usa `instance/database.db`. URLs SQLite relativas são resolvidas pelo Flask-SQLAlchemy dentro de `instance`, portanto evite `sqlite:///instance/database.db` (duplicaria `instance`).

4. Somente para **TESTE temporário**, configure `DATABASE_URL=sqlite:////tmp/database.db`.

**SQLite em /tmp NÃO É PERSISTENTE NA VERCEL.** Dados e tabelas podem desaparecer entre execuções, instâncias e deploys. Para produção com histórico permanente, utilize banco externo persistente, por exemplo PostgreSQL, com `DATABASE_URL` e o driver SQLAlchemy correspondente instalado. Não há migração automática de dados.

Inicialize as tabelas explicitamente com `flask --app index init-db`, em um ambiente com acesso ao banco configurado. O comando usa `create_all`, não apaga tabelas nem dados. Executá-lo localmente contra PostgreSQL externo prepara esse banco; executá-lo localmente ou no build contra `/tmp/database.db` **não prepara o SQLite da função em execução**. Um teste SQLite completo requer inicialização na mesma instância temporária; não há endpoint público nem inicialização automática do banco. Na ausência de tabelas, páginas que consultam o banco mostram uma mensagem com orientação para inicialização.

Com `VERCEL` definido, fotos e rascunhos usam `/tmp/work` e o diretório dos modelos é `/tmp/ocr-models`. Fotos são comprimidas no celular antes do envio, preservando a proporção e detalhes para OCR/OMR. O backend aceita requisições de até 4 MB, incluindo o formulário. Sem JavaScript, envie uma foto já abaixo desse limite. `DEBUG_OMR=false` não gera imagens de depuração. Ao confirmar, descartar ou sair, o trabalho temporário é eliminado; a limpeza remove trabalhos expirados após uma hora quando há novas requisições. Só dados da correção vão para o banco.

**Limitação do fluxo em várias requisições:** `/tmp` não é compartilhado entre instâncias e pode desaparecer. Uma foto enviada pode não estar disponível na prévia, processamento ou revisão seguinte; nesse caso será necessário repetir a captura. Um banco externo resolve a persistência do histórico, mas não essa limitação dos rascunhos. Garantir esse fluxo em produção serverless exigiria armazenamento temporário compartilhado com expiração e exclusão, uma adaptação adicional não implementada aqui.

EasyOCR é carregado sob demanda, apenas no reconhecimento do CPF; login, início, gabaritos e histórico não carregam EasyOCR/PyTorch. O reconhecedor é reutilizado por instância, com trava para inicialização concorrente. Downloads automáticos permanecem desativados (`download_enabled=False`), inclusive nos cold starts. O download é explícito: `python scripts/prepare_ocr.py` prepara os modelos em `instance/ocr-models` localmente ou `/tmp/ocr-models` com `VERCEL` definido. Importar esse script não carrega OCR nem baixa arquivos. Na Vercel, `/tmp/ocr-models` começa vazio: sem provisionar os modelos nessa instância, o sistema pede CPF manualmente. Modelos locais em `instance` não são automaticamente transferidos para `/tmp`.

EasyOCR/PyTorch têm dependências grandes; carregamento sob demanda reduz trabalho no startup, mas não o tamanho do pacote instalado. O deploy ainda depende dos limites de tamanho, memória e duração da função. Se o pacote exceder o limite contratado, será necessário um ambiente compatível com esses recursos ou separar o OCR. Nenhuma garantia de deploy real é inferida dos testes locais.

Referências: [Flask na Vercel](https://vercel.com/docs/frameworks/backend/flask) e [limites das funções](https://vercel.com/docs/functions/limitations).

### Tamanho do pacote de deploy

`.vercelignore` e `vercel.json` excluem ambientes virtuais, dados locais e arquivos de teste/documentação do deploy. Essas exclusões não removem as dependências instaladas a partir de `requirements.txt`: EasyOCR depende de PyTorch, cuja instalação padrão pode trazer bibliotecas NVIDIA de vários GB mesmo com `gpu=False` no código. Lazy loading não reduz o tamanho do pacote. Se o build ultrapassar 500 MB, essas exclusões sozinhas não garantem a solução; é necessário adequar a instalação do OCR ou executá-lo em outro ambiente.

## Docker

Requisitos: Docker Engine e plugin Docker Compose (`docker compose version`), internet
no primeiro build e espaço para as dependências CPU do PyTorch e modelos EasyOCR.
A imagem usa Python 3.12 slim, OpenCV headless e somente `libgomp1` como biblioteca
Linux adicional. Não instala CUDA nem servidor gráfico.

Copie `.env.example` para `.env` (sem sobrescrever uma configuração existente).
Gere `SECRET_KEY` e `ADMIN_PASSWORD_HASH` pelos comandos da seção **Iniciar**.
Se não tiver Python local, gere os valores depois de `docker compose build`:

```bash
docker compose run --rm --no-deps web python -c 'import secrets; print(secrets.token_hex(32))'
docker compose run --rm --no-deps web python -c 'from getpass import getpass; from werkzeug.security import generate_password_hash; print(generate_password_hash(getpass("Senha: ")))'
```

Cole os valores no `.env`. **Coloque o hash entre aspas simples**, assim:
`ADMIN_PASSWORD_HASH='<hash gerado>'`. Isso preserva os caracteres `$` durante a
[leitura pelo Compose](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/).
Não use o texto de exemplo como credencial. Proteja o arquivo com `chmod 600 .env`.
Use `COOKIE_SECURE=false` para HTTP local. Compose desativa `FLASK_DEBUG` e `DEBUG_OMR`.

`DATABASE_URL` vazio usa `sqlite:////app/data/database.db` no Compose. Se preencher,
use esse caminho para o Docker; uma URL relativa como `sqlite:///database.db` aponta
para `instance` e **fica fora do volume persistente**. Fora do Docker, deixe vazio
ou use `sqlite:///database.db` para continuar com o banco local. Bancos locais
existentes não são copiados nem migrados automaticamente para o volume.

```bash
docker compose up --build
# Em outro terminal, crie somente as tabelas ausentes:
docker compose exec web flask --app run.py init-db
```

Abra `http://localhost:8000`. Para executar em segundo plano:

```bash
docker compose up -d --build
docker compose exec web flask --app run.py init-db
docker compose ps
docker compose logs -f web
```

Gunicorn executa `app:create_app()` em `0.0.0.0:8000`, com **um worker síncrono**,
para limitar memória do OCR e concorrência de escrita no SQLite. O timeout de
180 segundos tolera o primeiro carregamento do OCR; uma correção ocupa esse worker.
O endpoint público `/health` retorna apenas `{"status":"ok"}` e alimenta o
healthcheck, sem consultar banco ou carregar OCR. Durante processamento demorado,
o healthcheck pode atrasar; ele verifica disponibilidade HTTP, não prontidão do banco.
Veja a documentação de [application factory do Gunicorn](https://docs.gunicorn.org/en/21.0.1/run.html).

O processo usa UID/GID 10001, sem root. O volume nomeado `corrigiai_data` é montado
em `/app/data`; o nome real recebe o prefixo do projeto Compose. Mantenha o mesmo
nome de projeto/diretório nos próximos deploys para reutilizar o volume.
Volumes novos recebem as permissões do diretório da imagem. Ao restaurar arquivos
ou usar um bind mount, garanta escrita pelo UID/GID 10001.

Fotos, rascunhos e debug ficam em `/tmp/corrigiai`, um tmpfs limitado a 256 MB,
separado do banco. A limpeza existente permanece: confirmação, descarte, logout
ou expiração. Parar o container também elimina esses temporários; revisões em
andamento precisam ser refeitas. Dimensione esse limite conforme o uso.
`WORK_DIR` e `OCR_MODEL_DIR` são configuráveis fora do Compose, preservando os
padrões locais e da Vercel.

Os modelos OCR são baixados explicitamente em `/app/ocr-models` durante o build,
sem credenciais da aplicação. Ficam na imagem e são reutilizados em cada container;
rebuilds podem repetir o download se a camada de cache for invalidada. Não há
volume de fotos ou de modelos junto ao SQLite. O reconhecedor continua lazy:
somente a correção carrega EasyOCR, reutilizando-o no processo. Requisições nunca
baixam modelos. O primeiro build precisa acessar PyPI, PyTorch e o servidor dos
modelos; se o download falhar, o build falha em vez de entregar OCR incompleto.

Parar e reconstruir:

```bash
docker compose down
docker compose up -d --build
```

Esses comandos preservam o volume e seus gabaritos, correções e histórico.
**ATENÇÃO: `docker compose down -v` remove os volumes e pode apagar todo o SQLite.**
Não o use na operação normal. Remover manualmente volumes também apaga os dados.

### Backup do SQLite

Use a API de backup do SQLite para obter uma cópia consistente, inclusive com a
aplicação em execução. Para o caminho padrão do Docker:

```bash
mkdir -p backups
chmod 700 backups
docker compose exec -T web python -c 'import sqlite3; src=sqlite3.connect("file:/app/data/database.db?mode=ro", uri=True); dst=sqlite3.connect("/tmp/database-backup.db"); src.backup(dst); dst.close(); src.close()'
docker compose cp web:/tmp/database-backup.db backups/database-backup.db
chmod 600 backups/database-backup.db
docker compose exec -T web python -c 'from pathlib import Path; Path("/tmp/database-backup.db").unlink()'
```

Esse exemplo sobrescreve o backup anterior; renomeie a cópia para guardar versões.
Proteja os backups, pois contêm CPF, e mantenha uma cópia fora da VM. Se alterar
`DATABASE_URL`, ajuste a origem. Não copie apenas o `.db` durante escritas com
`cp`: prefira o backup consistente acima. Para restaurar, pare a aplicação,
restaure a cópia no volume e garanta proprietário 10001:10001 antes de reiniciar.

### Validação no Docker

```bash
docker compose run --rm --no-deps -e DATABASE_URL=sqlite:// web pytest -q
```

Os testes usam bancos temporários e não baixam modelos OCR. Para validar a
persistência manualmente, inicialize o banco, faça login e cadastre um gabarito;
anote seu nome, execute `docker compose down` e `docker compose up -d --build`,
e confirme que ele permanece em Gabaritos. Repita com uma correção no Histórico.
`init-db` pode ser repetido: usa `create_all()`, sem apagar tabelas ou dados.

## Deploy em Azure VM

1. Crie uma VM Linux, por exemplo Ubuntu, e instale Docker Engine e o plugin
   Docker Compose conforme a documentação oficial da distribuição/Docker.
2. Clone o repositório e entre no diretório do projeto.
3. Copie `.env.example` para `.env`, gere a chave e o hash como descrito acima e
   configure `DATABASE_URL=sqlite:////app/data/database.db`.
4. Execute `docker compose up -d --build` e
   `docker compose exec web flask --app run.py init-db`.
5. Confira `docker compose ps`, `docker compose logs -f web` e `/health`.
6. Garanta que o armazenamento do Docker/volume esteja em **disco persistente da
   VM**, com backups externos. Não use disco temporário da Azure nem `/tmp` para
   SQLite. Persistência de volume não protege contra exclusão da VM/disco.
7. Configure posteriormente domínio, Nginx e HTTPS na infraestrutura. Flask e
   Gunicorn continuam em HTTP interno; não é necessário certificado no Flask.

Quando Nginx estiver na mesma VM, restrinja o mapeamento para
`127.0.0.1:8000:8000`, exponha somente as portas necessárias no firewall/NSG e use
`COOKIE_SECURE=true` com HTTPS. Configure no proxy limite de upload compatível com
4 MB e timeout compatível com o processamento. Não habilite confiança irrestrita
em headers de proxy; a aplicação atual não precisa disso para seu fluxo normal.
Nenhuma configuração Azure, Nginx ou PostgreSQL foi adicionada à aplicação.
