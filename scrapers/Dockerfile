# Usamos la imagen oficial de Playwright que ya tiene todo lo que necesitamos
FROM mcr.microsoft.com/playwright/python:v1.45.0-jammy

# Establecemos el directorio de trabajo dentro del contenedor
WORKDIR /app

# Copiamos solo el archivo de requisitos primero para aprovechar el caché de Docker
COPY requirements.txt .

# Instalamos las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de nuestro código (el script del scraper)
COPY . .

# El comando para correr el script será definido en render.yaml