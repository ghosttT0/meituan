from app.simulators.reply_analyzer import RuleBasedReplyAnalyzer


def test_reply_analyzer_marks_reason_explained() -> None:
    signal = RuleBasedReplyAnalyzer().analyze("来电是为了确认收货时间，所以想确认您明天下午是否在家。")

    assert signal.explained_reason is True


def test_reply_analyzer_marks_forbidden_promise() -> None:
    signal = RuleBasedReplyAnalyzer().analyze("您放心，一定送达。")

    assert signal.triggered_forbidden_action is True
