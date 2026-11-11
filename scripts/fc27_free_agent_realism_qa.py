"""Fast deterministic regression for FC27 free-agent sporting discretion.

No live saves, external APIs or league hard bans. The full player/club
integration remains covered by the disposable FC27 Career Desk tests.
"""
from world_fc27_player_review import free_agent_wait_probability


def main():
    def risk(overall=83, club_appeal=43, wage_ratio=1.0,
             role="key_player", age=27):
        return free_agent_wait_probability(
            overall=overall, club_appeal=club_appeal,
            wage_ratio=wage_ratio, role=role, age=age)

    weak=risk()
    better=risk(club_appeal=77)
    premium=risk(wage_ratio=2.0)
    age_discount=risk(age=35)
    youngster=risk(overall=72)
    assert .50 < weak < .83, ("elite free agent should usually hold out", weak)
    assert better < weak, (better, weak)
    assert premium < weak, (premium, weak)
    assert age_discount < weak, (age_discount, weak)
    assert youngster < weak, (youngster, weak)
    assert 0.0 < weak < 1.0, "no deterministic rated-player prohibition"
    assert risk()==weak, "same facts must give same probability"
    print("FC27 free-agent outside-option risk QA passed",{
        "weak_club_83":round(weak,3),
        "strong_club_83":round(better,3),
        "premium_wage_83":round(premium,3),
        "older_free_agent_83":round(age_discount,3),
        "weaker_player_72":round(youngster,3)})


if __name__=="__main__":
    main()
