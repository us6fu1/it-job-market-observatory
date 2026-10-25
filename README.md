# IT Job Market Observatory

Пет-проект для наблюдения за вакансиями Data Analyst, BI Developer и Data
Engineer. Он сохраняет историю снимков HeadHunter, строит PostgreSQL-слои
RAW/STG/DWH/MART и показывает витрины в Streamlit.

Сейчас готов локальный MVP. Офлайн-контур работает на Python 3.9 без внешних
пакетов. Интеграция с PostgreSQL 16 проверена на демонстрационных данных: от
записи RAW и журнала запуска до витрин MART и Streamlit. Доступ к справочнику
HH проверен, а токен для живого поиска вакансий пока ожидает одобрения.

## Быстрая офлайн-проверка

```bash
python3 -m unittest discover -s tests/unit -v
python3 -m ingestion sample --input data/sample --output build/sample
```

Данные в `data/sample` вымышлены. Команда проверяет весь путь от сырого JSON до
нормализованных файлов и сводки, но не создаёт выводы о реальном рынке.

## Структура

```text
ingestion/          клиент HH, сегментация, RAW и нормализация
sql/ddl/            схемы, таблицы, представления и индексы
sql/staging/        загрузка из STG в DWH
sql/marts/          описание витрин
sql/analytics/      аналитические SQL-запросы
tests/unit/         офлайн-тесты Python и контракта SQL
tests/data_quality/ SQL-проверки качества
dashboard/          Streamlit-дашборд
docs/               архитектура, методика и ER-модель
data/sample/        вымышленные примеры ответов
```

Подробная схема описана в [docs/architecture.md](docs/architecture.md), правила
расчётов - в [docs/methodology.md](docs/methodology.md).

## PostgreSQL

Запуск PostgreSQL через Docker:

```bash
cp .env.example .env
docker compose up -d postgres
python3 -m pip install .
export DATABASE_URL='postgresql://job_market:change_me@localhost:5432/job_market'
python3 scripts/run_sql.py ddl
```

Полную интеграционную цепочку можно проверить на вымышленных данных:

```bash
python3 scripts/load_sample_to_postgres.py
python3 scripts/run_sql.py load
python3 scripts/run_sql.py quality
```

Такой запуск получает источник `synthetic_demo`. Дашборд отдельно предупреждает,
что записи из него не являются статистикой HeadHunter.

Пароль в примере нужно заменить. `.env` исключён из Git.

## Реальная загрузка HH

Сначала задайте User-Agent с контактом. `HH_ACCESS_TOKEN` не нужен для
sample-режима и не мешает разрабатывать или проверять остальной конвейер. Для
повторяющегося живого поиска вакансий текущий API HH требует токен приложения:
без него после первого запроса может вернуться капча или HTTP 403.

```bash
export HH_USER_AGENT='IT-Job-Market-Observatory/0.1 (contact: email@example.com)'
export HH_ACCESS_TOKEN='полученный-токен'
python3 -m ingestion roles
python3 -m ingestion collect \
  --config config/search_segments.example.json \
  --raw-dir data/raw \
  --database-url "$DATABASE_URL"
python3 scripts/run_sql.py load
python3 scripts/run_sql.py quality
```

Старое имя `HH_OAUTH_TOKEN` пока поддерживается как запасной вариант, но новое
окружение лучше настраивать через `HH_ACCESS_TOKEN`. Токен нельзя добавлять в
Git: локальный `.env` уже исключён из репозитория.

Перед запуском измените даты и фильтры в конфигурации. Актуальный справочник
профессиональных ролей загружается отдельной командой: ID ролей не зашиты в код.
Если минимальный сегмент всё ещё больше 2 000, запуск получает статус `partial`,
а сегмент - `over_limit`. Такой случай нельзя скрывать или считать полной
выгрузкой.

## Дашборд

```bash
python3 -m pip install .
streamlit run dashboard/app.py
```

По умолчанию показывается заметно отмеченный офлайн-режим. Для настоящих витрин
выберите PostgreSQL в боковом меню и задайте `DATABASE_URL`.

## Что уже проверяется

- обработка HTTP 429 и 5xx с увеличивающейся задержкой;
- разбиение сегментов и явный контроль лимита 2 000;
- отсутствие выдуманной средней для односторонней зарплатной вилки;
- кэш детальных карточек между запусками;
- дубли в снимках, границы зарплаты, внешние ключи и обязательные поля;
- наличие `DENSE_RANK`, `LAG`, `FULL OUTER JOIN`, `PERCENTILE_CONT` и примера
  `EXPLAIN ANALYZE`.

## Ограничения текущей проверки

Проверены офлайн-тесты, PostgreSQL 16, загрузка RAW, преобразование в DWH,
витрины, SQL-проверки качества и оба режима дашборда. Живой поиск HH пока не
завершён из-за отсутствия одобренного токена, поэтому проект не заявляет никаких
результатов о рынке. Файлы из `data/sample` и строки запуска `synthetic_demo`
остаются только техническим примером.
