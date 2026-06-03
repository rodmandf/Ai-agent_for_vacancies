CREATE TABLE IF NOT EXISTS local_vacancies (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    description TEXT NOT NULL,
    city TEXT NOT NULL,
    remote INTEGER NOT NULL,
    work_format TEXT NOT NULL,
    level TEXT NOT NULL,
    stack TEXT NOT NULL,
    published_at TEXT NOT NULL,
    url TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'local'
);

INSERT OR IGNORE INTO local_vacancies VALUES
('local-001','Junior Python Backend Developer','North API Lab','Ищем junior Python разработчика для FastAPI сервисов, интеграций с REST API и PostgreSQL. Будет плюсом опыт с Docker и Telegram bots. Формат remote, менторинг, задачи уровня junior.','Remote',1,'remote','junior','Python, FastAPI, PostgreSQL, REST API, Docker, Git','2026-06-01','https://example.com/jobs/local-001','local'),
('local-002','LLM Engineer Intern','PromptWorks','Стажировка для Python разработчика в AI-команде. Нужно уметь работать с API, JSON, prompt engineering, Git. Будем делать Telegram-ботов и RAG-прототипы. Remote или гибрид Москва.','Москва',1,'remote/hybrid','intern','Python, LLM, Telegram Bot, Git, REST API','2026-05-28','https://example.com/jobs/local-002','local'),
('local-003','Backend Developer Junior+','DataDesk','Нужен junior+ backend developer: Python, SQL, FastAPI, базовое понимание Docker. Работа с внутренними API и аналитическими сервисами. Гибрид Санкт-Петербург.','Санкт-Петербург',0,'hybrid','junior+','Python, FastAPI, SQL, Docker','2026-05-25','https://example.com/jobs/local-003','local'),
('local-004','AI Product Intern','FlowMind','Стажировка в AI-продукте. Python, LLM API, prompt engineering, интеграции с внешними сервисами. Опыт backend будет плюсом. Remote.','Remote',1,'remote','intern','Python, LLM, APIs, Git','2026-05-20','https://example.com/jobs/local-004','local'),
('local-005','Junior API Integration Developer','Integratech','Разработка интеграций с REST API на Python, поддержка сервисов, SQL-запросы, документация. Нужны Git и аккуратность. Удаленно.','Remote',1,'remote','junior','Python, REST API, SQL, Git','2026-05-18','https://example.com/jobs/local-005','local'),
('local-006','Python Automation Intern','OpsPilot','Автоматизация внутренних процессов на Python, работа с API и простыми базами данных. Подойдет студенту или начинающему специалисту. Гибкий remote.','Remote',1,'remote','intern','Python, API, SQLite, Git','2026-05-12','https://example.com/jobs/local-006','local'),
('local-007','Junior Python Developer','LegacySoft','Поддержка внутренних Python-скриптов, SQL, работа с CSV/JSON. Офис Москва, удаленка не предусмотрена.','Москва',0,'office','junior','Python, SQL, CSV, JSON','2026-05-10','https://example.com/jobs/local-007','local'),
('local-008','Backend Engineer','ScaleCore','Backend engineer with 3+ years commercial experience. Python, Kubernetes, highload systems. Senior tasks, relocation required.','Berlin',0,'office','middle','Python, Kubernetes, PostgreSQL','2026-05-08','https://example.com/jobs/local-008','local'),
('local-009','Telegram Bot Developer Intern','ChatOps Studio','Стажер Python для разработки Telegram-ботов на aiogram, интеграций с REST API и простых LLM-функций. Нужен Git, желательно SQL. Remote.','Remote',1,'remote','intern','Python, aiogram, Telegram Bot, REST API, LLM, SQL','2026-06-02','https://example.com/jobs/local-009','local'),
('local-010','Junior Data Engineer','PipeData','Junior role: Python, SQL, ETL scripts, PostgreSQL. Опыт backend API будет плюсом. Гибрид Москва.','Москва',0,'hybrid','junior','Python, SQL, PostgreSQL, ETL','2026-04-29','https://example.com/jobs/local-010','local'),
('local-011','Unpaid Python Internship','FreeHands','Неоплачиваемая стажировка Python, базовые скрипты и документация. Full-time office.','Москва',0,'office','intern','Python, Git','2026-05-30','https://example.com/jobs/local-011','local'),
('local-012','Junior LLM Backend Developer','VectorApps','Python backend для LLM-фич: FastAPI, PostgreSQL, очереди задач, внешние API, Telegram integrations. Remote-first, junior или junior+.','Remote',1,'remote','junior+','Python, FastAPI, PostgreSQL, LLM, Telegram Bot, REST API','2026-06-03','https://example.com/jobs/local-012','local');
