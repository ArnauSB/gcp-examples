#!/bin/bash

# Nombre del tema
TEMA="iot-service" # <--- Cambia el tema

# Datos del mensaje (simulados)
temperature=$(($RANDOM % 40 + 10))  # Temperatura aleatoria entre 10 y 50
humidity=$(($RANDOM % 80 + 20))    # Humedad aleatoria entre 20 y 100

# Crear mensaje JSON
mensaje="{\"temperature\": $temperature, \"humidity\": $humidity}"

# Publicar mensaje
gcloud pubsub topics publish $TEMA --message="$mensaje"

echo "Mensaje publicado: $mensaje"
