from src.page_watch import PageSnapshot, change_notice


def test_same_creator_page_does_not_send_a_notice() -> None:
    old = PageSnapshot.from_content("https://creator.example/posts", "new studio notes")
    current = PageSnapshot.from_content("https://creator.example/posts", "new studio notes")

    assert change_notice(old, current) is None


def test_changed_creator_page_produces_a_reviewable_notice() -> None:
    old = PageSnapshot.from_content("https://creator.example/posts", "episode 12")
    current = PageSnapshot.from_content("https://creator.example/posts", "episode 13")

    notice = change_notice(old, current)

    assert notice is not None
    assert "creator page changed" in notice.lower()
    assert old.digest in notice and current.digest in notice
