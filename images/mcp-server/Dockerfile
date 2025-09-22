FROM python:3.12-slim

WORKDIR /app

COPY . .
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --no-cache-dir .

EXPOSE 8080
CMD ["python3", "-m", "palace.mcp_utils.mcp_server"]