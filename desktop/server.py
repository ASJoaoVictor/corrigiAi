"""Controlled Waitress lifecycle with an independent socket map."""
import errno
import json
import socket
import threading
import time
import urllib.request
from app.runtime import DEFAULT_PORT


class PortInUseError(RuntimeError): pass


def check_port(port=DEFAULT_PORT):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind(('0.0.0.0', port))
        except OSError as error:
            if error.errno in (errno.EADDRINUSE, 10048):
                raise PortInUseError('A porta utilizada pelo corrigiAi já está em uso.') from None
            raise


class LocalServer:
    def __init__(self, app, port=DEFAULT_PORT):
        self.app, self.port = app, port
        self.server = self.thread = None
        self.socket_map = {}
        self.failure = None

    def start(self):
        from waitress import create_server
        check_port(self.port)
        self.server = create_server(self.app, host='0.0.0.0', port=self.port, threads=4,
                                    asyncore_loop_timeout=0.2, map=self.socket_map)
        self.thread = threading.Thread(target=self._run, name='corrigiai-waitress', daemon=False)
        self.thread.start()

    def _run(self):
        try:
            self.server.run()
        except Exception as error:
            self.failure = error

    def wait_ready(self, timeout=30):
        deadline = time.monotonic() + timeout
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while time.monotonic() < deadline:
            if self.failure or not self.thread.is_alive(): break
            try:
                with opener.open(f'http://127.0.0.1:{self.port}/health', timeout=1) as response:
                    if response.status == 200 and json.load(response).get('status') == 'ok': return
            except (OSError, ValueError): pass
            time.sleep(0.15)
        raise RuntimeError('Não foi possível iniciar o corrigiAi.')

    def stop(self):
        if self.server:
            # Wait for in-flight OCR/transactions before closing DB and temp files.
            self.server.close()
            self.server.task_dispatcher.shutdown(timeout=300)
            if self.server.task_dispatcher.threads:
                raise RuntimeError('Há requisições em andamento; aguarde o encerramento.')
            for channel in list(self.socket_map.values()):
                channel.close()
            if self.thread: self.thread.join(timeout=5)
            if self.thread and self.thread.is_alive():
                raise RuntimeError('O servidor ainda está encerrando.')
            self.server = None
