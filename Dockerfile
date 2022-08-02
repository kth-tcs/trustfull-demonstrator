FROM python:3.8
WORKDIR /app
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY webdemo /app/webdemo
COPY auth/ /app/auth
CMD gunicorn auth.frejaeid.app:app --bind 0.0.0.0:8001 & \
  gunicorn webdemo.app:app --bind 0.0.0.0:8000 > /tmp/gunicorn.mylogs
