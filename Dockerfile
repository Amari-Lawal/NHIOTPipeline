FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

RUN chmod +x run_sub_server.sh run_sub_iot.sh run_pub.sh

CMD ["/bin/bash"]
