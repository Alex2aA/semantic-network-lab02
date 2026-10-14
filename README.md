# Семантическая сеть — Лабораторная работа 02

**Дисциплина:** Интеллектуальные информационные системы и технологии (ИИСиТ)
**Тема:** Разработка экспертной системы по выбору СУБД для проекта: объяснимая модель
фрагмента знаний — понятия и отношения, факты как триплеты, проверка сети поисковыми запросами.

**Репозиторий:** https://github.com/Alex2aA/semantic-network-lab02

## Что внутри

Ориентированный подписанный граф знаний предметной области
«выбор СУБД для проекта»: типы СУБД, кандидатные системы, проекты, требования
и критерии выбора.

| Показатель | Значение |
|---|---|
| Узлы | 38 (13 классов, 21 экземпляр, 4 значения) |
| Факты-триплеты | 76 |
| Типы отношений | 7 (подкласс, экземпляр, предъявляет, удовлетворяет, оценивается по, имеет значение, рекомендует) |
| Иерархия | 3 уровня (СУБД → Реляционная СУБД → Операционная (OLTP) СУБД) |
| Компетентностные вопросы | 5 (все с воспроизводимыми ответами) |
| Тесты | 21 unittest, 5 сценариев + отрицательный |

## Структура

```
data/                 — хранилище знаний (отдельно от кода)
  nodes.json          — словарь понятий: классы, экземпляры, значения
  relations.json      — каталог «паспортов» отношений
  triples.json        — 76 фактов «субъект — отношение → объект» + источник
  sources.json        — источники и пометки о модельных допущениях
semantic_net/         — программный прототип
  network.py          — ядро: neighbors, ancestors/descendants, find_path, validate
  queries.py          — 5 компетентностных вопросов с ожидаемыми ответами
  render.py           — визуализация Graphviz (DOT → PNG)
  interactive.py      — бонус: интерактивная HTML-схема (vis-network)
  rdf_export.py       — бонус: RDF/Turtle, SPARQL, SHACL
  cli.py              — консольный интерфейс
tests/test_network.py — 5 проверочных сценариев (unittest)
img/                  — обзорная схема и 2 фрагмента с легендой
export/graph.ttl      — экспорт в RDF/Turtle
interactive.html      — интерактивная схема (открыть в браузере)
REPORT.md             — полный отчёт по лабораторной работе
```

## Быстрый старт

```bash
# системная зависимость: Graphviz
brew install graphviz            # или apt-get install graphviz

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # rdflib, pyshacl (бонусный экспорт)

python -m unittest discover -s tests -v   # 21 тест, 5 сценариев
python -m semantic_net validate           # проверка целостности
python -m semantic_net queries            # ответы на 5 вопросов
python -m semantic_net neighbors req_acid --rel satisfies --direction in
python -m semantic_net path project_reco neo4j --rel presents satisfies
python -m semantic_net render --fragment overview
python -m semantic_net interactive        # интерактивная HTML-схема
python -m semantic_net export-rdf         # RDF + SPARQL + SHACL
```

## Изображения

| Схема | Файл |
|---|---|
| Обзорная схема всей сети | [img/overview.png](img/overview.png) |
| Фрагмент 1 — иерархия классов и экземпляры | [img/hierarchy.png](img/hierarchy.png) |
| Фрагмент 2 — подбор: проекты, требования, критерии, СУБД | [img/selection.png](img/selection.png) |

Легенда есть на каждой схеме: синий прямоугольник — класс, зелёный эллипс — экземпляр,
жёлтая заметка — значение свойства; сплошная дуга — предметное отношение, пунктир —
иерархия; стрелка и подпись задают направление и тип факта.

## Подробности

Полное описание домена, словарь, каталог отношений, все 76 триплетов, результаты
поиска, пять тестов и выводы — в [REPORT.md](REPORT.md).
