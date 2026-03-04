"""Generate text comparison reports for LLM consumption."""

from comparison.diff import StrokeDiff
from sport.tennis.strokes import TENNIS_STROKES


JOINT_DISPLAY_NAMES = {
    "right_shoulder": "Shoulder angle",
    "left_shoulder": "Left shoulder angle",
    "right_elbow": "Elbow angle",
    "left_elbow": "Left elbow angle",
    "right_hip": "Hip angle",
    "left_hip": "Left hip angle",
    "right_knee": "Knee bend",
    "left_knee": "Left knee bend",
    "hip_shoulder_separation": "Hip-shoulder separation",
}

PHASE_DISPLAY_NAMES = {
    "trophy": "Trophy Position",
    "racket_drop": "Racket Drop",
    "contact": "Contact",
    "follow_through": "Follow-Through",
    "ready": "Ready Position",
    "backswing": "Backswing",
    "forward_swing": "Forward Swing",
    "split_step": "Split Step",
    "racket_prep": "Racket Preparation",
    "recovery": "Recovery",
}


def generate_report(diff: StrokeDiff) -> str:
    """Generate a structured text report from stroke comparison.

    Args:
        diff: Computed stroke differences.

    Returns:
        Formatted text report for LLM consumption.
    """
    stroke_def = TENNIS_STROKES.get(diff.stroke_type)
    stroke_name = stroke_def.display_name if stroke_def else diff.stroke_type

    lines = [f"Stroke: {stroke_name}", ""]

    for pd in diff.phase_diffs:
        phase_display = PHASE_DISPLAY_NAMES.get(pd.phase_name, pd.phase_name)
        lines.append(f"Phase: {phase_display}")

        if not pd.angle_diffs:
            lines.append("  (no data)")
            lines.append("")
            continue

        for ad in sorted(pd.angle_diffs, key=lambda x: x.abs_diff, reverse=True):
            joint_display = JOINT_DISPLAY_NAMES.get(ad.joint, ad.joint)
            direction = "more" if ad.diff > 0 else "less"
            significance = " ***" if ad.significant else ""
            lines.append(
                f"  - {joint_display}: Student {ad.student_avg:.0f}° vs "
                f"Pro {ad.pro_avg:.0f}° ({ad.abs_diff:.0f}° {direction}){significance}"
            )
        lines.append("")

    # Top issues summary
    top = diff.top_issues
    if top:
        lines.append("Top issues by severity:")
        for i, (phase_name, ad) in enumerate(top, 1):
            phase_display = PHASE_DISPLAY_NAMES.get(phase_name, phase_name)
            joint_display = JOINT_DISPLAY_NAMES.get(ad.joint, ad.joint)
            direction = "more" if ad.diff > 0 else "less"
            lines.append(
                f"  {i}. {joint_display} at {phase_display}: "
                f"{ad.abs_diff:.0f}° {direction} than pro"
            )
    else:
        lines.append("No significant differences detected — great form!")

    return "\n".join(lines)
