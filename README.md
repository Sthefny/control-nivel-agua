# Control de Nivel de Agua

Prototipo de **prevención de inundaciones**: un tanque con dos bombas. La bomba superior echa agua de forma
aleatoria (simula lluvia) y la bomba inferior drena el tanque, controlada por un **PID** (también P, PI y PD).
Un semáforo indica el riesgo según el nivel (Normal, Precaución, Alerta de inundación). Incluye un modo de
simulación de fallo del drenaje, análisis de estabilidad y respuesta en frecuencia, y comparación con datos reales.

Hecho con Dash, Plotly y python-control.

## Correrlo en tu computador

```bash
pip install -r dash_app/requirements.txt
python dash_app/app.py
```

Luego abre http://127.0.0.1:8050

## Publicarlo (Render, plan gratis)

El archivo `render.yaml` ya trae la configuración: carpeta `dash_app`, instalación con `requirements.txt`
y arranque con `gunicorn app:server`.
