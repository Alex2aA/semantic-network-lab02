"""Пять компетентностных вопросов и их воспроизводимые ответы.

Ожидаемые ответы зафиксированы ДО запуска (константа EXPECTED) и
сопоставляются с фактическим результатом в тестах и в CLI `queries`.
"""

from __future__ import annotations

from typing import Dict, List

from .network import SemanticNetwork

QUESTIONS: List[Dict[str, str]] = [
    {
        "id": "Q1",
        "question": "Какие навыки требуются для вакансии Java-разработчика?",
        "expected": "[Java, Spring Framework, SQL]",
    },
    {
        "id": "Q2",
        "question": ("Каких навыков не хватает кандидату Ивану, чтобы претендовать "
                     "на вакансию Java-разработчика, и какие требования уже покрыты?"),
        "expected": "покрыты: [Java, SQL]; не хватает: [Spring Framework]",
    },
    {
        "id": "Q3",
        "question": ("Какие курсы помогут закрыть недостающие навыки кандидата Алексея "
                     "для той же вакансии?"),
        "expected": "курсы: [Курс «Spring с нуля», Курс «SQL: практика»]",
    },
    {
        "id": "Q4",
        "question": ("Какие подклассы есть у класса «Вакансия» и какие конкретные "
                     "вакансии к ним относятся?"),
        "expected": ("подклассы: [Вакансия разработчика, Вакансия бэкенд-разработчика]; "
                      "экземпляры: [Вакансия Java-разработчика, Вакансия Python-разработчика]"),
    },
    {
        "id": "Q5",
        "question": "Какой путь связывает курс «SQL: практика» с вакансией Java-разработчика?",
        "expected": "Курс «SQL: практика» —обучает→ SQL ←требует— Вакансия Java-разработчика",
    },
]

EXPECTED = {q["id"]: q["expected"] for q in QUESTIONS}


def gap_analysis(net: SemanticNetwork, candidate: str, vacancy: str) -> Dict:
    """Сравнение требований вакансии и навыков кандидата с опорными фактами."""
    required = net.neighbors(vacancy, "requires")
    skills = net.neighbors(candidate, "knows")
    covered = [s for s in required if s in skills]
    missing = [s for s in required if s not in skills]
    evidence = (
        [f"{net.label(vacancy)} —требует→ {net.label(s)}" for s in required]
        + [f"{net.label(candidate)} —владеет→ {net.label(s)}" for s in skills]
    )
    return {"required": required, "skills": skills, "covered": covered,
            "missing": missing, "evidence": evidence}


def courses_for(net: SemanticNetwork, skill_ids: List[str]) -> List[str]:
    """Курсы, обучающие указанным навыкам (обратный поиск по «обучает»)."""
    courses: List[str] = []
    for skill in skill_ids:
        for course in net.neighbors(skill, "teaches", direction="in"):
            if course not in courses:
                courses.append(course)
    return courses


def answer_q1(net: SemanticNetwork) -> Dict:
    vacancy = "vac_java"
    skills = net.neighbors(vacancy, "requires")
    return {
        "id": "Q1",
        "question": QUESTIONS[0]["question"],
        "expected": EXPECTED["Q1"],
        "answer": "[" + ", ".join(net.label(s) for s in skills) + "]",
        "method": "neighbors(vac_java, relation='требует', direction='out')",
        "evidence": [f"{net.label(vacancy)} —требует→ {net.label(s)}" for s in skills],
    }


def answer_q2(net: SemanticNetwork) -> Dict:
    gap = gap_analysis(net, "cand_ivan", "vac_java")
    return {
        "id": "Q2",
        "question": QUESTIONS[1]["question"],
        "expected": EXPECTED["Q2"],
        "answer": ("покрыты: [" + ", ".join(net.label(s) for s in gap["covered"]) +
                   "]; не хватает: [" + ", ".join(net.label(s) for s in gap["missing"]) + "]"),
        "method": "neighbors(владеет) и neighbors(требует) → разность множеств",
        "evidence": gap["evidence"],
        "explanation": (
            "Spring Framework — требование вакансии, но связи «владеет» от кандидата "
            "Ивана к этому навыку в графе нет, поэтому он попадает в разность множеств."
        ),
    }


def answer_q3(net: SemanticNetwork) -> Dict:
    gap = gap_analysis(net, "cand_alex", "vac_java")
    courses = courses_for(net, gap["missing"])
    return {
        "id": "Q3",
        "question": QUESTIONS[2]["question"],
        "expected": EXPECTED["Q3"],
        "answer": "курсы: [" + ", ".join(net.label(c) for c in courses) + "]",
        "method": "разность множеств → neighbors(навык, relation='обучает', direction='in')",
        "evidence": (
            [f"{net.label('cand_alex')} —владеет→ {net.label(s)}" for s in gap["skills"]]
            + [f"{net.label('vac_java')} —требует→ {net.label(s)}" for s in gap["required"]]
            + [f"{net.label(c)} —обучает→ {net.label(s)}"
               for s in gap["missing"] for c in net.neighbors(s, "teaches", direction="in")]
        ),
        "explanation": (
            "Недостающие навыки Алексея — Spring Framework и SQL; курс «Spring с нуля» "
            "обучает Spring, курс «SQL: практика» — SQL, поэтому оба курса закрывают "
            "выявленный разрыв."
        ),
    }


def answer_q4(net: SemanticNetwork) -> Dict:
    all_desc = net.descendants("vacancy")
    subclasses = [d for d in all_desc if net.kind(d) == "class"]
    instances = [d for d in all_desc if net.kind(d) == "instance"]
    return {
        "id": "Q4",
        "question": QUESTIONS[3]["question"],
        "expected": EXPECTED["Q4"],
        "answer": ("подклассы: [" + ", ".join(net.label(c) for c in subclasses) +
                   "]; экземпляры: [" + ", ".join(net.label(i) for i in instances) + "]"),
        "method": "descendants('vacancy') — транзитивный обход «подкласс» + «экземпляр»",
        "evidence": (
            ["Вакансия разработчика —подкласс→ Вакансия",
             "Вакансия бэкенд-разработчика —подкласс→ Вакансия разработчика"]
            + [f"{net.label(i)} —экземпляр→ Вакансия бэкенд-разработчика"
               for i in instances]
        ),
        "explanation": ("Иерархия имеет два уровня вложенности: Вакансия → "
                        "Вакансия разработчика → Вакансия бэкенд-разработчика; "
                        "конкретные вакансии — экземпляры нижнего класса."),
    }


def answer_q5(net: SemanticNetwork) -> Dict:
    hops = net.find_path("crs_sql", "vac_java")
    text = SemanticNetwork.path_to_text(net, hops)
    return {
        "id": "Q5",
        "question": QUESTIONS[4]["question"],
        "expected": EXPECTED["Q5"],
        "answer": text,
        "method": "find_path('crs_sql', 'vac_java') — поиск в ширину по дугам в обе стороны",
        "evidence": [f"{net.label('crs_sql')} —обучает→ {net.label('sk_sql')}",
                     f"{net.label('vac_java')} —требует→ {net.label('sk_sql')}"],
        "explanation": ("Цепочка читается как два утверждения: курс обучает навыку SQL, "
                        "а вакансия этот навык требует; стрелки показывают направление "
                        "каждого факта."),
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
