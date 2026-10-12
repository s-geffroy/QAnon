import os
from pathlib import Path

from ..secrets import read_secret


def download(ctx, handle):
    """Telecharge un dataset Kaggle public dans le cache du volume.

    Un jeton (secret `kaggle_api_token`) n'est utilise que s'il est present :
    les datasets publics se telechargent sans."""
    os.environ.setdefault("KAGGLEHUB_CACHE", str(ctx.state / "cache" / "kagglehub"))
    token = read_secret("kaggle_api_token")
    if token:
        os.environ["KAGGLE_API_TOKEN"] = token
    import kagglehub
    return Path(kagglehub.dataset_download(handle))
