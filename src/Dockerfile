FROM python:3.9

# Setup gunicorn env vars
ENV GUNICORN_DIRECTORY=/gunicorn \
    GUNICORN_WORKERS=1 \
    GUNICORN_WORKER_CLASS=gevent \
    GUNICORN_BACKLOG=2048 \
    APP_MODULE=main:app \
    APP_DIRECTORY=/src

# Setup gunicorn config
WORKDIR ${GUNICORN_DIRECTORY}
COPY gunicorn .

# Setup application
WORKDIR ${APP_DIRECTORY}

# Install container dependencies
# pydub - ffmpeg
RUN apt update && apt install -y ffmpeg libavcodec-extra

# Install python dependencies
RUN pip install pipenv
COPY src/Pipfile* ./
RUN pipenv install --system --deploy

# Copy remaining source
COPY src .

# Run the server
CMD gunicorn --bind 0.0.0.0:${PORT} --config ${GUNICORN_DIRECTORY}/gunicorn.conf.py --log-config ${GUNICORN_DIRECTORY}/logging.conf \
    --chdir ${APP_DIRECTORY} ${APP_MODULE}
