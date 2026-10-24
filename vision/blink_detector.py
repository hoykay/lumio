import cv2
import numpy as np
import time
import boto3
aws_session = boto3.Session(
    profile_name="lumio",
    region_name="us-east-1"
)

dynamodb = aws_session.resource("dynamodb")

session_table = dynamodb.Table(
    "lumio-sessions"
)
def log_session_to_aws(
    signal,
    confidence,
    action,
    result
):
    session_id = str(
        int(time.time() * 1000)
    )

    session_table.put_item(
        Item={
            "session_id": session_id,
            "device": "LUMIO TEST ROUTER X1",
            "signal": signal,
            "confidence": str(
                round(confidence, 1)
            ),
            "action": action,
            "result": result
        }
    )

    print(
        f"☁️ AWS session logged: "
        f"{session_id}"
    )
    
from collections import Counter

camera = cv2.VideoCapture(0)

if not camera.isOpened():
    print("❌ Could not open camera.")
    exit()

print("✅ Lumio camera connected")
print("Drag a box around the WAN light.")
print("Press Q to quit.")

window_name = "Lumio Vision Engine v0.7"

roi_box = None
drawing = False
start_x, start_y = 0, 0

stable_state = None
candidate_state = None
candidate_since = None
stable_since = None

blink_count = 0
on_durations = []
short_off_durations = []
cycle_colors = []

last_on_color = "UNKNOWN"
last_confidence = 0
last_led_ratio = 0.0
active_fault = None
healthy_since = None

LONG_PAUSE_THRESHOLD = 1.0
MIN_STABLE_TIME = 0.08

ON_RATIO_THRESHOLD = 0.12
OFF_RATIO_THRESHOLD = 0.05


# -----------------------------------
# Lumio demo device signal profiles
# -----------------------------------

SIGNAL_PROFILES = [
    {
        "name": "WAN FAILURE",
        "color": "AMBER",
        "blinks": 3,
        "on": 0.42,
        "short_off": 0.18,
        "pause": 1.80,
        "diagnosis": "WAN connection unavailable",
        "action": "Check the WAN cable connection."
    },
    {
        "name": "CONFIG ERROR",
        "color": "RED",
        "blinks": 2,
        "on": 0.35,
        "short_off": 0.25,
        "pause": 2.00,
        "diagnosis": "Device configuration error",
        "action": "Review the device configuration."
    }
]


def get_led_mask(hsv_roi):

    saturation = hsv_roi[:, :, 1]
    value = hsv_roi[:, :, 2]

    return (
        (saturation > 90)
        & (value > 100)
    )


def detect_color(hsv_roi, led_mask):

    if np.count_nonzero(led_mask) < 10:
        return "UNKNOWN"

    hue_values = hsv_roi[:, :, 0][led_mask]
    hue = np.median(hue_values)

    if hue < 8 or hue > 172:
        return "RED"

    elif 8 <= hue < 25:
        return "AMBER"

    elif 25 <= hue < 85:
        return "GREEN"

    elif 125 <= hue < 165:
        return "PURPLE"

    return "UNKNOWN"


def dominant_color(colors):

    valid = [
        color
        for color in colors
        if color != "UNKNOWN"
    ]

    if not valid:
        return "UNKNOWN"

    return Counter(valid).most_common(1)[0][0]


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
    avg_short_off,
    long_pause
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
            ) / 3
        )
    )

    on_score = similarity(
        avg_on,
        profile["on"],
        0.30
    )

    off_score = similarity(
        avg_short_off,
        profile["short_off"],
        0.20
    )

    pause_score = similarity(
        long_pause,
        profile["pause"],
        0.80
    )

    confidence = (
        color_score * 0.25
        + blink_score * 0.30
        + on_score * 0.20
        + off_score * 0.10
        + pause_score * 0.15
    )

    return confidence * 100


def find_best_profile(
    color,
    blinks,
    avg_on,
    avg_short_off,
    long_pause
):

    results = []

    for profile in SIGNAL_PROFILES:

        confidence = profile_confidence(
            profile,
            color,
            blinks,
            avg_on,
            avg_short_off,
            long_pause
        )

        results.append(
            (confidence, profile)
        )

    results.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return results[0] 

def get_reobservation_guidance(
    confidence,
    led_ratio,
    blinks
):

    # If Lumio captured a complete multi-blink pattern,
    # do not keep asking the user to move the camera.
    # A clear but unsupported signal should be escalated.
    if blinks >= 3:
        return None

    if blinks < 2:
        return "Keep the camera steady and observe one more full blink cycle."

    if led_ratio < 0.03:
        return "Move closer so the indicator fills more of the box."

    if confidence < 70:
        return "Reposition the camera and capture the signal again before diagnosing."

    return None

    if led_ratio < 0.03:
        return "Move closer so the indicator fills more of the box."

    if blinks < 2:
        return "Keep the camera steady and observe one more full blink cycle."

    if confidence < 70:
        return "Reposition the camera and capture the signal again before diagnosing."

    return None

    results.sort(
        key=lambda item: item[0],
        reverse=True
    )

    return results[0]


def reset_cycle():

    global blink_count
    global on_durations
    global short_off_durations
    global cycle_colors

    blink_count = 0
    on_durations = []
    short_off_durations = []
    cycle_colors = []


def decode_pattern(long_pause):

    global active_fault
    global last_confidence

    color = dominant_color(
        cycle_colors
    )

    if blink_count == 0:
        return

    avg_on = (
        np.mean(on_durations)
        if on_durations
        else 0
    )

    avg_short_off = (
        np.mean(short_off_durations)
        if short_off_durations
        else 0
    )

    confidence, profile = find_best_profile(
        color,
        blink_count,
        avg_on,
        avg_short_off,
        long_pause
    )

    last_confidence = confidence

    print("\n----------------------------")
    print("🔎 PATTERN DETECTED")
    print("----------------------------")

    print(f"Color: {color}")
    print(f"Blinks: {blink_count}")
    print(f"Long pause: {long_pause:.2f}s")
    print(f"Average ON: {avg_on:.2f}s")
    print(
        f"Average short OFF: "
        f"{avg_short_off:.2f}s"
    )

    print()
    print(
        f"Best match confidence: "
        f"{confidence:.1f}%"
    )

    exact_profile_match = (
        color == profile["color"]
        and blink_count == profile["blinks"]
    )

    if confidence >= 70 and exact_profile_match:

        active_fault = profile["name"]

        print()
        print(
            f"⚠️ {profile['name']} DETECTED"
        )

        print(
            f"Diagnosis: "
            f"{profile['diagnosis']}"
        )

        print(
            f"Recommended action: "
            f"{profile['action']}"
        )

    else:

        guidance = get_reobservation_guidance(
            confidence,
            last_led_ratio,
            blink_count
        )

        print()
        print("❓ UNKNOWN SIGNAL")

        print(
            "Lumio cannot safely match "
            "this pattern to a known profile."
        )

        if guidance:
            print(
                f"Re-observation guidance: "
                f"{guidance}"
            )
        else:
            print(
                "Action: save evidence or "
                "request human review."
            )

    print("----------------------------\n")

    reset_cycle()


def mouse_callback(
    event,
    x,
    y,
    flags,
    param
):

    global drawing
    global start_x
    global start_y
    global roi_box

    global stable_state
    global candidate_state
    global candidate_since
    global stable_since

    if event == cv2.EVENT_LBUTTONDOWN:

        drawing = True
        start_x, start_y = x, y

    elif event == cv2.EVENT_LBUTTONUP:

        drawing = False

        x1 = min(start_x, x)
        y1 = min(start_y, y)

        x2 = max(start_x, x)
        y2 = max(start_y, y)

        if (
            x2 - x1 > 10
            and y2 - y1 > 10
        ):

            roi_box = (
                x1,
                y1,
                x2 - x1,
                y2 - y1
            )

            stable_state = None
            candidate_state = None
            candidate_since = None
            stable_since = None

            reset_cycle()

            print()
            print("✅ WAN light selected")
            print("Watching signal...")


cv2.namedWindow(window_name)

cv2.setMouseCallback(
    window_name,
    mouse_callback
)


while True:

    success, frame = camera.read()

    if not success:

        print(
            "❌ Could not read camera frame."
        )

        break

    display = frame.copy()

    if roi_box is not None:

        x, y, w, h = roi_box

        roi = frame[
            y:y + h,
            x:x + w
        ]

        if roi.size > 0:

            hsv = cv2.cvtColor(
                roi,
                cv2.COLOR_BGR2HSV
            )

            led_mask = get_led_mask(
                hsv
            )

            led_ratio = (
                np.count_nonzero(
                    led_mask
                )
                / led_mask.size
            )

            now = time.time()

            if stable_state is None:

                raw_state = (
                    "ON"
                    if led_ratio
                    >= ON_RATIO_THRESHOLD
                    else "OFF"
                )

            elif (
                led_ratio
                >= ON_RATIO_THRESHOLD
            ):

                raw_state = "ON"

            elif (
                led_ratio
                <= OFF_RATIO_THRESHOLD
            ):

                raw_state = "OFF"

            else:

                raw_state = stable_state

            if (
                raw_state
                != candidate_state
            ):

                candidate_state = raw_state
                candidate_since = now

            if (
                raw_state != stable_state
                and candidate_since is not None
                and now - candidate_since
                >= MIN_STABLE_TIME
            ):

                new_state = raw_state

                if stable_state is not None:

                    duration = (
                        now - stable_since
                    )

                    print(
                        f"{stable_state:3} "
                        f"for {duration:.2f}s"
                    )

                    if stable_state == "ON":
                        global_healthy_color = last_on_color

                        last_led_ratio = led_ratio

                        if (
                            last_on_color == "GREEN"
                            and duration >= 1.5
                        ):
                            reset_cycle()

                        else:
                            blink_count += 1

                            on_durations.append(
                                duration
                            )

                            cycle_colors.append(
                                last_on_color
                            )

                    elif stable_state == "OFF":

                        if (
                            duration
                            >= LONG_PAUSE_THRESHOLD
                        ):

                            decode_pattern(
                                duration
                            )

                        else:

                            short_off_durations.append(
                                duration
                            )

                stable_state = new_state
                stable_since = now

            if stable_state == "ON":

                detected_color = detect_color(
                    hsv,
                    led_mask
                )

                if (
                    detected_color
                    != "UNKNOWN"
                ):

                    last_on_color = (
                        detected_color
                    )

                display_color = (
                    last_on_color
                )

                if (
                    active_fault is not None
                    and last_on_color == "GREEN"
                ):

                    if healthy_since is None:
                        healthy_since = now

                    elif now - healthy_since >= 1.5:

                        print()
                        print("✅ RECOVERY VERIFIED")
                        print(
                            f"{active_fault} cleared — "
                            "indicator is now solid GREEN."
                        )
                        print()
                        log_session_to_aws(
                            signal=active_fault,
                            confidence=last_confidence,
                            action="User performed recommended intervention",
                            result="RECOVERY_VERIFIED"
                        )
                        active_fault = None
                        healthy_since = None
                        reset_cycle()
                        
                else:
                    healthy_since = None
                    
            else:

                display_color = "-"

            state_text = (
                stable_state
                if stable_state is not None
                else "WAIT"
            )

            box_color = (
                (0, 255, 0)
                if stable_state == "ON"
                else (150, 150, 150)
            )

            cv2.rectangle(
                display,
                (x, y),
                (x + w, y + h),
                box_color,
                2
            )

            cv2.putText(
                display,
                f"{state_text} | "
                f"{display_color}",
                (
                    x,
                    max(y - 10, 25)
                ),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                box_color,
                2
            )

            cv2.putText(
                display,
                (
                    f"LED pixels: "
                    f"{led_ratio * 100:.1f}%"
                ),
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 255),
                2
            )

            if last_confidence > 0:

                cv2.putText(
                    display,
                    (
                        f"Confidence: "
                        f"{last_confidence:.1f}%"
                    ),
                    (20, 75),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (255, 255, 255),
                    2
                )

    else:

        cv2.putText(
            display,
            "Drag a box around the WAN light",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

    cv2.imshow(
        window_name,
        display
    )

    if (
        cv2.waitKey(1) & 0xFF
        == ord("q")
    ):

        break


camera.release()
cv2.destroyAllWindows()

print("\nLumio stopped.")