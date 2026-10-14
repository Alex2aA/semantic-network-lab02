"""Пять проверочных сценариев семантической сети (unittest).

Сценарии соответствуют таблице проверок из лабораторной работы:
  1. поиск по отношению (соседи нужного типа);
  2. иерархия (предки и потомки);
  3. путь A → B (существующая объяснимая цепочка);
  4. нет пути (пустой результат без ошибки) — отрицательный сценарий;
  5. некорректные данные (понятное сообщение проверки).

Запуск:  python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from semantic_net.loader import load_network  # noqa: E402
from semantic_net.network import SemanticNetwork  # noqa: E402
from semantic_net.queries import EXPECTED, run_all  # noqa: E402


class SemanticNetworkTestCase(unittest.TestCase):
    """Базовый сценарий: сеть загружается из data/."""

    @classmethod
    def setUpClass(cls):
        cls.net = load_network(PROJECT_DIR / "data")


class Test1NeighborsByRelation(SemanticNetworkTestCase):
    """Проверка 1: поиск по отношению — все соседи нужного типа."""

    def test_outgoing_requires(self):
        result = self.net.neighbors("vac_java", relation="requires", direction="out")
        self.assertEqual(sorted(result), ["sk_java", "sk_spring", "sk_sql"])

    def test_neighbors_have_expected_types(self):
        """Каждый сосед по «требует» — экземпляр класса «Навык»."""
        for skill in self.net.neighbors("vac_java", relation="requires"):
            chain = self.net.class_chain(skill)
            self.assertIn("skill", chain,
                          f"узел '{skill}' не является навыком")

    def test_reverse_direction(self):
        """Обратный поиск: вакансии, требующие SQL."""
        result = self.net.neighbors("sk_sql", relation="requires", direction="in")
        self.assertEqual(sorted(result), ["vac_java", "vac_python"])

    def test_relation_filter_excludes_others(self):
        """Фильтр по отношению не смешивает типы связей."""
        knows_only = self.net.neighbors("cand_ivan", relation="knows")
        self.assertEqual(sorted(knows_only), ["sk_git", "sk_java", "sk_sql"])
        # Связи других типов («экземпляр», «имеет опыта») не попадают в выдачу.
        self.assertNotIn("candidate", knows_only)
        self.assertNotIn("val_op_3y", knows_only)
        knows_objects = [t["o"] for t in self.net.triples
                         if t["s"] == "cand_ivan" and t["p"] == "knows"]
        self.assertEqual(sorted(knows_only), sorted(knows_objects))


class Test2Hierarchy(SemanticNetworkTestCase):
    """Проверка 2: иерархия — верные предки и потомки."""

    def test_ancestors_of_instance(self):
        self.assertEqual(self.net.ancestors("vac_java"),
                         ["vacancy_backend", "vacancy_dev", "vacancy"])

    def test_ancestors_of_skill(self):
        self.assertEqual(self.net.ancestors("sk_spring"), ["skill_fw", "skill"])

    def test_descendants_of_vacancy(self):
        desc = self.net.descendants("vacancy")
        self.assertEqual(sorted(desc),
                         ["vac_java", "vac_python", "vacancy_backend", "vacancy_dev"])

    def test_hierarchy_has_two_levels(self):
        """Иерархия классов имеет минимум 2 уровня (3 узла в цепочке)."""
        self.assertEqual(self.net.ancestors("vacancy_backend"),
                         ["vacancy_dev", "vacancy"])


class Test3PathExists(SemanticNetworkTestCase):
    """Проверка 3: путь A → B — существующая объяснимая цепочка."""

    def test_path_course_to_vacancy(self):
        hops = self.net.find_path("crs_sql", "vac_java")
        self.assertTrue(hops, "ожидался существующий путь")
        self.assertEqual(self.net.path_nodes("crs_sql", "vac_java"),
                         ["crs_sql", "sk_sql", "vac_java"])

    def test_path_text_is_readable(self):
        hops = self.net.find_path("crs_sql", "vac_java")
        text = self.net.path_to_text(self.net, hops)
        self.assertEqual(
            text,
            "Курс «SQL: практика» —обучает→ SQL ←требует— Вакансия Java-разработчика",
        )

    def test_path_directions_match_triples(self):
        """Каждый шаг пути соответствует реально записанному факту."""
        hops = self.net.find_path("crs_spring", "cand_ivan")
        self.assertTrue(hops)
        facts = {(t["s"], t["p"], t["o"]) for t in self.net.triples}
        for hop in hops:
            key = ((hop.current, hop.rel, hop.next) if hop.forward
                   else (hop.next, hop.rel, hop.current))
            self.assertIn(key, facts)


class Test4NoPath(SemanticNetworkTestCase):
    """Проверка 4 (отрицательный сценарий): нет пути — пустой результат."""

    def test_no_path_in_hierarchy_only(self):
        """Между классами «Навык» и «Вакансия» нет пути по иерархическим связям."""
        hops = self.net.find_path("skill", "vacancy",
                                  relations={"subclass", "instance"})
        self.assertEqual(hops, [])  # пусто, исключение не выброшено

    def test_same_nodes_connected_by_subject_relations(self):
        """Контраст: при всех отношениях путь существует — проверка корректности фильтра."""
        hops = self.net.find_path("skill", "vacancy")
        self.assertTrue(hops)

    def test_unknown_node_reported_cleanly(self):
        with self.assertRaises(Exception) as ctx:
            self.net.find_path("no_such_node", "vac_java")
        self.assertIn("Неизвестный узел", str(ctx.exception))


class Test5Validate(SemanticNetworkTestCase):
    """Проверка 5: некорректные данные — понятное сообщение проверки."""

    def test_main_data_is_valid(self):
        errors = [i for i in self.net.validate() if i.severity == "error"]
        self.assertEqual(errors, [], [str(i) for i in errors])

    @staticmethod
    def _corrupted_network():
        nodes = [
            {"id": "a_cls", "kind": "class", "label": "Класс A", "definition": "d",
             "source": "model"},
            {"id": "b_cls", "kind": "class", "label": "Класс B", "definition": "d",
             "source": "model"},
            {"id": "dup", "kind": "instance", "label": "Дубль 1", "definition": "d",
             "source": "model"},
            {"id": "dup", "kind": "instance", "label": "Дубль 2", "definition": "d",
             "source": "model"},
            {"id": "stranger", "kind": "instance", "label": "Чужой объект",
             "definition": "d", "source": "model"},
        ]
        relations = [
            {"id": "subclass", "label": "подкласс", "domain_kinds": ["class"],
             "range_kinds": ["class"], "domain_classes": [], "range_classes": [],
             "meaning": "m", "inverse": "i", "transitive": True, "symmetric": False,
             "irreflexive": True},
            {"id": "knows", "label": "владеет", "domain_kinds": ["instance"],
             "domain_classes": ["a_cls"], "range_kinds": ["instance"],
             "range_classes": ["b_cls"], "meaning": "m", "inverse": "i",
             "transitive": False, "symmetric": False, "irreflexive": True},
        ]
        triples = [
            # цикл в иерархии
            {"s": "a_cls", "p": "subclass", "o": "b_cls", "source": "model"},
            {"s": "b_cls", "p": "subclass", "o": "a_cls", "source": "model"},
            # неизвестный узел и неизвестное отношение
            {"s": "ghost", "p": "knows", "o": "b_cls", "source": "model"},
            {"s": "a_cls", "p": "likes", "o": "b_cls", "source": "model"},
            # недопустимый тип конца: класс не может «владеть»
            {"s": "a_cls", "p": "knows", "o": "b_cls", "source": "model"},
            # неизвестный источник
            {"s": "b_cls", "p": "knows", "o": "a_cls", "source": "nope"},
            # верный вид узла, но не тот класс (и самоссылка по «владеет»)
            {"s": "stranger", "p": "knows", "o": "b_cls", "source": "model"},
            # самоссылка в иерархии
            {"s": "a_cls", "p": "subclass", "o": "a_cls", "source": "model"},
        ]
        sources = [{"id": "model", "title": "допущение", "locator": "—", "note": "—"}]
        return SemanticNetwork(nodes, relations, triples, sources)

    def test_corrupted_data_reports_all_error_types(self):
        net = self._corrupted_network()
        codes = {i.code for i in net.validate() if i.severity == "error"}
        for expected_code in ("DUPLICATE_NODE_ID", "UNKNOWN_NODE", "UNKNOWN_RELATION",
                              "ENDPOINT_TYPE_MISMATCH", "ENDPOINT_CLASS_MISMATCH",
                              "CYCLE_IN_HIERARCHY", "UNKNOWN_SOURCE", "SELF_LOOP"):
            self.assertIn(expected_code, codes,
                          f"ожидалась ошибка {expected_code}, получено: {sorted(codes)}")

    def test_messages_are_human_readable(self):
        net = self._corrupted_network()
        messages = [i.message for i in net.validate()]
        self.assertTrue(any("цикл" in m for m in messages))
        self.assertTrue(any("отсутствует в словаре" in m for m in messages))


class TestCompetencyQuestions(SemanticNetworkTestCase):
    """Контроль: ответы на 5 вопросов совпадают с ожидаемыми."""

    def test_all_expected_answers_reproduced(self):
        for result in run_all(self.net):
            self.assertEqual(
                result["answer"], EXPECTED[result["id"]],
                f"{result['id']}: {result['answer']} != {result['expected']}",
            )


class TestNetworkRequirements(SemanticNetworkTestCase):
    """Количественные требования лабораторной работы."""

    def test_node_and_relation_counts(self):
        stats = self.net.stats()
        self.assertGreaterEqual(stats["nodes"], 25)
        self.assertLessEqual(stats["nodes"], 40)
        self.assertGreaterEqual(stats["triples"], 30)
        self.assertGreaterEqual(stats["relations"], 5)

    def test_at_least_three_instances(self):
        stats = self.net.stats()
        self.assertGreaterEqual(stats["instances"], 3)

    def test_no_duplicate_ids(self):
        ids = [n["id"] for n in self.net.nodes_list]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
