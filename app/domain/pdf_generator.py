"""ATS-Compliant PDF Generator using ReportLab (Phase 4).

Generates clean, single-column, standard-font PDFs parseable by modern ATS systems
(Greenhouse, Lever, Ashby, Workday).
"""

import io
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer


class AtsPdfGenerator:
    """Generates standard ATS-compliant PDFs for Resumes and Cover Letters."""

    @staticmethod
    def generate_resume_pdf(data: Dict[str, Any]) -> bytes:
        """Renders single-column ATS-compliant resume PDF bytes from structured data."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()
        name_style = ParagraphStyle(
            "CandidateName",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=1,  # Center
            textColor=colors.HexColor("#111827"),
        )
        contact_style = ParagraphStyle(
            "ContactInfo",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=1,  # Center
            textColor=colors.HexColor("#4B5563"),
        )
        heading_style = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            spaceBefore=10,
            spaceAfter=4,
            textColor=colors.HexColor("#1F2937"),
            textTransform="uppercase",
        )
        body_style = ParagraphStyle(
            "BodyText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#374151"),
        )
        bold_title_style = ParagraphStyle(
            "RoleTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#111827"),
        )
        bullet_style = ParagraphStyle(
            "BulletText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            leftIndent=14,
            firstLineIndent=-10,
            spaceAfter=2,
            textColor=colors.HexColor("#374151"),
        )

        story: List[Any] = []

        # 1. Header: Candidate Name & Contact Info
        name = data.get("candidate_name") or "Candidate"
        story.append(Paragraph(name, name_style))
        story.append(Spacer(1, 4))

        contact = data.get("contact_info", {})
        contact_parts = []
        if isinstance(contact, dict):
            for k in ["email", "phone", "location", "linkedin", "github"]:
                if contact.get(k):
                    contact_parts.append(str(contact[k]))
        elif isinstance(contact, str):
            contact_parts.append(contact)

        if contact_parts:
            story.append(Paragraph(" • ".join(contact_parts), contact_style))
            story.append(Spacer(1, 8))

        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#D1D5DB"), spaceAfter=8))

        # 2. Summary
        summary = data.get("summary")
        if summary:
            story.append(Paragraph("Professional Summary", heading_style))
            story.append(Paragraph(summary, body_style))
            story.append(Spacer(1, 6))

        # 3. Technical Skills
        skills = data.get("skills", [])
        if skills:
            story.append(Paragraph("Technical Skills", heading_style))
            skills_text = ", ".join(skills) if isinstance(skills, list) else str(skills)
            story.append(Paragraph(skills_text, body_style))
            story.append(Spacer(1, 6))

        # 4. Professional Experience
        experience = data.get("experience", [])
        if experience:
            story.append(Paragraph("Professional Experience", heading_style))
            for exp in experience:
                title = exp.get("title", "")
                company = exp.get("company", "")
                dates = exp.get("dates", "")
                location = exp.get("location", "")

                line1 = f"{title} | <b>{company}</b>"
                if location:
                    line1 += f" ({location})"
                if dates:
                    line1 += f" — <i>{dates}</i>"

                story.append(Paragraph(line1, bold_title_style))
                story.append(Spacer(1, 2))

                bullets = exp.get("bullets", [])
                for b in bullets:
                    story.append(Paragraph(f"• {b}", bullet_style))
                story.append(Spacer(1, 4))

        # 5. Education
        education = data.get("education", [])
        if education:
            story.append(Paragraph("Education", heading_style))
            for edu in education:
                degree = edu.get("degree", "")
                institution = edu.get("institution", "")
                year = edu.get("year", "")
                edu_line = f"<b>{degree}</b> — {institution}"
                if year:
                    edu_line += f" ({year})"
                story.append(Paragraph(edu_line, body_style))
                story.append(Spacer(1, 2))

        doc.build(story)
        return buffer.getvalue()

    @staticmethod
    def generate_cover_letter_pdf(data: Dict[str, Any]) -> bytes:
        """Renders single-column ATS-compliant cover letter PDF bytes."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=48,
            rightMargin=48,
            topMargin=48,
            bottomMargin=48,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            spaceAfter=12,
            textColor=colors.HexColor("#111827"),
        )
        body_style = ParagraphStyle(
            "LetterBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            spaceAfter=8,
            textColor=colors.HexColor("#374151"),
        )

        story: List[Any] = []
        title = data.get("title") or f"Cover Letter for {data.get('job_title', 'Role')}"
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 10))

        body_text = data.get("body_text", "")
        for paragraph in body_text.split("\n\n"):
            if paragraph.strip():
                story.append(Paragraph(paragraph.strip(), body_style))
                story.append(Spacer(1, 6))

        doc.build(story)
        return buffer.getvalue()


pdf_generator = AtsPdfGenerator()
