FROM python:3.10

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y fonts-dejavu-core

EXPOSE 5010

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5010"]