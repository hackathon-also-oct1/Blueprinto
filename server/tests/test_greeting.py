"""When the presenter says its opening line.

The line is spoken exactly once per session: when the client shows the presenter's
video, right away when there is no video to wait for, or after a fallback when a
client never reports its video.
"""

import asyncio

from blueprint.conversation import WELCOME, Greeter


class Voice:
    """Counts how often the opener is said."""

    def __init__(self):
        self.said = 0

    async def speak(self):
        self.said += 1


def test_opening_line_introduces_nuno_and_asks_the_first_question():
    assert WELCOME == "Hi, I'm Nuno. What kind of website are you thinking about?"


async def test_voice_only_server_greets_as_soon_as_the_client_is_ready():
    voice = Voice()
    g = Greeter(voice.speak, wait_for_video=False)
    await g.client_ready()
    assert voice.said == 1


async def test_with_video_the_greeting_waits_for_the_video_to_show():
    voice = Voice()
    g = Greeter(voice.speak, wait_for_video=True, fallback_secs=60)
    await g.client_ready()
    assert voice.said == 0, "spoke before the visitor could see the presenter"
    await g.presenter_ready()
    assert voice.said == 1
    g.cancel()


async def test_the_greeting_is_said_once_even_if_the_video_reports_twice():
    voice = Voice()
    g = Greeter(voice.speak, wait_for_video=True, fallback_secs=60)
    await g.client_ready()
    await g.presenter_ready()
    await g.presenter_ready()
    await g.client_ready()
    assert voice.said == 1
    g.cancel()


async def test_video_showing_before_the_handshake_greets_at_client_ready():
    voice = Voice()
    g = Greeter(voice.speak, wait_for_video=True, fallback_secs=60)
    await g.presenter_ready()
    assert voice.said == 0, "spoke before the client could take the bot's output"
    await g.client_ready()
    assert voice.said == 1


async def test_avatar_failure_means_voice_greets_without_waiting():
    voice = Voice()
    g = Greeter(voice.speak, wait_for_video=True, fallback_secs=60)
    await g.client_ready()
    await g.avatar_unavailable("concurrent_session_limit")
    assert voice.said == 1
    g.cancel()


async def test_avatar_failure_before_the_handshake_greets_at_client_ready():
    voice = Voice()
    g = Greeter(voice.speak, wait_for_video=True, fallback_secs=60)
    await g.avatar_unavailable("connect failed")
    assert voice.said == 0
    await g.client_ready()
    assert voice.said == 1


async def test_a_client_that_never_reports_its_video_is_greeted_after_the_fallback():
    voice = Voice()
    g = Greeter(voice.speak, wait_for_video=True, fallback_secs=0.05)
    await g.client_ready()
    assert voice.said == 0
    await asyncio.sleep(0.2)
    assert voice.said == 1
    # A late video report does not repeat it.
    await g.presenter_ready()
    assert voice.said == 1


async def test_cancel_stops_the_fallback_when_the_client_leaves():
    voice = Voice()
    g = Greeter(voice.speak, wait_for_video=True, fallback_secs=0.05)
    await g.client_ready()
    g.cancel()
    await asyncio.sleep(0.2)
    assert voice.said == 0
