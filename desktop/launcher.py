"""Tk stays on the main thread; startup, DB and shutdown never block the UI."""
import queue
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser

from app.models import db
from app.runtime import DEFAULT_PORT, VERSION
from .application import desktop_app
from .config import ConfigurationError, load_config, new_config, save_config
from .database import prepare_database, DatabaseSetupError
from .logging_config import configure_logging, log_failure
from .network import access_url, lan_addresses
from .paths import application_paths
from .server import LocalServer, PortInUseError, check_port
from .sqlite_test import TEST_PORT, TEST_NAME, desktop_database_path, sqlite_url, prepare_test_database


class Launcher:
    def __init__(self, root, paths, *, sqlite_test=False):
        self.root, self.paths = root, paths
        self.sqlite_test = sqlite_test
        self.port = TEST_PORT if sqlite_test else DEFAULT_PORT
        self.name = TEST_NAME if sqlite_test else 'corrigiAi'
        self.events = queue.Queue()
        self.server = self.app = None
        self.busy = self.closing = False
        self.started = False
        root.title(f'{self.name} {VERSION}')
        root.resizable(False, False)
        self.frame = ttk.Frame(root, padding=24)
        self.frame.pack(fill='both', expand=True)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)
        if paths.config.exists():
            self.status('Iniciando corrigiAi…')
            self.start_worker(None)
        else:
            self.setup_form()

    def clear(self):
        for widget in self.frame.winfo_children(): widget.destroy()

    def status(self, text):
        self.clear()
        ttk.Label(self.frame, text=text, wraplength=380).pack(pady=20)

    def setup_form(self):
        self.clear()
        ttk.Label(self.frame, text='Configuração inicial', font=('', 16, 'bold')).pack()
        ttk.Label(self.frame, text='SQLite local · Somente testes' if self.sqlite_test else 'PostgreSQL / Supabase · public.participants (cpf/grade)').pack(pady=10)
        self.fields = {}
        fields = [('username', 'Usuário administrador'), ('password', 'Senha (mínimo 10 caracteres)'), ('confirmation', 'Confirme a senha')]
        if not self.sqlite_test: fields.insert(0, ('url', 'DATABASE_URL'))
        for key, label in fields:
            ttk.Label(self.frame, text=label).pack(anchor='w', pady=(8, 2))
            entry = ttk.Entry(self.frame, width=52, show='' if key == 'username' else '*')
            entry.pack(fill='x')
            self.fields[key] = entry
        self.fields['username'].insert(0, 'admin')
        ttk.Button(self.frame, text='Testar conexão e iniciar', command=self.configure).pack(pady=16)

    def configure(self):
        try:
            if self.fields['password'].get() != self.fields['confirmation'].get():
                raise ConfigurationError('A confirmação da senha não confere.')
            url = sqlite_url(desktop_database_path()) if self.sqlite_test else self.fields['url'].get()
            config = new_config(url, self.fields['username'].get(), self.fields['password'].get(), sqlite_test=self.sqlite_test)
        except (ConfigurationError, OSError) as error:
            messagebox.showerror('Configuração', str(error), parent=self.root)
            return
        for field in self.fields.values(): field.delete(0, 'end')
        self.status('Verificando o banco e iniciando o servidor…')
        self.start_worker(config)

    def start_worker(self, config):
        self.busy = True
        threading.Thread(target=self.start, args=(config,), name='corrigiai-startup', daemon=False).start()

    def start(self, config):
        initial = config is not None
        try:
            check_port(self.port)
            if config is None: config = load_config(self.paths.config, sqlite_test=self.sqlite_test)
            if not (self.paths.models / 'english_g2.pth').is_file():
                raise ConfigurationError('Os modelos OCR não foram encontrados. Reinstale o corrigiAi.')
            if self.sqlite_test:
                config = {**config, 'SQLALCHEMY_DATABASE_URI': sqlite_url(desktop_database_path())}
            self.app = desktop_app(config, self.paths, sqlite_test=self.sqlite_test)
            if self.sqlite_test: prepare_test_database(self.app)
            else: prepare_database(self.app)
            if initial: save_config(self.paths.config, config, sqlite_test=self.sqlite_test)
            self.server = LocalServer(self.app, port=self.port)
            self.server.start()
            self.server.wait_ready()
            self.started = True
            self.events.put(('ready', lan_addresses()))
        except Exception as error:
            log_failure('startup_failed', error)
            if self.server:
                try: self.server.stop()
                except Exception as stop_error: log_failure('shutdown_failed', stop_error)
            if self.app:
                with self.app.app_context(): db.engine.dispose()
            safe = str(error) if isinstance(error, (ConfigurationError, DatabaseSetupError, PortInUseError)) else 'Não foi possível iniciar o corrigiAi.'
            self.events.put(('error', safe))

    def poll(self):
        try:
            event, value = self.events.get_nowait()
        except queue.Empty:
            event = None
        if event == 'stopped':
            self.root.destroy()
            return
        if event in ('ready', 'error'):
            self.busy = False
            if self.closing:
                self.close()
            elif event == 'ready': self.control_panel(value)
            else:
                messagebox.showerror('corrigiAi', value, parent=self.root)
                if not self.paths.config.exists(): self.setup_form()
                else: self.status(value + '\nFeche a janela e tente novamente após verificar a configuração ou consulte o suporte.')
        if event == 'stop_error':
            self.busy = self.closing = False
            messagebox.showerror('corrigiAi', 'Ainda não foi possível encerrar. Aguarde e feche a janela novamente.', parent=self.root)
        self.root.after(100, self.poll)

    def control_panel(self, addresses):
        self.clear()
        ttk.Label(self.frame, text=f'{self.name} {VERSION}', font=('', 18, 'bold')).pack()
        ttk.Label(self.frame, text='Servidor: ● Funcionando').pack(pady=12)
        if self.sqlite_test:
            from sqlalchemy.engine import make_url
            ttk.Label(self.frame, text='Banco local: ' + make_url(self.app.config['SQLALCHEMY_DATABASE_URI']).database, wraplength=380).pack(pady=8)
        self.local_url = access_url('localhost', self.port)
        ttk.Label(self.frame, text='Neste computador:').pack()
        ttk.Label(self.frame, text=self.local_url).pack(pady=(0, 12))
        self.mobile_url = tk.StringVar()
        self.qr = ttk.Label(self.frame)
        if addresses:
            ttk.Label(self.frame, text='No celular:').pack()
            options = {f'{name} — {ip}': ip for name, ip in addresses}
            selected = tk.StringVar(value=next(iter(options)))
            if len(options) > 1:
                chooser = ttk.Combobox(self.frame, values=list(options), textvariable=selected, state='readonly', width=45)
                chooser.pack()
                chooser.bind('<<ComboboxSelected>>', lambda _: self.update_qr(options[selected.get()]))
            ttk.Label(self.frame, textvariable=self.mobile_url).pack()
            self.qr.pack(pady=10)
            self.update_qr(addresses[0][1])
        else:
            ttk.Label(self.frame, text='O corrigiAi foi iniciado, mas não foi possível identificar a rede local.', wraplength=360).pack(pady=10)
        ttk.Label(self.frame, text='Celular e computador devem estar na mesma rede Wi-Fi.\nUse uma rede privada no Windows.', wraplength=360).pack()
        ttk.Button(self.frame, text='Abrir corrigiAi', command=lambda: webbrowser.open(self.local_url)).pack(fill='x', pady=(16, 4))
        ttk.Button(self.frame, text='Copiar endereço', command=self.copy_url).pack(fill='x')

    def update_qr(self, ip):
        import qrcode
        from PIL import ImageTk
        self.mobile_url.set(access_url(ip, self.port))
        image = qrcode.make(self.mobile_url.get()).get_image().resize((230, 230))
        self.qr_image = ImageTk.PhotoImage(image)
        self.qr.configure(image=self.qr_image)

    def copy_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.mobile_url.get() or self.local_url)

    def close(self):
        self.closing = True
        self.status('Encerrando corrigiAi…\nAguarde o processamento em andamento terminar.')
        if self.busy: return
        self.busy = True
        threading.Thread(target=self.stop, name='corrigiai-shutdown', daemon=False).start()

    def stop(self):
        try:
            if self.app:
                # Do not delete photos while OCR/OMR is using them.
                with self.app.extensions['processing_lock']:
                    if self.server: self.server.stop()
                with self.app.app_context():
                    db.session.remove()
                    db.engine.dispose()
            if self.started:
                shutil.rmtree(self.paths.work, ignore_errors=True)
            self.events.put(('stopped', None))
        except Exception as error:
            log_failure('shutdown_failed', error)
            self.events.put(('stop_error', None))


def main(*, sqlite_test=False):
    root = tk.Tk()
    try:
        paths = application_paths(sqlite_test=sqlite_test)
        paths.prepare()
        configure_logging(paths.logs)
        Launcher(root, paths, sqlite_test=sqlite_test)
        root.mainloop()
    except Exception as error:
        log_failure('launcher_failed', error)
        messagebox.showerror('corrigiAi', 'Não foi possível iniciar o corrigiAi. Consulte o suporte da organização.', parent=root)
        root.destroy()
