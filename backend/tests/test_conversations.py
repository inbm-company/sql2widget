from app.repositories import conversations as conv_repo


def test_update_and_delete_conversation():
    conv = conv_repo.create_conversation("tenant_demo", "user_admin", "테스트 대화")
    conv_id = conv["id"]

    updated = conv_repo.update_conversation(
        conv_id, "tenant_demo", "user_admin", "이름 변경됨"
    )
    assert updated["title"] == "이름 변경됨"

    assert conv_repo.delete_conversation(conv_id, "tenant_demo", "user_admin") is True
    assert conv_repo.get_conversation(conv_id, "tenant_demo", "user_admin") is None

    assert conv_repo.delete_conversation(conv_id, "tenant_demo", "user_admin") is False
