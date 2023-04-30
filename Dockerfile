FROM python:3.11.2
WORKDIR /app/
COPY . .
CMD ["bash","run"]
