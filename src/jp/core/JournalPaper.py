import json
import os
import subprocess
from pathlib import Path

from pylatex import Command, Document, Package
from pylatex.utils import NoEscape


class JournalPaper:
    def __init__(self, dir_path: str):
        self.dir_path = dir_path
        self.metadata = self.load_metadata()

    def load_metadata(self):
        """Load metadata from metadata.json if it exists."""
        metadata_path = os.path.join(self.dir_path, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, "r") as f:
                return json.load(f)
        return {}

    def get_tex_files(self):
        """Get all .tex files in the directory, sorted by filename."""
        tex_files = sorted(Path(self.dir_path).glob("*.tex"))
        return tex_files

    def _setup_packages(self, doc):
        """Add all required LaTeX packages to the document."""
        # Load xcolor first as it's needed by lstset
        doc.packages.append(Package("xcolor"))
        # NeurIPS style loads Times and natbib automatically
        doc.packages.append(NoEscape(r"\usepackage[preprint]{neurips_2023}"))
        doc.packages.append(Package("inputenc", options="utf8"))
        doc.packages.append(Package("amsmath"))
        doc.packages.append(
            Package(
                "hyperref",
                options="colorlinks=true,linkcolor=blue,"
                + "citecolor=blue,urlcolor=blue",
            )
        )
        doc.packages.append(Package("url"))
        doc.packages.append(Package("booktabs"))
        doc.packages.append(Package("amsfonts"))
        doc.packages.append(Package("nicefrac"))
        doc.packages.append(Package("microtype"))
        doc.packages.append(Package("listings"))

        # Configure listings for code formatting
        doc.preamble.append(
            NoEscape(
                r"""
\lstset{
    backgroundcolor=\color{gray!10},
    basicstyle=\ttfamily\small,
    breaklines=true,
    keywordstyle=\color{blue},
    commentstyle=\color{green!40!black},
    stringstyle=\color{orange},
    frame=single
}
"""
            )
        )

    def _setup_title(self, doc):
        """Add title and subtitle to the document."""
        if "title" not in self.metadata:
            return

        title_text = self.metadata["title"]
        if "subtitle" in self.metadata:
            # NeurIPS format: combine title and subtitle
            title_text += NoEscape(r" \\ ")
            title_text += self.metadata["subtitle"]
        doc.preamble.append(Command("title", NoEscape(title_text)))

    def _setup_authors(self, doc):
        """Add author information to the document."""
        if "authors" not in self.metadata:
            return

        authors_list = []
        for author in self.metadata["authors"]:
            author_str = author.get("name", "")
            if "email" in author:
                # NeurIPS format uses \thanks for email
                author_str += NoEscape(
                    rf"\thanks{{\texttt{{{author['email']}}}}}"
                )
            authors_list.append(author_str)

        author_combined = NoEscape(r" \and ".join(authors_list))
        doc.preamble.append(Command("author", author_combined))

    def _setup_title_and_authors(self, doc):
        """Add title, subtitle, and author information from metadata."""
        if not self.metadata:
            return

        self._setup_title(doc)
        self._setup_authors(doc)

    def create_document(self):
        """Create a PyLaTeX Document with all necessary packages."""
        # NeurIPS uses article class without options (handled by style file)
        doc = Document(documentclass="article")
        self._setup_packages(doc)
        self._setup_title_and_authors(doc)
        return doc

    def _add_document_content(self, doc, tex_files, has_bibliography):
        """Add maketitle, tex files, and bibliography to the document."""
        if self.metadata:
            doc.append(NoEscape(r"\maketitle"))

        for tex_file in tex_files:
            doc.append(NoEscape(f"\\input{{../{tex_file.name}}}"))

        if has_bibliography:
            # NeurIPS uses natbib with specific style
            doc.append(NoEscape(r"\bibliographystyle{plainnat}"))
            doc.append(NoEscape(r"\bibliography{../refs}"))

    def _compile_with_bibliography(self, doc, compiled_dir, output_path):
        """Run the full LaTeX compilation cycle with BibTeX using subprocess."""
        # Set TEXINPUTS to include the common directory
        common_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../../common")
        )
        env = os.environ.copy()
        env["TEXINPUTS"] = common_dir + os.pathsep + env.get("TEXINPUTS", "")

        # First pdflatex pass
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "main.tex"],
            cwd=compiled_dir,
            check=True,
            env=env,
        )

        # Run bibtex
        subprocess.run(
            ["bibtex", "main"], cwd=compiled_dir, check=True, env=env
        )

        # Second pdflatex pass
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "main.tex"],
            cwd=compiled_dir,
            check=True,
            env=env,
        )

        # Third pdflatex pass
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "main.tex"],
            cwd=compiled_dir,
            check=True,
            env=env,
        )

        return output_path + ".pdf"

    def build(self):
        """Build latex files and compile into PDF."""
        doc = self.create_document()
        tex_files = self.get_tex_files()

        bib_path = os.path.join(self.dir_path, "refs.bib")
        has_bibliography = os.path.exists(bib_path)

        self._add_document_content(doc, tex_files, has_bibliography)

        compiled_dir = os.path.join(self.dir_path, "__compiled")
        os.makedirs(compiled_dir, exist_ok=True)
        output_path = os.path.join(compiled_dir, "main")

        doc.generate_tex(filepath=output_path)

        # Set TEXINPUTS to include the common directory for PDF generation
        common_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "../../../common")
        )
        env = os.environ.copy()
        env["TEXINPUTS"] = common_dir + os.pathsep + env.get("TEXINPUTS", "")

        if has_bibliography:
            pdf_path = self._compile_with_bibliography(
                doc, compiled_dir, output_path
            )
        else:
            # For non-bibliography case, temporarily set TEXINPUTS
            original_texinputs = os.environ.get("TEXINPUTS", "")
            os.environ["TEXINPUTS"] = env["TEXINPUTS"]
            try:
                pdf_path = doc.generate_pdf(
                    filepath=output_path, clean_tex=False, compiler="pdflatex"
                )
            finally:
                if original_texinputs:
                    os.environ["TEXINPUTS"] = original_texinputs
                else:
                    os.environ.pop("TEXINPUTS", None)

        print(f"Successfully built PDF: {pdf_path}")
        return pdf_path
