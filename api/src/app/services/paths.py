import os
from ..core.config import settings

DATA = settings.DATA_DIR
CURRENT = os.path.join(DATA, "current")
STAGING = os.path.join(DATA, "staging")
ARCHIVE = os.path.join(DATA, "archive")
UPLOADS = os.path.join(DATA, "uploads")

for p in (DATA, CURRENT, STAGING, ARCHIVE, UPLOADS):
    os.makedirs(p, exist_ok=True)
