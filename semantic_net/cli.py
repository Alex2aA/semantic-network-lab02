"""Консольный интерфейс: валидация, запросы, поиск, отрисовка, экспорт."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import DATA_DIR, load_network
from .network import UnknownNodeError, UnknownRelationError
from .queries import print_results, run_all
from .render import FRAGMENTS, IMG_DIR, render_graph


def _cmd_validate(net) -> int:
    issues = net.validate()
    stats = net.stats()
    print("Сводка сети: "
          f"{stats['nodes']} узлов ({stats['classes']} классов, "
          f"{stats['instances']} экземпляров, {stats['values']} значений), "
          f"{stats['relations']} типов отношений, {stats['triples']} фактов, "
          f"{stats['sources']} источников.")
    if not issues:
        print("Проверка целостности: ошибок и предупреждений нет.")
        return 0
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    for issue in issues:
        print(f"  {issue}")
    print(f"Итого: {len(errors)} ошибок, {len(warnings)} предупреждений.")
    return 1 if errors else 0


def _cmd_queries(net) -> int:
    print_results(run_all(net))
    return 0


def _cmd_neighbors(net, args) -> int:
    nodes = net.neighbors(args.node, relation=args.rel, direction=args.direction)
    rel_txt = f"по отношению «{net.rel_label(args.rel)}»" if args.rel else "по всем отношениям"
    dir_txt = {"out": "по стрелке", "in": "против стрелки", "both": "в обе стороны"}[args.direction]
    print(f"Соседи узла «{net.label(args.node)}» {rel_txt}, {dir_txt}:")
    if not nodes:
        print("  (нет)")
    for nid in nodes:
        print(f"  - {net.label(nid)} [{nid}]")
    return 0


def _cmd_hierarchy(net, args, kind: str) -> int:
    if kind == "ancestors":
        nodes = net.ancestors(args.node)
        title = "Предки"
    else:
        nodes = net.descendants(args.node)
        title = "Потомки"
    print(f"{title} узла «{net.label(args.node)}»:")
    if not nodes:
        print("  (нет)")
    for nid in nodes:
        print(f"  - [{net.kind(nid)}] {net.label(nid)} [{nid}]")
    return 0


def _cmd_path(net, args) -> int:
    relations = args.rel if args.rel else None
    hops = net.find_path(args.source, args.target, relations)
    if not hops:
        print(f"Путь между «{net.label(args.source)}» и "
              f"«{net.label(args.target)}» не найден (пустой результат, без ошибки).")
        return 0
    print("Цепочка: " + net.path_to_text(net, hops))
    print("Шаги:")
    for i, hop in enumerate(hops, 1):
        rel = net.rel_label(hop.rel)
        sign = f"—[{rel}]→" if hop.forward else f"←[{rel}]—"
        note = "" if hop.forward else " (движение против стрелки)"
        print(f"  {i}. {net.label(hop.current)} {sign} {net.label(hop.next)}{note}")
    return 0


def _cmd_render(net, args) -> int:
    if args.fragment:
        spec = FRAGMENTS[args.fragment]
        node_ids = spec["nodes"](net)
        clusters = spec["clusters"](net)
        edge_relations = spec.get("edge_relations")
        title = args.title or spec["title"]
        out = Path(args.out) if args.out else IMG_DIR / f"{args.fragment}.png"
    else:
        node_ids = args.nodes or None
        clusters = None
        edge_relations = None
        title = args.title
        out = Path(args.out) if args.out else IMG_DIR / "custom.png"
    path = render_graph(net, out, node_ids=node_ids, title=title, clusters=clusters,
                        edge_relations=edge_relations)
    print(f"Изображение сохранено: {path}")
    return 0


def _cmd_export_rdf(net, args) -> int:
    from .rdf_export import export_ttl, shacl_check, sparql_demo

    out = Path(args.out) if args.out else Path(__file__).resolve().parents[1] / "export" / "graph.ttl"
    path = export_ttl(net, out)
    print(f"RDF/Turtle сохранён: {path}")
    rows = sparql_demo(net)
    print("SPARQL-демо (требования вакансии Java-разработчика):")
    for row in rows:
        print(f"  {row['vacancy']} -> {row['skill']}")
    if not args.no_shacl:
        report = shacl_check(net)
        print("SHACL-проверка: " + ("соответствует" if report["conforms"]
                                    else "есть нарушения"))
        if not report["conforms"]:
            print(report["report"])
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="semantic_net",
        description="Семантическая сеть: загрузка, поиск, проверка и визуализация.",
    )
    parser.add_argument("--data", default=str(DATA_DIR),
                        help="каталог с файлами данных (по умолчанию: data/)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="проверить целостность данных")
    sub.add_parser("queries", help="ответить на 5 компетентностных вопросов")
    sub.add_parser("stats", help="показать сводку по сети")

    p = sub.add_parser("neighbors", help="соседи по типу отношения")
    p.add_argument("node")
    p.add_argument("--rel", help="идентификатор отношения (например, requires)")
    p.add_argument("--direction", choices=["out", "in", "both"], default="out")

    p = sub.add_parser("ancestors", help="предки в иерархии")
    p.add_argument("node")

    p = sub.add_parser("descendants", help="потомки в иерархии")
    p.add_argument("node")

    p = sub.add_parser("path", help="путь между двумя узлами")
    p.add_argument("source")
    p.add_argument("target")
    p.add_argument("--rel", nargs="*", help="учитывать только эти типы отношений")

    p = sub.add_parser("render", help="построить изображение графа")
    p.add_argument("--fragment", choices=sorted(FRAGMENTS), default=None)
    p.add_argument("--nodes", nargs="*", help="узлы для собственного фрагмента")
    p.add_argument("--out", help="путь к PNG")
    p.add_argument("--title", help="заголовок схемы")

    p = sub.add_parser("export-rdf", help="экспорт в RDF/Turtle + SPARQL + SHACL")
    p.add_argument("--out", help="путь к graph.ttl")
    p.add_argument("--no-shacl", action="store_true", help="пропустить SHACL-проверку")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    net = load_network(Path(args.data))
    try:
        if args.command == "validate":
            return _cmd_validate(net)
        if args.command == "queries":
            return _cmd_queries(net)
        if args.command == "stats":
            stats = net.stats()
            for key, value in stats.items():
                print(f"{key}: {value}")
            return 0
        if args.command == "neighbors":
            return _cmd_neighbors(net, args)
        if args.command == "ancestors":
            return _cmd_hierarchy(net, args, "ancestors")
        if args.command == "descendants":
            return _cmd_hierarchy(net, args, "descendants")
        if args.command == "path":
            return _cmd_path(net, args)
        if args.command == "render":
            return _cmd_render(net, args)
        if args.command == "export-rdf":
            return _cmd_export_rdf(net, args)
    except (UnknownNodeError, UnknownRelationError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
