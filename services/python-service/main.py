import os
import time
import json
import io
import pika
from minio import Minio
from PIL import Image
import numpy as np
from datetime import timedelta


MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
BACKOFF_SECONDS = float(os.getenv("RETRY_BACKOFF", "1.0"))


def retry(operation, name="operation", retries=MAX_RETRIES, backoff=BACKOFF_SECONDS):
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return operation()
        except Exception as e:
            last_exc = e
            wait = backoff * (2 ** (attempt - 1))
            print(f"{name} failed (attempt {attempt}/{retries}): {e}; retrying in {wait:.1f}s")
            time.sleep(wait)
    print(f"{name} failed after {retries} attempts: {last_exc}")
    raise last_exc


def create_minio_client():
    return Minio(
        "minio:9000",
        access_key=os.getenv("MINIO_ACCESS", "minioadmin"),
        secret_key=os.getenv("MINIO_SECRET", "minioadmin"),
        secure=False,
    )


def ensure_bucket(client, bucket_name="images"):
    def op():
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        return True

    return retry(op, name=f"ensure_bucket:{bucket_name}")


def generate_image_bytes(width: int, height: int):
    arr = (np.random.rand(height, width, 3) * 255).astype(np.uint8)
    img = Image.fromarray(arr, 'RGB')
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def upload_image_bytes(client, bucket_name: str, object_name: str, buf: io.BytesIO):
    def op():
        client.put_object(bucket_name, object_name, buf, length=buf.getbuffer().nbytes, content_type="image/png")
        return True

    return retry(op, name=f"upload:{object_name}")


def connect_rabbitmq():
    def op():
        conn = pika.BlockingConnection(pika.ConnectionParameters("rabbitmq"))
        return conn

    return retry(op, name="rabbitmq_connect")


def run_worker():
    client = create_minio_client()
    ensure_bucket(client, "images")

    conn = connect_rabbitmq()
    ch = conn.channel()
    ch.queue_declare(queue="generate")
    ch.basic_qos(prefetch_count=1)

    print(" [*] Awaiting RPC requests on 'generate' queue")

    def on_request(ch, method, props, body):
        try:
            data = json.loads(body)
            filename = data.get("filename") or data.get("name") or "result.png"
            width = int(data.get("width", 200))
            height = int(data.get("height", 200))
        except Exception as e:
            print("Invalid request payload:", e)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        print(f" [.] Generating image {filename} ({width}x{height})")
        try:
            buf = generate_image_bytes(width, height)
            upload_image_bytes(client, "images", filename, buf)
            try:
                url = client.presigned_get_object("images", filename, expires=timedelta(hours=1))
            except Exception:
                url = f"http://minio:9000/images/{filename}"

            # publish a notification to the 'tasks' queue so node-service can download the image
            try:
                task_id = os.path.splitext(filename)[0]
                task_msg = {"id": task_id, "url": url, "status": "done"}
                # ensure tasks queue exists and publish
                ch.queue_declare(queue="tasks", durable=False)
                ch.basic_publish(exchange="", routing_key="tasks", body=json.dumps(task_msg))
                print(f" [>] Published task to 'tasks' queue: {task_msg}")
            except Exception as e_pub:
                print(" [!] Failed to publish task message:", e_pub)

            response = {"status": "ok", "url": url, "filename": filename}
        except Exception as e:
            print("error generating/uploading:", e)
            response = {"status": "error", "detail": str(e)}

        # reply if possible
        if props and props.reply_to:
            ch.basic_publish(
                exchange="",
                routing_key=props.reply_to,
                properties=pika.BasicProperties(correlation_id=props.correlation_id),
                body=json.dumps(response),
            )

        ch.basic_ack(delivery_tag=method.delivery_tag)

    ch.basic_consume(queue="generate", on_message_callback=on_request)
    try:
        ch.start_consuming()
    except KeyboardInterrupt:
        try:
            ch.stop_consuming()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == "__main__":
    run_worker()

