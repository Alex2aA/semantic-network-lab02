"""Пять компетентностных вопросов и их воспроизводимые ответы.

Ожидаемые ответы зафиксированы ДО запуска (константа EXPECTED) и
сопоставляются с фактическим результатом в тестах и в CLI `queries`.
Домен: выбор СУБД для проекта (фрагмент экспертных знаний).
"""

from __future__ import annotations

from typing import Dict, List

from .network import SemanticNetwork

QUESTIONS: List[Dict[str, str]] = [
    {
        "id": "Q1",
        "question": ("Какие СУБД удовлетворяют требованию проекта "
                     "«Онлайн-магазин» — транзакциям ACID?"),
        "expected": "[MySQL, Oracle Database, PostgreSQL, SQLite]",
    },
    {
        "id": "Q2",
        "question": ("Какие требования проекта «Онлайн-магазин» покрыты "
                     "PostgreSQL, а какие — нет по данным графа?"),
        "expected": ("покрыты: [Транзакции ACID, Хранение документов, "
                     "Горизонтальное масштабирование]; не покрыто: [Низкая задержка чтения]"),
    },
    {
        "id": "Q3",
        "question": ("Какие критерии выбора соответствуют требованиям "
                     "проекта «Сервис рекомендаций»?"),
        "expected": "[Модель данных и формат, Задержка операций]",
    },
    {
        "id": "Q4",
        "question": ("Какие подклассы есть у класса «СУБД» и какие конкретные "
                     "СУБД к ним относятся?"),
        "expected": ("подклассы: [Графовая СУБД, Документо-ориентированная СУБД, "
                     "Операционная (OLTP) СУБД, Реляционная СУБД, СУБД ключ–значение]; "
                     "экземпляры: [MongoDB, MySQL, Neo4j, Oracle Database, "
                     "PostgreSQL, Redis, SQLite]"),
    },
    {
        "id": "Q5",
        "question": ("Какой путь связывает проект «Сервис рекомендаций» "
                     "с СУБД Neo4j (по предметным связям)?"),
        "expected": ("Проект «Сервис рекомендаций» —предъявляет→ Граф связей "
                     "←удовлетворяет— Neo4j"),
    },
]

EXPECTED = {q["id"]: q["expected"] for q in QUESTIONS}


def requirements_for(net: SemanticNetwork, project: str) -> List[str]:
    """Требования, которые предъявляет проект."""
    return net.neighbors(project, "presents")


def covered_requirements(net: SemanticNetwork, dbms: str) -> List[str]:
    """Требования, которые СУБД покрывает по данным графа."""
    return net.neighbors(dbms, "satisfies")


def gap_analysis(net: SemanticNetwork, project: str, dbms: str) -> Dict:
    """Сравнение требований проекта и покрытия со стороны СУБД."""
    required = requirements_for(net, project)
    covered_list = covered_requirements(net, dbms)
    covered = [r for r in required if r in covered_list]
    missing = [r for r in required if r not in covered_list]
    evidence = (
        [f"{net.label(project)} —предъявляет→ {net.label(r)}" for r in required]
        + [f"{net.label(dbms)} —удовлетворяет→ {net.label(r)}" for r in covered_list]
    )
    return {"required": required, "covered": covered, "missing": missing,
            "evidence": evidence}


def answer_q1(net: SemanticNetwork) -> Dict:
    matches = sorted(net.neighbors("req_acid", "satisfies", direction="in"),
                     key=lambda n: net.label(n))
    return {
        "id": "Q1",
        "question": QUESTIONS[0]["question"],
        "expected": EXPECTED["Q1"],
        "answer": "[" + ", ".join(net.label(m) for m in matches) + "]",
        "method": "neighbors(req_acid, relation='удовлетворяет', direction='in')",
        "evidence": [f"{net.label(m)} —удовлетворяет→ Транзакции ACID"
                     for m in matches],
        "explanation": ("Обратный поиск по типу связи: вакантно не «какая СУБД "
                        "лучше», а какие СУБД связаны фактом «удовлетворяет» с "
                        "конкретным требованием."),
    }


def answer_q2(net: SemanticNetwork) -> Dict:
    gap = gap_analysis(net, "project_shop", "postgresql")
    return {
        "id": "Q2",
        "question": QUESTIONS[1]["question"],
        "expected": EXPECTED["Q2"],
        "answer": ("покрыты: [" + ", ".join(net.label(r) for r in gap["covered"]) +
                   "]; не покрыто: [" + ", ".join(net.label(r) for r in gap["missing"]) + "]"),
        "method": "neighbors(project, 'предъявляет') и neighbors(dbms, 'удовлетворяет') → разность множеств",
        "evidence": gap["evidence"],
        "explanation": ("Ни одно из требований магазина не связано фактом "
                        "«удовлетворяет» с низкой задержкой чтения для PostgreSQL, "
                        "поэтому требование попадает в разность множеств. Вывод "
                        "держится на явно записанных связях."),
    }


def answer_q3(net: SemanticNetwork) -> Dict:
    requirements = requirements_for(net, "project_reco")
    criteria = []
    for req in requirements:
        for crit in net.neighbors(req, "evaluated_by"):
            if crit not in criteria:
                criteria.append(crit)
    return {
        "id": "Q3",
        "question": QUESTIONS[2]["question"],
        "expected": EXPECTED["Q3"],
        "answer": "[" + ", ".join(net.label(c) for c in criteria) + "]",
        "method": "neighbors(project, 'предъявляет') → neighbors(требование, 'оценивается по')",
        "evidence": (
            [f"{net.label('project_reco')} —предъявляет→ {net.label(r)}"
             for r in requirements]
            + [f"{net.label(r)} —оценивается по→ {net.label(c)}"
               for r in requirements for c in net.neighbors(r, "evaluated_by")]
        ),
        "explanation": ("Требования проекта переводятся в критерии сравнения: "
                        "граф связывает требование с критерием, по которому "
                        "эксперт будет сравнивать кандидатные СУБД."),
    }


def answer_q4(net: SemanticNetwork) -> Dict:
    all_desc = net.descendants("dbms")
    subclasses = sorted((d for d in all_desc if net.kind(d) == "class"),
                        key=lambda n: net.label(n))
    instances = sorted((d for d in all_desc if net.kind(d) == "instance"),
                       key=lambda n: net.label(n))
    return {
        "id": "Q4",
        "question": QUESTIONS[3]["question"],
        "expected": EXPECTED["Q4"],
        "answer": ("подклассы: [" + ", ".join(net.label(c) for c in subclasses) +
                   "]; экземпляры: [" + ", ".join(net.label(i) for i in instances) + "]"),
        "method": "descendants('dbms') — транзитивный обход «подкласс» + «экземпляр»",
        "evidence": (
            [f"{net.label('dbms_rel')} —подкласс→ СУБД",
             f"{net.label('dbms_oltp')} —подкласс→ Реляционная СУБД"]
            + [f"{net.label(i)} —экземпляр→ {net.label(net.classes_of(i)[0])}"
               for i in instances]
        ),
        "explanation": ("Иерархия имеет два уровня вложенности: СУБД → "
                        "Реляционная СУБД → Операционная (OLTP) СУБД; конкретные "
                        "системы — экземпляры нижних классов."),
    }


def answer_q5(net: SemanticNetwork) -> Dict:
    hops = net.find_path("project_reco", "neo4j",
                         relations={"presents", "satisfies"})
    text = SemanticNetwork.path_to_text(net, hops)
    return {
        "id": "Q5",
        "question": QUESTIONS[4]["question"],
        "expected": EXPECTED["Q5"],
        "answer": text,
        "method": ("find_path('project_reco', 'neo4j', "
                   "relations={'предъявляет', 'удовлетворяет'}) — поиск в ширину"),
        "evidence": ["Сервис рекомендаций —предъявляет→ Граф связей",
                     "Neo4j —удовлетворяет→ Граф связей"],
        "explanation": ("Цепочка читается как два утверждения: проект предъявляет "
                        "требование «граф связей», а Neo4j это требование "
                        "удовлетворяет; стрелки показывают направление фактов. "
                        "Фильтр исключает прямой факт «рекомендует», чтобы "
                        "показать объяснимую предметную цепочку."),
    }


def run_all(net: SemanticNetwork) -> List[Dict]:
    """Запускает все пять вопросов и возвращает их результаты."""
    return [answer_q1(net), answer_q2(net), answer_q3(net), answer_q4(net), answer_q5(net)]


def print_results(results: List[Dict]) -> None:
    for res in results:
        print(f"\n{res['id']}. {res['question']}")
        print(f"   Ожидаемый ответ : {res['expected']}")
        print(f"   Фактический ответ: {res['answer']}")
        print(f"   Метод            : {res['method']}")
        status = "СОВПАДАЕТ" if res["answer"] == res["expected"] else "РАСХОЖДЕНИЕ"
        print(f"   Контроль         : {status}")
        if res.get("evidence"):
            print("   Опорные факты:")
            for ev in res["evidence"]:
                print(f"     - {ev}")
        if res.get("explanation"):
            print(f"   Объяснение       : {res['explanation']}")
