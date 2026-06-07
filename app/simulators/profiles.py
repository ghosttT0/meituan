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
        persona_note="性格随和，愿意配合完成任务，不会主动刁难，偶尔会确认细节。",
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
        persona_note="对新事物持观望态度，担心费用增加或操作复杂，需要对方解释清楚才肯答应。",
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
        persona_note="态度强硬，不想被打扰，倾向于直接拒绝或质疑来电目的。",
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
        persona_note="正在处理其他事务，耐心极低，希望对方30秒内说完重点，否则直接挂断。",
    ),
    UserProfile(
        profile_id="interrupting",
        name="打断型",
        cooperation_level=0.5,
        patience_level=0.4,
        interruption_probability=0.8,
        preferred_question_sources=["objection", "step"],
        max_interrupt_rounds=2,
        persona_note="习惯打断对方，思维跳跃，会在对方说到一半时插话或转移话题。",
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
        persona_note="对细节很在意，会连续追问差异、操作步骤和注意事项，直到满意为止。",
    ),
    UserProfile(
        profile_id="uninformed",
        name="信息不对称型",
        cooperation_level=0.7,
        patience_level=0.6,
        question_probability=0.7,
        preferred_question_sources=["faq", "step"],
        preferred_question_tags=["operation", "visibility", "difference"],
        max_question_rounds=3,
        max_objection_rounds=0,
        persona_note="记不清自己是否已签约或做过相关操作，需要对方先确认基本情况再推进，容易因信息不对称产生困惑。",
        style_prompt='表现出不确定和疑惑，常说"我不太清楚""你说的这个我没印象""我当时好像没操作"等。',
    ),
]


def get_profile(profile_id: str) -> UserProfile:
    for profile in DEFAULT_PROFILES:
        if profile.profile_id == profile_id:
            return profile
    raise KeyError(profile_id)
