import requests
import json
import urllib3
from requests.auth import HTTPBasicAuth

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def fetch_logs_from_elasticsearch(es_url, query, log_file):
	headers = {
		"Content-Type": "application/json"
	 }
	try:
		response = requests.get(es_url + "/_search", headers=headers, json=query, verify=False, auth=HTTPBasicAuth('elastic','cybermenace'))		
		response.raise_for_status()

		data = response.json()


		with open(log_file, 'w') as file:
			for hit in data['hits']['hits']:
				log_entry = json.dumps(hit['_source'])
				file.write(log_entry + '\n')

		print(f"Logs récupérés et sauvegardés dans {log_file}")

	except requests.RequestException as e:
		print(f"Request failed: {e}")

if __name__ == "__main__":
	es_url = "https://192.168.100.234:9200"


	query = {
		"query": {
			"match_all": {}
		},
		"size": 1000
	}

	log_file = "elastic.log"

	fetch_logs_from_elasticsearch(es_url, query, log_file)
