FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
COPY deployment/requirements.txt ./deployment/requirements.txt
RUN pip install --no-cache-dir -r deployment/requirements.txt
COPY . .
RUN mkdir -p /app/instance
EXPOSE 8000
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", "foodbridge:create_app()"]
