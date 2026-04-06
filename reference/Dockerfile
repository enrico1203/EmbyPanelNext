FROM python:3.11.4-slim

# Dipendenze sistema per Selenium/Chromium e librerie grafiche
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    libglib2.0-0 \
    libnss3 \
    libgdk-pixbuf2.0-0 \
    libgtk-3-0 \
    libxss1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Installa dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia tutto il progetto
COPY . .

# Rimuovi i file dati che verranno montati come volumi
RUN rm -f demo.db schedules.json app.log

EXPOSE 5000

CMD ["python", "app.py"]
