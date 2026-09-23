"""Descoberta dos casos no dataset de input.

O spot-check tem uma pasta por caso e ainda `retrieval-corpora/`, que e material
de apoio e nao um caso. O conjunto de teste e privado, por isso a deteccao e
deliberadamente tolerante: qualquer subpasta com ficheiros conta como caso.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Subpastas do input que nunca sao casos (corpora de apoio ao retrieval).
NON_CASE_DIRECTORIES = frozenset({"retrieval-corpora"})


@dataclass(frozen=True)
class Case:
    """Um caso administrativo: o identificador e os documentos que o compoem."""

    case_id: str
    directory: Path
    files: tuple[Path, ...]

    @property
    def filenames(self) -> list[str]:
        return [path.name for path in self.files]


def _case_files(directory: Path) -> tuple[Path, ...]:
    return tuple(sorted(p for p in directory.iterdir() if p.is_file()))


def discover_cases(input_directory: Path) -> list[Case]:
    """Devolve os casos por ordem alfabetica de `case_id`.

    Subpastas sem ficheiros sao ignoradas, para que uma pasta vazia no dataset
    nao produza uma linha em `predictions.jsonl` sem documentos por tras.
    """
    if not input_directory.is_dir():
        raise NotADirectoryError(f"Input nao e uma pasta: {input_directory}")

    cases: list[Case] = []
    for directory in sorted(input_directory.iterdir()):
        if not directory.is_dir() or directory.name in NON_CASE_DIRECTORIES:
            continue
        files = _case_files(directory)
        if not files:
            continue
        cases.append(Case(case_id=directory.name, directory=directory, files=files))
    return cases
