FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# roda sem root (uid 1000 = mesmo dono dos arquivos do projeto montados pelo docker-compose)
RUN useradd --create-home --uid 1000 app && chown -R app:app /app
USER app

EXPOSE 5000

# producao: gunicorn (sem depurador). --preload carrega o app uma vez so no processo principal,
# entao a chave da sessao (secret_key) e a migracao de inicio rodam uma vez, nao por worker
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "--preload", "app:app"]
