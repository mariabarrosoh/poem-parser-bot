import requests

if __name__ == "__main__":

    local = False
    poem_path = 'test/input/junin.jpeg'

    if local:
        url = "http://localhost:8080/api/parse"
    else:
        url = "https://poem-parser.onrender.com/api/parse"


    try:
        with open(poem_path, 'rb') as img_file:
            files = [('images', img_file)]
            response = requests.post(url, files=files)

        print("Status Code:", response.status_code)
        try:
            print("Response JSON:", response.json())
        except ValueError:
            print("Response Text:", response.text)

    except FileNotFoundError:
        print(f"Error: File not found - {poem_path}")
