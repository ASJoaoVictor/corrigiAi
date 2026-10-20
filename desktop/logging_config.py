"""Keep diagnostics free of credentials, SQL values, CPF and request bodies."""
import logging
from logging.handlers import RotatingFileHandler


class SafeFormatter(logging.Formatter):
    def format(self, record):
        # Desktop emits event codes and exception class names only. Third-party
        # messages/tracebacks may contain connection URLs and personal data.
        if not record.name.startswith('desktop'):
            return f'{record.levelname} {record.name}: evento técnico (detalhes omitidos)'
        return super().format(record)


def configure_logging(directory):
    handler = RotatingFileHandler(directory / 'corrigiai.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
    handler.setFormatter(SafeFormatter('%(asctime)s %(levelname)s %(message)s'))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def log_failure(event, error):
    logging.getLogger('desktop').error('%s (%s)', event, type(error).__name__)
