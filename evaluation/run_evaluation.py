import csv
import random
from pathlib import Path


random.seed(42)


PROFILES = {
    "WAN_FAILURE": {
        "color": "AMBER",
        "blinks": 3,
        "on": 0.42,
        "off": 0.18,
        "pause": 1.80,
    },
    "CONFIG_ERROR": {
        "color": "RED",
        "blinks": 2,
        "on": 0.35,
        "off": 0.25,
        "pause": 2.00,
    },
}


def similarity(actual, expected, tolerance):
    difference = abs(actual - expected)

    score = 1 - (
        difference / tolerance
    )

    return max(
        0,
        min(1, score)
    )


def profile_confidence(
    profile,
    color,
    blinks,
    avg_on,
    avg_off,
    pause,
):
    color_score = (
        1.0
        if color == profile["color"]
        else 0.0
    )

    blink_score = (
        1.0
        if blinks == profile["blinks"]
        else max(
            0,
            1 - abs(
                blinks - profile["blinks"]
            ) / 3,
        )
    )

    on_score = similarity(
        avg_on,
        profile["on"],
        0.30,
    )

    off_score = similarity(
        avg_off,
        profile["off"],
        0.20,
    )

    pause_score = similarity(
        pause,
        profile["pause"],
        0.80,
    )

    confidence = (
        color_score * 0.25
        + blink_score * 0.30
        + on_score * 0.20
        + off_score * 0.10
        + pause_score * 0.15
    )

    return confidence * 100


def nearest_profile(sample):
    scores = []

    for name, profile in PROFILES.items():
        confidence = profile_confidence(
            profile,
            sample["color"],
            sample["blinks"],
            sample["on"],
            sample["off"],
            sample["pause"],
        )

        scores.append(
            (confidence, name)
        )

    scores.sort(
        reverse=True
    )

    return scores[0]


def baseline_predict(sample):
    """
    Fixed baseline:
    always chooses the nearest known profile.

    It has no abstention and no
    re-observation behavior.
    """

    confidence, name = nearest_profile(
        sample
    )

    return {
        "prediction": name,
        "confidence": confidence,
        "action": "DIAGNOSE",
    }


def lumio_predict(sample):
    """
    Lumio adaptive behavior:
    - incomplete capture -> re-observe
    - exact grounded match + confidence -> diagnose
    - otherwise -> abstain / human review
    """

    confidence, name = nearest_profile(
        sample
    )

    profile = PROFILES[name]

    exact_profile_match = (
        sample["color"]
        == profile["color"]
        and sample["blinks"]
        == profile["blinks"]
    )

    if sample["blinks"] < 2:
        return {
            "prediction": "REOBSERVE",
            "confidence": confidence,
            "action": "REOBSERVE",
        }

    if (
        confidence >= 70
        and exact_profile_match
    ):
        return {
            "prediction": name,
            "confidence": confidence,
            "action": "DIAGNOSE",
        }

    return {
        "prediction": "UNKNOWN",
        "confidence": confidence,
        "action": "HUMAN_REVIEW",
    }


def jitter(value, amount):
    return max(
        0.01,
        value
        + random.uniform(
            -amount,
            amount,
        ),
    )


def generate_known_samples(
    label,
    profile,
    count=40,
):
    samples = []

    for _ in range(count):
        condition = random.choice(
            [
                "clean",
                "timing_noise",
                "large_timing_noise",
                "partial_capture",
            ]
        )

        color = profile["color"]
        blinks = profile["blinks"]

        on_noise = 0.04
        off_noise = 0.04
        pause_noise = 0.15

        if condition == "timing_noise":
            on_noise = 0.08
            off_noise = 0.07
            pause_noise = 0.30

        elif condition == "large_timing_noise":
            on_noise = 0.14
            off_noise = 0.10
            pause_noise = 0.50

        elif condition == "partial_capture":
            blinks = max(
                1,
                profile["blinks"] - 1,
            )

        samples.append(
            {
                "truth": label,
                "condition": condition,
                "color": color,
                "blinks": blinks,
                "on": jitter(
                    profile["on"],
                    on_noise,
                ),
                "off": jitter(
                    profile["off"],
                    off_noise,
                ),
                "pause": jitter(
                    profile["pause"],
                    pause_noise,
                ),
            }
        )

    return samples


def generate_unknown_samples(
    count=40,
):
    samples = []

    colors = [
        "PURPLE",
        "GREEN",
        "BLUE",
    ]

    for _ in range(count):
        samples.append(
            {
                "truth": "UNKNOWN",
                "condition": "unsupported_pattern",
                "color": random.choice(
                    colors
                ),
                "blinks": random.choice(
                    [3, 4, 5]
                ),
                "on": random.uniform(
                    0.20,
                    0.60,
                ),
                "off": random.uniform(
                    0.12,
                    0.40,
                ),
                "pause": random.uniform(
                    1.1,
                    2.5,
                ),
            }
        )

    return samples


samples = []

for label, profile in PROFILES.items():
    samples.extend(
        generate_known_samples(
            label,
            profile,
        )
    )

samples.extend(
    generate_unknown_samples()
)


rows = []

baseline_correct = 0
lumio_correct = 0

baseline_unsafe_unknown = 0
lumio_unsafe_unknown = 0

lumio_reobserve = 0
lumio_human_review = 0


for index, sample in enumerate(
    samples,
    start=1,
):
    baseline = baseline_predict(
        sample
    )

    lumio = lumio_predict(
        sample
    )

    truth = sample["truth"]

    baseline_is_correct = (
        baseline["prediction"]
        == truth
    )

    if truth == "UNKNOWN":
        lumio_is_correct = (
            lumio["prediction"]
            in [
                "UNKNOWN",
                "REOBSERVE",
            ]
        )
    else:
        lumio_is_correct = (
            lumio["prediction"]
            == truth
            or lumio["prediction"]
            == "REOBSERVE"
        )

    if baseline_is_correct:
        baseline_correct += 1

    if lumio_is_correct:
        lumio_correct += 1

    if truth == "UNKNOWN":
        if (
            baseline["prediction"]
            != "UNKNOWN"
        ):
            baseline_unsafe_unknown += 1

        if (
            lumio["prediction"]
            not in [
                "UNKNOWN",
                "REOBSERVE",
            ]
        ):
            lumio_unsafe_unknown += 1

    if (
        lumio["action"]
        == "REOBSERVE"
    ):
        lumio_reobserve += 1

    if (
        lumio["action"]
        == "HUMAN_REVIEW"
    ):
        lumio_human_review += 1

    rows.append(
        {
            "sample": index,
            "truth": truth,
            "condition": sample[
                "condition"
            ],
            "color": sample["color"],
            "blinks": sample["blinks"],
            "on_seconds": round(
                sample["on"],
                3,
            ),
            "off_seconds": round(
                sample["off"],
                3,
            ),
            "pause_seconds": round(
                sample["pause"],
                3,
            ),
            "baseline_prediction":
                baseline[
                    "prediction"
                ],
            "baseline_confidence":
                round(
                    baseline[
                        "confidence"
                    ],
                    1,
                ),
            "lumio_prediction":
                lumio[
                    "prediction"
                ],
            "lumio_confidence":
                round(
                    lumio[
                        "confidence"
                    ],
                    1,
                ),
            "lumio_action":
                lumio["action"],
        }
    )


output_dir = Path(
    __file__
).parent

csv_path = (
    output_dir
    / "evaluation_results.csv"
)

with open(
    csv_path,
    "w",
    newline="",
) as file:
    writer = csv.DictWriter(
        file,
        fieldnames=rows[0].keys(),
    )

    writer.writeheader()
    writer.writerows(rows)


total = len(samples)

unknown_total = sum(
    1
    for sample in samples
    if sample["truth"] == "UNKNOWN"
)


baseline_accuracy = (
    baseline_correct
    / total
    * 100
)

lumio_safe_accuracy = (
    lumio_correct
    / total
    * 100
)

baseline_unknown_fp = (
    baseline_unsafe_unknown
    / unknown_total
    * 100
)

lumio_unknown_fp = (
    lumio_unsafe_unknown
    / unknown_total
    * 100
)


print()
print(
    "================================"
)
print(
    "LUMIO CONTROLLED EVALUATION"
)
print(
    "================================"
)

print(
    f"Total simulated observations: "
    f"{total}"
)

print()

print(
    "Fixed baseline accuracy: "
    f"{baseline_accuracy:.1f}%"
)

print(
    "Lumio safe decision rate: "
    f"{lumio_safe_accuracy:.1f}%"
)

print()

print(
    "Unsafe diagnosis rate "
    "on unknown patterns:"
)

print(
    f"  Fixed baseline: "
    f"{baseline_unknown_fp:.1f}%"
)

print(
    f"  Lumio: "
    f"{lumio_unknown_fp:.1f}%"
)

print()

print(
    "Lumio autonomous behaviors:"
)

print(
    f"  Re-observation requests: "
    f"{lumio_reobserve}"
)

print(
    f"  Human-review escalations: "
    f"{lumio_human_review}"
)

print()

print(
    "Results saved to:"
)

print(
    csv_path
)

print(
    "================================"
)