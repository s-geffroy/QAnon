FROM python:3.13-slim

# git : publication du site sur la branche gh-pages.
RUN apt-get update \
 && apt-get install -y --no-install-recommends git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Utilisateur non-root : rien n'oblige ce conteneur a tourner en root.
# /state est cree ICI, et possede par 'app' : Docker initialise un volume nomme
# vide avec le proprietaire et les droits du repertoire de l'image. Sans ca, le
# volume arriverait en root:root et le worker ne pourrait pas y ecrire.
RUN useradd -m -u 10001 app && mkdir -p /state && chown -R app:app /app /state
USER app
ENV HOME=/home/app PYTHONPATH=/app

# Aucun EXPOSE : ce conteneur n'ouvre rien.
# -u : sortie non bufferisee, sinon les logs n'apparaissent que par blocs.
CMD ["python3", "-u", "/app/worker.py"]
