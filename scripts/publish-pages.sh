#!/usr/bin/env bash
# Publie le site genere par le worker (/state/site) sur la branche gh-pages,
# en SSH avec la cle de l'utilisateur de l'hote. Aucun jeton dans le conteneur.
#
# Le site est extrait par un conteneur jetable (appctl run), puis pousse en un
# seul commit (force-push) : gh-pages ne garde pas d'historique.
set -euo pipefail
cd "$(dirname "$0")/.."

remote=${PAGES_REMOTE:-$(git remote get-url origin)}
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

sudo appctl run worker sh -c 'test -f /state/site/index.html && tar -C /state/site -czf - . | base64 -w0' \
  2>"$tmp/err" | base64 -d > "$tmp/site.tgz" \
  || { cat "$tmp/err"; echo "ECHEC : extraction de /state/site"; exit 1; }
mkdir "$tmp/site"
tar -xzf "$tmp/site.tgz" -C "$tmp/site"
test -f "$tmp/site/index.html" || { echo "ECHEC : site vide"; exit 1; }

# Version citable : le commit du code qui a genere le site (+ "-modifie" si
# l'arbre de travail n'est pas propre).
version=$(git rev-parse --short HEAD)
git diff --quiet HEAD -- src || version="$version-modifie"
grep -rl "@@VERSION@@" "$tmp/site" | xargs -r sed -i "s/@@VERSION@@/$version/g"

cd "$tmp/site"
git init -q -b gh-pages
git add -A
git -c user.name="$(git -C "$OLDPWD" config user.name)" -c user.email="$(git -C "$OLDPWD" config user.email)" \
  commit -q -m "site genere par le worker qanon ($(date +%F))"
git push -q --force "$remote" gh-pages
echo "OK : $(find . -type f -not -path './.git/*' | wc -l) fichiers publies sur $remote (gh-pages), version $version"
