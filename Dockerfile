# Imagen para Hugging Face Spaces (SDK Docker): la app Dash de dash_app/
FROM python:3.12-slim

# Hugging Face exige un usuario no root con UID 1000
RUN useradd -m -u 1000 usuario
USER usuario
ENV HOME=/home/usuario PATH=/home/usuario/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# Solo se copia dash_app/ (nada de la versión Streamlit ni de los prompts)
WORKDIR /home/usuario/app/dash_app
COPY --chown=usuario dash_app/ .
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 7860
# Los imports (graficos, modelo, datos_reales) son simples: se arranca desde dentro de dash_app/
CMD ["gunicorn", "app:server", "--bind", "0.0.0.0:7860", "--workers", "2", "--threads", "4", "--timeout", "120"]
