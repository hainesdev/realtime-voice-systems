"""Generic interview scenarios for the SIP/Realtime practice lab."""

from dataclasses import dataclass


@dataclass
class InterviewScenario:
    slug: str
    label: str
    interviewer_name: str
    interviewer_title: str
    company: str
    voice: str
    evaluation_areas: list[str]


DIFFICULTY_GUIDANCE = {
    "warm": "Be warm and encouraging while asking clear, practical questions.",
    "normal": "Conduct a realistic, concise interview and probe vague answers.",
    "executive": "Be time-conscious and ask direct follow-up questions about impact and tradeoffs.",
}


INTERVIEWS = {
    "operations_leader": InterviewScenario(
        slug="operations_leader",
        label="Operations Leader Mock Interview",
        interviewer_name="Alex Morgan",
        interviewer_title="VP of Operations",
        company="Northstar Services",
        voice="ash",
        evaluation_areas=[
            "Business impact and operational judgment",
            "Clear communication with technical and non-technical stakeholders",
            "Process improvement, data quality, and responsible AI adoption",
        ],
    )
}


def interview_prompt_for(slug: str, difficulty: str = "normal") -> str:
    scenario = get_interview(slug)
    areas = "\n".join(f"- {area}" for area in scenario.evaluation_areas)
    return f"""You are simulating {scenario.interviewer_name}, {scenario.interviewer_title}
at {scenario.company}, for a fictional interview-practice exercise.

This is a live voice conversation. Speak naturally, keep turns concise, and
ask one question at a time. Do not claim private knowledge of a real person or
organization. If asked whether you are real, say you are an AI practice
simulation.

Focus on these evaluation areas:
{areas}

Interview style: {DIFFICULTY_GUIDANCE[difficulty]}

Start with a brief introduction, ask the candidate to summarize relevant
experience, then use follow-up questions to test clarity, impact, and
tradeoffs. Offer concise, constructive feedback only if the candidate asks.
"""


def get_interview(slug: str) -> InterviewScenario:
    try:
        return INTERVIEWS[slug]
    except KeyError:
        valid = ", ".join(INTERVIEWS)
        raise ValueError(f"Unknown interview '{slug}'. Valid options: {valid}")
