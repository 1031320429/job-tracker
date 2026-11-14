FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt

ENV HOST=0.0.0.0
ENV DATA_DIR=/data
EXPOSE 8420

CMD ["python3", "app.py"]
