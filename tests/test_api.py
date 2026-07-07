async def test_auth_check_rejects_missing_password(client):
    del client.headers["X-App-Password"]
    response = await client.get("/auth/check")
    assert response.status_code == 401


async def test_auth_check_rejects_wrong_password(client):
    client.headers["X-App-Password"] = "wrong-password"
    response = await client.get("/auth/check")
    assert response.status_code == 401


async def test_auth_check_accepts_correct_password(client):
    response = await client.get("/auth/check")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


async def test_create_meme_returns_201(client):
    files = {"image": ("doge.png", b"fake-bytes", "image/png")}
    data = {"category": "reaction", "sourceUrl": "https://example.com"}
    response = await client.post("/memes", files=files, data=data)
    assert response.status_code == 201
    body = response.json()
    assert "id" in body
    assert body["blobUrl"].endswith(".png")


async def test_create_meme_rejects_invalid_category(client):
    files = {"image": ("doge.png", b"fake-bytes", "image/png")}
    response = await client.post("/memes", files=files, data={"category": "not-a-real-category"})
    assert response.status_code == 400


async def test_create_meme_rejects_duplicate_image(client):
    data = {"category": "reaction"}
    first = await client.post("/memes", files={"image": ("a.png", b"same-bytes", "image/png")}, data=data)
    assert first.status_code == 201

    second = await client.post("/memes", files={"image": ("b.png", b"same-bytes", "image/png")}, data=data)
    assert second.status_code == 409
    assert second.json()["detail"]["id"] == first.json()["id"]


async def test_get_meme_not_found(client):
    response = await client.get("/memes/does-not-exist")
    assert response.status_code == 404


async def test_meme_get_list_update_delete_roundtrip(client):
    files = {"image": ("doge.png", b"roundtrip-bytes", "image/png")}
    created = await client.post("/memes", files=files, data={"category": "reaction"})
    meme_id = created.json()["id"]

    get_response = await client.get(f"/memes/{meme_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == meme_id

    list_response = await client.get("/memes", params={"category": "reaction"})
    assert list_response.status_code == 200
    assert any(m["id"] == meme_id for m in list_response.json())

    patch_response = await client.patch(f"/memes/{meme_id}", json={"caption": "updated caption"})
    assert patch_response.status_code == 200
    assert patch_response.json()["caption"] == "updated caption"

    delete_response = await client.delete(f"/memes/{meme_id}")
    assert delete_response.status_code == 204

    missing_response = await client.get(f"/memes/{meme_id}")
    assert missing_response.status_code == 404


async def test_search_text_returns_list(client):
    response = await client.post("/search/text", json={"query": "dog meme", "topK": 5})
    assert response.status_code == 200
    assert response.json() == []
