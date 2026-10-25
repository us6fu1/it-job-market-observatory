"""Streamlit-дашборд: демо работает офлайн, PostgreSQL подключается по DATABASE_URL."""

import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from ingestion.pipeline import build_sample


st.set_page_config(
    page_title="IT Job Market Observatory",
    page_icon="🔭",
    layout="wide",
)

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; padding-bottom: 3rem;}
    [data-testid="stMetric"] {
        background: #f5f7fb;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 14px 16px;
    }
    .observatory-note {
        border-left: 4px solid #f59e0b;
        background: #fffbeb;
        color: #78350f;
        padding: 0.8rem 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.5rem 0 1.2rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


@st.cache_data
def load_demo() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    output = ROOT / "build" / "sample"
    summary_path = output / "summary.json"
    vacancies_path = output / "vacancies.jsonl"
    if not summary_path.exists() or not vacancies_path.exists():
        build_sample(ROOT / "data" / "sample", output)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return summary, _read_jsonl(vacancies_path)


@st.cache_data(ttl=300)
def load_postgres(
    database_url: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("Не установлен psycopg. Выполните python3 -m pip install .") from exc

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    count(*) AS unique_vacancies,
                    count(*) FILTER (
                        WHERE salary_from IS NOT NULL OR salary_to IS NOT NULL
                    ) AS vacancies_with_salary
                FROM mart.v_current_vacancies
                """
            )
            summary = cursor.fetchone()
            cursor.execute(
                """
                SELECT source, status, started_at
                FROM audit.etl_run
                WHERE status IN ('success', 'partial')
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            latest_run = cursor.fetchone() or {}
            summary.update(latest_run)
            cursor.execute("SELECT * FROM mart.v_market_overview ORDER BY job_group_name")
            overview = cursor.fetchall()
            cursor.execute(
                """
                SELECT job_group_name, skill_name, vacancy_count, skill_rank
                FROM mart.v_top_skills
                WHERE skill_rank <= 10
                ORDER BY job_group_name, skill_rank, skill_name
                """
            )
            skills = cursor.fetchall()
            cursor.execute(
                """
                SELECT
                    current.vacancy_id,
                    current.vacancy_name,
                    employer.employer_name,
                    area.area_name,
                    current.published_at,
                    current.salary_from,
                    current.salary_to,
                    current.salary_currency
                FROM mart.v_current_vacancies AS current
                LEFT JOIN dwh.dim_employer AS employer
                  ON employer.employer_sk = current.employer_sk
                LEFT JOIN dwh.dim_area AS area
                  ON area.area_sk = current.area_sk
                ORDER BY current.published_at DESC NULLS LAST
                LIMIT 200
                """
            )
            vacancies = cursor.fetchall()
    total = summary["unique_vacancies"]
    summary["salary_coverage"] = summary["vacancies_with_salary"] / total if total else 0
    return summary, overview, skills, vacancies


def _money(value: Any) -> str:
    if value is None:
        return "-"
    return "{:,.0f}".format(float(value)).replace(",", " ")


st.title("IT Job Market Observatory")
st.caption("Data Analyst · BI Developer · Data Engineer")

source = st.sidebar.radio("Источник", ("Офлайн-демо", "PostgreSQL"))

if source == "Офлайн-демо":
    summary, vacancies = load_demo()
    st.markdown(
        '<div class="observatory-note"><b>Демонстрационный режим.</b> '
        "Записи вымышлены и нужны только для проверки интерфейса. "
        "Это не статистика HeadHunter.</div>",
        unsafe_allow_html=True,
    )
    group_filter = st.sidebar.multiselect(
        "Направления",
        sorted({group for row in vacancies for group in row["job_groups"]}),
    )
    if group_filter:
        vacancies = [
            row for row in vacancies if set(row["job_groups"]) & set(group_filter)
        ]

    salary_count = sum(1 for row in vacancies if row["has_salary"])
    left, middle, right = st.columns(3)
    left.metric("Уникальные вакансии", len(vacancies))
    middle.metric("С указанной зарплатой", salary_count)
    right.metric(
        "Покрытие зарплатами",
        "{:.0%}".format(salary_count / len(vacancies) if vacancies else 0),
    )

    st.subheader("Срез по направлениям")
    group_counts: Dict[str, int] = {}
    for row in vacancies:
        for group in row["job_groups"]:
            group_counts[group] = group_counts.get(group, 0) + 1
    st.bar_chart(group_counts, horizontal=True)

    st.subheader("Навыки")
    skill_counts: Dict[str, int] = {}
    for row in vacancies:
        for skill in row["key_skills"]:
            skill_counts[skill] = skill_counts.get(skill, 0) + 1
    skill_rows = [
        {"Навык": name, "Вакансий": count}
        for name, count in sorted(skill_counts.items(), key=lambda item: (-item[1], item[0]))
    ]
    st.bar_chart(skill_rows, x="Навык", y="Вакансий")

    st.subheader("Вакансии")
    table = [
        {
            "Вакансия": row["name"],
            "Работодатель": row["employer_name"],
            "Регион": row["area_name"],
            "Зарплата от": _money(row["salary_from"]),
            "Зарплата до": _money(row["salary_to"]),
            "Валюта": row["salary_currency"] or "-",
        }
        for row in vacancies
    ]
    st.dataframe(table, width="stretch", hide_index=True)
else:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        st.error("Задайте DATABASE_URL и перезапустите дашборд.")
        st.stop()
    try:
        summary, overview, skills, vacancies = load_postgres(database_url)
    except Exception as exc:
        st.error("Не удалось прочитать витрины PostgreSQL: {}".format(exc))
        st.stop()
    if summary.get("source") == "synthetic_demo":
        st.markdown(
            '<div class="observatory-note"><b>PostgreSQL работает на демонстрационных данных.</b> '
            "Они нужны для интеграционной проверки и не описывают рынок HeadHunter.</div>",
            unsafe_allow_html=True,
        )
    left, middle, right = st.columns(3)
    left.metric("Доступные вакансии", summary["unique_vacancies"])
    middle.metric("С указанной зарплатой", summary["vacancies_with_salary"])
    right.metric("Покрытие зарплатами", "{:.0%}".format(summary["salary_coverage"]))
    st.subheader("Срез по направлениям")
    st.dataframe(overview, width="stretch", hide_index=True)
    st.subheader("Топ навыков")
    st.dataframe(skills, width="stretch", hide_index=True)
    st.subheader("Последние вакансии")
    st.dataframe(vacancies, width="stretch", hide_index=True)

st.caption(
    "Средняя точка зарплатной вилки считается только тогда, когда указаны обе границы. "
    "Отсутствие вакансии в поиске не считается подтверждением закрытия."
)
