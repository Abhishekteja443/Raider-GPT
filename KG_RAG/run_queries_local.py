import argparse
import json
import re
from pathlib import Path

from rdflib import Graph, URIRef, BNode


parser = argparse.ArgumentParser(description="Run CQ SPARQL queries against local Turtle graphs")
parser.add_argument("ontology", nargs="?", help="Ontology Turtle file")
parser.add_argument("graph", nargs="?", help="Knowledge graph Turtle file")
parser.add_argument("queries", nargs="?", help="RQ file containing # CQ queries")
parser.add_argument("output", nargs="?", help="Output JSON file")
args = parser.parse_args()


def find_file(filename):
    """Find a file from the current directory or the script's workspace."""
    search_roots = (Path.cwd(), Path(__file__).resolve().parent)
    for root in search_roots:
        candidate = root / filename
        if candidate.is_file():
            return candidate
        matches = sorted(root.rglob(filename), key=lambda p: len(p.parts))
        if matches:
            return matches[0]
    return None


ONTOLOGY = Path(args.ontology).expanduser() if args.ontology else find_file("wsu-ontology.ttl")
GRAPH = Path(args.graph).expanduser() if args.graph else find_file("*.ttl")
QUERIES = Path(args.queries).expanduser() if args.queries else (find_file("*.rq") if find_file("*.rq") else None)

if ONTOLOGY is None:
    parser.error("Ontology not found; provide its path as the first argument")
if GRAPH is None:
    parser.error("Graph not found; provide its path as the second argument")
if QUERIES is None:
    parser.error("RQ file not found; provide its path as the third argument")

ONTOLOGY = ONTOLOGY.resolve()
GRAPH = GRAPH.resolve()
QUERIES = QUERIES.resolve()
OUTPUT = Path(args.output).expanduser().resolve() if args.output else GRAPH.parent / "query_results.json"

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
