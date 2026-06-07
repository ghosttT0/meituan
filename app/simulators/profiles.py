from app.domain.simulation import UserProfile

DEFAULT_PROFILES = [
    UserProfile(
        profile_id="cooperative",
        name="配合型",
        cooperation_level=0.9,
        patience_level=0.8,
        preferred_question_sources=["step"],
        max_question_rounds=1,
        max_objection_rounds=0,
    ),
    UserProfile(
        profile_id="hesitant",
        name="犹豫型",
        cooperation_level=0.5,
        patience_level=0.7,
        question_probability=0.6,
        preferred_question_sources=["faq", "step"],
        preferred_question_tags=["risk", "impact", "cost"],
        max_question_rounds=2,
        max_objection_rounds=1,
    ),
    UserProfile(
        profile_id="rejecting",
        name="拒绝型",
        cooperation_level=0.2,
        patience_level=0.4,
        reject_probability=0.8,
        preferred_question_sources=["objection"],
        max_question_rounds=1,
        max_objection_rounds=2,
    ),
    UserProfile(
        profile_id="busy",
        name="忙碌型",
        cooperation_level=0.4,
        patience_level=0.2,
        preferred_question_sources=["objection"],
        preferred_question_tags=["busy", "objection"],
        max_question_rounds=1,
        max_objection_rounds=2,
    ),
    UserProfile(
        profile_id="interrupting",
        name="打断型",
        cooperation_level=0.5,
        patience_level=0.4,
        interruption_probability=0.8,
        preferred_question_sources=["objection", "step"],
        max_interrupt_rounds=2,
    ),
    UserProfile(
        profile_id="questioning",
        name="追问型",
        cooperation_level=0.6,
        patience_level=0.7,
        question_probability=0.9,
        preferred_question_sources=["faq", "step"],
        preferred_question_tags=["difference", "feature", "operation"],
        max_question_rounds=3,
        max_objection_rounds=1,
    ),
] 


def get_profile(profile_id: str) -> UserProfile:
    for profile in DEFAULT_PROFILES:
        if profile.profile_id == profile_id:
            return profile
    raise KeyError(profile_id)
