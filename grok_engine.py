"""
grok_engine.py
Grok-3 API integration for resume generation.
Uses OpenAI-compatible client pointed at xAI endpoint.
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ─── Client Setup ───────────────────────────────────────────────────────────────
def get_client() -> OpenAI:
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        raise ValueError(
            "GROK_API_KEY not found. Create a .env file with: GROK_API_KEY=your_key_here\n"
            "Get your key from: https://console.x.ai"
        )
    return OpenAI(
        api_key=api_key,
        base_url="https://api.x.ai/v1"
    )


# ─── Main Resume Generator ──────────────────────────────────────────────────────
def generate_resume_latex(prompt: str, model: str = "grok-3") -> str:
    """
    Send prompt to Grok-3 and get back optimized LaTeX resume code.

    Args:
        prompt: Complete optimization prompt from prompt_template.py
        model: Grok model to use (default: grok-3)

    Returns:
        LaTeX string ready for PDF compilation
    """
    client = get_client()

    system_prompt = """You are NeuroResume — the world's most advanced AI resume optimization engine.

Your ONLY output is valid, compilable LaTeX code. Nothing else.

STRICT RULES:
1. Output ONLY LaTeX code. Zero preamble, zero explanation, zero markdown.
2. Start directly with \\documentclass
3. End with \\end{document}
4. Use ONLY standard LaTeX packages: geometry, fontenc, inputenc, hyperref, enumitem, titlesec, xcolor, parskip, multicol
5. NO external fonts that require special installation (no fontawesome unless specified)
6. Make it ATS-parseable: clean structure, no tables for layout, no columns for main content
7. Quantify ALL achievements with numbers where possible
8. Keywords from job description must appear naturally throughout
9. Clean professional formatting with proper spacing

LATEX TEMPLATE STYLE:
- Document class: article with [letterpaper, 11pt, margin config]
- Packages: geometry (margins), titlesec (section formatting), enumitem (lists), xcolor (minimal color), hyperref (links)
- Sections: SUMMARY, EXPERIENCE, SKILLS, EDUCATION, PROJECTS (include all that are relevant)
- No fancy graphics, no tikz, no complex packages
- Single column layout for ATS compatibility
"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.6,
        max_tokens=4096,
    )

    raw_output = response.choices[0].message.content.strip()

    # ── Clean output if model wraps in markdown ────────────────────────────────
    latex = _clean_latex_output(raw_output)
    return latex


def _clean_latex_output(raw: str) -> str:
    """Remove any markdown code fences if model accidentally added them."""
    # Remove ```latex or ``` wrappers
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove first line (```latex or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines)

    # Ensure starts with \documentclass
    if "\\documentclass" in raw:
        idx = raw.index("\\documentclass")
        raw = raw[idx:]

    return raw.strip()


# ─── Quick Test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    test_prompt = """
    Job: Senior Python Developer at TechCorp
    Resume: John Doe, 3 years Python experience, built REST APIs, worked with PostgreSQL
    Generate a professional LaTeX resume.
    """
    print("Testing Grok connection...")
    try:
        result = generate_resume_latex(test_prompt)
        print("✓ Grok connected successfully")
        print(f"✓ Output length: {len(result)} characters")
        print(result[:500] + "...")
    except Exception as e:
        print(f"✗ Error: {e}")
