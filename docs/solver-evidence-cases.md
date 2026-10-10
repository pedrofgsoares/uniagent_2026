# Comparação por caso e repetição

`-e`: pipeline anterior; experimental: ronda + reparação; conservadora:
defaults finais desligados. 1 indica coincidência com o rótulo, inclusive fallback.
Métricas completas de fundamentação e chamadas: `solver-evidence-results.json`.

| Caso | Rep | -e | Experimental | Conservadora | Rondas exp. | Reparações exp. | Mudou resultado | Regras cons. | Chamadas cons. |
|---|---:|---:|---:|---:|---:|---:|---|---|---:|
| dienstreiseantrag-01 | 1 | 1 | 1 | 1 | 0 | 0 | False | True | 8 |
| dienstreiseantrag-02 | 1 | 1 | 0 | 1 | 1 | 0 | False | False | 2 |
| dienstreiseantrag-03 | 1 | 1 | 1 | 1 | 0 | 0 | False | False | 3 |
| dienstreiseantrag-04 | 1 | 1 | 1 | 1 | 1 | 0 | False | False | 4 |
| dienstreiseantrag-05 | 1 | 1 | 1 | 1 | 0 | 0 | False | False | 2 |
| dienstreiseantrag-01 | 2 | 1 | 1 | 1 | 0 | 0 | False | False | 7 |
| dienstreiseantrag-02 | 2 | 1 | 0 | 1 | 1 | 0 | False | False | 4 |
| dienstreiseantrag-03 | 2 | 1 | 1 | 1 | 0 | 0 | False | False | 2 |
| dienstreiseantrag-04 | 2 | 1 | 0 | 1 | 1 | 0 | False | False | 3 |
| dienstreiseantrag-05 | 2 | 0 | 1 | 1 | 0 | 0 | False | False | 2 |
| beschaffungsantrag-01 | 1 | 1 | 1 | 1 | 1 | 0 | False | False | 6 |
| beschaffungsantrag-02 | 1 | 1 | 0 | 1 | 0 | 0 | False | True | 2 |
| beschaffungsantrag-03 | 1 | 0 | 1 | 0 | 0 | 0 | False | True | 2 |
| beschaffungsantrag-04 | 1 | 1 | 1 | 1 | 0 | 0 | False | True | 2 |
| beschaffungsantrag-05 | 1 | 0 | 0 | 0 | 0 | 0 | False | True | 2 |
| beschaffungsantrag-06 | 1 | 0 | 0 | 0 | 0 | 0 | False | False | 2 |
| beschaffungsantrag-07 | 1 | 0 | 0 | 0 | 0 | 0 | False | False | 3 |
| beschaffungsantrag-08 | 1 | 1 | 1 | 1 | 1 | 0 | False | False | 2 |
| beschaffungsantrag-01 | 2 | 1 | 1 | 1 | 0 | 0 | False | False | 6 |
| beschaffungsantrag-02 | 2 | 1 | 1 | 0 | 0 | 0 | False | False | 2 |
| beschaffungsantrag-03 | 2 | 0 | 1 | 1 | 0 | 0 | False | False | 3 |
| beschaffungsantrag-04 | 2 | 1 | 0 | 0 | 0 | 0 | False | False | 3 |
| beschaffungsantrag-05 | 2 | 1 | 0 | 1 | 1 | 0 | False | True | 2 |
| beschaffungsantrag-06 | 2 | 0 | 1 | 1 | 0 | 0 | False | False | 2 |
| beschaffungsantrag-07 | 2 | 0 | 1 | 0 | 0 | 0 | False | True | 3 |
| beschaffungsantrag-08 | 2 | 1 | 0 | 1 | 1 | 1 | False | False | 2 |
| auslagenerstattung-01 | 1 | 0 | 0 | 0 | 1 | 1 | False | True | 6 |
| auslagenerstattung-02 | 1 | 0 | 0 | 1 | 0 | 0 | False | True | 2 |
| auslagenerstattung-03 | 1 | 0 | 0 | 1 | 1 | 0 | False | False | 2 |
| auslagenerstattung-04 | 1 | 1 | 1 | 1 | 0 | 0 | False | True | 3 |
| auslagenerstattung-05 | 1 | 1 | 1 | 0 | 1 | 0 | False | True | 2 |
| auslagenerstattung-06 | 1 | 0 | 1 | 1 | 1 | 1 | False | True | 2 |
| auslagenerstattung-07 | 1 | 1 | 1 | 1 | 1 | 1 | False | True | 2 |
| auslagenerstattung-08 | 1 | 1 | 0 | 0 | 0 | 0 | False | False | 2 |
| auslagenerstattung-01 | 2 | 0 | 0 | 0 | 1 | 0 | False | False | 6 |
| auslagenerstattung-02 | 2 | 1 | 0 | 0 | 1 | 0 | False | True | 2 |
| auslagenerstattung-03 | 2 | 1 | 1 | 1 | 0 | 0 | False | True | 2 |
| auslagenerstattung-04 | 2 | 1 | 1 | 1 | 0 | 0 | False | False | 1 |
| auslagenerstattung-05 | 2 | 1 | 0 | 0 | 0 | 0 | False | True | 2 |
| auslagenerstattung-06 | 2 | 0 | 1 | 1 | 0 | 0 | False | False | 2 |
| auslagenerstattung-07 | 2 | 1 | 1 | 1 | 1 | 0 | False | True | 2 |
| auslagenerstattung-08 | 2 | 1 | 0 | 0 | 1 | 0 | False | True | 2 |
