# Delay Chain Mapper

Delay Chain Mapper is a Django web application for modeling project task dependencies, tracking delays, and understanding how delays propagate across a task chain.

It includes AI-assisted planning and analysis powered by Groq, plus PDF export for reporting.

## Features

- Interactive task-chain mapping (nodes + dependency links)
- Delay propagation simulation across downstream tasks
- AI chain generation from a natural-language project prompt
- AI delay optimization analysis and recommendations
- Project save/load APIs backed by SQLite
- User authentication (register, login, logout, status)
- Admin-only analytics endpoint
- PDF report export for project delay summaries

## Tech Stack

- Python 3
- Django 6
- SQLite (default DB)
- Groq API (optional AI features)
- ReportLab (PDF generation)
- Tailwind CDN + D3.js on frontend templates

## Project Structure

- `delaychain/` - Django project config (settings, root URLs, WSGI/ASGI)
- `mapper/` - Core app (models, views, API routes, Groq integration)
- `templates/mapper/` - Frontend templates (dashboard, login, register)
- `db.sqlite3` - Local development database

## Quick Start

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Add environment variables in `.env` (optional for AI):

```env
GROQ_API_KEY=your_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

4. Run migrations:

```bash
python manage.py migrate
```

5. Start the server:

```bash
python manage.py runserver
```

## Core Data Model

- Project: owned (or anonymous/default) container for a task graph
- Task: node in the graph (`task_id`, `name`, `duration`, `delay`, `timestamp`)
- Link: directed dependency (`source_task_id -> target_task_id`)

## Main API Endpoints

- `GET /api/project/` - load current project graph
- `POST /api/project/save/` - bulk save full graph state
- `POST /api/task/create/` - create task
- `DELETE /api/task/<task_id>/delete/` - delete task + related links
- `POST /api/delay/propagate/` - apply/propagate delay
- `POST /api/generate-chain/` - AI chain generation from prompt
- `POST /api/analyze-delay/` - AI optimization analysis
- `POST /api/export-pdf/` - export delay analysis PDF
- `POST /api/auth/register/` - register user
- `POST /api/auth/login/` - login
- `POST /api/auth/logout/` - logout
- `GET /api/auth/status/` - auth status
- `GET /api/admin/analytics/` - admin analytics

## Notes

- AI endpoints return service-unavailable responses if `GROQ_API_KEY` is missing.
- Static files are configured with WhiteNoise (`STATIC_ROOT=staticfiles`).
- Current settings use `DEBUG=True` and permissive hosts for development.

## License

No license file is currently defined in this repository.
