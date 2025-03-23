# #!/usr/bin/env python3

import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _decrypt_artifacts() -> None:
    if (fernet_key := os.environ.get("ARTIFACT_ENCRYPTION_KEY")) is None:
        return

    try:
        fernet_key = Fernet(fernet_key)
    except ValueError:
        logger.exception("Invalid Fernet key provided.")
        return

    for enc_f in Path("tests/artifacts").glob(pattern="*.encrypted"):
        with enc_f.open(mode="rb") as f:
            enc_data = f.read()

        try:
            dec_data = fernet_key.decrypt(enc_data)
        except Exception:
            logger.exception("Failed to decrypt: `%s`.", enc_f)
            continue

        with (enc_f.parent / enc_f.stem).open(mode="wb") as f:
            f.write(dec_data)


# Note: This wait time is necessary because of django-countries sometimes being not
# ready. Simple workaround to fix the issue and barely noticeable.
def pytest_sessionstart(session) -> None:
    _decrypt_artifacts()
