from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime

app = FastAPI()
# uvicorn main:app --host 0.0.0.0 --reload

class TrainRequest(BaseModel):
    text: str

# Setup RabbitMQ connection
# credentials = pika.PlainCredentials('user', 'bitnami')
# connection = pika.BlockingConnection(pika.ConnectionParameters('localhost', credentials=credentials))
# channel = connection.channel()
# channel.queue_declare(queue='train_queue')

def log_request(request_text: str):
    # Obtenir le timestamp actuel
    timestamp = datetime.now().isoformat()
    # Construire la ligne à écrire dans le fichier
    log_line = f"Next Log $*$ - {timestamp} - {request_text}\n"
    # Écrire dans le fichier en mode append
    with open("elastic2.log", "a") as log_file:
        log_file.write(log_line)

@app.post("/train")
async def train_model(request: TrainRequest):
    try:
        print(request)
        log_request(request.text)
        # channel.basic_publish(exchange='',
        #                       routing_key='train_queue',
        #                       body=request.text)
        return {"message": "Training request received"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Server is running"}
