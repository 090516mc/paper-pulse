"""
Weekly PDF report generator for Paper Pulse.
Generates a beautifully formatted PDF with the top 20 newest papers.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
import urllib.request
import zipfile
import shutil

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from progress import github_group, github_notice, github_warning
    HAS_PROGRESS = True
except ImportError:
    HAS_PROGRESS = False
    class github_group:
        def __init__(self, name): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    def github_notice(msg): print(f"Notice: {msg}")
    def github_warning(msg): print(f"Warning: {msg}")


FONT_DIR = Path(__file__).parent.parent / "fonts"
FONT_URL = "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf"
FONT_BOLD_URL = "https://github.com/notofonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Bold.otf"
FONT_PATH = FONT_DIR / "NotoSansCJKsc-Regular.otf"
FONT_BOLD_PATH = FONT_DIR / "NotoSansCJKsc-Bold.otf"

MAX_PAPERS = 20


def ensure_fonts():
    """Download Noto Sans SC fonts if not present."""
    FONT_DIR.mkdir(parents=True, exist_ok=True)

    if not FONT_PATH.exists():
        print("Downloading NotoSansCJKsc-Regular font...")
        urllib.request.urlretrieve(FONT_URL, FONT_PATH)
        print("Font downloaded.")

    if not FONT_BOLD_PATH.exists():
        print("Downloading NotoSansCJKsc-Bold font...")
        urllib.request.urlretrieve(FONT_BOLD_URL, FONT_BOLD_PATH)
        print("Bold font downloaded.")


def load_papers(data_dir: Path) -> list:
    """Load papers from JSON, sorted by published date descending, return top 20."""
    papers_file = data_dir / "papers.json"
    if not papers_file.exists():
        print(f"Papers file not found: {papers_file}")
        return []

    with open(papers_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    papers = data.get("papers", [])
    # Sort by published date descending
    papers.sort(key=lambda p: p.get("published", "0000-00-00"), reverse=True)
    top_papers = papers[:MAX_PAPERS]
    print(f"Loaded {len(papers)} papers, selecting top {len(top_papers)} newest")
    return top_papers


def safe_text(text, max_len=2000):
    """Clean text for PDF embedding."""
    if not text:
        return ""
    text = str(text)
    # Replace problematic characters
    text = text.replace('\u200b', '')  # zero-width space
    text = text.replace('\ufeff', '')  # BOM
    # Limit length
    if len(text) > max_len:
        text = text[:max_len] + "..."
    return text


def generate_pdf(papers: list, output_path: Path, site_url: str = ""):
    """Generate a beautifully formatted PDF with paper details."""
    try:
        from fpdf import FPDF
    except ImportError:
        print("fpdf2 not installed. Install with: pip install fpdf2")
        sys.exit(1)

    ensure_fonts()

    class PaperPDF(FPDF):
        def header(self):
            if self.page_no() > 1:
                self.set_font("NotoSansCJK", "", 8)
                self.set_text_color(100, 100, 100)
                self.cell(0, 8, "Paper Pulse - Weekly Research Digest", align="C")
                self.ln(10)

        def footer(self):
            if self.page_no() > 1:
                self.set_y(-15)
                self.set_font("NotoSansCJK", "", 8)
                self.set_text_color(128, 128, 128)
                self.cell(0, 10, f"Page {self.page_no() - 1}", align="C")

        def add_cover_page(self, paper_count, date_str):
            """Generate a professional cover page."""
            self.add_page()
            # Skip the header/footer on cover
            self.set_y(60)
            # Title block
            self.set_font("NotoSansCJK", "B", 28)
            self.set_text_color(25, 60, 120)
            self.cell(0, 15, "Paper Pulse", align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(5)
            self.set_font("NotoSansCJK", "", 16)
            self.set_text_color(60, 60, 60)
            self.cell(0, 12, "Weekly Research Paper Digest", align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(10)

            # Decorative line
            self.set_draw_color(25, 60, 120)
            self.set_line_width(0.8)
            x_center = self.w / 2
            self.line(x_center - 40, self.get_y(), x_center + 40, self.get_y())
            self.ln(15)

            # Info block
            self.set_font("NotoSansCJK", "", 11)
            self.set_text_color(80, 80, 80)
            info_items = [
                f"Report Date: {date_str}",
                f"Papers Included: {paper_count}",
                f"Source: arXiv & IACR ePrint",
                f"Powered by DeepSeek AI",
            ]
            for item in info_items:
                self.cell(0, 10, item, align="C", new_x="LMARGIN", new_y="NEXT")
            self.ln(15)

            # Description
            self.set_font("NotoSansCJK", "", 10)
            self.set_text_color(100, 100, 100)
            desc = (
                "This digest presents the 20 most recent research papers "
                "automatically fetched, filtered, and summarized. "
                "Each entry includes the full title, authors, abstract, "
                "and AI-generated bilingual summaries."
            )
            self.multi_cell(0, 7, desc, align="C")
            self.ln(20)

            if site_url:
                self.set_font("NotoSansCJK", "", 9)
                self.set_text_color(0, 102, 204)
                self.cell(0, 8, f"Online: {site_url}", align="C", new_x="LMARGIN", new_y="NEXT")

        def add_paper_entry(self, paper, index):
            """Add a single paper entry to the PDF."""
            # Check if we need a new page (don't start paper too close to bottom)
            if self.get_y() > 220:
                self.add_page()

            # Paper number header
            self.set_font("NotoSansCJK", "B", 14)
            self.set_text_color(25, 60, 120)
            self.cell(0, 10, f"Paper {index}", new_x="LMARGIN", new_y="NEXT")
            self.ln(2)

            # Title
            title = safe_text(paper.get("title", "Untitled"), 500)
            self.set_font("NotoSansCJK", "B", 12)
            self.set_text_color(30, 30, 30)
            self.multi_cell(0, 7, title)
            self.ln(3)

            # Meta info
            self.set_font("NotoSansCJK", "", 9)
            self.set_text_color(100, 100, 100)

            authors = paper.get("authors", [])
            if isinstance(authors, list):
                authors_str = ", ".join(authors[:5])
                if len(authors) > 5:
                    authors_str += f" et al."
            else:
                authors_str = str(authors)
            self.multi_cell(0, 5, f"Authors: {safe_text(authors_str, 300)}")

            source = paper.get("source", "Unknown")
            published = paper.get("published", "Unknown")
            categories = paper.get("categories", [])
            if isinstance(categories, list):
                categories_str = ", ".join(categories[:5])
            else:
                categories_str = str(categories)

            self.cell(0, 5, f"Source: {source}  |  Published: {published}", new_x="LMARGIN", new_y="NEXT")
            if categories_str:
                self.cell(0, 5, f"Categories: {categories_str}", new_x="LMARGIN", new_y="NEXT")

            url = paper.get("url", "") or paper.get("pdf_link", "")
            if url:
                self.set_text_color(0, 102, 204)
                self.cell(0, 5, f"URL: {safe_text(url, 150)}", new_x="LMARGIN", new_y="NEXT")
                self.set_text_color(100, 100, 100)

            keywords = paper.get("keywords", [])
            if keywords:
                kw_str = ", ".join(keywords[:8])
                self.cell(0, 5, f"Keywords: {kw_str}", new_x="LMARGIN", new_y="NEXT")

            self.ln(3)

            # Separator
            self.set_draw_color(200, 200, 200)
            self.set_line_width(0.3)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(4)

            # Abstract section
            abstract = safe_text(paper.get("abstract", "No abstract available."), 3000)
            self.set_font("NotoSansCJK", "B", 10)
            self.set_text_color(50, 50, 50)
            self.cell(0, 7, "Abstract", new_x="LMARGIN", new_y="NEXT")
            self.set_font("NotoSansCJK", "", 9)
            self.set_text_color(60, 60, 60)
            self.multi_cell(0, 5.5, abstract)
            self.ln(4)

            # Chinese summary
            summary_zh = safe_text(paper.get("summary_zh", ""), 3000)
            if summary_zh and paper.get("summary_status") == "success":
                self.set_font("NotoSansCJK", "B", 10)
                self.set_text_color(180, 40, 40)  # Dark red for Chinese
                self.cell(0, 7, "Chinese Summary", new_x="LMARGIN", new_y="NEXT")
                self.set_font("NotoSansCJK", "", 9)
                self.set_text_color(60, 60, 60)
                self.multi_cell(0, 5.5, summary_zh)
                self.ln(4)

            # English summary
            summary_en = safe_text(paper.get("summary_en", ""), 2500)
            if summary_en and paper.get("summary_status") == "success":
                self.set_font("NotoSansCJK", "B", 10)
                self.set_text_color(25, 60, 120)  # Dark blue for English
                self.cell(0, 7, "English Summary", new_x="LMARGIN", new_y="NEXT")
                self.set_font("NotoSansCJK", "", 9)
                self.set_text_color(60, 60, 60)
                self.multi_cell(0, 5.5, summary_en)
                self.ln(4)

            # End of paper separator
            self.set_draw_color(25, 60, 120)
            self.set_line_width(0.5)
            y = self.get_y()
            self.line(self.l_margin, y, self.w - self.r_margin, y)
            self.ln(8)

    pdf = PaperPDF()
    pdf.set_auto_page_break(auto=True, margin=20)

    # Add the fonts
    pdf.add_font("NotoSansCJK", "", str(FONT_PATH))
    pdf.add_font("NotoSansCJK", "B", str(FONT_BOLD_PATH))

    date_str = datetime.now().strftime("%Y-%m-%d %H:%M UTC")
    paper_count = len(papers)

    # Cover page
    pdf.add_cover_page(paper_count, date_str)

    # Table of Contents
    if papers:
        pdf.add_page()
        pdf.set_font("NotoSansCJK", "B", 18)
        pdf.set_text_color(25, 60, 120)
        pdf.cell(0, 12, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(5)
        pdf.set_draw_color(25, 60, 120)
        pdf.set_line_width(0.5)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(8)

        for i, paper in enumerate(papers, 1):
            title = safe_text(paper.get("title", "Untitled"), 100)
            pdf.set_font("NotoSansCJK", "", 10)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(0, 7, f"{i}. {title}", new_x="LMARGIN", new_y="NEXT")

    # Paper entries
    for i, paper in enumerate(papers, 1):
        pdf.add_paper_entry(paper, i)

    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(output_path))
    print(f"PDF generated: {output_path} ({os.path.getsize(output_path) / 1024:.0f} KB)")
    return str(output_path)


def main():
    """Main entry point for PDF generation."""
    with github_group(" Generating weekly PDF report"):
        # Load config
        config_path = Path(__file__).parent.parent / "config.toml"
        site_url = ""
        data_dir = Path(__file__).parent.parent / "data"
        if config_path.exists():
            try:
                import tomllib
            except ModuleNotFoundError:
                import tomli as tomllib
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
            site_url = config.get("general", {}).get("site_url", "")
            data_dir = Path(__file__).parent.parent / config.get("general", {}).get("data_dir", "data")

        # Load papers
        papers = load_papers(data_dir)
        if not papers:
            github_warning("No papers found to generate PDF.")
            return

        # Generate PDF
        output_path = data_dir / "weekly_report.pdf"
        generate_pdf(papers, output_path, site_url)
        github_notice(f"Weekly PDF report generated with {len(papers)} papers")


if __name__ == "__main__":
    main()