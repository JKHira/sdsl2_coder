FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    build-essential \
    pipx \
  && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:${PATH}"

RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir --upgrade open-interpreter \
  && pipx install semgrep==1.146.0

WORKDIR /files
CMD ["interpreter"]
