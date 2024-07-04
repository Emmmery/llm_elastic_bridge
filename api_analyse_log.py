import requests
import json
import time

last_line_index = 0

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
		print(f"Final Message: {final_message}")

	except requests.RequestException as e:
		print(f"Request failed: {e}")

def read_new_log_lines(files_path):
	global last_line_index

	with open(files_path, 'r') as file:
		for _ in range(last_line_index):
			file.readline()

		new_lines = file.readlines()
		last_line_index += len(new_lines)

		return new_lines

if __name__ == "__main__":
	url = "http://localhost:11434/api/chat"
	log_file = "elastic.log"

	prompt = "Décris-moi en français ce qui suit :"

	while True:
		new_lines = read_new_log_lines(log_file)

		for line in new_lines:
			data = {
				"model": "phi3:medium",
				"messages": [
					{"role": "user", "content": f"{prompt}{line.strip()}"}
				]
			}

			print(f"Sending log line: {line.strip()}")

			send_api_request(url, data)

		time.sleep(1)
