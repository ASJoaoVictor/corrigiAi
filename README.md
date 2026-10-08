# corrigiAi

Sistema web para auxiliar a correção dos cartões-resposta da Olimpíada Picuiense de Informática (OPI), com leitura por fotografia e revisão humana antes de salvar o resultado.

## Sobre o projeto

O corrigiAi foi desenvolvido para apoiar a organização da OPI na correção do cartão Fundamental de 30 questões. A partir de uma fotografia, utiliza visão computacional para identificar as alternativas marcadas e reconhecimento de texto para auxiliar na leitura do CPF.

A organização confere e ajusta a leitura antes de confirmar. O resultado é a quantidade de acertos, salva em um histórico local. O uso atual é pelo navegador, no computador ou no celular conectado à mesma rede.

## Funcionalidades

- Login com credenciais da organização.
- Cadastro de provas e gabaritos de 30 questões, com alternativas A–E.
- Captura de foto pelo celular ou envio de imagem.
- Leitura e validação do CPF.
- Identificação das respostas e cálculo da quantidade de acertos.
- Revisão manual do CPF e das alternativas antes de salvar.
- Histórico das correções confirmadas.

## Tecnologias

- **Python e Flask:** aplicação web, com páginas em Jinja2.
- **Flask-SQLAlchemy e PostgreSQL (Supabase):** armazenamento dos gabaritos e resultados.
- **OpenCV, NumPy e Pillow:** processamento das imagens.
- **EasyOCR e PyTorch:** reconhecimento dos dígitos do CPF.
- **HTML, CSS e JavaScript:** interface adaptada ao celular.
- **pytest:** testes automatizados.

## Instalação com Docker

Requer internet e [Docker Engine com Compose no Linux](https://docs.docker.com/engine/install/) ou [Docker Desktop no Windows](https://docs.docker.com/desktop/setup/install/windows-install/). No Windows, mantenha o Docker Desktop em execução com containers Linux. Não é necessário Python no computador.

Baixe o projeto e abra um terminal na sua pasta.

### Linux

```bash
chmod +x install.sh
./install.sh
```

### Windows

Execute no PowerShell:

```powershell
.\install.ps1
```

Se a política bloquear, após conferir o script, execute somente nesta nova sessão de processo (sem alterar a política global):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

O instalador constrói a imagem e prepara o OCR; depois solicita usuário, senha e a **connection string PostgreSQL do Supabase** (`DATABASE_URL`). Use uma conexão acessível a partir do seu computador, como o pooler em modo sessão se a conexão direta exigir IPv6 indisponível. Senhas com caracteres especiais na URL devem estar codificadas como URL. A entrada de senha e URL fica oculta. A chave secreta é automática e somente o hash Werkzeug da senha é salvo. O `.env` guarda a URL com credenciais: não o compartilhe. Se já existir, escolha reutilizar ou confirme a reconfiguração.

O instalador inicia o serviço, executa `flask --app run.py init-db` e aguarda `/health` por cerca de 60 segundos. Acesse **http://localhost:8000**. Pelo celular na mesma rede, use `http://IP-DO-COMPUTADOR:8000`; o endereço sugerido pode variar com VPNs e interfaces de rede. Se necessário, confira a porta 8000 no firewall; o instalador não altera regras.

Nesta versão, `init-db` cria somente `exam`, `answer_key` e `correction`, preservando dados e sem modificar a tabela externa `public.participants`. A aplicação consulta participantes pelo CPF e atualiza a nota após confirmação humana. O Compose usa o banco do Supabase; volumes legados existentes não são apagados pelo instalador.

Para parar sem apagar volumes:

```bash
docker compose down
```

Para diagnóstico: `docker compose logs web` (revise possíveis credenciais antes de compartilhar logs). Você pode executar o instalador novamente; ele não remove dados ou volumes. O healthcheck valida a resposta HTTP interna do container; a conexão ao banco é verificada pelo `init-db`, e firewall/acesso pelo celular precisam ser conferidos na rede local.

As seções seguintes descrevem a instalação manual para desenvolvimento.

## Requisitos

- Python 3.10 ou superior e pip.
- Ambiente virtual recomendado para instalar as dependências.
- Internet durante a instalação e o download inicial dos modelos OCR.

Não é necessário ter GPU. Após preparar os modelos, o reconhecimento funciona localmente, sem internet.

## Instalação

Baixe o repositório e abra um terminal na raiz do projeto. Os comandos abaixo consideram Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Em máquinas sem GPU, é recomendado instalar primeiro a versão CPU do PyTorch para evitar o download de bibliotecas CUDA:

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

Instale as dependências do projeto:

```bash
pip install -r requirements.txt
```

Mantenha o ambiente virtual ativado para os próximos comandos.

## Configuração

Prepare o arquivo `.env` com o assistente:

```bash
python scripts/setup_local.py
```

Ele solicita o usuário e uma senha de pelo menos 10 caracteres, gera a `SECRET_KEY` e salva somente o hash da senha em `ADMIN_PASSWORD_HASH`. A senha não aparece enquanto você digita.

O assistente não sobrescreve um `.env` existente. Se já houver um, confira `SECRET_KEY`, `ADMIN_USERNAME` e `ADMIN_PASSWORD_HASH`; use `.env.example` como referência das opções disponíveis.

Para o uso local, mantenha `COOKIE_SECURE=false`, `DEBUG_OMR=false` e `PORT=5000`. Configure `DATABASE_URL` com a string de conexão PostgreSQL do projeto no Supabase, por exemplo `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE`. A URL é uma credencial: mantenha-a somente no `.env`.

Prepare os modelos de reconhecimento do CPF:

```bash
python scripts/prepare_ocr.py
```

Esse comando baixa os modelos em `instance/ocr-models/` para reutilização. Sem os modelos disponíveis, o sistema solicita o preenchimento manual do CPF.

## Banco de dados

Inicialize as tabelas antes de usar a aplicação:

```bash
flask --app run.py init-db
```

O corrigiAi usa PostgreSQL hospedado no Supabase, acessado diretamente pelo Flask-SQLAlchemy. Executar o comando cria apenas as tabelas próprias do corrigiAi (`Exam`, `AnswerKey` e `Correction`), sem apagar os dados existentes e sem criar ou modificar `public.participants`. Os gabaritos são cadastrados pela interface.

A tabela `public.participants` já deve existir no banco e é administrada por outro sistema. O corrigiAi apenas consulta o aluno pelo CPF e, após a confirmação humana, substitui `participants.grade` pela quantidade final de acertos. O CPF é consultado no formato `123.456.789-12`. CPF não encontrado impede a confirmação; nenhum aluno é criado pela aplicação.

## Executando

Na raiz do projeto, com o ambiente virtual ativado:

```bash
python run.py
```

Abra [http://localhost:5000](http://localhost:5000) no navegador. A porta padrão é 5000 e pode ser alterada pela variável `PORT` no `.env`.

## Acesso pelo celular

1. Conecte o computador e o celular à mesma rede Wi-Fi.
2. Inicie o servidor conforme a seção anterior e mantenha-o em execução.
3. Descubra o IP local do computador. No Linux:

   ```bash
   hostname -I
   ```

4. No navegador do celular, acesse o IP do computador e a porta configurada, por exemplo: `http://192.168.1.20:5000`.

O servidor já aceita conexões da rede local. Pode ser necessário liberar a porta 5000 no firewall do computador.

## Como usar

1. Faça login com as credenciais configuradas no `.env`.
2. Em **Gabaritos**, crie a prova e informe as 30 alternativas corretas.
3. Toque em **Tirar foto de cartão** e escolha a prova.
4. Fotografe o cartão inteiro, sobre uma superfície plana e bem iluminada, ou envie uma imagem.
5. Confira a prévia, toque em **Usar foto e processar cartão** e aguarde.
6. Confira o CPF e todas as respostas; corrija manualmente o que for necessário.
7. Toque em **Revisar confirmação** e confira a quantidade de acertos.
8. Se estiver tudo correto, toque em **Confirmar correção**.
9. Consulte o resultado em **Histórico**.

São aceitas imagens JPEG, PNG e WebP; HEIC não é aceito. CPF inválido precisa ser corrigido antes da confirmação. Respostas em branco, múltiplas ou ambíguas contam como erro enquanto não forem ajustadas na revisão.

## Estrutura do projeto

```text
app/
├── routes/       # Rotas da aplicação
├── models/       # Modelos do banco de dados
├── services/     # Processamento e correção
├── omr/          # Modelo do cartão e referência
├── templates/    # Páginas Jinja2
└── static/       # CSS e JavaScript
scripts/          # Configuração e ferramentas auxiliares
tests/            # Testes automatizados
docs/             # Imagens e materiais de referência
instance/         # Modelos OCR e temporários locais
run.py            # Inicialização do servidor local
```

## Testes

Na raiz do projeto, com as dependências instaladas e o ambiente virtual ativado:

```bash
pytest -q
```

Para verificar também o OCR com dígitos impressos sintéticos, após preparar os modelos:

```bash
python scripts/check_ocr.py
```

Esse teste adicional não mede a precisão da leitura de CPF manuscrito.

## Limitações atuais

- O modelo atual é específico para o cartão Fundamental da OPI, com 30 questões.
- CPF manuscrito pode exigir preenchimento ou correção manual; a revisão humana é obrigatória.
- Sombras, desfoque, cortes, papel curvo e perspectiva excessiva podem prejudicar o reconhecimento.
- A validação atual usa o cartão de referência e imagens sintéticas; ainda é necessário avaliar uma amostra representativa de fotos reais.
- A tabela externa `participants` deve conter ao menos as colunas `cpf` e `grade`, e cada CPF deve identificar somente um aluno. O valor de `cpf` deve usar o formato `123.456.789-12`.

## Privacidade

CPF é dado pessoal: mantenha os resultados em ambiente controlado. As fotos são temporárias e não ficam no histórico; são removidas ao concluir ou descartar o trabalho, sair da sessão ou na limpeza de trabalhos expirados.

Não envie o `.env`, o banco ou imagens de participantes ao Git. O `.env` e a pasta `instance/` já estão incluídos no `.gitignore`.
