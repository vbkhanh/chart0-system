import os
import requests
import time

def get_access_token(email: str, password: str) -> str:
    url = 'https://symbol-service.api.firmbond.sea2.eaera.com/adminlogin'
    headers = {
        'accept': 'application/json',
        'Content-Type': 'application/json'
    }
    data = {
        "email": email,
        "password": password
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    return response.json().get('access_token')

def upload_file(file_name: str, file_path: str, access_token: str):
    url = 'https://symbol-service.api.firmbond.sea2.eaera.com/tokyo_stock/upload'
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    files = [
        ('files', (file_name, open(file_path, 'rb'), 'text/csv'))
    ]
    response = requests.post(url, headers=headers, files=files)
    if response.status_code == 401:
        raise PermissionError("Unauthorized access, token might be expired.")
    response.raise_for_status()
    return response.json()

def main():
    email = ""
    password = ""
    folder_path = "scripts/TRIPLAYZ_DATA"

    # Get access token
    access_token = get_access_token(email, password)
    print(access_token)
    
    # Iterate over files in the folder and upload each
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)
        if os.path.isfile(file_path):
            while True:
                try:
                    response = upload_file(file_name, file_path, access_token)
                    print(f"Uploaded {file_name}: {response}")
                    break
                except PermissionError:
                    print(f"Token expired, retrying to get a new access token for {file_name}.")
                    access_token = get_access_token(email, password)
                except Exception as e:
                    print(f"Failed to upload {file_name}: {e}")
                    break
        time.sleep(1)

if __name__ == "__main__":
    main()
