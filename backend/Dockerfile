FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
# COPY package-lock.json .

RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD [ "python", "manage.py", "runserver", "0.0.0.0:8000" ]