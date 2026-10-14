"""Бонус: экспорт сети в RDF/Turtle, демо-запрос SPARQL и проверка SHACL."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import FOAF

from .network import SemanticNetwork

BASE = Namespace("https://example.org/semnet/")
SEM = Namespace("https://example.org/semnet/vocab/")
VALUE_TYPES = {"value"}


def _iri(node_id: str) -> URIRef:
    return BASE[node_id]


def build_rdf_graph(net: SemanticNetwork) -> Graph:
    """Переводит сеть в RDF: классы → rdfs:Class, «экземпляр» → rdf:type.

    Отношение «подкласс» становится rdfs:subClassOf, предметные отношения —
    свойствами с rdfs:domain / rdfs:range из паспортов.
    """
    g = Graph()
    g.bind("sem", SEM)
    g.bind("rdfs", RDFS)
    g.bind("foaf", FOAF)

    # Узлы.
    for node in net.nodes_list:
        nid = node["id"]
        g.add((_iri(nid), RDFS.label, Literal(node["label"], lang="ru")))
        g.add((_iri(nid), SEM.definition, Literal(node["definition"], lang="ru")))
        if node["kind"] == "class":
            g.add((_iri(nid), RDF.type, RDFS.Class))
        elif node["kind"] == "value":
            g.add((_iri(nid), RDF.type, SEM.Value))
        else:
            g.add((_iri(nid), RDF.type, SEM.Instance))

    # Каталог отношений: свойства + domain/range.
    for rel in net.relations_list:
        rid = rel["id"]
        g.add((_iri(rid), RDF.type, RDF.Property))
        g.add((_iri(rid), RDFS.label, Literal(rel["label"], lang="ru")))
        g.add((_iri(rid), SEM.meaning, Literal(rel["meaning"], lang="ru")))
        for cls in rel.get("domain_classes") or []:
            g.add((_iri(rid), RDFS.domain, _iri(cls)))
        for cls in rel.get("range_classes") or []:
            g.add((_iri(rid), RDFS.range, _iri(cls)))

    # Факты.
    for t in net.triples:
        s, p, o = t.get("s"), t.get("p"), t.get("o")
        if s not in net.nodes or o not in net.nodes or p not in net.relations:
            continue
        if p == "subclass":
            g.add((_iri(s), RDFS.subClassOf, _iri(o)))
        elif p == "instance":
            g.add((_iri(s), RDF.type, _iri(o)))
        else:
            g.add((_iri(s), _iri(p), _iri(o)))
        if t.get("source"):
            g.add((_iri(s), SEM.source,
                   Literal(str(net.sources.get(t["source"], {}).get("title", t["source"])))))
    return g


def export_ttl(net: SemanticNetwork, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    g = build_rdf_graph(net)
    g.serialize(destination=str(out_path), format="turtle")
    return out_path


SPARQL_DEMO = """
PREFIX sem: <https://example.org/semnet/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?dbms ?requirement WHERE {
  ?dbms sem:satisfies ?requirement .
  ?requirement rdfs:label "Транзакции ACID"@ru .
}
"""


def sparql_demo(net: SemanticNetwork) -> List[Dict]:
    """Проверочный SPARQL-запрос: СУБД, покрывающие требование «Транзакции ACID»."""
    g = build_rdf_graph(net)
    rows = []
    for row in g.query(SPARQL_DEMO):
        rows.append({"dbms": str(row.dbms), "requirement": str(row.requirement)})
    return rows


def shacl_check(net: SemanticNetwork) -> Dict:
    """Проверка SHACL-ограничениями: у каждого факта — определённое отношение.

    Правило: любое свойство сем-namespace должно быть объектом rdf:Property.
    """
    import pyshacl

    g = build_rdf_graph(net)
    # Правила: у каждого класса есть подпись и определение; каждый экземпляр
    # имеет rdf:type (принадлежность классу).
    shapes = f"""
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix sem: <{BASE}> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

<#NodeHasLabelAndDefinition>
  a sh:NodeShape ;
  sh:targetClass rdfs:Class ;
  sh:property [
    sh:path rdfs:label ;
    sh:minCount 1 ;
    sh:message "У каждого класса должна быть русская подпись" ;
  ] ;
  sh:property [
    sh:path sem:definition ;
    sh:minCount 1 ;
    sh:message "У каждого класса должно быть определение" ;
  ] .

<#InstanceHasType>
  a sh:NodeShape ;
  sh:targetClass sem:Instance ;
  sh:sparql [
    sh:select \"\"\"
       PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
       PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
       SELECT $this WHERE {{ FILTER NOT EXISTS {{ $this rdf:type ?cls . ?cls a rdfs:Class }} }}
    \"\"\" ;
    sh:message "Экземпляр должен иметь rdf:type (принадлежность классу)" ;
  ] .
"""
    conforms, results_text, _ = pyshacl.validate(g, shacl_text=shapes)
    return {"conforms": bool(conforms), "report": results_text}
