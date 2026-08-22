FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PERSONAL_REPO_MCP_HOST=0.0.0.0 \
    PERSONAL_REPO_MCP_PORT=8000 \
    PERSONAL_REPO_MCP_ROOT=/srv/personal-repo-mcp/repositories \
    PERSONAL_REPO_MCP_CONFIG=/etc/personal-repo-mcp/repositories.json

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && printf '%s\n' \
       '#!/bin/sh' \
       'case "$1" in' \
       '  *Username*) printf "%s\\n" "x-access-token" ;;' \
       '  *) printf "%s\\n" "${PERSONAL_REPO_MCP_GITHUB_PAT}" ;;' \
       'esac' > /usr/local/bin/personal-repo-mcp-git-askpass \
    && chmod 0555 /usr/local/bin/personal-repo-mcp-git-askpass

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install --no-cache-dir .

RUN mkdir -p /srv/personal-repo-mcp/repositories /etc/personal-repo-mcp \
    && useradd --create-home --uid 10001 app \
    && chown -R app:app /srv/personal-repo-mcp

USER app

EXPOSE 8000

CMD ["personal-repo-mcp"]
