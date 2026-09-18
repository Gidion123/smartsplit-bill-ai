# Image aplikasi: hanya dependensi Streamlit + reader DeepSeek.
# Untuk ikut memasang model lokal (Donut/Qwen, dipakai benchmark riset):
#   docker build --build-arg WITH_LOCAL_MODELS=1 -t smartsplit .
FROM python:3.12-slim

ARG WITH_LOCAL_MODELS=0
WORKDIR /app

COPY requirements.txt requirements-local.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && if [ "$WITH_LOCAL_MODELS" = "1" ]; then pip install --no-cache-dir -r requirements-local.txt; fi

COPY . .

EXPOSE 8501
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
