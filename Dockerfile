# Stage 1: Build React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline 2>/dev/null || npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Python backend + serve frontend
FROM python:3.12-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt; \
    # sgmllib3k fails to build on Python 3.11 due to distutils changes; \
    # install a minimal stub that satisfies feedparser's import \
    python -c "import importlib.util, site, os; stub='''import html.parser,re\nclass SGMLParseError(Exception):pass\nentityref=re.compile(r\"&(?P<ref>[a-zA-Z][-.a-zA-Z0-9]*)[^a-zA-Z0-9]\")\nincomplete=re.compile(r\"&[a-zA-Z#]\")\ninteresting=re.compile(r\"[&<]\")\nshorttag=re.compile(r\"<(?P<name>[a-zA-Z][-.a-zA-Z0-9]*)/\")\nshorttagopen=re.compile(r\"<[a-zA-Z][-.a-zA-Z0-9]*/\")\nstarttagopen=re.compile(r\"<[>a-zA-Z]\")\nclass SGMLParser(html.parser.HTMLParser):\n def __init__(self,v=0): super().__init__(convert_charrefs=False)\n'''; [open(os.path.join(d,\"sgmllib.py\"),\"w\").write(stub) for d in site.getsitepackages() if os.path.isdir(d)][:1]"

COPY backend/app ./app

# Copy built React app into /app/static (FastAPI serves it)
COPY --from=frontend-build /app/static ./static

# Data directory for SQLite
RUN mkdir -p /data

ENV DATABASE_URL=sqlite:////data/newsrobot.db \
    PORT=8000 \
    LOG_LEVEL=info

EXPOSE 8000

CMD ["sh", "-c", "python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
