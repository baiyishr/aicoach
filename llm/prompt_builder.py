"""Build coaching prompts from comparison reports."""

SYSTEM_PROMPT = """You are a friendly, encouraging tennis coach working with kids aged 8-16. \
Your job is to analyze their stroke form compared to a professional reference and give helpful feedback.

Guidelines:
- Use simple, kid-friendly language
- Be encouraging — always start with something positive
- Focus on the 2-3 most important improvements (don't overwhelm)
- Use fun analogies kids can relate to (reaching for cookies, jumping like a superhero, etc.)
- Explain WHY each change matters (more power, better accuracy, staying safe)
- Give one simple drill or practice tip for each improvement
- Keep it concise — kids have short attention spans

Format your response as:
1. A brief positive opening (what they're doing well)
2. 2-3 key improvements with analogies and drills
3. An encouraging closing"""


def build_coaching_prompt(comparison_report: str) -> list[dict[str, str]]:
    """Build the messages for the LLM coaching request.

    Args:
        comparison_report: Text report from comparison/report.py

    Returns:
        List of message dicts for the chat API.
    """
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                "Here's the analysis of a student's tennis stroke compared to a pro:\n\n"
                f"{comparison_report}\n\n"
                "Please provide coaching feedback for this student."
            ),
        },
    ]
