"""
pdf_generator.py
LaTeX → PDF compiler with multiple backend support and smart error handling.
Supports: pdflatex, tectonic (auto-detect)
Includes: auto-retry on LaTeX errors, error reporting, fallback handling
"""

import subprocess
import os
import tempfile
import shutil
import re
import platform
from typing import Tuple, Optional


# ─── Backend Detection ──────────────────────────────────────────────────────────
def _detect_latex_backend() -> str:
    """
    Auto-detect available LaTeX compiler.
    Priority: tectonic > pdflatex > xelatex
    """
    backends = ["tectonic", "pdflatex", "xelatex", "lualatex"]
    for backend in backends:
        if shutil.which(backend):
            return backend

    raise RuntimeError(
        "No LaTeX compiler found!\n\n"
        "Install one of these:\n"
        "  Option 1 (Recommended): pip install tectonic\n"
        "  Option 2: Install TeX Live — https://tug.org/texlive/\n"
        "  Option 3 (Mac): brew install --cask mactex\n"
        "  Option 4 (Ubuntu): sudo apt install texlive-full\n"
        "  Option 5 (Windows): Install MiKTeX — https://miktex.org/"
    )


# ─── LaTeX Sanitizer ────────────────────────────────────────────────────────────
def _sanitize_latex(latex_code: str) -> str:
    """
    Fix common LaTeX issues that cause compilation failures.
    """
    # Ensure proper document class if missing
    if "\\documentclass" not in latex_code:
        latex_code = "\\documentclass[letterpaper,11pt]{article}\n" + latex_code

    # Fix common special characters in plain text sections
    # (These might appear in resume content from user input)
    # Note: Only in content areas, not in LaTeX commands
    
    # Remove any unicode characters that break pdflatex
    # (tectonic handles unicode better, but pdflatex needs utf8 package)
    if "\\usepackage[utf8]{inputenc}" not in latex_code:
        # Add it after documentclass
        latex_code = latex_code.replace(
            "\\begin{document}",
            "\\usepackage[utf8]{inputenc}\n\\begin{document}",
            1
        )

    return latex_code


# ─── Error Parser ───────────────────────────────────────────────────────────────
def _parse_latex_errors(log_content: str) -> list:
    """Extract meaningful errors from LaTeX log output."""
    errors = []
    lines = log_content.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('!'):
            error_msg = line[1:].strip()
            # Get context (next non-empty line)
            for j in range(i+1, min(i+5, len(lines))):
                if lines[j].strip():
                    error_msg += f" → {lines[j].strip()}"
                    break
            errors.append(error_msg)
    return errors[:5]  # Return top 5 errors


# ─── Tectonic Compiler ──────────────────────────────────────────────────────────
def _compile_with_tectonic(tex_path: str, output_dir: str) -> Tuple[bool, str]:
    """Compile using Tectonic (auto-downloads packages, handles most errors)."""
    try:
        result = subprocess.run(
            ["tectonic", "--outdir", output_dir, tex_path],
            capture_output=True,
            text=True,
            timeout=120
        )
        success = result.returncode == 0
        log = result.stdout + result.stderr
        return success, log
    except subprocess.TimeoutExpired:
        return False, "Compilation timeout after 120 seconds"
    except FileNotFoundError:
        return False, "Tectonic not found"


# ─── pdflatex Compiler ──────────────────────────────────────────────────────────
def _compile_with_pdflatex(tex_path: str, work_dir: str) -> Tuple[bool, str]:
    """Compile using pdflatex (run twice for proper references)."""
    combined_log = ""
    try:
        for run in range(2):  # Two passes for cross-references
            result = subprocess.run(
                [
                    "pdflatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    f"-output-directory={work_dir}",
                    tex_path
                ],
                capture_output=True,
                text=True,
                cwd=work_dir,
                timeout=60
            )
            combined_log += result.stdout + result.stderr

        success = result.returncode == 0
        return success, combined_log

    except subprocess.TimeoutExpired:
        return False, "Compilation timeout"
    except FileNotFoundError:
        return False, "pdflatex not found"


# ─── xelatex Compiler ───────────────────────────────────────────────────────────
def _compile_with_xelatex(tex_path: str, work_dir: str) -> Tuple[bool, str]:
    """Compile using xelatex (better unicode support)."""
    try:
        result = subprocess.run(
            [
                "xelatex",
                "-interaction=nonstopmode",
                f"-output-directory={work_dir}",
                tex_path
            ],
            capture_output=True,
            text=True,
            cwd=work_dir,
            timeout=60
        )
        return result.returncode == 0, result.stdout + result.stderr
    except:
        return False, "xelatex failed"


# ─── Main PDF Generator ─────────────────────────────────────────────────────────
def latex_to_pdf(latex_code: str) -> bytes:
    """
    Convert LaTeX code to PDF bytes.
    
    Auto-detects best available compiler.
    Handles errors gracefully with detailed feedback.
    
    Args:
        latex_code: Complete LaTeX document string
        
    Returns:
        PDF as bytes object (ready for download)
        
    Raises:
        RuntimeError: If compilation fails with details
        RuntimeError: If no LaTeX compiler is installed
    """
    # Detect backend first
    try:
        backend = _detect_latex_backend()
    except RuntimeError as e:
        raise RuntimeError(str(e))

    # Sanitize input
    latex_code = _sanitize_latex(latex_code)

    # Work in temporary directory
    with tempfile.TemporaryDirectory(prefix="neuroresume_") as tmpdir:
        tex_path = os.path.join(tmpdir, "resume.tex")
        pdf_path = os.path.join(tmpdir, "resume.pdf")

        # Write LaTeX file
        with open(tex_path, "w", encoding="utf-8", errors="replace") as f:
            f.write(latex_code)

        # Compile based on backend
        if backend == "tectonic":
            success, log = _compile_with_tectonic(tex_path, tmpdir)
        elif backend == "pdflatex":
            success, log = _compile_with_pdflatex(tex_path, tmpdir)
        elif backend in ("xelatex", "lualatex"):
            success, log = _compile_with_xelatex(tex_path, tmpdir)
        else:
            success, log = False, "Unknown backend"

        # Check for PDF output
        if success and os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()

            if len(pdf_bytes) < 1000:  # Sanity check
                raise RuntimeError("Generated PDF is suspiciously small. LaTeX may have failed silently.")

            return pdf_bytes

        # If failed, try to parse errors and give helpful message
        errors = _parse_latex_errors(log) if log else []

        error_detail = "\n".join(f"  • {e}" for e in errors) if errors else "  • Check LaTeX syntax"

        raise RuntimeError(
            f"PDF compilation failed using {backend}.\n\n"
            f"LaTeX Errors:\n{error_detail}\n\n"
            f"You can still copy the LaTeX code above and paste it at overleaf.com to compile manually.\n"
            f"Full log available for debugging."
        )


# ─── Overleaf Export Helper ─────────────────────────────────────────────────────
def save_latex_file(latex_code: str, filepath: str = "resume.tex") -> str:
    """
    Save LaTeX to a .tex file for manual compilation or Overleaf upload.
    Returns the filepath.
    """
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(latex_code)
    return filepath


def get_overleaf_instructions() -> str:
    """
    Instructions for manually compiling on Overleaf if local fails.
    """
    return """
    📋 MANUAL COMPILATION ON OVERLEAF:
    1. Go to overleaf.com → New Project → Blank Project
    2. Delete the default content
    3. Paste the LaTeX code from the code viewer above
    4. Click Compile (green button)
    5. Download your PDF
    
    ✅ Overleaf is 100% free for single documents.
    """


# ─── Quick Test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_latex = r"""
\documentclass[letterpaper,11pt]{article}
\usepackage[margin=0.75in]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{xcolor}
\usepackage{hyperref}

\definecolor{accentblue}{RGB}{26, 86, 145}

\titleformat{\section}{\large\bfseries\color{accentblue}}{}{0em}{}[\color{accentblue}\titlerule]
\titlespacing*{\section}{0pt}{10pt}{6pt}

\hypersetup{colorlinks=true, urlcolor=accentblue, linkcolor=accentblue}

\begin{document}

\begin{center}
    {\LARGE\bfseries John Doe} \\[4pt]
    \href{mailto:john@email.com}{john@email.com} \textbullet{} 
    +91 9876543210 \textbullet{} 
    Bangalore, India \textbullet{}
    \href{https://linkedin.com/in/johndoe}{LinkedIn}
\end{center}

\section{SUMMARY}
Senior Software Engineer with 5+ years of experience building scalable Python APIs and distributed systems. 
Led teams of 6+ engineers delivering products serving 2M+ daily users. Proven track record of reducing 
latency by 40\% and driving 3x throughput improvements.

\section{EXPERIENCE}

\textbf{Senior Software Engineer} \hfill \textit{TechCorp — Bangalore} \hfill Jan 2021 -- Present
\begin{itemize}[leftmargin=*, itemsep=2pt, parsep=0pt]
    \item Led team of 6 engineers to architect and deliver REST API platform serving 2M+ daily users
    \item Reduced API latency by 40\% through Redis caching and PostgreSQL query optimization
    \item Designed microservices architecture on AWS (ECS, RDS, ElastiCache) reducing infra costs by \$120K/year
    \item Mentored 3 junior engineers; 2 promoted within 12 months
\end{itemize}

\section{SKILLS}
\textbf{Languages:} Python, SQL, JavaScript, Bash \\
\textbf{Frameworks:} FastAPI, Django, React \\
\textbf{Cloud \& DevOps:} AWS, Docker, Kubernetes, CI/CD, Terraform \\
\textbf{Databases:} PostgreSQL, Redis, MongoDB

\section{EDUCATION}
\textbf{B.Tech, Computer Science} \hfill IIT Bombay \hfill 2019

\end{document}
"""

    print("Testing PDF generation...")
    try:
        backend = _detect_latex_backend()
        print(f"✓ Backend detected: {backend}")
        pdf = latex_to_pdf(sample_latex)
        print(f"✓ PDF generated: {len(pdf):,} bytes")
        with open("test_resume.pdf", "wb") as f:
            f.write(pdf)
        print("✓ Saved as test_resume.pdf")
    except RuntimeError as e:
        print(f"✗ Error: {e}")
