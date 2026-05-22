from app.domain.simulation import UserIntent, UserProfile
from app.simulators.response_generator import TemplateFirstResponseGenerator


def test_response_generator_emits_busy_phrase() -> None:
    generator = TemplateFirstResponseGenerator()
    profile = UserProfile(profile_id="busy", name="忙碌型", cooperation_level=0.4, patience_level=0.2)

    reply = generator.render(UserIntent(action="say_busy", state="busy"), profile)

    assert "忙" in reply or "稍后" in reply


def test_response_generator_emits_question_phrase() -> None:
    generator = TemplateFirstResponseGenerator()
    profile = UserProfile(profile_id="questioning", name="追问型", cooperation_level=0.6, patience_level=0.7)

    reply = generator.render(UserIntent(action="ask_why", state="questioning"), profile)

    assert "为什么" in reply or "啥意思" in reply
