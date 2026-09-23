"""Extracao de texto dos documentos de um caso.

Usa `pdftotext -layout` (poppler-utils, ja na imagem) porque preserva o
alinhamento em colunas: num formulario, o rotulo e o valor ficam na mesma
linha ("Ende Dienstgeschaeft:    11.02.2026"), que e o que torna o texto
legivel para o modelo. Bibliotecas Python de extracao desfazem esse
alinhamento.
"""

from __future__ import annotations

import subprocess
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

#: Separador de pagina do pdftotext.
PAGE_BREAK = "\f"

EXTRACTION_TIMEOUT_SECONDS = 60


class ExtractionError(RuntimeError):
    """A extracao de texto falhou (ver subclasses)."""


class PdftotextMissingError(ExtractionError):
    """O binario `pdftotext` nao esta disponivel."""


class NoTextLayerError(ExtractionError):
    """O PDF nao tem camada de texto (precisaria de OCR)."""


def extract_pages(path: Path, timeout: float = EXTRACTION_TIMEOUT_SECONDS) -> list[str]:
    """Devolve o texto do PDF, uma entrada por pagina.

    Falha de forma explicita quando nao ha texto: um documento digitalizado
    nao pode ser confundido com um documento em branco, porque o agente
    tiraria a conclusao errada.
    """
    try:
        completed = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as error:
        raise PdftotextMissingError(
            "`pdftotext` nao encontrado. Instalar poppler-utils "
            "(ja incluido na imagem Docker do projeto)."
        ) from error
    except subprocess.TimeoutExpired as error:
        raise ExtractionError(f"Extracao de {path.name} excedeu {timeout}s.") from error

    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise ExtractionError(f"pdftotext falhou em {path.name}: {detail}")

    text = completed.stdout.decode("utf-8", "replace")
    pages = [page.strip("\n") for page in text.split(PAGE_BREAK)]
    while pages and not pages[-1].strip():
        pages.pop()

    if not any(page.strip() for page in pages):
        raise NoTextLayerError(
            f"{path.name} nao tem camada de texto (documento digitalizado?). "
            "Este sistema nao faz OCR."
        )
    return pages


def normalize(text: str) -> str:
    """Minusculas sem acentos, para procuras tolerantes.

    "Rueckreise", "Rückreise" e "RUCKREISE" passam a comparar-se entre si.
    """
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


@dataclass
class DocumentStore:
    """Documentos de um caso, com o texto extraido em cache.

    Criado por caso, o que mantem a cache isolada: dois casos com ficheiros
    do mesmo nome nunca se misturam.
    """

    case_directory: Path
    _pages: dict[str, list[str]] = field(default_factory=dict, init=False)

    def filenames(self) -> list[str]:
        return sorted(p.name for p in self.case_directory.iterdir() if p.is_file())

    def resolve(self, filename: str) -> Path:
        """Valida que `filename` e um ficheiro deste caso.

        Recusa caminhos que saiam da pasta do caso: o agente so deve poder
        ler o processo que lhe foi entregue.
        """
        candidate = (self.case_directory / filename).resolve()
        case_root = self.case_directory.resolve()
        if not candidate.is_relative_to(case_root) or not candidate.is_file():
            available = ", ".join(self.filenames())
            raise FileNotFoundError(
                f"{filename!r} nao e um documento deste caso. Disponiveis: {available}"
            )
        return candidate

    def pages(self, filename: str) -> list[str]:
        """Texto do documento, por pagina, extraido no maximo uma vez."""
        path = self.resolve(filename)
        if path.name not in self._pages:
            self._pages[path.name] = extract_pages(path)
        return self._pages[path.name]

    def page_count(self, filename: str) -> int:
        return len(self.pages(filename))
