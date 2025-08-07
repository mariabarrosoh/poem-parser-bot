import requests

url = "http://localhost:8080/api/parse"
files = [
    ('images', open('test/input/junin.jpeg', 'rb'))
]

response = requests.post(url, files=files)

print("Status Code:", response.status_code)
print("Response JSON:", response.json())
