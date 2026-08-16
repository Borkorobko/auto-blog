from pathlib import Path

TARGET_HREF = "leg-workout-for-football.html"

RULES = {
    "posts/football-fitness-training.html": {
        "anchor": '<p>Train strength 2-3 times per week on non-consecutive days. Stop and reduce load if sharp or persistent joint or muscle pain arises, and seek advice if problems continue.</p>',
        "insert": '<p>For a dedicated lower-body session with sets, reps and progression, use our <a href="leg-workout-for-football.html">leg workout for football players</a>.</p>',
    },
    "posts/gym-workout-for-football-players.html": {
        "anchor": '<p>This guide offers practical advice focused on strength and power development, providing clear exercises, training tips, and progression ideas suited for players seeking safe and effective gym work to complement their football training.</p>',
        "insert": '<p>If your priority is lower-body strength, pair this gym guide with our <a href="leg-workout-for-football.html">lower body workout for football players</a>, which focuses on football-specific leg exercises, sets and reps.</p>',
    },
    "posts/strength-training-for-football.html": {
        "anchor": '<p>The foundation for a football strength program is exercises that build functional power and stability. Below are suggested exercises, grouped by movement types, with notes on sets, reps, and progression for beginners to intermediates.</p>',
        "insert": '<p>For a more focused lower-body plan, see our <a href="leg-workout-for-football.html">leg workout for football players</a> with practical squats, lunges, jumps, sprint work and weekly progression.</p>',
    },
    "posts/explosive-training-football.html": {
        "anchor": '<p>This kind of training focuses on fast, forceful contractions of muscles, encouraging the development of fast-twitch muscle fibers which are essential for short bursts of speed and power rather than endurance.</p>',
        "insert": '<p>Explosive work is easier to build on top of a solid strength base, so players can also use our <a href="leg-workout-for-football.html">leg workout for football players</a> for lower-body strength and power work.</p>',
    },
    "posts/football-workout.html": {
        "anchor": '<p>A well-rounded football workout focusing on speed and conditioning should emphasize the following elements:</p>',
        "insert": '<p>For the strength part of that plan, our <a href="leg-workout-for-football.html">lower body workout for football players</a> gives a dedicated football leg session with sets, reps and progression.</p>',
    },
}


def add_link(path_str: str, anchor: str, insert: str) -> str:
    path = Path(path_str)
    if not path.exists():
        return f"SKIP missing: {path_str}"

    text = path.read_text(encoding="utf-8")
    if TARGET_HREF in text:
        return f"OK already linked: {path_str}"

    if anchor not in text:
        return f"WARN anchor not found: {path_str}"

    text = text.replace(anchor, anchor + "\n" + insert, 1)
    path.write_text(text, encoding="utf-8")
    return f"LINKED: {path_str}"


def main() -> None:
    changed = 0
    for path_str, rule in RULES.items():
        result = add_link(path_str, rule["anchor"], rule["insert"])
        print(result)
        if result.startswith("LINKED:"):
            changed += 1

    print(f"Contextual internal links added: {changed}")


if __name__ == "__main__":
    main()
