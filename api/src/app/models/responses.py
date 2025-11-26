from pydantic import BaseModel
from typing import Any, List, Optional

class Meta(BaseModel):
    version: str | None
    created_at: str | None
    modules: list[str]

class Indicador(BaseModel):
    anio: int
    eje: str
    total: float
    cumplimiento: float

class Comercializacion(BaseModel):
    anio: int
    estrategia: str
    total: float
    operaciones: int
