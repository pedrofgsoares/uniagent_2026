import sys, json, re, collections, tempfile, pathlib
sys.path.insert(0, "src")
from uniagent.tools.rules import RuleSearch
from uniagent.tools.extraction import DocumentStore
D = pathlib.Path("data/uniagent-code/cikm26/datasets")
bench = json.load(open("docs/rule-retrieval-benchmark.json"))
DATASET = {"dienstreiseantrag": "business-trip-spot-check", "beschaffungsantrag": "task-2-procurement-spot-check",
           "auslagenerstattung": "task-2-expense-reimbursement-spot-check"}
work = pathlib.Path(tempfile.mkdtemp())
search = RuleSearch(D / "business-trip-spot-check" / "inputs", work)

def pages(case):
    store = DocumentStore(D / DATASET[case.rsplit("-", 1)[0]] / "inputs" / case)
    out = []
    for name in store.filenames():
        try: out += [(name, i, t) for i, t in enumerate(store.pages(name), 1)]
        except Exception: pass
    return out

def s1(case, ps):
    names = " ".join(n.rsplit(".", 1)[0].replace("-", " ") for n in sorted({p[0] for p in ps}))
    return f"{case.rsplit('-', 1)[0]} {names}"

def s2(case, ps):
    main = [p for p in ps if "antrag" in p[0].lower() and p[1] == 1] or ps[:1]
    return " ".join(main[0][2].split())[:1000]

def s3(case, ps, k=20):
    index = search._index("university-kassel-public-de")
    tokens = collections.Counter(t for p in ps for t in index.tokenize(p[2]))
    scored = sorted(tokens, key=lambda t: -tokens[t] * index._idf(t))
    # Termos do dossier com maior tf x idf; os numeros e IDs raros dominariam, por isso so palavras.
    words = [t for t in scored if not t.isdigit() and len(t) > 3][:k]
    return " ".join(words)

rows = []
for rule in bench["rules"]:
    pat = re.compile(rule["pattern"])
    for case in rule["cases"]:
        ps = pages(case)
        for name, build in (("S1 tipo+ficheiros", s1), ("S2 formulario p1", s2), ("S3 termos tf-idf", s3)):
            q = build(case, ps)
            res = search.search(q, "")
            hit = any(pat.search(x["text"]) for r in res for x in r["passages"])
            page = any(pat.search(search.indices[r["corpus"]].documents[r["doc_id"]].text) for r in res)
            rows.append((name, rule["rule"], case, hit, page))
by = collections.defaultdict(lambda: [0, 0, 0])
for name, rule, case, hit, page in rows:
    by[name][0] += hit; by[name][1] += page; by[name][2] += 1
for name, (h, p, n) in by.items(): print(f"{name:20} passagem {h}/{n}  pagina {p}/{n}")
for name, rule, case, hit, page in rows:
    if hit: print("   ", name, rule, case)
search.close()
