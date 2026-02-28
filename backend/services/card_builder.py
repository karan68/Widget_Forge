import json
from datetime import datetime, timezone
from backend.services.llm_service import generate_completion

async def generate_card(intent: dict, data: dict) -> dict:
    """Generate an Adaptive Card JSON from intent and data."""
    with open("backend/prompts/card_generator.txt") as f:
        system_prompt = f.read()

    user_message = (
        f"Widget Intent:\n{json.dumps(intent, indent=2)}\n\n"
        f"Live Data:\n{json.dumps(data, indent=2)}\n\n"
        f"Current time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}\n\n"
        f"Generate the Adaptive Card JSON for this widget."
    )

    content = await generate_completion(system_prompt, user_message, expect_json=True)
    
    # Parse JSON from response
    try:
        card = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON from response if it has extra text
        import re
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            card = json.loads(json_match.group())
        else:
            raise ValueError(f"Failed to parse JSON from LLM response: {content[:500]}")

    # Validate basic structure
    assert card.get("type") == "AdaptiveCard", "LLM did not generate a valid AdaptiveCard"
    assert "body" in card, "AdaptiveCard missing body"

    return card
