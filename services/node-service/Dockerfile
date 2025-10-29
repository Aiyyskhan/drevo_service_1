FROM node:18
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd curl && rm -rf /var/lib/apt/lists/*
COPY wait-for.sh /app/wait-for.sh
RUN chmod +x /app/wait-for.sh
CMD ["/app/wait-for.sh"]
