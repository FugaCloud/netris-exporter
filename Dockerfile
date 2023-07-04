FROM python:latest

COPY exporter.py /app/exporter.py
COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip3 install -r requirements.txt

CMD python3 exporter.py
