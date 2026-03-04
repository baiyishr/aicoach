"""Tennis stroke definitions — phases and key metrics for each stroke type."""

from sport.base import StrokeDefinition, PhaseDefinition


SERVE = StrokeDefinition(
    name="serve",
    display_name="Serve",
    phases=[
        PhaseDefinition("trophy", "Trophy position — racket arm raised, knees bent"),
        PhaseDefinition("racket_drop", "Racket drop — racket falls behind back"),
        PhaseDefinition("contact", "Contact — ball strike at highest point"),
        PhaseDefinition("follow_through", "Follow-through — arm swings across body"),
    ],
    key_metrics=[
        "right_shoulder", "right_elbow", "right_knee", "left_knee",
        "hip_shoulder_separation",
    ],
)

FOREHAND = StrokeDefinition(
    name="forehand",
    display_name="Forehand",
    phases=[
        PhaseDefinition("ready", "Ready position — split step"),
        PhaseDefinition("backswing", "Backswing — racket taken back"),
        PhaseDefinition("forward_swing", "Forward swing — racket accelerates forward"),
        PhaseDefinition("contact", "Contact — ball strike"),
        PhaseDefinition("follow_through", "Follow-through — racket wraps around"),
    ],
    key_metrics=[
        "right_shoulder", "right_elbow", "right_hip", "left_hip",
        "right_knee", "hip_shoulder_separation",
    ],
)

BACKHAND_1H = StrokeDefinition(
    name="backhand_1h",
    display_name="Backhand (One-Handed)",
    phases=[
        PhaseDefinition("ready", "Ready position"),
        PhaseDefinition("backswing", "Backswing — shoulder turn, single arm back"),
        PhaseDefinition("forward_swing", "Forward swing — arm extends"),
        PhaseDefinition("contact", "Contact — full arm extension"),
        PhaseDefinition("follow_through", "Follow-through"),
    ],
    key_metrics=[
        "right_shoulder", "right_elbow", "right_hip",
        "hip_shoulder_separation",
    ],
)

BACKHAND_2H = StrokeDefinition(
    name="backhand_2h",
    display_name="Backhand (Two-Handed)",
    phases=[
        PhaseDefinition("ready", "Ready position"),
        PhaseDefinition("backswing", "Backswing — both hands, shoulder turn"),
        PhaseDefinition("forward_swing", "Forward swing — both arms drive forward"),
        PhaseDefinition("contact", "Contact — both hands on racket"),
        PhaseDefinition("follow_through", "Follow-through"),
    ],
    key_metrics=[
        "right_shoulder", "left_shoulder", "right_elbow", "left_elbow",
        "right_hip", "hip_shoulder_separation",
    ],
)

VOLLEY = StrokeDefinition(
    name="volley",
    display_name="Volley",
    phases=[
        PhaseDefinition("split_step", "Split step — ready position"),
        PhaseDefinition("racket_prep", "Racket preparation — compact prep"),
        PhaseDefinition("contact", "Contact — punch the ball out front"),
        PhaseDefinition("recovery", "Recovery — return to ready"),
    ],
    key_metrics=[
        "right_shoulder", "right_elbow", "right_knee",
    ],
)

# Registry of all tennis strokes
TENNIS_STROKES: dict[str, StrokeDefinition] = {
    "serve": SERVE,
    "forehand": FOREHAND,
    "backhand_1h": BACKHAND_1H,
    "backhand_2h": BACKHAND_2H,
    "volley": VOLLEY,
}
