from .conftest import TestingSessionLocal
from .. import models


def _create_user(client, email="deadpool@example.com"):
    response = client.post(
        "/users/",
        json={"email": email, "password": "chimichangas4life"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_item(client, user_id, headers, title="default title", description="default description"):
    response = client.post(
        f"/users/{user_id}/items/",
        headers=headers,
        json={"title": title, "description": description},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _delete_user(client, user_id, headers=None):
    return client.delete(f"/users/{user_id}", headers=headers or {})


def _auth_headers(api_token):
    return {"X-API-TOKEN": api_token}


def _create_authenticated_user(client, email="deadpool@example.com"):
    user = _create_user(client, email=email)
    return user, _auth_headers(user["api_token"])


def _deactivate_user(user_id: int):
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        assert user is not None, "User to deactivate must exist"
        user.is_active = False
        db.commit()
    finally:
        db.close()


# ユーザ作成時にAPIトークンが返却されることを確認する
def test_create_user_returns_api_token(test_db, client):
    user = _create_user(client)
    assert user["email"] == "deadpool@example.com"
    assert "id" in user
    assert "api_token" in user
    assert isinstance(user["api_token"], str)
    assert len(user["api_token"]) >= 32


# 認証ヘッダがない場合は各エンドポイントが401を返すことを確認する
def test_list_users_requires_token(test_db, client):
    _create_user(client)
    response = client.get("/users/")
    assert response.status_code == 401


def test_user_detail_requires_token(test_db, client):
    user = _create_user(client)
    response = client.get(f"/users/{user['id']}")
    assert response.status_code == 401


def test_list_items_requires_token(test_db, client):
    _create_user(client)
    response = client.get("/items/")
    assert response.status_code == 401


def test_me_items_requires_token(test_db, client):
    response = client.get("/me/items")
    assert response.status_code == 401


def test_create_item_requires_token(test_db, client):
    user = _create_user(client)
    response = client.post(
        f"/users/{user['id']}/items/",
        json={"title": "katana polish", "description": "shine it up"},
    )
    assert response.status_code == 401


# 正しいトークンを付与すると各エンドポイントが成功することを確認する
def test_list_users_returns_users_when_authorized(test_db, client):
    user, headers = _create_authenticated_user(client)
    response = client.get("/users/", headers=headers)
    assert response.status_code == 200
    users = response.json()
    assert any(u["email"] == user["email"] for u in users)
    assert all(u.get("api_token") is None for u in users)


def test_user_detail_returns_user_when_authorized(test_db, client):
    user, headers = _create_authenticated_user(client)
    response = client.get(f"/users/{user['id']}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user["email"]
    assert body["id"] == user["id"]
    assert body["api_token"] is None


def test_create_item_for_user_authorized(test_db, client):
    user, headers = _create_authenticated_user(client)
    response = client.post(
        f"/users/{user['id']}/items/",
        headers=headers,
        json={"title": "chimichanga prep", "description": "ingredients run"},
    )
    assert response.status_code == 200
    item = response.json()
    assert item["owner_id"] == user["id"]


def test_items_list_includes_created_item(test_db, client):
    user, headers = _create_authenticated_user(client)
    created_item = _create_item(
        client,
        user["id"],
        headers,
        title="owner task",
        description="belongs to owner",
    )
    response = client.get("/items/", headers=headers)
    assert response.status_code == 200
    items = response.json()
    assert any(i["id"] == created_item["id"] for i in items)


# 誤ったトークンではアクセスが拒否されることを確認する
def test_invalid_api_token_rejected(test_db, client):
    _create_user(client)
    response = client.get("/users/", headers=_auth_headers("invalid-token"))
    assert response.status_code == 401


def test_me_items_returns_only_current_user_items(test_db, client):
    owner, owner_headers = _create_authenticated_user(client)
    other, other_headers = _create_authenticated_user(
        client, email="wolverine@example.com"
    )

    owner_item = _create_item(
        client,
        owner["id"],
        owner_headers,
        title="owner task",
        description="belongs to owner",
    )
    _create_item(
        client,
        other["id"],
        other_headers,
        title="other task",
        description="belongs to other user",
    )

    response = client.get("/me/items", headers=owner_headers)
    assert response.status_code == 200
    items = response.json()
    assert items, "Expected at least one item for owner"
    assert any(i["id"] == owner_item["id"] for i in items)
    assert all(i["owner_id"] == owner["id"] for i in items)


def test_me_items_returns_empty_list_for_user_without_items(test_db, client):
    user, headers = _create_authenticated_user(client, email="empty@example.com")

    response = client.get("/me/items", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


    # 削除ユーザの所有アイテムが、最小IDのアクティブユーザに移譲されることを確認
def test_delete_user_transfers_items_to_lowest_active_user(test_db, client):
    inactive, _ = _create_authenticated_user(
        client, email="inactive@example.com"
    )
    # receiverより小さいIDだが非アクティブなユーザを用意し、移譲先選定がis_activeを考慮することを検証
    _deactivate_user(inactive["id"])
    receiver, receiver_headers = _create_authenticated_user(
        client, email="receiver@example.com"
    )
    extra, extra_headers = _create_authenticated_user(
        client, email="extra@example.com"
    )
    owner, owner_headers = _create_authenticated_user(
        client, email="owner@example.com"
    )

    first_item = _create_item(
        client,
        owner["id"],
        owner_headers,
        title="task one",
        description="owned by deleted user",
    )
    second_item = _create_item(
        client,
        owner["id"],
        owner_headers,
        title="task two",
        description="owned by deleted user",
    )

    response = _delete_user(client, owner["id"], headers=extra_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == owner["id"]
    assert body["is_active"] is False
    assert body["api_token"] is None

    items_response = client.get("/items/", headers=receiver_headers)
    assert items_response.status_code == 200
    items = items_response.json()
    transferred_ids = {first_item["id"], second_item["id"]}
    transferred_items = [i for i in items if i["id"] in transferred_ids]
    assert transferred_items, "Expected transferred items"
    assert all(i["owner_id"] == receiver["id"] for i in transferred_items)


    # 単独のアクティブユーザ削除は拒否される（400）ことを確認
def test_delete_only_active_user_rejected(test_db, client):
    user, headers = _create_authenticated_user(client, email="solo@example.com")

    response = _delete_user(client, user["id"], headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"] == "Cannot delete the only active user"


    # 認証ヘッダなしの削除リクエストが401となることを確認
def test_delete_user_requires_token(test_db, client):
    user, _ = _create_authenticated_user(client, email="unauthorized@example.com")

    response = _delete_user(client, user["id"])
    assert response.status_code == 401


    # 存在しないユーザIDを削除しようとすると404となることを確認
def test_delete_nonexistent_user_returns_not_found(test_db, client):
    _, headers = _create_authenticated_user(client, email="admin@example.com")

    response = _delete_user(client, 9999, headers=headers)
    assert response.status_code == 404
