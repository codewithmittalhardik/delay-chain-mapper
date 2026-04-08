import json
import traceback
from django.conf import settings

try:
    from groq import Groq
except ImportError:
    Groq = None


def _get_client():
    """Return a configured Groq client or None."""
    api_key = settings.GROQ_API_KEY
    if not api_key or api_key == 'your_groq_api_key_here' or Groq is None:
        return None
    return Groq(api_key=api_key)


def generate_chain(prompt: str) -> dict | None:
    """
    Send a project description to Groq and get back structured tasks + links.
    Returns dict with 'nodes' and 'links' keys, or None on failure.
    """
    client = _get_client()
    if not client:
        return None

    system_msg = """You are a project planning AI. Given a project description, 
return a JSON object with exactly two keys:
- "nodes": array of objects with keys "id" (string number starting from "1"), "name" (string), "duration" (integer, days), "delay" (integer, default 0)
- "links": array of objects with keys "source" (string id), "target" (string id) representing dependencies

Return ONLY valid JSON, no markdown, no explanation. Example:
{"nodes":[{"id":"1","name":"Design Phase","duration":10,"delay":0},{"id":"2","name":"Development","duration":20,"delay":0}],"links":[{"source":"1","target":"2"}]}"""

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=2000,
        )

        raw = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        data = json.loads(raw)

        # Normalize
        if "nodes" in data:
            for node in data["nodes"]:
                node["id"] = str(node.get("id", ""))
                node["name"] = str(node.get("name", "Unnamed"))
                node["duration"] = int(node.get("duration", 10))
                node["delay"] = int(node.get("delay", 0))

        if "links" in data:
            for link in data["links"]:
                link["source"] = str(link.get("source", ""))
                link["target"] = str(link.get("target", ""))

        return data

    except Exception as e:
        traceback.print_exc()
        return None


def analyze_delay_optimization(project_data: dict) -> str | None:
    """
    Analyze the current project state and provide AI-powered recommendations
    on how to optimize delays in the task chain.
    
    project_data: dict with 'nodes' and 'links' keys
    Returns: markdown-formatted analysis string, or None on failure.
    """
    client = _get_client()
    if not client:
        return None

    system_msg = """You are an expert project management consultant specializing in delay chain analysis and schedule optimization. 

Given a project's task dependency graph with current delays, provide a comprehensive but concise analysis. Format your response in clean sections:

1. **🔍 Root Cause Analysis** — Identify the true root causes of delays in the chain
2. **⚡ Optimization Strategies** — Specific, actionable recommendations to reduce delays:
   - Which tasks can be parallelized?
   - Where can scope be reduced?
   - What re-sequencing would help?
3. **⚠️ Risk Assessment** — What cascading risks exist if delays aren't addressed
4. **📊 Estimated Impact** — Projected time savings if recommendations are followed

Keep the tone professional but accessible. Use bullet points for clarity. Be specific to the actual tasks and delays provided."""

    # Build a readable summary of the project state
    nodes_summary = "\n".join([
        f"  - Task '{n['name']}' (ID: {n['id']}): Duration={n['duration']}d, Current Delay={n['delay']}d"
        for n in project_data.get('nodes', [])
    ])
    
    links_summary = "\n".join([
        f"  - {l['source']} → {l['target']}"
        for l in project_data.get('links', [])
    ])

    user_msg = f"""Analyze this project's delay chain and provide optimization recommendations:

**Tasks:**
{nodes_summary}

**Dependencies (source → target):**
{links_summary}

Total tasks: {len(project_data.get('nodes', []))}
Delayed tasks: {len([n for n in project_data.get('nodes', []) if n.get('delay', 0) > 0])}
"""

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.5,
            max_tokens=1500,
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        traceback.print_exc()
        return None
