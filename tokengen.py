import requests

def gen_token(username: str, password: str) -> str:
    auth_server_url = 'https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token'

    payload = {
        'username': username,
        'password': password,
        'grant_type': 'password',
        'client_id': 'cdse-public'
    }

    response = requests.post(auth_server_url, data=payload, timeout=10)

    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        raise Exception(f'Error generating auth token. Status code = {response.status_code}')