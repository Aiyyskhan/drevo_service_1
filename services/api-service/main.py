import pika, uuid, time, json, os, io
from datetime import timedelta
from minio import Minio
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, File, UploadFile

MINIO_HOST = os.getenv("MINIO_HOST", "minio:9000")
MINIO_USER = os.getenv("MINIO_ACCESS", "minioadmin")
MINIO_PASS = os.getenv("MINIO_SECRET", "minioadmin")
BUCKET = "images"

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

app = FastAPI()


class RpcClient:
    def __init__(self, host: str = "rabbitmq"):
        self.host = host

    def call(self, payload: dict, timeout: float = 10.0) -> dict:
        correlation_id = str(uuid.uuid4())
        connection = pika.BlockingConnection(pika.ConnectionParameters(self.host))
        channel = connection.channel()

        # declare a temporary exclusive queue for replies
        result = channel.queue_declare(queue="", exclusive=True)
        callback_queue = result.method.queue

        response = None

        def on_response(ch, method, props, body):
            nonlocal response
            if props.correlation_id == correlation_id:
                try:
                    response = json.loads(body)
                except Exception:
                    response = {"status": "error", "detail": "invalid json"}

        channel.basic_consume(queue=callback_queue, on_message_callback=on_response, auto_ack=True)

        # publish request
        channel.basic_publish(
            exchange="",
            routing_key="generate",
            properties=pika.BasicProperties(reply_to=callback_queue, correlation_id=correlation_id),
            body=json.dumps(payload),
        )

        # wait for response or timeout
        start = time.time()
        while response is None and (time.time() - start) < timeout:
            connection.process_data_events(time_limit=0.1)

        try:
            connection.close()
        except Exception:
            pass

        if response is None:
            raise TimeoutError("no response from worker")

        return response


@app.get("/generate")
def generate(filename: str = Query(..., min_length=1), width: Optional[int] = Query(200, ge=1), height: Optional[int] = Query(200, ge=1)):
    """Request python-service to generate a random image.

    Returns a JSON with status and presigned URL (if successful).
    """
    payload = {"filename": filename, "width": int(width), "height": int(height)}
    client = RpcClient()
    try:
        resp = client.call(payload, timeout=15.0)
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return resp


@app.post("/upload")
async def upload_gif(file: UploadFile = File(...)):
    """Принимает GIF, загружает в MinIO и отправляет задачу в очередь."""
    if not file.filename.lower().endswith(".gif"):
        return {"status": "error", "detail": "Можно загружать только GIF"}

    # Инициализируем MinIO
    client = Minio(MINIO_HOST, access_key=MINIO_USER, secret_key=MINIO_PASS, secure=False)

    if not client.bucket_exists(BUCKET):
        client.make_bucket(BUCKET)

    # Загружаем GIF в MinIO
    file_bytes = await file.read()
    file_buf = io.BytesIO(file_bytes)
    client.put_object(
        BUCKET, file.filename, file_buf, length=len(file_bytes), content_type="image/gif"
    )

    # Создаём временную ссылку
    url = client.presigned_get_object(BUCKET, file.filename, expires=timedelta(hours=1))

    # Публикуем задачу в RabbitMQ
    conn = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    ch = conn.channel()
    ch.queue_declare(queue="tasks")

    msg = {"id": os.path.splitext(file.filename)[0], "url": url, "status": "done"}
    ch.basic_publish(exchange="", routing_key="tasks", body=json.dumps(msg))
    conn.close()

    return {"status": "ok", "url": url, "filename": file.filename}

# docker compose up --build
# curl 'http://localhost:8080/generate?filename=test1.png&width=300&height=150'
# curl -X POST http://localhost:8080/upload -F "file=@leaders_5.50.3_1_0.gif"