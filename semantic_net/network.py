"""Ядро семантической сети: модель данных, поиск и проверка целостности."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

# Отношения, образующие иерархию (проверка циклов выполняется по ним).
HIERARCHY_RELATIONS = ("subclass", "part_of")

KINDS = ("class", "instance", "value")
KIND_LABELS = {"class": "класс", "instance": "экземпляр", "value": "значение"}


class UnknownNodeError(ValueError):
    """Узел с указанным идентификатором отсутствует в сети."""


class UnknownRelationError(ValueError):
    """Отношение с указанным идентификатором отсутствует в каталоге."""


@dataclass(frozen=True)
class Issue:
    """Результат проверки целостности сети."""

    code: str
    severity: str  # "error" | "warning"
    message: str

    def __str__(self) -> str:
        mark = "ОШИБКА" if self.severity == "error" else "предупреждение"
        return f"[{mark}] {self.code}: {self.message}"


@dataclass(frozen=True)
class Hop:
    """Шаг пути: из узла current в узел next по отношению rel.

    forward=True  — движение вдоль стрелки: current —rel→ next;
    forward=False — движение против стрелки: next —rel→ current.
    """

    current: str
    rel: str
    next: str
    forward: bool


class SemanticNetwork:
    """Ориентированный подписанный граф знаний.

    Узлы (nodes)   — классы, экземпляры и значения свойств.
    Отношения (relations) — каталог «паспортов» дуг.
    Факты (triples) — триплеты «субъект — отношение → объект».
    """

    def __init__(self, nodes, relations, triples, sources=None):
        self.nodes_list: List[dict] = list(nodes)
        self.relations_list: List[dict] = list(relations)
        self.triples: List[dict] = list(triples)
        self.sources_list: List[dict] = list(sources or [])

        # Индексы с контролем дублей идентификаторов.
        self.nodes: Dict[str, dict] = {}
        self.relations: Dict[str, dict] = {}
        self.sources: Dict[str, dict] = {}
        self.duplicate_node_ids: List[str] = []
        self.duplicate_relation_ids: List[str] = []
        self.duplicate_source_ids: List[str] = []

        for item in self.nodes_list:
            nid = item["id"]
            if nid in self.nodes:
                if nid not in self.duplicate_node_ids:
                    self.duplicate_node_ids.append(nid)
            else:
                self.nodes[nid] = item
        for item in self.relations_list:
            rid = item["id"]
            if rid in self.relations:
                if rid not in self.duplicate_relation_ids:
                    self.duplicate_relation_ids.append(rid)
            else:
                self.relations[rid] = item
        for item in self.sources_list:
            sid = item["id"]
            if sid in self.sources:
                if sid not in self.duplicate_source_ids:
                    self.duplicate_source_ids.append(sid)
            else:
                self.sources[sid] = item

        # Индексы соседства: только по факту, у которого известны оба конца
        # и отношение; некорректные факты находит validate().
        self._out: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        self._in: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for t in self.triples:
            s, p, o = t.get("s"), t.get("p"), t.get("o")
            if s in self.nodes and o in self.nodes and p in self.relations:
                self._out[(s, p)].append(o)
                self._in[(o, p)].append(s)

    # ------------------------------------------------------------------ узлы

    def node(self, node_id: str) -> dict:
        """Возвращает запись узла; при отсутствии — понятную ошибку."""
        if node_id not in self.nodes:
            raise UnknownNodeError(
                f"Неизвестный узел '{node_id}'. Всего узлов в сети: {len(self.nodes)}."
            )
        return self.nodes[node_id]

    def label(self, node_id: str) -> str:
        """Человекочитаемая подпись узла (с фолбэком на идентификатор)."""
        node = self.nodes.get(node_id)
        return node["label"] if node else node_id

    def kind(self, node_id: str) -> str:
        return self.node(node_id)["kind"]

    def classes_of(self, node_id: str) -> List[str]:
        """Непосредственные классы объекта (по отношению «экземпляр»)."""
        self.node(node_id)
        return list(self._out.get((node_id, "instance"), []))

    def class_chain(self, node_id: str) -> List[str]:
        """Все классы объекта, включая предков по отношениям «подкласс».

        Для класса возвращает его собственных предков плюс его самого —
        полезно для проверки допустимости концов связи.
        """
        node = self.node(node_id)
        if node["kind"] == "class":
            return [node_id] + self.ancestors(node_id)
        if node["kind"] == "instance":
            return self.ancestors(node_id)
        return []

    # ------------------------------------------------------------ отношения

    def relation(self, rel_id: str) -> dict:
        if rel_id not in self.relations:
            raise UnknownRelationError(
                f"Неизвестное отношение '{rel_id}'. В каталоге: "
                + ", ".join(sorted(self.relations))
            )
        return self.relations[rel_id]

    def rel_label(self, rel_id: str) -> str:
        rel = self.relations.get(rel_id)
        return rel["label"] if rel else rel_id

    def triples_of(self, node_id: str) -> List[dict]:
        """Все факты, где узел выступает субъектом или объектом."""
        self.node(node_id)
        return [t for t in self.triples if t.get("s") == node_id or t.get("o") == node_id]

    def neighbors(
        self,
        node_id: str,
        relation: Optional[str] = None,
        direction: str = "out",
    ) -> List[str]:
        """Соседи по выбранному типу отношения.

        direction="out"  — по стрелке (узел — отношение → сосед);
        direction="in"   — против стрелки (сосед — отношение → узел);
        direction="both" — в обе стороны.
        Без relation возвращаются все соседи по всем типам связей.
        """
        self.node(node_id)
        if relation is not None:
            self.relation(relation)
        if direction not in ("out", "in", "both"):
            raise ValueError("direction должен быть 'out', 'in' или 'both'")

        result: List[str] = []
        seen: Set[str] = set()

        def push(nid: str) -> None:
            if nid not in seen and nid != node_id:
                seen.add(nid)
                result.append(nid)

        def walk_out() -> None:
            if relation is not None:
                for o in self._out.get((node_id, relation), []):
                    push(o)
            else:
                for t in self.triples:
                    if t.get("s") == node_id and t.get("o") in self.nodes:
                        push(t["o"])

        def walk_in() -> None:
            if relation is not None:
                for s in self._in.get((node_id, relation), []):
                    push(s)
            else:
                for t in self.triples:
                    if t.get("o") == node_id and t.get("s") in self.nodes:
                        push(t["s"])

        if direction in ("out", "both"):
            walk_out()
        if direction in ("in", "both"):
            walk_in()
        return result

    # ----------------------------------------------------------- иерархия

    def ancestors(self, node_id: str) -> List[str]:
        """Предки в иерархии: для экземпляра — классы, для класса — надклассы.

        Порядок — от ближнего предка к дальнему.
        """
        node = self.node(node_id)
        if node["kind"] == "value":
            return []
        if node["kind"] == "instance":
            result: List[str] = list(self.classes_of(node_id))
            queue: deque = deque(result)
            seen: Set[str] = set(result)
        else:  # класс: обходим надклассы, начиная с него самого
            result = []
            queue = deque([node_id])
            seen = {node_id}
        while queue:
            current = queue.popleft()
            for sup in self._out.get((current, "subclass"), []):
                if sup not in seen:
                    seen.add(sup)
                    result.append(sup)
                    queue.append(sup)
        return result

    def descendants(self, node_id: str) -> List[str]:
        """Потомки класса: подклассы + экземпляры самого класса и подклассов.

        Для экземпляра и значения возвращает [].
        """
        node = self.node(node_id)
        if node["kind"] != "class":
            return []
        subclasses: List[str] = []
        seen: Set[str] = set()
        queue: deque = deque([node_id])
        while queue:
            current = queue.popleft()
            for sub in self._in.get((current, "subclass"), []):
                if sub not in seen:
                    seen.add(sub)
                    subclasses.append(sub)
                    queue.append(sub)
        result = list(subclasses)
        for cls in [node_id] + subclasses:
            for inst in self._in.get((cls, "instance"), []):
                if inst not in result:
                    result.append(inst)
        return result

    # --------------------------------------------------------------- путь

    def find_path(
        self, source: str, target: str, relations: Optional[Iterable[str]] = None
    ) -> List[Hop]:
        """Ищет путь между двумя узлами (в обе стороны дуг).

        Возвращает список шагов-«ходов»; пустой список — пути нет
        (не является ошибкой). Если задан relations, учитываются только
        указанные типы отношений.
        """
        self.node(source)
        self.node(target)
        allowed = set(relations) if relations is not None else None
        if allowed is not None:
            for rel in allowed:
                self.relation(rel)

        adjacency: Dict[str, List[Tuple[str, str, bool]]] = defaultdict(list)
        for t in self.triples:
            s, p, o = t.get("s"), t.get("p"), t.get("o")
            if allowed is not None and p not in allowed:
                continue
            if s in self.nodes and o in self.nodes and p in self.relations:
                adjacency[s].append((o, p, True))
                adjacency[o].append((s, p, False))

        if source == target:
            return []

        prev: Dict[str, Tuple[str, str, bool]] = {}
        visited: Set[str] = {source}
        queue: deque = deque([source])
        while queue:
            current = queue.popleft()
            for nxt, rel, forward in adjacency.get(current, []):
                if nxt in visited:
                    continue
                visited.add(nxt)
                prev[nxt] = (current, rel, forward)
                if nxt == target:
                    hops: List[Hop] = []
                    cursor = target
                    while cursor != source:
                        base, rel, forward = prev[cursor]
                        hops.append(Hop(base, rel, cursor, forward))
                        cursor = base
                    hops.reverse()
                    return hops
                queue.append(nxt)
        return []

    def path_nodes(self, source: str, target: str,
                   relations: Optional[Iterable[str]] = None) -> List[str]:
        """Путь в виде последовательности узлов (без дублей)."""
        hops = self.find_path(source, target, relations)
        if not hops:
            return []
        nodes = [hops[0].current] + [h.next for h in hops]
        return nodes

    @staticmethod
    def path_to_text(net: "SemanticNetwork", hops: List[Hop]) -> str:
        """Понятная цепочка: «A —предъявляет→ B ←удовлетворяет— C»."""
        if not hops:
            return "(путь не найден)"
        parts = [net.label(hops[0].current)]
        for hop in hops:
            rel = net.rel_label(hop.rel)
            other = net.label(hop.next)
            if hop.forward:
                parts.append(f" —{rel}→ {other}")
            else:
                parts.append(f" ←{rel}— {other}")
        return "".join(parts)

    # --------------------------------------------------------- валидация

    def validate(self) -> List[Issue]:
        """Проверка целостности: дубли, неизвестные узлы, типы концов, циклы."""
        issues: List[Issue] = []

        for nid in self.duplicate_node_ids:
            issues.append(Issue("DUPLICATE_NODE_ID", "error",
                                f"повторяющийся идентификатор узла '{nid}'"))
        for rid in self.duplicate_relation_ids:
            issues.append(Issue("DUPLICATE_RELATION_ID", "error",
                                f"повторяющийся идентификатор отношения '{rid}'"))
        for sid in self.duplicate_source_ids:
            issues.append(Issue("DUPLICATE_SOURCE_ID", "error",
                                f"повторяющийся идентификатор источника '{sid}'"))

        seen_facts: Set[Tuple[str, str, str]] = set()
        for idx, t in enumerate(self.triples, start=1):
            s, p, o = t.get("s"), t.get("p"), t.get("o")
            fact = f"факт №{idx}: '{s}' —{p}→ '{o}'"
            unknown = False
            if s not in self.nodes:
                issues.append(Issue("UNKNOWN_NODE", "error",
                                    f"{fact}: субъект '{s}' отсутствует в словаре"))
                unknown = True
            if o not in self.nodes:
                issues.append(Issue("UNKNOWN_NODE", "error",
                                    f"{fact}: объект '{o}' отсутствует в словаре"))
                unknown = True
            if p not in self.relations:
                issues.append(Issue("UNKNOWN_RELATION", "error",
                                    f"{fact}: отношение '{p}' отсутствует в каталоге"))
                unknown = True
            if unknown:
                continue

            key = (s, p, o)
            if key in seen_facts:
                issues.append(Issue("DUPLICATE_FACT", "warning",
                                    f"{fact}: такой факт уже встречался"))
            seen_facts.add(key)

            src = t.get("source")
            if src not in self.sources:
                issues.append(Issue("UNKNOWN_SOURCE", "error",
                                    f"{fact}: источник '{src}' не найден в sources.json"))
            elif src == "model":
                pass  # модельное допущение — допустимая пометка

            rel = self.relations[p]
            issues.extend(self._check_endpoints(fact, s, o, rel))
            if s == o and rel.get("irreflexive"):
                issues.append(Issue("SELF_LOOP", "error",
                                    f"{fact}: отношение '{rel['label']}' не допускает "
                                    "самоссылки (s = o)"))

        issues.extend(self._check_cycles())

        connected = {t.get("s") for t in self.triples} | {t.get("o") for t in self.triples}
        for nid, node in self.nodes.items():
            if nid not in connected:
                issues.append(Issue("ORPHAN_NODE", "warning",
                                    f"узел '{nid}' ({node['label']}) не имеет ни одной связи"))
        return issues

    def _check_endpoints(self, fact: str, s: str, o: str, rel: dict) -> List[Issue]:
        issues: List[Issue] = []

        def check(node_id: str, side: str, kinds: Sequence[str],
                   classes: Sequence[str]) -> None:
            node = self.nodes[node_id]
            if node["kind"] not in kinds:
                allowed = ", ".join(KIND_LABELS.get(k, k) for k in kinds)
                issues.append(Issue(
                    "ENDPOINT_TYPE_MISMATCH", "error",
                    f"{fact}: {side} '{node_id}' имеет тип "
                    f"«{KIND_LABELS.get(node['kind'], node['kind'])}», а отношение "
                    f"«{rel['label']}» допускает только: {allowed}"))
                return
            if classes:
                chain = self.class_chain(node_id)
                if not any(c in classes for c in chain):
                    need = ", ".join(self.label(c) for c in classes)
                    got = ", ".join(self.label(c) for c in chain) or "—"
                    issues.append(Issue(
                        "ENDPOINT_CLASS_MISMATCH", "error",
                        f"{fact}: {side} '{node_id}' не принадлежит допустимым классам "
                        f"отношения «{rel['label']}» (нужен класс: {need}; "
                        f"фактические классы: {got})"))

        check(s, "субъект", rel.get("domain_kinds", KINDS),
              rel.get("domain_classes") or [])
        check(o, "объект", rel.get("range_kinds", KINDS),
              rel.get("range_classes") or [])
        return issues

    def _check_cycles(self) -> List[Issue]:
        issues: List[Issue] = []
        for rel_id in HIERARCHY_RELATIONS:
            if rel_id not in self.relations:
                continue
            graph: Dict[str, List[str]] = defaultdict(list)
            for t in self.triples:
                if t.get("p") == rel_id and t.get("s") in self.nodes and t.get("o") in self.nodes:
                    graph[t["s"]].append(t["o"])

            state: Dict[str, int] = {}  # 0 — не посещён, 1 — в стеке, 2 — готов
            stack: List[str] = []

            def dfs(u: str) -> Optional[List[str]]:
                state[u] = 1
                stack.append(u)
                for v in graph.get(u, []):
                    if state.get(v, 0) == 1:
                        cycle = stack[stack.index(v):] + [v]
                        return cycle
                    if state.get(v, 0) == 0:
                        found = dfs(v)
                        if found:
                            return found
                stack.pop()
                state[u] = 2
                return None

            for start in list(graph):
                if state.get(start, 0) == 0:
                    cycle = dfs(start)
                    if cycle:
                        rel_label = self.rel_label(rel_id)
                        chain = " → ".join(cycle)
                        issues.append(Issue(
                            "CYCLE_IN_HIERARCHY", "error",
                            f"цикл в отношении «{rel_label}»: {chain}"))
                        break  # достаточно одного цикла на отношение
        return issues

    # ------------------------------------------------------------- сводка

    def stats(self) -> Dict[str, int]:
        return {
            "nodes": len(self.nodes),
            "classes": sum(1 for n in self.nodes.values() if n["kind"] == "class"),
            "instances": sum(1 for n in self.nodes.values() if n["kind"] == "instance"),
            "values": sum(1 for n in self.nodes.values() if n["kind"] == "value"),
            "relations": len(self.relations),
            "triples": len(self.triples),
            "sources": len(self.sources),
        }
