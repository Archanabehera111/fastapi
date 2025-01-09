FROM python:3.8.10-slim

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

CMD ["uvicorn", "main:app", "--port", "8005", "--host", "0.0.0.0", "--reload"]
