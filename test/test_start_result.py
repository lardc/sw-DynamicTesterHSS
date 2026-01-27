import requests, json

port: int = 8080
url: str = f"http://127.0.0.1:{port}"

data = "Vce"

post_body = "{" + f"\"emulation\": true, \"csv_path\": \"data/data100k_{data}0.csv\", \"sample_rate\": 1e-10" + "}"

def get_data():
    requests.post(f"{url}/start")
    res = json.dumps(requests.get(f"{url}/results").json(), indent=4)
    return res

if __name__ == "__main__":
    response = requests.post(f"{url}/configure", post_body)
    print(response.json())

    res_data = get_data()
    print(res_data)
    with open(f"result_{data}0.json", "w") as f:
        f.write(res_data)


