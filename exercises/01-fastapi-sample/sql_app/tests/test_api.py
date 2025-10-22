def _create_user(client, email="deadpool@example.com"):
    response = client.post(
        "/users/",
        json={"email": email, "password": "chimichangas4life"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _auth_headers(api_token):
    return {"X-API-TOKEN": api_token}


# ユーザ作成時にAPIトークンが返却されることを確認する
def test_create_user_returns_api_token(test_db, client):
    user = _create_user(client)
    assert user["email"] == "deadpool@example.com"
    assert "id" in user
    assert "api_token" in user
    assert isinstance(user["api_token"], str)
    assert len(user["api_token"]) >= 32


# 認証ヘッダがない場合は保護されたエンドポイントが401を返すことを確認する
def test_protected_endpoints_require_token(test_db, client):
    user = _create_user(client)

    responses = [
        client.get("/users/"),
        client.get(f"/users/{user['id']}"),
        client.get("/items/"),
        client.post(
            f"/users/{user['id']}/items/",
            json={"title": "katana polish", "description": "shine it up"},
        ),
    ]

    for response in responses:
        assert response.status_code == 401


# 正しいトークンを付与すると各エンドポイントが成功することを確認する
def test_protected_endpoints_accept_valid_token(test_db, client):
    user = _create_user(client)
    headers = _auth_headers(user["api_token"])

    response = client.get("/users/", headers=headers)
    assert response.status_code == 200
    users = response.json()
    assert any(u["email"] == user["email"] for u in users)

    response = client.get(f"/users/{user['id']}", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == user["email"]

    response = client.post(
        f"/users/{user['id']}/items/",
        headers=headers,
        json={"title": "chimichanga prep", "description": "ingredients run"},
    )
    assert response.status_code == 200
    item = response.json()
    assert item["owner_id"] == user["id"]

    response = client.get("/items/", headers=headers)
    assert response.status_code == 200
    assert any(i["id"] == item["id"] for i in response.json())


# 誤ったトークンではアクセスが拒否されることを確認する
def test_invalid_api_token_rejected(test_db, client):
    _create_user(client)
    response = client.get("/users/", headers=_auth_headers("invalid-token"))
    assert response.status_code == 401
