# Part of the With FBraun project template.
# Author: František Braun <frantisek.braun95@gmail.com>
# Freely available as a template for building custom applications.

"""The local violation score: what it flags, what it must leave alone, and
how the percentages map to levels."""

import pytest

from app.modules.boards.config import ModerationConfig
from app.modules.boards.moderation.assess import level_for
from app.modules.boards.moderation.scorer import MAX_COUNTED, score_violations

CONFIG = ModerationConfig()


def _codes(text):
    return [finding.code for finding in score_violations(text).findings]


def _percent(text):
    return score_violations(text).percent


# --- What must be left alone ----------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Attention is the only thing we spend that we can never earn back.",
        "Pozornost je jediná věc, kterou utrácíme a nikdy nezískáme zpět.",
        "Dnes jsem potkal kamaráda a šli jsme na pivo, pak jsme se bavili o filosofii.",
        "Ahoj, jak se máš? Já se mám dobře!!",
        "Meeting on 2026-10-02 12:00 about 123 456 items, room 101.",
        "Version 3.5.1 was released in 2026; see section 4.2.",
        "Thoughts 💡 on 🔥 everyday things 🎉",
    ],
)
def test_ordinary_text_scores_nothing(text):
    result = score_violations(text)
    assert (result.percent, result.findings) == (0, ())


@pytest.mark.parametrize(
    "text",
    [
        "The class assessment at Scunthorpe was a bass-heavy classic.",
        "Assistant, associate and passage are ordinary words; so are cockpit and shitake.",
        "Hello from Penistone, home of the Dickens society.",
    ],
)
def test_a_bad_word_hidden_inside_a_longer_word_is_not_a_hit(text):
    assert _percent(text) == 0


def test_numbers_are_not_read_as_letters():
    assert _percent("5 4 3 1 0 7 and 5431 07 ok") == 0


# --- Words ----------------------------------------------------------------------


def test_one_profanity_is_a_warning_two_a_risk_four_a_block():
    one = _percent("This is bullshit")
    two = _percent("This is bullshit, damn shit")
    four = _percent("fuck shit bitch asshole")
    assert level_for(one, CONFIG) == "warn"
    assert level_for(two, CONFIG) == "risk"
    assert level_for(four, CONFIG) == "blocked"


def test_czech_profanity_counts_with_or_without_diacritics():
    assert _codes("Ty jsi kokot") == ["profanity"]
    assert _codes("ty jsi zasraný") == ["profanity"]
    assert _codes("TY JSI ZASRANY") != []


@pytest.mark.parametrize("text", ["what the f u c k", "f.u.c.k this", "F  U  C  K"])
def test_letters_spread_apart_are_joined(text):
    assert "profanity" in _codes(text)


@pytest.mark.parametrize("text", ["sh1t happens", "k0kot", "this is sh!t", "bull$hit", "fuuuuuck", "fuuck", "assssshole"])
def test_the_usual_disguises_are_seen_through(text):
    assert "profanity" in _codes(text)


def test_a_disguised_word_counts_once():
    assert score_violations("sh1t").findings[0].weight == pytest.approx(0.35)


def test_repeating_one_word_counts_each_time_but_not_forever():
    def profanity_weight(text):
        return next(f.weight for f in score_violations(text).findings if f.code == "profanity")

    assert profanity_weight("shit shit shit") > profanity_weight("shit")
    assert profanity_weight("shit " * 30) == profanity_weight("shit " * MAX_COUNTED)


def test_insults_are_milder_than_profanity():
    assert _percent("You are an idiot") == 20
    assert level_for(_percent("idiot, moron and imbecile"), CONFIG) == "warn"
    assert level_for(_percent("idiot, moron, imbecile, dumbass and retard"), CONFIG) == "risk"
    assert level_for(_percent("You are an idiot"), CONFIG) == "ok"


def test_a_slur_alone_is_already_a_risk_and_two_are_a_block():
    assert level_for(_percent("you faggot"), CONFIG) == "risk"
    assert level_for(_percent("faggot, nigger"), CONFIG) == "blocked"
    assert _codes("negr") == ["hate"]


@pytest.mark.parametrize("text", ["heil hitler", "White Power!", "Smrt všem muslimům", "death to all jews"])
def test_hate_phrases_count(text):
    assert _codes(text) == ["hate"]


@pytest.mark.parametrize(
    "text",
    [
        "I will kill you tomorrow",
        "i'll murder them",
        "kill yourself",
        "kys",
        "go die",
        "I hope you die",
        "Zabiju tě",
        "zabij se",
        "Zdechni",
    ],
)
def test_threats_block_on_their_own(text):
    result = score_violations(text)
    assert [f.code for f in result.findings] == ["threat"]
    assert level_for(result.percent, CONFIG) == "blocked"


@pytest.mark.parametrize("text", ["I will kill the process", "I will kill time", "kysely is a soup", "Zabiju čas čtením"])
def test_threat_words_in_harmless_use_are_left_alone(text):
    assert _percent(text) == 0


# --- Links, personal data, spam -------------------------------------------------


def test_links_and_scam_phrases_add_up():
    text = "Visit www.cheap-pills.com or buy now, free money bitcoin giveaway https://x.io/abc"
    result = score_violations(text)
    assert {f.code for f in result.findings} == {"spam_links", "spam_phrases"}
    assert level_for(result.percent, CONFIG) == "risk"


def test_one_link_is_a_small_signal():
    assert _percent("See example.com for details") == 20


def test_an_email_is_not_also_counted_as_a_link():
    result = score_violations("Write to john@example.com")
    assert [f.code for f in result.findings] == ["personal_data"]


def test_emails_and_phone_numbers_count_as_personal_data():
    result = score_violations("Call +420 123 456 789 or john@example.com")
    assert [f.code for f in result.findings] == ["personal_data"]
    assert result.percent == 44


def test_a_date_and_a_time_are_not_a_phone_number():
    assert _percent("2026-10-02 12:00 and 2026 10 02 12 00") == 0


# --- Shape of the text ----------------------------------------------------------


def test_shouting_is_a_mild_signal():
    result = score_violations("HELLO EVERYBODY THIS IS A VERY LOUD MESSAGE FOR YOU ALL")
    assert [f.code for f in result.findings] == ["shouting"]
    assert level_for(result.percent, CONFIG) == "ok"


def test_short_capitals_and_a_few_exclamation_marks_are_fine():
    assert _percent("OK, WOW! Great idea!!") == 0
    assert _codes("Why?!?!?! Really!!!!!") == ["shouting"]


def test_repetition_is_seen_by_diversity_runs_and_character_floods():
    assert _codes("a b " * 50) == ["repetition"]
    assert _codes("no no no no no no no") == ["repetition"]
    assert _codes("sooooooooooooooooooo good") == ["repetition"]
    assert _codes("💡" * 40) == ["repetition"]


def test_a_full_post_of_one_emoji_is_still_publishable():
    assert level_for(_percent("💡" * 2048), CONFIG) == "ok"


def test_a_very_long_unbroken_word_is_gibberish():
    word = "abcdefghij" * 3  # 30 letters, no repeated character
    assert _codes(word) == ["gibberish"]
    assert _codes(word[:-1]) == []


def test_findings_come_strongest_first_with_the_authors_own_words_as_matches():
    result = score_violations("You idiot, I will kill you, shit")
    weights = [f.weight for f in result.findings]
    assert weights == sorted(weights, reverse=True)
    assert result.findings[0].code == "threat"
    by_code = {f.code: f for f in result.findings}
    assert by_code["profanity"].matches == ("shit",)
    assert by_code["insult"].matches == ("idiot",)


def test_matches_are_distinct_few_and_short():
    result = score_violations("shit " * 3 + "fuck bitch asshole cunt whore slut")
    matches = result.findings[0].matches
    assert len(matches) == len(set(matches)) <= 5
    assert all(len(match) <= 40 for match in matches)


def test_the_percent_never_passes_100():
    text = "fuck shit nigger kill yourself I will kill you www.a.com buy now casino " * 20
    assert _percent(text) <= 100


def test_scoring_is_deterministic():
    text = "Some text with shit and www.example.com in it"
    assert score_violations(text) == score_violations(text)


# --- Levels ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("percent", "level"),
    [(0, "ok"), (30, "ok"), (31, "warn"), (50, "warn"), (51, "risk"), (75, "risk"), (76, "blocked"), (100, "blocked")],
)
def test_a_percent_must_be_strictly_above_a_threshold(percent, level):
    assert level_for(percent, CONFIG) == level


def test_levels_follow_the_configured_thresholds():
    strict = ModerationConfig(warn_percent=10, risk_percent=20, block_percent=30)
    assert [level_for(p, strict) for p in (10, 11, 21, 31)] == ["ok", "warn", "risk", "blocked"]
