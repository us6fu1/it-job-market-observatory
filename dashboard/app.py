"""Streamlit-витрина IT Job Market Observatory."""

import csv
from io import StringIO
import json
import os
from datetime import datetime
from pathlib import Path
import sys
from typing import Any, Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from ingestion.pipeline import build_sample
from dashboard.metrics import (
    filtered_salary_rows,
    filtered_skill_rows,
    filtered_weekly_rows,
)


st.set_page_config(
    page_title="IT Job Market Observatory",
    page_icon="🔭",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 1320px; padding-top: 1.5rem; padding-bottom: 4rem;}
    [data-testid="stToolbar"] {visibility: hidden;}
    [data-testid="stDecoration"] {display: none;}
    [data-testid="stSidebar"] {background: #f8fafc; border-right: 1px solid #e2e8f0;}
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, #ffffff, #f8fafc);
        border: 1px solid #e2e8f0;
        border-radius: 16px;
        padding: 16px 18px;
        box-shadow: 0 8px 24px rgba(15, 23, 42, 0.05);
    }
    [data-testid="stMetricValue"] {font-weight: 750; letter-spacing: -0.04em;}
    .hero {
        padding: 28px 32px;
        border-radius: 24px;
        color: white;
        background:
            radial-gradient(circle at 90% 15%, rgba(56, 189, 248, .35), transparent 26%),
            linear-gradient(125deg, #0f172a 0%, #172554 55%, #164e63 100%);
        box-shadow: 0 18px 48px rgba(15, 23, 42, .18);
        margin-bottom: 18px;
    }
    .hero-kicker {font-size: .78rem; font-weight: 700; letter-spacing: .14em; opacity: .72;}
    .hero h1 {font-size: 2.35rem; line-height: 1.08; margin: 8px 0 10px; letter-spacing: -.04em;}
    .hero p {max-width: 760px; font-size: 1rem; line-height: 1.55; margin: 0; opacity: .85;}
    .source-card {
        border: 1px solid #bae6fd;
        background: #f0f9ff;
        color: #0c4a6e;
        padding: .85rem 1rem;
        border-radius: 12px;
        margin: .4rem 0 1.2rem;
    }
    .demo-card {
        border: 1px solid #fde68a;
        background: #fffbeb;
        color: #78350f;
        padding: .85rem 1rem;
        border-radius: 12px;
        margin: .4rem 0 1.2rem;
    }
    .section-note {color: #64748b; font-size: .88rem; margin-top: -.55rem; margin-bottom: .8rem;}
    .small-pill {
        display: inline-block;
        padding: .25rem .55rem;
        margin-right: .35rem;
        border-radius: 999px;
        background: rgba(255,255,255,.12);
        border: 1px solid rgba(255,255,255,.18);
        font-size: .78rem;
    }
    .footer-note {color: #64748b; font-size: .82rem; line-height: 1.5; margin-top: 2rem;}
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


@st.cache_data(ttl=180)
def load_postgres(database_url: str) -> Dict[str, Any]:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("Не установлен psycopg. Выполните python3 -m pip install .") from exc

    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (source)
                           run_id, source, status, started_at, finished_at, parameters,
                           rows_received, unique_vacancies, details_loaded,
                           filtered_out, rejected_rows
                    FROM audit.etl_run
                    WHERE status IN ('success', 'partial')
                    ORDER BY source, started_at DESC
                ), selected AS (
                    SELECT * FROM latest WHERE source <> 'synthetic_demo'
                    UNION ALL
                    SELECT * FROM latest
                    WHERE source = 'synthetic_demo'
                      AND NOT EXISTS (
                          SELECT 1 FROM latest WHERE source <> 'synthetic_demo'
                      )
                )
                SELECT *
                FROM selected
                ORDER BY started_at DESC
                """
            )
            runs = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT count(*) AS unique_vacancies,
                       count(DISTINCT employer_sk) AS employers,
                       count(DISTINCT area_sk) AS regions,
                       count(*) FILTER (
                           WHERE salary_from IS NOT NULL OR salary_to IS NOT NULL
                       ) AS vacancies_with_salary
                FROM mart.v_current_vacancies
                """
            )
            summary = dict(cursor.fetchone())
            cursor.execute(
                """
                SELECT job_group_code, job_group_name, available_vacancies,
                       vacancies_with_salary, salary_coverage
                FROM mart.v_market_overview
                ORDER BY available_vacancies DESC, job_group_name
                """
            )
            overview = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """
                WITH ranked AS (
                    SELECT job_group_code, job_group_name, skill_name,
                           vacancy_count, skill_rank,
                           row_number() OVER (
                               PARTITION BY job_group_code
                               ORDER BY vacancy_count DESC, skill_name
                           ) AS display_rank
                    FROM mart.v_top_skills
                )
                SELECT job_group_code, job_group_name, skill_name,
                       vacancy_count, skill_rank
                FROM ranked
                WHERE display_rank <= 10
                ORDER BY job_group_name, display_rank
                """
            )
            skills = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT job_group_code, job_group_name, week_start,
                       new_vacancies, previous_week_vacancies, absolute_change
                FROM mart.v_weekly_new_vacancies
                ORDER BY week_start, job_group_name
                """
            )
            weekly = [dict(row) for row in cursor.fetchall()]
            cursor.execute(
                """
                SELECT current.source, current.run_id,
                       current.vacancy_id, current.vacancy_name,
                       employer.employer_name, area.area_name,
                       current.published_at, current.salary_from, current.salary_to,
                       current.salary_currency, current.work_formats,
                       vacancy.alternate_url,
                       array_remove(array_agg(DISTINCT groups.job_group_name), NULL) AS job_groups,
                       array_remove(array_agg(DISTINCT skill.skill_name), NULL) AS skills
                FROM mart.v_current_vacancies AS current
                JOIN dwh.dim_vacancy AS vacancy ON vacancy.vacancy_sk = current.vacancy_sk
                LEFT JOIN dwh.dim_employer AS employer ON employer.employer_sk = current.employer_sk
                LEFT JOIN dwh.dim_area AS area ON area.area_sk = current.area_sk
                LEFT JOIN dwh.bridge_vacancy_job_group AS vacancy_group
                  ON vacancy_group.vacancy_sk = current.vacancy_sk
                LEFT JOIN dwh.dim_job_group AS groups
                  ON groups.job_group_sk = vacancy_group.job_group_sk
                LEFT JOIN dwh.bridge_vacancy_skill AS vacancy_skill
                  ON vacancy_skill.vacancy_sk = current.vacancy_sk
                LEFT JOIN dwh.dim_skill AS skill
                  ON skill.skill_sk = vacancy_skill.skill_sk
                GROUP BY current.source, current.run_id,
                         current.vacancy_id, current.vacancy_name,
                         employer.employer_name, area.area_name, current.published_at,
                         current.salary_from, current.salary_to, current.salary_currency,
                         current.work_formats, vacancy.alternate_url
                ORDER BY current.published_at DESC NULLS LAST, current.vacancy_name
                """
            )
            vacancies = [dict(row) for row in cursor.fetchall()]
            quality: Dict[str, Any] = {}
            segments: List[Dict[str, Any]] = []
            run_ids = [str(run["run_id"]) for run in runs]
            if run_ids:
                cursor.execute(
                    """
                    SELECT count(*) AS requests,
                           count(*) FILTER (WHERE status_code BETWEEN 200 AND 299) AS successful_requests,
                           count(*) FILTER (WHERE status_code = 429) AS rate_limits,
                           count(*) FILTER (
                               WHERE status_code >= 500 OR error_message IS NOT NULL
                           ) AS request_errors
                    FROM audit.api_request
                    WHERE run_id = ANY(%s::uuid[])
                    """,
                    (run_ids,),
                )
                quality = dict(cursor.fetchone())
                cursor.execute(
                    """
                    SELECT run.source, segment.segment_id, segment.job_group_code,
                           segment.found, segment.received, segment.status
                    FROM audit.search_segment AS segment
                    JOIN audit.etl_run AS run ON run.run_id = segment.run_id
                    WHERE segment.run_id = ANY(%s::uuid[])
                    ORDER BY run.source, segment.job_group_code, segment.segment_id
                    """,
                    (run_ids,),
                )
                segments = [dict(row) for row in cursor.fetchall()]

    total = int(summary.get("unique_vacancies") or 0)
    summary["salary_coverage"] = (
        int(summary.get("vacancies_with_salary") or 0) / total if total else 0
    )
    return {
        "runs": runs,
        "summary": summary,
        "overview": overview,
        "skills": skills,
        "weekly": weekly,
        "vacancies": vacancies,
        "quality": quality,
        "segments": segments,
    }


def _money(value: Any) -> str:
    if value is None:
        return "-"
    return "{:,.0f}".format(float(value)).replace(",", " ")


def _display_time(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone().strftime("%d.%m.%Y %H:%M")
    return str(value or "-")


def _source_name(value: Any) -> str:
    return {
        "trudvsem": "Работа России",
        "trudvsem_api": "Работа России",
        "hh": "HeadHunter",
        "hh_api": "HeadHunter",
        "synthetic_demo": "Демонстрационный набор",
    }.get(str(value or ""), str(value or "Неизвестный источник"))


def _to_csv(rows: List[Dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def _hero() -> None:
    st.markdown(
        """
        <div class="hero">
          <div class="hero-kicker">DATA ENGINEERING PORTFOLIO PROJECT</div>
          <h1>IT Job Market Observatory</h1>
          <p>ETL-система для наблюдения за вакансиями Data Analyst, BI Developer и Data Engineer. Обезличенные данные API проходят через RAW, STG и DWH, после чего превращаются в проверяемые аналитические витрины PostgreSQL.</p>
          <div style="margin-top:16px">
            <span class="small-pill">Python</span><span class="small-pill">PostgreSQL</span><span class="small-pill">SQL</span><span class="small-pill">REST API</span><span class="small-pill">Streamlit</span><span class="small-pill">Docker</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_demo() -> None:
    _, vacancies = load_demo()
    st.markdown(
        '<div class="demo-card"><b>Офлайн-демо.</b> Здесь всего несколько '
        "вымышленных записей для проверки интерфейса. Они не описывают реальный рынок.</div>",
        unsafe_allow_html=True,
    )
    groups = sorted({group for row in vacancies for group in row["job_groups"]})
    selected = st.sidebar.multiselect("Направления", groups, default=groups)
    filtered = [row for row in vacancies if set(row["job_groups"]) & set(selected)]
    salary_count = sum(1 for row in filtered if row["has_salary"])
    columns = st.columns(4)
    columns[0].metric("Вакансии", len(filtered))
    columns[1].metric("Работодатели", len({row["employer_name"] for row in filtered}))
    columns[2].metric("Регионы", len({row["area_name"] for row in filtered}))
    columns[3].metric(
        "С зарплатой",
        "{:.0%}".format(salary_count / len(filtered) if filtered else 0),
    )
    group_counts: Dict[str, int] = {}
    for row in filtered:
        for group in row["job_groups"]:
            group_counts[group] = group_counts.get(group, 0) + 1
    st.subheader("Направления")
    st.bar_chart(group_counts, horizontal=True)
    st.subheader("Примеры вакансий")
    st.dataframe(
        [
            {
                "Вакансия": row["name"],
                "Работодатель": row["employer_name"],
                "Регион": row["area_name"],
                "Зарплата от": _money(row["salary_from"]),
                "Зарплата до": _money(row["salary_to"]),
            }
            for row in filtered
        ],
        width="stretch",
        hide_index=True,
    )


def render_postgres(data: Dict[str, Any]) -> None:
    runs = data["runs"]
    source_codes = [str(run.get("source") or "") for run in runs]
    if source_codes and all(source == "synthetic_demo" for source in source_codes):
        card_class = "demo-card"
        source_text = "В базе сейчас демонстрационные данные. Это технический прогон, а не срез рынка."
    else:
        card_class = "source-card"
        source_names = ", ".join(_source_name(source) for source in source_codes)
        latest_time = max(
            (
                run.get("finished_at") or run.get("started_at")
                for run in runs
                if run.get("finished_at") or run.get("started_at")
            ),
            default=None,
        )
        source_text = (
            "Витрина объединяет последние завершённые снимки источников: {}. "
            "Последнее обновление: {}."
        ).format(
            source_names or "источники не найдены",
            _display_time(latest_time),
        )
    st.markdown(
        '<div class="{}">{}</div>'.format(card_class, source_text),
        unsafe_allow_html=True,
    )

    all_groups = sorted(
        {group for row in data["vacancies"] for group in row.get("job_groups", [])}
    )
    all_regions = sorted(
        {row.get("area_name") or "Не указан" for row in data["vacancies"]}
    )
    all_sources = sorted(
        {str(row.get("source") or "") for row in data["vacancies"]}
    )
    selected_sources = st.sidebar.multiselect(
        "Источники",
        all_sources,
        default=all_sources,
        format_func=_source_name,
    )
    selected_groups = st.sidebar.multiselect(
        "Направления", all_groups, default=all_groups
    )
    selected_regions = st.sidebar.multiselect("Регионы", all_regions)
    salary_only = st.sidebar.checkbox("Только с указанной зарплатой")

    vacancies = []
    for row in data["vacancies"]:
        source_match = not selected_sources or row.get("source") in selected_sources
        groups_match = not selected_groups or bool(
            set(row.get("job_groups", [])) & set(selected_groups)
        )
        region = row.get("area_name") or "Не указан"
        region_match = not selected_regions or region in selected_regions
        salary_match = (
            not salary_only
            or row.get("salary_from") is not None
            or row.get("salary_to") is not None
        )
        if source_match and groups_match and region_match and salary_match:
            vacancies.append(row)

    salary_count = sum(
        1
        for row in vacancies
        if row.get("salary_from") is not None or row.get("salary_to") is not None
    )
    columns = st.columns(4)
    columns[0].metric("Вакансии", len(vacancies))
    columns[1].metric(
        "Работодатели",
        len(
            {
                row.get("employer_name")
                for row in vacancies
                if row.get("employer_name")
            }
        ),
    )
    columns[2].metric(
        "Регионы",
        len({row.get("area_name") for row in vacancies if row.get("area_name")}),
    )
    columns[3].metric(
        "С зарплатой",
        "{:.0%}".format(salary_count / len(vacancies) if vacancies else 0),
    )

    overview_tab, salary_tab, skills_tab, vacancies_tab, quality_tab = st.tabs(
        ["Обзор", "Зарплаты", "Навыки", "Вакансии", "Качество данных"]
    )
    with overview_tab:
        left, right = st.columns([1.35, 1])
        with left:
            st.subheader("Вакансии по направлениям")
            st.markdown(
                '<div class="section-note">Одна вакансия может попасть сразу в несколько групп.</div>',
                unsafe_allow_html=True,
            )
            group_counts: Dict[str, int] = {}
            for row in vacancies:
                for group in row.get("job_groups", []):
                    if not selected_groups or group in selected_groups:
                        group_counts[group] = group_counts.get(group, 0) + 1
            st.bar_chart(group_counts, horizontal=True)
        with right:
            st.subheader("Регионы")
            region_counts: Dict[str, int] = {}
            for row in vacancies:
                region = row.get("area_name") or "Не указан"
                region_counts[region] = region_counts.get(region, 0) + 1
            top_regions = dict(
                sorted(region_counts.items(), key=lambda item: (-item[1], item[0]))[
                    :10
                ]
            )
            st.bar_chart(top_regions, horizontal=True)
        weekly_rows = filtered_weekly_rows(vacancies, selected_groups, runs)
        if weekly_rows:
            st.subheader("Публикации по неделям")
            st.line_chart(
                weekly_rows,
                x="Неделя",
                y="Новые вакансии",
                color="Направление",
            )

    with salary_tab:
        st.subheader("Медианная зарплатная вилка")
        st.markdown(
            '<div class="section-note">Расчёт использует только вакансии с обеими границами вилки. Валюты не смешиваются.</div>',
            unsafe_allow_html=True,
        )
        salary_rows = filtered_salary_rows(vacancies, selected_groups)
        if salary_rows:
            st.bar_chart(
                salary_rows,
                x="Направление",
                y="Медиана середины вилки",
                color="Валюта",
            )
            st.dataframe(
                [
                    {
                        **row,
                        "Медиана середины вилки": _money(
                            row["Медиана середины вилки"]
                        ),
                    }
                    for row in salary_rows
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("В выбранном срезе нет полных зарплатных вилок.")

    with skills_tab:
        st.subheader("Навыки, найденные в требованиях")
        st.markdown(
            '<div class="section-note">Для источника «Работа России» навыки извлекаются прозрачным словарём из текста вакансии. Это не ML-классификация.</div>',
            unsafe_allow_html=True,
        )
        skill_rows = filtered_skill_rows(vacancies, selected_groups)
        if skill_rows:
            st.bar_chart(
                skill_rows,
                x="Навык",
                y="Вакансии",
                color="Направление",
                horizontal=True,
            )
        else:
            st.info("В выбранном срезе навыки не найдены.")

    with vacancies_tab:
        st.subheader("Найденные вакансии")
        st.markdown(
            '<div class="section-note">Фильтры слева применяются к таблице и показателям наверху.</div>',
            unsafe_allow_html=True,
        )
        table = [
            {
                "Источник": _source_name(row.get("source")),
                "Вакансия": row["vacancy_name"],
                "Направление": ", ".join(row.get("job_groups") or []),
                "Работодатель": row.get("employer_name") or "-",
                "Регион": row.get("area_name") or "-",
                "Опубликована": (
                    row["published_at"].date()
                    if isinstance(row.get("published_at"), datetime)
                    else row.get("published_at")
                ),
                "Зарплата от": _money(row.get("salary_from")),
                "Зарплата до": _money(row.get("salary_to")),
                "Валюта": row.get("salary_currency") or "-",
                "Ссылка": row.get("alternate_url") or "",
            }
            for row in vacancies
        ]
        st.dataframe(
            table,
            width="stretch",
            hide_index=True,
            column_config={
                "Ссылка": st.column_config.LinkColumn("Ссылка", display_text="Открыть")
            },
        )
        st.download_button(
            "Скачать выбранный срез в CSV",
            data=_to_csv(table),
            file_name="job_market_vacancies.csv",
            mime="text/csv",
            disabled=not table,
        )

    with quality_tab:
        st.subheader("Контроль последней загрузки")
        quality = data["quality"]
        rows_received = sum(int(run.get("rows_received") or 0) for run in runs)
        filtered_out = sum(int(run.get("filtered_out") or 0) for run in runs)
        quality_columns = st.columns(5)
        quality_columns[0].metric(
            "Проверено строк",
            rows_received + filtered_out,
        )
        quality_columns[1].metric(
            "После фильтра", rows_received
        )
        quality_columns[2].metric(
            "Уникальных", len(data["vacancies"])
        )
        quality_columns[3].metric(
            "API-запросов", int(quality.get("requests") or 0)
        )
        quality_columns[4].metric(
            "Ошибок API", int(quality.get("request_errors") or 0)
        )
        st.markdown(
            "Загрузка хранит параметры запросов, HTTP-статусы, повторные попытки и результат каждого поискового сегмента. "
            "После переноса в DWH отдельно запускаются SQL-проверки дублей, обязательных полей, зарплатных вилок и внешних ключей."
        )
        if data["segments"]:
            st.dataframe(
                [
                    {
                        "Источник": _source_name(row["source"]),
                        "Направление": row["job_group_code"],
                        "Найдено источником": row["found"],
                        "Прошло фильтр заголовка": row["received"],
                        "Статус": row["status"],
                    }
                    for row in data["segments"]
                ],
                width="stretch",
                hide_index=True,
            )


_hero()
st.sidebar.markdown("### Режим просмотра")
mode = st.sidebar.radio(
    "Данные",
    ("Реальные витрины", "Офлайн-демо"),
    label_visibility="collapsed",
)
st.sidebar.markdown("---")
st.sidebar.caption(
    "Фильтры меняют показатели и таблицы, но не изменяют данные в хранилище."
)

if mode == "Офлайн-демо":
    render_demo()
else:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        st.warning("DATABASE_URL не задан. Переключаюсь на офлайн-демо.")
        render_demo()
    else:
        try:
            render_postgres(load_postgres(database_url))
        except Exception as exc:
            st.error("Не удалось прочитать витрины PostgreSQL: {}".format(exc))

st.markdown(
    '<div class="footer-note">Методика: средняя точка зарплатной вилки считается только при наличии обеих границ. '
    "Исчезновение вакансии из поиска само по себе не считается подтверждением её закрытия. "
    "Источник, дата загрузки и ограничения анализа всегда показываются рядом с результатом.</div>",
    unsafe_allow_html=True,
)
