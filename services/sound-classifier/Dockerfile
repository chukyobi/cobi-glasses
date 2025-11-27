
FROM python:3.10-bullseye

WORKDIR /app

COPY services/sound-classifier/requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY services/sound-classifier/app.py .
COPY services/sound-classifier/entrypoint.sh .

ENV PYTHONPATH=/app
RUN chmod +x entrypoint.sh

CMD ["./entrypoint.sh"]
