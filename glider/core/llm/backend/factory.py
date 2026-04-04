from __future__ import annotations

from glider.core.llm.backend.generic import GenericBackend
from glider.core.llm.backend.mistral import MistralBackend
from glider.core.types import Backend

BACKEND_FACTORY = {Backend.MISTRAL: MistralBackend, Backend.GENERIC: GenericBackend}
