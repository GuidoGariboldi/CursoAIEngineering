FROM python:3.12-slim
WORKDIR /code

# PyTorch en versión CPU (mucho más liviana) para el modelo de embeddings
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY conocimiento ./conocimiento
COPY tests ./tests
COPY pytest.ini .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
