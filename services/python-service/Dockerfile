FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
# Install small utils used by the health/wait script (curl/netcat)
RUN apt-get update \
	&& apt-get install -y --no-install-recommends curl netcat-openbsd \
	&& rm -rf /var/lib/apt/lists/*

COPY . .
COPY wait-for.sh /app/wait-for.sh
RUN chmod +x /app/wait-for.sh

CMD ["/app/wait-for.sh"]
