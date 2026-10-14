"""Бонус: интерактивная визуализация (фильтрация и выделение пути).

Генерирует автономный interactive.html: узлы и дуги встроены в файл,
раскладка и подсветка выполняются в браузере (vis-network с CDN).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from .network import SemanticNetwork

PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_OUT = PROJECT_DIR / "interactive.html"

# Пять вопросов: какие узлы и дуги подсвечивать, путь — если есть.
QUESTIONS: List[Dict] = [
    {
        "id": "Q1",
        "text": "Q1. Какие СУБД удовлетворяют требованию «Транзакции ACID»?",
        "answer": "[MySQL, Oracle Database, PostgreSQL, SQLite]",
        "nodes": ["req_acid", "postgresql", "mysql", "sqlite", "oracle"],
        "edges": [["postgresql", "satisfies", "req_acid"],
                  ["mysql", "satisfies", "req_acid"],
                  ["sqlite", "satisfies", "req_acid"],
                  ["oracle", "satisfies", "req_acid"]],
        "path": [],
        "accent": ["postgresql", "mysql", "sqlite", "oracle"],
    },
    {
        "id": "Q2",
        "text": "Q2. Какие требования проекта «Онлайн-магазин» покрыты PostgreSQL?",
        "answer": "покрыты: [Транзакции ACID, Хранение документов, "
                  "Горизонтальное масштабирование]; не покрыто: [Низкая задержка чтения]",
        "nodes": ["project_shop", "postgresql", "req_acid", "req_docs", "req_scale",
                  "req_latency"],
        "edges": [["project_shop", "presents", "req_acid"],
                  ["project_shop", "presents", "req_docs"],
                  ["project_shop", "presents", "req_scale"],
                  ["project_shop", "presents", "req_latency"],
                  ["postgresql", "satisfies", "req_acid"],
                  ["postgresql", "satisfies", "req_docs"],
                  ["postgresql", "satisfies", "req_scale"]],
        "path": [],
        "accent": ["req_latency"],  # красным — требование без факта покрытия
    },
    {
        "id": "Q3",
        "text": "Q3. Какие критерии выбора соответствуют требованиям проекта "
                "«Сервис рекомендаций»?",
        "answer": "[Модель данных и формат, Задержка операций]",
        "nodes": ["project_reco", "req_graph", "req_latency",
                  "crit_model", "crit_latency"],
        "edges": [["project_reco", "presents", "req_graph"],
                  ["project_reco", "presents", "req_latency"],
                  ["req_graph", "evaluated_by", "crit_model"],
                  ["req_latency", "evaluated_by", "crit_latency"]],
        "path": [],
        "accent": ["crit_model", "crit_latency"],
    },
    {
        "id": "Q4",
        "text": "Q4. Какие подклассы у класса «СУБД» и какие СУБД к ним относятся?",
        "answer": "подклассы: [Графовая СУБД, Документо-ориентированная СУБД, "
                  "Операционная (OLTP) СУБД, Реляционная СУБД, СУБД ключ–значение]; "
                  "экземпляры: [MongoDB, MySQL, Neo4j, Oracle Database, "
                  "PostgreSQL, Redis, SQLite]",
        "nodes": ["dbms", "dbms_rel", "dbms_oltp", "dbms_doc", "dbms_kv",
                  "dbms_graph", "postgresql", "mysql", "sqlite", "oracle",
                  "mongodb", "redis", "neo4j"],
        "edges": [["dbms_rel", "subclass", "dbms"],
                  ["dbms_oltp", "subclass", "dbms_rel"],
                  ["dbms_doc", "subclass", "dbms"],
                  ["dbms_kv", "subclass", "dbms"],
                  ["dbms_graph", "subclass", "dbms"],
                  ["postgresql", "instance", "dbms_oltp"],
                  ["mysql", "instance", "dbms_oltp"],
                  ["sqlite", "instance", "dbms_oltp"],
                  ["oracle", "instance", "dbms_oltp"],
                  ["mongodb", "instance", "dbms_doc"],
                  ["redis", "instance", "dbms_kv"],
                  ["neo4j", "instance", "dbms_graph"]],
        "path": [],
        "accent": [],
    },
    {
        "id": "Q5",
        "text": "Q5. Какой путь связывает проект «Сервис рекомендаций» с СУБД Neo4j?",
        "answer": "Проект «Сервис рекомендаций» —предъявляет→ Граф связей "
                  "←удовлетворяет— Neo4j",
        "nodes": ["project_reco", "req_graph", "neo4j"],
        "edges": [["project_reco", "presents", "req_graph"],
                  ["neo4j", "satisfies", "req_graph"]],
        "path": ["project_reco", "req_graph", "neo4j"],
        "accent": ["project_reco", "req_graph", "neo4j"],
    },
]

TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Семантическая сеть — интерактивная фильтрация</title>
<script src="https://unpkg.com/vis-network/standalone/umd/vis-network.min.js"></script>
<style>
  body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif;
         margin: 0; display: flex; flex-direction: column; height: 100vh; }
  header { padding: 10px 16px; border-bottom: 1px solid #ccc; background: #f7f9fb; }
  header h1 { font-size: 16px; margin: 0 0 8px; }
  .controls { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
  select, button { font-size: 13px; padding: 4px 8px; }
  button.q { background: #e3f2fd; border: 1px solid #90caf9; border-radius: 4px;
             cursor: pointer; }
  button.q:hover { background: #bbdefb; }
  #info { padding: 8px 16px; background: #fff8e1; border-bottom: 1px solid #ccc;
          font-size: 13px; min-height: 18px; }
  /* min-height:0 — иначе flex-элемент растёт по содержимому (canvas),
     его высота уходит за предел браузера и отрисовка становится пустой */
  #net { flex: 1; min-height: 0; overflow: hidden; }
  .legend { font-size: 12px; color: #555; margin-top: 6px; }
  .dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%;
         margin-right: 4px; }
</style>
</head>
<body>
<header>
  <h1>Семантическая сеть: интерактивная фильтрация и выделение пути</h1>
  <div class="controls">
    <label>Тип отношения:
      <select id="relFilter">__REL_OPTIONS__</select>
    </label>
    <label><input type="checkbox" id="hideOthers"> скрыть узлы без видимых дуг</label>
    <button id="reset">Сбросить</button>
    __Q_BUTTONS__
  </div>
  <div class="legend">
    <span class="dot" style="background:#90caf9;border:1px solid #1565c0"></span>класс
    <span class="dot" style="background:#a5d6a7;border:1px solid #2e7d32"></span>экземпляр
    <span class="dot" style="background:#ffe082;border:1px solid #f9a825"></span>значение свойства
    · пунктир — иерархия · красный — выделенный путь или недостающее требование ·
    клик по узлу — его соседи по типу отношения
  </div>
</header>
<div id="info">Выберите вопрос или тип отношения.</div>
<div id="net"></div>
<script>
const RAW_NODES = __NODES__;
const RAW_EDGES = __EDGES__;
const QUESTIONS = __QUESTIONS__;

const KIND_STYLE = {
  class:    { color: { background: "#bbdefb", border: "#1565c0" }, shape: "box" },
  instance: { color: { background: "#c8e6c9", border: "#2e7d32" }, shape: "ellipse" },
  value:    { color: { background: "#fff59d", border: "#f9a825" }, shape: "note" }
};

const nodes = new vis.DataSet(RAW_NODES.map(n => {
  const st = KIND_STYLE[n.kind] || KIND_STYLE.instance;
  return { id: n.id, label: n.label,
           title: "[" + n.id + "] " + n.definition, shape: st.shape,
           color: { background: st.color.background, border: st.color.border,
                    highlight: { background: "#ffcc80", border: "#e65100" } },
           font: { size: 13 } };
}));
const edges = new vis.DataSet(RAW_EDGES.map((e, i) => ({
  id: i, from: e.s, to: e.o, relation: e.p, label: e.label,
  dashes: e.dashed, arrows: "to",
  color: { color: "#37474f", highlight: "#e65100" },
  font: { size: 11, align: "middle" }
})));

const network = new vis.Network(document.getElementById("net"),
  { nodes, edges },
  { nodes: { shapeProperties: { useBorderWithImage: true },
             // drawThreshold:1 — не прятать подписи при автоподгонке всей сети
             scaling: { label: { drawThreshold: 1 } } },
    edges: { smooth: { type: "dynamic" }, length: 180,
             scaling: { label: { drawThreshold: 1 } } },
    physics: { solver: "forceAtlas2Based",
               forceAtlas2Based: { gravitationalConstant: -60, springLength: 120 },
               stabilization: { iterations: 250 } },
    interaction: { hover: true } });

// После стабилизации — вписать сеть и сразу приблизить до читаемого масштаба:
// при полном вписывании подпись (13px × масштаб) была бы меньше 4px.
network.once("stabilizationIterationsDone", () => {
  network.fit({ animation: false });
  const s = network.getScale();
  network.moveTo({ scale: Math.min(1, Math.max(0.7, s * 2)) });
});

const info = document.getElementById("info");
const relFilter = document.getElementById("relFilter");
const hideOthers = document.getElementById("hideOthers");
let activeQuestion = null;

function baseColor(nid) {
  const n = RAW_NODES.find(x => x.id === nid);
  const st = KIND_STYLE[n.kind] || KIND_STYLE.instance;
  return { background: st.color.background, border: st.color.border,
           highlight: { background: "#ffcc80", border: "#e65100" } };
}

function applyFilter() {
  const rel = relFilter.value;
  const visibleEdges = [];
  edges.forEach(e => {
    const show = rel === "all" || e.relation === rel;
    visibleEdges.push({ id: e.id, hidden: !show });
  });
  edges.update(visibleEdges);
  if (hideOthers.checked && rel !== "all") {
    const used = new Set();
    RAW_EDGES.forEach(e => { if (e.p === rel) { used.add(e.s); used.add(e.o); } });
    nodes.update(RAW_NODES.map(n => ({ id: n.id, hidden: !used.has(n.id) })));
  } else {
    nodes.update(RAW_NODES.map(n => ({ id: n.id, hidden: false })));
  }
}

function resetStyles() {
  nodes.update(RAW_NODES.map(n => ({ id: n.id, color: baseColor(n.id),
                                     borderWidth: 1, opacity: 1 })));
  edges.update(edges.getIds().map(id => ({ id, color: { color: "#37474f",
                                                        highlight: "#e65100" },
                                           width: 1, hidden:
                                             relFilter.value !== "all" &&
                                             edges.get(id).relation !== relFilter.value })));
}

function showQuestion(q) {
  activeQuestion = q;
  resetStyles();
  const inQ = new Set(q.nodes);
  nodes.update(RAW_NODES.map(n => ({
    id: n.id,
    opacity: inQ.has(n.id) ? 1 : 0.15,
    borderWidth: inQ.has(n.id) ? 2 : 1
  })));
  (q.accent || []).forEach(nid => nodes.update({
    id: nid, color: { background: "#ffcdd2", border: "#c62828",
                      highlight: { background: "#ff8a80", border: "#b71c1c" } },
    borderWidth: 3 }));
  const key = new Set((q.edges || []).map(e => e[0] + "|" + e[1] + "|" + e[2]));
  edges.update(edges.getIds().map(id => {
    const e = edges.get(id);
    const hit = key.has(e.from + "|" + e.relation + "|" + e.to);
    return { id, hidden: !hit, width: hit ? 3 : 1,
             color: hit ? { color: "#c62828", highlight: "#b71c1c" }
                        : { color: "#37474f", highlight: "#e65100" } };
  }));
  info.innerHTML = "<b>" + q.text + "</b><br>Ожидаемый ответ: " + q.answer +
    (q.path && q.path.length ? "<br>Путь выделен красным: " +
      q.path.map(nid => RAW_NODES.find(x => x.id === nid).label).join(" → ") : "");
  // показать выделенные узлы целиком (не дальше масштаба 1, чтобы подписи читались)
  if (q.nodes && q.nodes.length) {
    network.fit({ nodes: q.nodes, animation: false });
    if (network.getScale() > 1) network.moveTo({ scale: 1 });
  }
}

network.on("click", params => {
  if (params.nodes.length !== 1) return;
  const nid = params.nodes[0];
  const rel = relFilter.value;
  const outs = RAW_EDGES.filter(e => e.s === nid && (rel === "all" || e.p === rel));
  const ins = RAW_EDGES.filter(e => e.o === nid && (rel === "all" || e.p === rel));
  const node = RAW_NODES.find(n => n.id === nid);
  info.innerHTML = "<b>" + node.label + "</b> (" + node.kind + ") — " + node.definition +
    "<br>Идёт по стрелке: " + (outs.length ? outs.map(e => e.label + " → " +
      RAW_NODES.find(n => n.id === e.o).label).join("; ") : "—") +
    "<br>Против стрелки: " + (ins.length ? ins.map(e => e.label + " ← " +
      RAW_NODES.find(n => n.id === e.s).label).join("; ") : "—");
});

relFilter.addEventListener("change", () => { resetStyles(); applyFilter(); });
hideOthers.addEventListener("change", applyFilter);
document.getElementById("reset").addEventListener("click", () => {
  activeQuestion = null; relFilter.value = "all"; resetStyles(); applyFilter();
  info.textContent = "Выберите вопрос или тип отношения.";
});
QUESTIONS.forEach(q => {
  const b = document.createElement("button");
  b.className = "q"; b.textContent = q.id;
  b.title = q.text;
  b.onclick = () => showQuestion(q);
  document.getElementById("qButtons").appendChild(b);
});
</script>
</body>
</html>
"""


def build_html(net: SemanticNetwork) -> str:
    nodes = [{"id": n["id"], "kind": n["kind"], "label": n["label"],
              "definition": n["definition"]} for n in net.nodes_list]
    edges = []
    for t in net.triples:
        s, p, o = t.get("s"), t.get("p"), t.get("o")
        if s in net.nodes and o in net.nodes and p in net.relations:
            edges.append({"s": s, "o": o, "p": p, "label": net.rel_label(p),
                          "dashed": p in ("subclass", "instance", "part_of")})

    rel_options = ['<option value="all">все отношения</option>'] + [
        f'<option value="{rid}">{rel["label"]} ({rid})</option>'
        for rid, rel in net.relations.items()
    ]
    q_buttons = '<span id="qButtons"></span>'
    html = (TEMPLATE
            .replace("__NODES__", json.dumps(nodes, ensure_ascii=False))
            .replace("__EDGES__", json.dumps(edges, ensure_ascii=False))
            .replace("__QUESTIONS__", json.dumps(QUESTIONS, ensure_ascii=False))
            .replace("__REL_OPTIONS__", "\n      ".join(rel_options))
            .replace("__Q_BUTTONS__", q_buttons))
    return html


def generate(net: SemanticNetwork, out_path: Path = DEFAULT_OUT) -> Path:
    out_path = Path(out_path)
    out_path.write_text(build_html(net), encoding="utf-8")
    return out_path
