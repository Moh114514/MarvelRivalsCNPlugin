import unittest
from unittest.mock import patch

from marvel_rivals_bot.storage.interaction_sessions import InteractionSessionStore
from messaging import OneBotSender, SenderRouter


class FakeEvent:
    def __init__(self, platform="aiocqhttp", group_id=None):
        self.platform = platform
        self.group_id = group_id
        self.chain = None

    def get_platform_name(self):
        return self.platform

    def get_sender_id(self):
        return "42"

    def get_group_id(self):
        return self.group_id

    def chain_result(self, chain):
        self.chain = chain
        return ("chain", chain)

    def image_result(self, image_url):
        return ("image", image_url)


class TestInteractionSessionStore(unittest.TestCase):
    def test_recent_selection_is_scoped_and_expires(self):
        now = [100.0]
        store = InteractionSessionStore(ttl_seconds=300, clock=lambda: now[0])
        store.set_recent("42", "group-a", ["a", "b"])

        self.assertEqual(store.get_recent("42", "group-a").match_uids, ("a", "b"))
        self.assertIsNone(store.get_recent("42", "group-b"))

        now[0] = 400.0
        self.assertIsNone(store.get_recent("42", "group-a"))
        self.assertEqual(store.cleanup(), 0)


class TestOneBotSender(unittest.TestCase):
    def test_group_chain_mentions_sender_before_image(self):
        event = FakeEvent(group_id="group-a")
        with patch.object(
            OneBotSender,
            "_component",
            side_effect=lambda name, **kwargs: {"type": name, **kwargs},
        ):
            result = SenderRouter(OneBotSender()).image_result(event, "https://example.test/a.png")

        self.assertEqual(result[0], "chain")
        self.assertEqual(result[1], [
            {"type": "At", "qq": "42"},
            {"type": "Image", "url": "https://example.test/a.png"},
        ])

    def test_private_chain_contains_only_image(self):
        event = FakeEvent(group_id=None)
        with patch.object(
            OneBotSender,
            "_component",
            side_effect=lambda name, **kwargs: {"type": name, **kwargs},
        ):
            result = OneBotSender.image_result(event, "https://example.test/a.png")

        self.assertEqual(result[0], "chain")
        self.assertEqual(result[1], [{"type": "Image", "url": "https://example.test/a.png"}])


if __name__ == "__main__":
    unittest.main()
