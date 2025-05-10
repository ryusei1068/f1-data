FROM python:3.13.3

RUN pip install uv
COPY main.py .
COPY pyproject.toml .
RUN mkdir fastf1_cache

CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]