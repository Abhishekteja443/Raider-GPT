import json, re, sys
from pathlib import Path
from rdflib import Graph, URIRef, BNode


ONTOLOGY = Path(r"C:\Users\gabhi\Projects\KG-RAG\wsu-ontology.ttl")
GRAPH    = Path(r"C:\Users\gabhi\Projects\KG-RAG\Models comparision\Online models\Opus5.5\opus 5_5.ttl")
QUERIES  = Path(r"C:\Users\gabhi\Projects\KG-RAG\Models comparision\Online models\Opus5.5\all_20_queries_opus5_5.rq")   # <-- adjust to where your .rq file is
OUTPUT   = GRAPH.parent / "query_results.json"                          # saved next to Graph.ttl

if len(sys.argv) == 5:
    ONTOLOGY, GRAPH, QUERIES, OUTPUT = map(Path, sys.argv[1:5])

g = Graph()
g.parse(ONTOLOGY, format="turtle")
g.parse(GRAPH, format="turtle")
print(f"Loaded {len(g)} triples")

text = QUERIES.read_text(encoding="utf-8")
matches = list(re.finditer(r"^#\s*CQ\s*(\d+)\s*:\s*(.*)$", text, re.MULTILINE))

def to_json(t):
    if isinstance(t, URIRef): return {"type": "uri", "value": str(t)}
    if isinstance(t, BNode):  return {"type": "bnode", "value": str(t)}
    d = {"type": "literal", "value": str(t)}
    if t.language: d["lang"] = t.language
    if t.datatype: d["datatype"] = str(t.datatype)
    return d

results = []
for i, m in enumerate(matches):
    end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
    q = text[m.end():end].strip()
    entry = {"id": f"CQ{m.group(1)}", "question": m.group(2).strip(), "query": q}
    try:
        res = g.query(q)
        entry["variables"] = [str(v) for v in res.vars]
        entry["bindings"] = [{str(v): to_json(row[v]) for v in res.vars if row[v] is not None} for row in res]
        entry["count"] = len(entry["bindings"])
    except Exception as e:
        entry["error"] = str(e); entry["count"] = 0
    print(entry["id"], entry["count"], entry.get("error", ""))
    results.append(entry)

OUTPUT.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print("Wrote", OUTPUT)
