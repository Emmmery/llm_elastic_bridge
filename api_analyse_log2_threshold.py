import requests
import json
import time
from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.exceptions import TransportError
from requests.auth import HTTPBasicAuth
import urllib3
import warnings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
urllib3.disable_warnings(urllib3.exceptions.SecurityWarning)

warnings.filterwarnings('ignore', category=DeprecationWarning)

last_timestamp = None
last_position = 0

def send_api_request(url, data):
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()

        response_lines = response.text.strip().split('\n')
        contents = []

        for line in response_lines:
            try:
                obj = json.loads(line)
                if 'message' in obj and 'content' in obj['message']:
                    contents.append(obj['message']['content'])
            except json.JSONDecodeError as e:
                print(f"JSON decode failed for line: {line} with error: {e}")

        final_message = ''.join(contents)
        print("------------------------------")
        print(f"Final Message: {final_message}")
        print("------------------------------")

        if is_valid_score(final_message):
            score = final_message.strip()
        else:
            score = 0
            #score = input("Enter the score for this block (0-100): ").strip()

        return score

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

def is_valid_score(message):
    try:
        score = float(message)
        return 0 <= score <= 100
    except ValueError:
        return False

def read_logs_by_timestamp(file_path):
    global last_timestamp, last_position
    
    try:
        with open(file_path, 'r') as file:
            file.seek(last_position)
            lines = file.readlines()
            last_position = file.tell()
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return []
    except Exception as e:
        print(f"Error reading file {file_path}: {e}")
        return []
    
    new_blocks = []
    current_block = []
    current_timestamp = None

    for line in lines:
        if line.startswith("Next Log $*$ -"):
            try:
                _, timestamp_str, content = line.split(' - ', 2)
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError as e:
                print(f"Error parsing line: {line} - {e}")
                continue
            if last_timestamp is None or timestamp > last_timestamp:
                if current_block:
                    new_blocks.append((''.join(current_block)).strip())
                current_block = ["-------------START-------------\n", content]
                current_timestamp = timestamp
            else:
                current_block.append(line)
        else:
            current_block.append(line)

    if current_block and (last_timestamp is None or (current_timestamp and current_timestamp > last_timestamp)):
        new_blocks.append((''.join(current_block)).strip())
        last_timestamp = current_timestamp

    return new_blocks

def check_if_request_already_sent(block):
    with open("correct_training_data.txt", "r") as file:
        if block in file.read():
            return True

    with open("incorrect_training_data.txt", "r") as file:
        if block in file.read():
            return True

    return False

def write_to_file(file_path, block):
    with open(file_path, "a") as file:
        file.write(block + "\n")
        
def send_to_elasticsearch(data, es_url="https://192.168.100.234:9200"):
    es = Elasticsearch([es_url], http_auth=('elastic', 'cybermenace'), verify_certs=False,ssl_show_warn=False)
    headers = {
        "Content-Type": "application/json"
    }

    try:
        res = es.index(index="alert_llm_poisoning", body=data, headers=headers)
        print(f"Data sent to Elasticsearch: {res}")

    except TransportError as e:
        print(f"Failed to send data to Elasticsearch: {e}")


if __name__ == "__main__":
    url = "http://localhost:11434/api/chat"
    log_file = "elastic2.log"

    prompt = "La seule chose que tu es autorisé à répondre est une note entre 0 et 100. Il est imperatif que la réponse soit un nombre entre 0 et 100 (donc 1 à 3 chaine de caractères de type numérique). 0 étant une donnée totalement corrompu et 100 une donnée totalement correcte. Tu n'es pas autorisé à justifier ou expliquer. Les critères d'une bonne note (100) la bonne qualité du français (orthographe, vocabulaire, grammaire, syntaxe correctes etc... Si les calculs mathématiques sont correctes ... exemple de données corrompu : 'Bqxzznilhrpustg tiehnnzr' car ni Bqxzznilhrpustg ni tiehnnzr n'appartiennent aux dictionnaires français. De plus, en l'absence de données réelles à évaluer, la note doit être basse, voire nulle. Il ne faut pas supposer que les critères sont respectés. Enfin, le notation doit être proportionnelle à la longueur, si une phrase courte est correcte, elle doit avoir une bonne note, et si une est longue phrase mais incorrecte, elle doit avoir une note basse. Si tu m'envoie ne serait-ce qu'une lettre le programme va crasher, alors le seule format autorisé est le suivant : 15"
	
    while True:
        new_blocks = read_logs_by_timestamp(log_file)

        if not new_blocks:
            #print("No new logs found.")
            time.sleep(5)
            continue

        for block in new_blocks:
            if check_if_request_already_sent(block):
                #print(f"Request already sent for block: {block.strip()}")
                continue

            data = {
                "model": "phi3:medium",
                "messages": [
                    {"role": "user", "content": f"{prompt}{block.strip()}"}
                ]
            }

            print(f"Sending log block: {block.strip()}")
            score = send_api_request(url, data)

            if score is not None:
                if is_valid_score(score):
                    if float(score) >= 50:
                        write_to_file("correct_training_data.txt", block)
                    else:
                        write_to_file("incorrect_training_data.txt", block)
                        data_for_es = {
                            "timestamp": datetime.now(),
                            "block_content": block.strip(),
                            "score_received": score
                        }
                        # send_to_elasticsearch(data_for_es)
                else:
                    print("Invalid score received. Skipping writing to file.")

        time.sleep(1)
