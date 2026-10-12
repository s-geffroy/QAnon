"""Lecture des secrets Docker Compose. Jamais journalises, jamais renvoyes dans
un message d'erreur."""
import os
from pathlib import Path


def read_secret(name):
    """Renvoie le secret `name`, ou None s'il n'est pas monte.

    Chemin : variable <NAME>_FILE si definie, sinon /run/secrets/<name>."""
    path = Path(os.environ.get(f"{name.upper()}_FILE", f"/run/secrets/{name}"))
    try:
        value = path.read_text().strip()
    except (FileNotFoundError, PermissionError):
        return None
    return value or None
