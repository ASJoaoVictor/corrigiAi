# Distribuição Windows

O sistema continua Flask no navegador. Docker usa Gunicorn; o executável Windows
usa Tkinter na thread principal e Waitress em uma thread controlada, escutando
`0.0.0.0:8000`. Os dois compartilham `create_app()`. `run.py` continua independente
(porta 5000 por compatibilidade com desenvolvimento e `.env` existentes).
`app/runtime.py` centraliza versão e porta do desktop; o build repassa esses
valores ao MSI. Não exponha o servidor por roteadores, túneis ou UPnP.

## Gerar pelo GitHub Actions a partir do Linux

Envie o projeto, incluindo `.github/workflows/windows-installer.yml` e os arquivos
novos do modo Windows, para o seu repositório GitHub. O workflow precisa estar na
branch padrão para aparecer no botão de execução manual.

1. Abra o repositório no GitHub e entre em **Actions**.
2. Se solicitado, habilite os workflows do repositório.
3. Selecione **Instalador Windows** e clique em **Run workflow**.
4. Escolha a branch com o código e confirme **Run workflow**.
5. Aguarde a execução ficar verde. Abra a execução e, em **Artifacts**, baixe
   **corrigiAi-Windows-MSI**.
6. Extraia o ZIP: o instalador é `corrigiAi-Setup.msi`. O pacote também inclui o
   checksum SHA256 e a lista de dependências usadas no build.

O runner Windows instala Python e WiX, prepara os modelos OCR, executa os testes
e gera o MSI com o script compartilhado. Seu Linux não precisa dessas ferramentas.
Não cadastre DATABASE_URL, senha administrativa ou SECRET_KEY nos secrets do
GitHub: essas informações são solicitadas apenas na primeira execução do aplicativo.
O workflow tem somente permissão de leitura do repositório e não publica releases.
É iniciado manualmente para evitar builds pesados em cada commit; o artefato fica
disponível por 14 dias. É necessário estar conectado ao GitHub para baixá-lo.
Se falhar, abra a etapa vermelha para consultar os logs; não haverá instalador novo.

O workflow só executa após ser enviado ao GitHub; criar o arquivo localmente não
inicia o build. Confira o consumo de minutos e armazenamento do seu plano GitHub.
O MSI ainda não possui assinatura digital: valide-o pelo checklist de Windows limpo
antes da distribuição. O build automático não comprova interface, firewall ou LAN.

## Ambiente de build

Use Windows 10/11 x64 e Python **3.12 x64** oficial, com pip, venv e Tcl/Tk.
O usuário final não precisa de Python, Docker, .NET, WiX ou terminal.
O desenvolvedor precisa de internet, espaço para PyTorch e seu ambiente de build,
.NET SDK compatível com WiX 4 e **WiX CLI 4.0.6** no PATH:

```powershell
dotnet tool install --global wix --version 4.0.6
.\scripts\build_windows.ps1
```

O script cria `.venv-windows-build`, instala wheels CPU de torch/torchvision,
valida `torch.version.cuda is None`, instala `requirements-build.txt`, prepara OCR,
executa pytest, gera onedir com PyInstaller, valida os recursos e gera o MSI.
Usa a extensão `WixToolset.Firewall.wixext/4.0.6`. Não use ambiente com wheels CUDA.
Para builds de release, registre `pip freeze` e as versões das ferramentas junto
aos artefatos: os intervalos de dependências ainda não são um lock reproduzível.

Saídas:

- `dist/corrigiAi/corrigiAi.exe` e `_internal/`: distribuição onedir completa;
- `dist/corrigiAi-Setup.msi`: instalador x64;
- `build/Payload.wxs`: inventário WiX gerado de todos os arquivos do onedir.

Nunca distribua somente o EXE separado de `_internal`.
O build Windows não é realizado em Linux.

## Etapas individuais

No ambiente virtual Windows com as dependências de build instaladas:

```powershell
$env:OCR_MODEL_DIR = "$PWD\build\ocr-models"
python scripts/prepare_ocr.py
python -m pytest -q
python -m PyInstaller --noconfirm --clean corrigiai.spec
python scripts/windows_payload.py dist/corrigiAi build/Payload.wxs
$AppVersion = python -c "from app.runtime import VERSION; print(VERSION)"
$AppPort = python -c "from app.runtime import DEFAULT_PORT; print(DEFAULT_PORT)"
wix extension add WixToolset.Firewall.wixext/4.0.6
wix build packaging/windows/Package.wxs build/Payload.wxs -arch x64 -ext WixToolset.Firewall.wixext/4.0.6 -d "AppVersion=$AppVersion" -d "AppPort=$AppPort" -d "DistDir=$PWD\dist\corrigiAi" -o dist/corrigiAi-Setup.msi
```

O spec inclui templates, static, referência PNG, JSONs do OMR, modelos OCR e dados,
binários e imports necessários de EasyOCR/PyTorch/OpenCV. Usa `COLLECT`/onedir,
sem UPX e sem console. `assets/corrigiai.ico` é opcional.
O modelo `english_g2.pth` precisa existir antes do empacotamento. O Reader continua
lazy/singleton, CPU e `download_enabled=False`: não baixa modelos em runtime.
Sua pasta auxiliar `ocr-user-network` fica no diretório do usuário; os pesos
permanecem na instalação. A preparação dos modelos ocorre apenas no build.
Não copie a raiz do projeto para dist. O inventário rejeita `.env`, configurações,
banco local, uploads, backups e testes. Revise o pacote antes de publicar.

## Primeira execução e armazenamento

Escolhemos **LocalAppData por usuário**, pois cada operador Windows mantém suas
credenciais e DPAPI em seu próprio perfil. Não exige elevação para executar.
Os celulares compartilham o servidor aberto por esse usuário Windows, com sessões
Flask distintas. Feche a instância antes de trocar de usuário ou atualizar.

```text
%LOCALAPPDATA%\corrigiAi\
  config\settings.dpapi     configuração protegida
  logs\corrigiai.log        rotação: 2 MB + 3 arquivos
  temp\<token>\            fotos e revisão por sessão
  ocr-user-network\        diretório auxiliar do Reader
```

O launcher solicita URL PostgreSQL, usuário, senha e confirmação. Gera hash
Werkzeug e SECRET_KEY automaticamente. Testa conexão, verifica somente a presença
de `public.participants` com `cpf` e `grade` e cria apenas `exam`, `answer_key` e
`correction`; então salva configuração e inicia Waitress. A tabela externa não
participa do metadata da aplicação e não é criada nem alterada estruturalmente.
Mantivemos **participants/grade**, conforme confirmação do responsável; o pedido
original citava aluno/nota, que não corresponde ao repositório atual.
A confirmação de uma correção continua atualizando somente a nota do participante
existente, na mesma transação do histórico. Regras de CPF e nota foram preservadas.

Todo o JSON (URL, usuário, hash e SECRET_KEY) é protegido com **Windows DPAPI no
escopo do usuário**, via pywin32; não há fallback para texto puro. Permissões herdadas
do perfil Windows continuam se aplicando. Outro perfil ou computador não consegue
simplesmente reutilizar esse arquivo; guarde as credenciais originais com a
organização. DPAPI não protege contra malware executando como o próprio usuário.
Não há credenciais no MSI, source ou Program Files; o desktop não carrega `.env`.
Para reconfigurar, feche o aplicativo e, com apoio do suporte, remova somente
`config/settings.dpapi`, depois execute novamente. Trocar SECRET_KEY invalida as
sessões anteriores. A configuração não é apagada por atualização/desinstalação.

Os logs registram eventos e classes de falhas; mensagens SQL, parâmetros, URLs,
tracebacks e mensagens arbitrárias das bibliotecas são omitidos para evitar
vazamento de credenciais/CPF. Isso limita a profundidade do diagnóstico.
Temporários expiram em uma hora e são removidos na confirmação/descarte/logout;
o encerramento normal do launcher remove seu diretório temp após parar o servidor.

## Rede, interface e encerramento

`desktop/network.py` enumera interfaces ativas por psutil, aceita somente RFC1918
IPv4 e exclui interfaces virtuais/VPNs com nomes conhecidos. Um socket UDP local,
sem envio de pacote, consulta roteamento entre os endereços já encontrados.
Não consulta serviços externos nem usa DNS de hostname como única estratégia.
Quando há várias interfaces, um seletor atualiza a URL e o QR. Nomes desconhecidos
de VPN podem escapar do filtro: o operador deve escolher a interface LAN correta.
Sem LAN, localhost continua disponível; após trocar de rede, reinicie o launcher.

O QR é produzido por qrcode/Pillow inteiramente local e contém exatamente
`http://IP:8000`. O botão abre localhost; outro copia a URL. Não há abertura repetida
automática do navegador. A porta ocupada gera erro amigável e não mata processos.
`/health` é aguardado antes da indicação de servidor funcionando.

Fechar a janela aguarda startup, sinaliza encerramento, espera o OCR em andamento,
fecha listener, encerra workers Waitress, fecha canais e dispõe conexões SQLAlchemy.
A janela continua respondendo enquanto encerra. Não usa `os._exit`. Se uma operação
ficar bloqueada além do prazo de encerramento, mantém a janela e informa que deve
aguardar/tentar fechar novamente. Não apaga temporários com requests ainda ativos.
A etapa pesada `/process` usa lock não bloqueante por processo: outra sessão vê
"O sistema está processando outro cartão. Aguarde alguns segundos." O Docker
continua com um worker; vários workers/processos teriam locks independentes.

## MSI e firewall

WiX instala em Program Files, registra desinstalação padrão, cria atalhos no Menu
Iniciar e na Área de Trabalho. O UpgradeCode é estável; aumente VERSION em
`app/runtime.py` para cada release. Feche o app antes de atualizar/desinstalar.
Não há remoção dos dados de LocalAppData.

A extensão oficial WiX cria **corrigiAi Local Server**, associada ao executável,
entrada TCP 8000, perfil **private**, escopo **localSubnet**. Não libera redes
públicas nem desliga o firewall. A regra é removida pela desinstalação e sua falha
provoca rollback do MSI. A elevação ocorre somente na instalação.
A rede precisa estar marcada como privada e permitir comunicação entre clientes;
isolamento Wi-Fi, políticas corporativas e firewalls adicionais podem impedir acesso.
O HTTP LAN preserva o comportamento atual de cookies/CSRF/autenticação; use apenas
rede controlada, pois HTTP não cifra o tráfego de login. Não há acesso público.

## Checklist em Windows limpo

Use uma VM/máquina sem Python e sem Docker. Esta validação é necessária antes da
publicação: os testes Linux não comprovam o funcionamento do MSI/DPAPI/OCR empacotado.

1. Instalar `corrigiAi-Setup.msi` e conferir Program Files e Aplicativos instalados.
2. Abrir pelo Menu Iniciar, como usuário sem privilégios administrativos.
3. Preencher primeira configuração com banco de teste Supabase; testar também URL
   incorreta, tabela ausente e estrutura incompatível, sem exibir credenciais.
4. Confirmar que só as três tabelas próprias são inicializadas.
5. Conferir servidor funcionando, localhost, IP LAN, QR e botão copiar/abrir.
6. Conferir regra `corrigiAi Local Server`: executável correto, TCP 8000, apenas
   Private/LocalSubnet; acesso em rede pública não deve ser liberado pela regra.
7. Escanear QR no celular na mesma Wi-Fi e fazer login.
8. Tirar/enviar foto, executar OCR/OMR sem baixar modelos, revisar CPF.
9. CPF inexistente deve impedir confirmação; CPF conhecido deve atualizar grade,
   registrar Correction e aparecer no histórico sem alterar outras colunas.
10. Usar dois celulares: fotos/revisões isoladas e mensagem de ocupado no OCR.
11. Testar Wi-Fi + Ethernet/VPN e seleção de interface; testar localhost sem LAN.
12. Abrir segunda instância: porta ocupada, sem encerrar a primeira nem apagar fotos.
13. Fechar durante OCR, aguardar encerramento e verificar ausência de processo/porta.
14. Abrir novamente e conferir configuração persistente; checar ausência de senhas,
    URL, CPF e fotos nos logs. Testar leitura DPAPI por outro usuário (deve falhar).
15. Atualizar MSI com VERSION maior: preservar configuração e dados.
16. Desinstalar normalmente: remover programa, atalhos e regra; preservar LocalAppData.

## Referências técnicas

- [PyInstaller: spec files e COLLECT/onedir](https://pyinstaller.org/en/stable/spec-files.html)
- [Waitress: servidor WSGI](https://docs.pylonsproject.org/projects/waitress/en/stable/)
- [WiX: FirewallException](https://docs.firegiant.com/wix/schema/firewall/firewallexception/)
