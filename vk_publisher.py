import os
import time
import requests
from datetime import datetime


VK_API_VERSION = "5.131"
VK_API_URL = "https://api.vk.com/method/"


def _api(method: str, params: dict) -> dict:
    token = os.getenv("VK_ACCESS_TOKEN")
    if not token:
        raise ValueError("VK_ACCESS_TOKEN не найден в .env")
    response = requests.post(
        VK_API_URL + method,
        data={**params, "access_token": token, "v": VK_API_VERSION},
        timeout=30,
    )
    data = response.json()
    if "error" in data:
        raise RuntimeError(f"VK API ошибка: {data['error']['error_msg']}")
    return data.get("response", {})


def publish_to_wall(text: str, owner_id: int, publish_at: datetime = None) -> int:
    """
    Публикует пост на стену.
    owner_id > 0 — личная страница пользователя
    owner_id < 0 — группа (передавай со знаком минус: -GROUP_ID)
    publish_at — если указан datetime, пост будет отложен
    Возвращает post_id.
    """
    params = {
        "owner_id": owner_id,
        "message": text,
        "from_group": 1 if owner_id < 0 else 0,
    }
    if publish_at:
        params["publish_date"] = int(publish_at.timestamp())

    result = _api("wall.post", params)
    return result.get("post_id")


def get_user_id() -> int:
    """Возвращает VK ID текущего пользователя."""
    result = _api("users.get", {})
    return result[0]["id"]


def publish_post(text: str, targets: list[str], publish_at: datetime = None) -> dict:
    """
    Публикует пост на выбранные площадки.
    targets: список из "personal" и/или "group"
    Возвращает словарь с результатами по каждой площадке.
    """
    results = {}

    if "personal" in targets:
        user_id = int(os.getenv("VK_USER_ID", "0"))
        if not user_id:
            user_id = get_user_id()
        post_id = publish_to_wall(text, owner_id=user_id, publish_at=publish_at)
        results["personal"] = post_id

    if "group" in targets:
        group_id = int(os.getenv("VK_GROUP_ID", "0"))
        if not group_id:
            raise ValueError("VK_GROUP_ID не найден в .env")
        post_id = publish_to_wall(text, owner_id=-group_id, publish_at=publish_at)
        results["group"] = post_id

    return results
