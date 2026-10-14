"""Статическая визуализация сети: Graphviz DOT → PNG."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable, List, Optional

from .network import SemanticNetwork

PROJECT_DIR = Path(__file__).resolve().parents[1]
IMG_DIR = PROJECT_DIR / "img"
DOT_DIR = IMG_DIR / "dots"

NODE_STYLE = {
    "class": {"shape": "box", "style": "rounded,filled", "fillcolor": "#BBDEFB",
              "color": "#1565C0"},
    "instance": {"shape": "ellipse", "style": "filled", "fillcolor": "#C8E6C9",
                 "color": "#2E7D32"},
    "value": {"shape": "note", "style": "filled", "fillcolor": "#FFF59D",
              "color": "#F9A825"},
}

# Отношения иерархии выделяем пунктиром, предметные — сплошной линией.
HIERARCHY_EDGES = {"subclass", "instance", "part_of"}


def _esc(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _node_ids(net: SemanticNetwork, node_ids: Optional[Iterable[str]]) -> List[str]:
    if node_ids is None:
        return [n["id"] for n in net.nodes_list]
    selected = []
    for nid in node_ids:
        net.node(nid)  # контроль существования
        if nid not in selected:
            selected.append(nid)
    return selected


def build_dot(
    net: SemanticNetwork,
    node_ids: Optional[Iterable[str]] = None,
    title: Optional[str] = None,
    show_legend: bool = True,
    rankdir: str = "TB",
    clusters: Optional[List] = None,
    edge_relations: Optional[Iterable[str]] = None,
) -> str:
    """Собирает исходник Graphviz DOT для указанного набора узлов.

    clusters — список пар (заголовок блока, список идентификаторов узлов);
    узлы, не попавшие в блоки, выводятся на общем плане.
    edge_relations — выводить только эти типы отношений (None — все).
    """
    ids = _node_ids(net, node_ids)
    id_set = set(ids)
    allowed_edges = set(edge_relations) if edge_relations is not None else None

    lines = [
        "digraph SemanticNetwork {",
        f"  rankdir={rankdir};",
        '  graph [fontname="Helvetica", labelloc="t", labeljust="c", pad="0.3",'
        " nodesep=0.55, ranksep=1.6, newrank=true];",
        '  node [fontname="Helvetica", fontsize=11];',
        '  edge [fontname="Helvetica", fontsize=9, color="#37474F", arrowsize=0.7];',
    ]
    if title:
        lines.append(f'  label="{_esc(title)}";')

    if show_legend:
        lines += [
            "  subgraph cluster_legend {",
            '    label="Легенда"; fontsize=11; fontname="Helvetica";',
            '    style="rounded"; color="#90A4AE"; bgcolor="#FAFAFA";',
            '    lg_class [label="Класс", shape=box, style="rounded,filled",'
            ' fillcolor="#BBDEFB", color="#1565C0", fontsize=10];',
            '    lg_inst [label="Экземпляр", shape=ellipse, style=filled,'
            ' fillcolor="#C8E6C9", color="#2E7D32", fontsize=10];',
            '    lg_val [label="Значение свойства", shape=note, style=filled,'
            ' fillcolor="#FFF59D", color="#F9A825", fontsize=10];',
            '    lg_dir [label="Стрелка = направление факта,\\nподпись = тип отношения",'
            ' shape=plaintext, fontsize=9];',
            "    lg_class -> lg_inst [style=invis];",
            "    lg_inst -> lg_val [style=invis];",
            "    lg_val -> lg_dir [style=invis];",
            "  }",
        ]

    def emit_node(nid: str, indent: str = "  ") -> str:
        node = net.nodes[nid]
        style = NODE_STYLE.get(node["kind"], NODE_STYLE["instance"])
        label = f"{node['label']}\\n[{nid}]"
        opts = ", ".join(
            f'{k}="{v}"' if k in ("shape", "style", "fillcolor", "color") else f"{k}={v}"
            for k, v in style.items()
        )
        return f'{indent}"{_esc(nid)}" [label="{_esc(label)}", {opts}];'

    cluster_colors = ["#E3F2FD", "#E8F5E9", "#FFF8E1", "#F3E5F5", "#ECEFF1",
                      "#E0F7FA", "#FBE9E7", "#F1F8E9"]
    clustered: set = set()
    for idx, (cluster_title, cluster_nodes) in enumerate(clusters or []):
        members = [n for n in cluster_nodes if n in id_set and n not in clustered]
        if not members:
            continue
        clustered.update(members)
        color = cluster_colors[idx % len(cluster_colors)]
        lines.append(f'  subgraph "cluster_{idx}" {{')
        lines.append(f'    label="{_esc(cluster_title)}"; fontsize=11;'
                     ' fontname="Helvetica";')
        lines.append(f'    style="rounded,filled"; fillcolor="{color}";'
                     ' color="#78909C";')
        for nid in members:
            lines.append(emit_node(nid, indent="    "))
        lines.append("  }")

    for nid in ids:
        if nid not in clustered:
            lines.append(emit_node(nid))

    for t in net.triples:
        s, p, o = t.get("s"), t.get("p"), t.get("o")
        if s not in id_set or o not in id_set:
            continue
        if allowed_edges is not None and p not in allowed_edges:
            continue
        if s not in net.nodes or o not in net.nodes or p not in net.relations:
            continue  # некорректный факт в граф не выводим (находит validate)
        label = _esc(net.rel_label(p))
        if p in HIERARCHY_EDGES:
            lines.append(f'  "{_esc(s)}" -> "{_esc(o)}" [label="{label}", '
                         'style=dashed, color="#546E7A"];')
        else:
            lines.append(f'  "{_esc(s)}" -> "{_esc(o)}" [label="{label}"];')

    lines.append("}")
    return "\n".join(lines)


def render_graph(
    net: SemanticNetwork,
    out_path: Path,
    node_ids: Optional[Iterable[str]] = None,
    title: Optional[str] = None,
    dpi: int = 150,
    save_dot: bool = True,
    clusters: Optional[List] = None,
    edge_relations: Optional[Iterable[str]] = None,
) -> Path:
    """Рисует сеть по текущим данным: PNG рядом с исходником DOT."""
    if shutil.which("dot") is None:
        raise RuntimeError(
            "Не найден Graphviz (команда dot). Установите: brew install graphviz"
        )
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    dot_src = build_dot(net, node_ids=node_ids, title=title, clusters=clusters,
                        edge_relations=edge_relations)

    if save_dot:
        DOT_DIR.mkdir(parents=True, exist_ok=True)
        (DOT_DIR / (out_path.stem + ".dot")).write_text(dot_src, encoding="utf-8")

    subprocess.run(
        ["dot", f"-Tpng", f"-Gdpi={dpi}", "-o", str(out_path)],
        input=dot_src,
        text=True,
        check=True,
    )
    return out_path


# ---------------------------------------------------------------- фрагменты

def overview_nodes(net: SemanticNetwork) -> List[str]:
    """Обзорная схема: все узлы сети."""
    return [n["id"] for n in net.nodes_list]


def overview_clusters(net: SemanticNetwork) -> List:
    """Блоки обзорной схемы: иерархии, предметные группы, значения."""
    return [
        ("Классы: вакансии", ["vacancy", "vacancy_dev", "vacancy_backend"]),
        ("Классы: навыки", ["skill", "skill_lang", "skill_fw", "skill_db", "skill_tool"]),
        ("Классы: участники", ["candidate", "course", "course_module"]),
        ("Вакансии (экземпляры)", ["vac_java", "vac_python"]),
        ("Навыки (экземпляры)", ["sk_java", "sk_python", "sk_spring", "sk_django",
                                 "sk_sql", "sk_git", "sk_docker"]),
        ("Кандидаты", ["cand_ivan", "cand_maria", "cand_alex"]),
        ("Курсы и модули", ["crs_spring", "crs_sql", "crs_git",
                            "mod_spring_basics", "mod_sql_practice"]),
        ("Значения свойства «опыт»", ["val_op_1y", "val_op_2y", "val_op_3y"]),
    ]


def hierarchy_nodes(net: SemanticNetwork) -> List[str]:
    """Фрагмент «иерархия»: все классы и экземпляры (без значений)."""
    return [n["id"] for n in net.nodes_list if n["kind"] != "value"]


def hierarchy_clusters(net: SemanticNetwork) -> List:
    return [
        ("Иерархия: вакансии", ["vacancy", "vacancy_dev", "vacancy_backend"]),
        ("Иерархия: навыки", ["skill", "skill_lang", "skill_fw", "skill_db",
                              "skill_tool"]),
        ("Классы: участники", ["candidate", "course", "course_module"]),
        ("Экземпляры вакансий", ["vac_java", "vac_python"]),
        ("Экземпляры навыков", ["sk_java", "sk_python", "sk_spring", "sk_django",
                                "sk_sql", "sk_git", "sk_docker"]),
        ("Экземпляры: кандидаты", ["cand_ivan", "cand_maria", "cand_alex"]),
        ("Экземпляры: курсы и модули", ["crs_spring", "crs_sql", "crs_git",
                                         "mod_spring_basics", "mod_sql_practice"]),
    ]


def hiring_nodes(net: SemanticNetwork) -> List[str]:
    """Фрагмент «подбор»: вакансии, навыки, кандидаты, курсы и опыт."""
    return [
        "vac_java", "vac_python",
        "sk_java", "sk_python", "sk_spring", "sk_sql", "sk_git", "sk_docker",
        "cand_ivan", "cand_maria", "cand_alex",
        "crs_spring", "crs_sql", "crs_git",
        "val_op_1y", "val_op_2y", "val_op_3y",
    ]


def hiring_clusters(net: SemanticNetwork) -> List:
    return [
        ("Вакансии", ["vac_java", "vac_python"]),
        ("Навыки", ["sk_java", "sk_python", "sk_spring", "sk_sql", "sk_git",
                    "sk_docker"]),
        ("Кандидаты", ["cand_ivan", "cand_maria", "cand_alex"]),
        ("Курсы", ["crs_spring", "crs_sql", "crs_git"]),
        ("Значения свойства «опыт»", ["val_op_1y", "val_op_2y", "val_op_3y"]),
    ]


FRAGMENTS = {
    "overview": {
        "nodes": overview_nodes,
        "clusters": overview_clusters,
        "title": "Обзорная схема семантической сети",
    },
    "hierarchy": {
        "nodes": hierarchy_nodes,
        "clusters": hierarchy_clusters,
        "title": "Фрагмент 1. Иерархия классов и принадлежность экземпляров",
        "edge_relations": ["subclass", "instance", "part_of"],
    },
    "hiring": {
        "nodes": hiring_nodes,
        "clusters": hiring_clusters,
        "title": "Фрагмент 2. Подбор: вакансии, навыки, кандидаты, курсы",
    },
}
