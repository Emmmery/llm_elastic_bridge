import requests
import json
import time
from datetime import datetime
from sentence_transformers import SentenceTransformer, util

last_timestamp = None
last_position = 0
context = []  # Contexte de la conversation
qna_database = "qna_db.json"  # Fichier de stockage des questions et réponses
model = SentenceTransformer('all-MiniLM-L6-v2')  # Utiliser un modèle d'embedding

def load_qna_db():
    try:
        with open(qna_database, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def save_qna_db(qna_dict):
    with open(qna_database, 'w') as file:
        json.dump(qna_dict, file)

def get_most_similar_question(new_question, qna_dict, threshold=0.8):
    new_question_embedding = model.encode(new_question)
    best_match = None
    best_similarity = threshold

    for stored_question in qna_dict:
        if stored_question.startswith("La seule chose que tu es autorisé à répondre est une note entre 0 et 100, sous ce format : "):
            continue  # Exclure le prompt initial de la comparaison
        stored_question_embedding = model.encode(stored_question)
        similarity = util.pytorch_cos_sim(new_question_embedding, stored_question_embedding).item()
        
        if similarity > best_similarity:
            best_match = stored_question
            best_similarity = similarity

    return best_match

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

        return final_message

    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None

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
                    new_blocks.append((current_timestamp, ''.join(current_block)))
                current_timestamp = timestamp
                current_block = [content]
            else:
                current_block.append(line)
        else:
            current_block.append(line)

    if current_block and (last_timestamp is None or (current_timestamp and current_timestamp > last_timestamp)):
        new_blocks.append((current_timestamp, ''.join(current_block)))

    if new_blocks:
        last_timestamp = new_blocks[-1][0]

    return [block for _, block in new_blocks]

if __name__ == "__main__":
    url = "http://localhost:11434/api/chat"
    log_file = "elastic2.log"

    prompt = "La seule chose que tu es autorisé à répondre est une note entre 0 et 100. Il est imperatif que la réponse soit un nombre entre 0 et 100 (donc 1 à 3 chaine de caractères de type numérique). 0 étant une donnée totalement corrompu et 100 une donnée totalement correcte. Tu n'es pas autorisé à justifier ou expliquer. Les critères d'une bonne note (100) la bonne qualité du français (orthographe, vocabulaire, grammaire, syntaxe correctes etc... Si les calculs mathématiques sont correctes ... exemple de données corrompu : 'Bqxzznilhrpustg tiehnnzr' car ni Bqxzznilhrpustg ni tiehnnzr n'appartiennent aux dictionnaires français. De plus, en l'absence de données réelles à évaluer, la note doit être basse, voire nulle. Il ne faut pas supposer que les critères sont respectés. Enfin, le notation doit être proportionnelle à la longueur, si une phrase courte est correcte, elle doit avoir une bonne note, et si une est longue phrase mais incorrecte, elle doit avoir une note basse. Si tu m'envoie ne serait-ce qu'une lettre le programme va crasher, alors le seule format autorisé est le suivant : 15"
    
    qna_dict = load_qna_db()

    while True:
        new_blocks = read_logs_by_timestamp(log_file)

        if not new_blocks:
            print("No new logs found.")
            time.sleep(5)

        for block in new_blocks:
            question = f"{prompt}{block.strip()}"
            
            # Trouver la question la plus similaire
            similar_question = get_most_similar_question(question, qna_dict)

            if similar_question:
                response = qna_dict[similar_question]
                print(f"Reusing stored response: {response}")
            else:
                # Ajouter le bloc actuel au contexte
                context.append({"role": "user", "content": question})

                data = {
                    "model": "mistral",
                    "messages": context  # Envoyer tout le contexte
                }

                print(f"Sending log block: {block.strip()}")

                response = send_api_request(url, data)

                if response:
                    # Ajouter la réponse au contexte et l'enregistrer dans la base de données
                    context.append({"role": "assistant", "content": response})
                    qna_dict[question] = response
                    save_qna_db(qna_dict)

        time.sleep(1)
