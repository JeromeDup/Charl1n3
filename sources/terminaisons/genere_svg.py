#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Générateur de phrases SVG pour les exercices de terminaisons.

Syntaxe de phrases.txt :

    # Commentaire
    [PRES3]
    &Le petit/t garçon& *jou/e dans le jardin.
    &Les petit/s chat/s& *mang/ent leur repas.
    &Un chaton/& *regard/e les oiseau/x.

Conventions :
- Les lignes commençant par # sont ignorées.
- Les lignes [ ... ] définissent une catégorie.
- & ... & délimite le sujet.
- * placé juste avant le verbe identifie le verbe conjugué.
- / marque le début de la terminaison à masquer.
- Les lettres immédiatement après / constituent la réponse.
- Si / est suivi d'autre chose qu'une lettre, la réponse est vide.

Sortie :
    sortie_svg/
        phrases_svg/
            phrase_0001.svg
            ...
        phrases.json
        phrases.txt
        _build/
            fichiers LaTeX, PDF et journaux
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

SOURCE_FILE = BASE_DIR / "phrases.txt"

OUTPUT_DIR = BASE_DIR / "sortie_svg"
SVG_DIR = OUTPUT_DIR / "phrases_svg"
BUILD_DIR = OUTPUT_DIR / "_build"

LATEX = "pdflatex"
PDF_TO_SVG = "pdftocairo"

PAPER_WIDTH = "300mm"
PAPER_HEIGHT = "60mm"

MIN_TERM_WIDTH_MM = 8
TERM_MARGIN_MM = 2


# ============================================================
# OUTILS
# ============================================================

def check_program(program):

    if shutil.which(program) is None:
        raise RuntimeError(
            f"Commande introuvable : {program}\n"
            "Vérifie que le programme est installé."
        )


def tex_escape(text):

    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }

    return "".join(
        replacements.get(char, char)
        for char in text
    )


def is_letter(char):

    return bool(char) and char.isalpha()


# ============================================================
# LECTURE ET ANALYSE DES PHRASES
# ============================================================

def parse_phrase(raw_line, category, line_number):

    plain_chars = []

    targets = []
    subjects = []
    verbs = []

    subject_start = None
    verb_start = None

    i = 0

    while i < len(raw_line):

        char = raw_line[i]

        # ----------------------------------------
        # Début ou fin du sujet
        # ----------------------------------------

        if char == "&":

            if subject_start is None:

                subject_start = len(plain_chars)

            else:

                subjects.append({
                    "start": subject_start,
                    "end": len(plain_chars),
                })

                subject_start = None

            i += 1
            continue

        # ----------------------------------------
        # Identification du verbe
        # ----------------------------------------

        if char == "*":

            if verb_start is not None:

                raise ValueError(
                    f"Ligne {line_number} : "
                    "marqueur * précédent non terminé."
                )

            verb_start = len(plain_chars)

            i += 1
            continue

        # ----------------------------------------
        # Terminaison à masquer
        # ----------------------------------------

        if char == "/":

            target_start = len(plain_chars)

            answer_chars = []

            i += 1

            while (
                i < len(raw_line)
                and is_letter(raw_line[i])
            ):

                answer_chars.append(raw_line[i])

                plain_chars.append(raw_line[i])

                i += 1

            answer = "".join(answer_chars)

            targets.append({

                "plain_start": target_start,

                "answer": answer,

                "answer_length": len(answer),

            })

            continue

        # ----------------------------------------
        # Fin du verbe
        # ----------------------------------------

        if verb_start is not None and not is_letter(char):

            verbs.append({

                "start": verb_start,

                "end": len(plain_chars),

            })

            verb_start = None

        plain_chars.append(char)

        i += 1

    # ----------------------------------------
    # Vérifications finales
    # ----------------------------------------

    if subject_start is not None:

        raise ValueError(
            f"Ligne {line_number} : "
            "marqueur & de sujet non refermé."
        )

    if verb_start is not None:

        verbs.append({

            "start": verb_start,

            "end": len(plain_chars),

        })

    text = "".join(plain_chars)

    if not text.strip():

        raise ValueError(
            f"Ligne {line_number} : phrase vide."
        )

    return {

        "category": category,

        "source_line": line_number,

        "text": text,

        "subjects": subjects,

        "verbs": verbs,

        "targets": targets,

    }


def read_phrases(path):

    if not path.exists():

        raise FileNotFoundError(
            f"Fichier source absent : {path}"
        )

    phrases = []

    category = "SANS_CATEGORIE"

    lines = path.read_text(
        encoding="utf-8-sig"
    ).splitlines()

    for line_number, raw in enumerate(lines, start=1):

        line = raw.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if line.startswith("[") and line.endswith("]"):

            category = line[1:-1].strip()

            continue

        phrase = parse_phrase(
            line,
            category,
            line_number
        )

        if not phrase["targets"]:

            print(
                f"Attention : ligne {line_number}, "
                "aucune terminaison à masquer."
            )

        phrases.append(phrase)

    return phrases


# ============================================================
# MESURE DES TERMINAISONS
# ============================================================

def create_measurement_file(phrases, path):

    answers = sorted({

        target["answer"]

        for phrase in phrases

        for target in phrase["targets"]

        if target["answer"]

    })

    lines = [

        r"\newlength{\TermWidth}",

        r"\newlength{\TermMeasure}",

        rf"\setlength{{\TermWidth}}{{{MIN_TERM_WIDTH_MM}mm}}",

    ]

    for answer in answers:

        escaped = tex_escape(answer)

        lines.extend([

            rf"\settowidth{{\TermMeasure}}{{{{\Large\cursive {escaped}}}}}",

            r"\ifdim\TermMeasure>\TermWidth",

            r"\setlength{\TermWidth}{\TermMeasure}",

            r"\fi",

        ])

    lines.append(

        rf"\addtolength{{\TermWidth}}{{{TERM_MARGIN_MM}mm}}"

    )

    path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )


# ============================================================
# CONSTRUCTION DU DOCUMENT LATEX
# ============================================================

def latex_document(phrase):

    parts = []

    i = 0

    text = phrase["text"]

    targets = phrase["targets"]

    for target in targets:

        start = target["plain_start"]

        answer_length = target["answer_length"]

        if start < i:

            raise ValueError(
                "Les marqueurs de terminaison se chevauchent."
            )

        parts.append(
            tex_escape(text[i:start])
        )

        parts.append(
            r"\TermMarker{}"
        )

        i = start + answer_length

    parts.append(
        tex_escape(text[i:])
    )

    rendered_phrase = "".join(parts)

    return r"""
\documentclass[12pt]{article}

\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[french]{babel}

\usepackage{frcursive}
\usepackage{xcolor}
\usepackage{tikz}

\usepackage[
    paperwidth=300mm,
    paperheight=60mm,
    left=10mm,
    right=10mm,
    top=5mm,
    bottom=5mm
]{geometry}

\pagestyle{empty}

\setlength{\parindent}{0pt}
\setlength{\parskip}{0pt}

\renewcommand{\seyesDefault}{\color{blue!65}}
\setlength{\seyesThickness}{0.10mm}

\input{terminaisons_mesures.tex}

\newcommand{\TermMarker}{%
    \tikz[baseline=-0.35ex]{%
        \fill[magenta]
        (0,-0.15ex)
        rectangle
        (\TermWidth,1.05em);
    }%
}

\begin{document}

\noindent
{\Large\cursive\seyes{
""" + rendered_phrase + r"""
}}

\end{document}
"""


# ============================================================
# EXÉCUTION DES COMMANDES
# ============================================================

def run_command(command, cwd):

    return subprocess.run(

        command,

        cwd=str(cwd),

        stdout=subprocess.PIPE,

        stderr=subprocess.STDOUT,

        text=True,

        encoding="utf-8",

        errors="replace",

    )


# ============================================================
# COMPILATION LATEX
# ============================================================

def compile_latex(tex_file):

    command = [

        LATEX,

        "-interaction=nonstopmode",

        "-halt-on-error",

        "-output-directory",

        str(BUILD_DIR),

        tex_file.name,

    ]

    print("Commande :", " ".join(command), flush=True)

    result = run_command(
        command,
        BUILD_DIR
    )

    if result.returncode != 0:

        print()
        print("Erreur pendant la compilation LaTeX.")
        print(result.stdout[-6000:])

        raise RuntimeError(
            "Échec de compilation LaTeX."
        )

    pdf_file = BUILD_DIR / (
        tex_file.stem + ".pdf"
    )

    if not pdf_file.exists():

        raise RuntimeError(
            f"PDF non trouvé : {pdf_file}"
        )

    return pdf_file


# ============================================================
# CONVERSION PDF VERS SVG
# ============================================================

def convert_pdf_to_svg(pdf_file, svg_file):

    prefix = svg_file.with_suffix("")

    # Suppression des anciens fichiers éventuels

    possible_outputs = [

        svg_file,

        prefix.with_name(
            prefix.name + "-1.svg"
        ),

        prefix,

    ]

    for candidate in possible_outputs:

        if candidate.exists() and candidate.is_file():

            candidate.unlink()

    command = [

        PDF_TO_SVG,

        "-svg",

        str(pdf_file),

        str(prefix),

    ]

    print(
        "Conversion PDF vers SVG...",
        flush=True
    )

    print(
        "Commande :",
        " ".join(command),
        flush=True
    )

    result = run_command(
        command,
        BUILD_DIR
    )

    if result.stdout.strip():

        print(
            result.stdout.strip(),
            flush=True
        )

    # IMPORTANT :
    # generated_svg est défini ici, dans cette fonction.

    generated_svg = None

    for candidate in possible_outputs:

        if candidate.exists() and candidate.is_file():

            generated_svg = candidate

            break

    if result.returncode != 0 or generated_svg is None:

        print(
            "Code retour pdftocairo :",
            result.returncode,
            flush=True
        )

        print(
            "Fichiers recherchés :",
            flush=True
        )

        for candidate in possible_outputs:

            print(
                candidate,
                "existe :", candidate.exists(),
                flush=True
            )

        raise RuntimeError(
            "Échec de conversion PDF vers SVG : "
            f"aucun fichier créé pour {pdf_file.name}."
        )

    # Déplacement vers le nom final souhaité

    if generated_svg != svg_file:

        if svg_file.exists():

            svg_file.unlink()

        generated_svg.rename(svg_file)


# ============================================================
# PROGRAMME PRINCIPAL
# ============================================================

def main():

    check_program(LATEX)

    check_program(PDF_TO_SVG)

    phrases = read_phrases(
        SOURCE_FILE
    )

    if not phrases:

        raise RuntimeError(
            "Aucune phrase exploitable dans phrases.txt."
        )

    print(
        f"{len(phrases)} phrase(s) trouvée(s).",
        flush=True
    )

    # Création des répertoires

    SVG_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    BUILD_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    # Fichier de mesure commun à toutes les phrases

    measurement_file = (
        BUILD_DIR / "terminaisons_mesures.tex"
    )

    create_measurement_file(
        phrases,
        measurement_file
    )

    shutil.copy2(
        measurement_file,
        OUTPUT_DIR / "terminaisons_mesures.tex"
    )

    manifest = []

    # ----------------------------------------
    # Génération des SVG
    # ----------------------------------------

    for index, phrase in enumerate(
        phrases,
        start=1
    ):

        phrase_id = f"phrase_{index:04d}"

        tex_file = (
            BUILD_DIR / f"{phrase_id}.tex"
        )

        svg_file = (
            SVG_DIR / f"{phrase_id}.svg"
        )

        print(
            f"\n[{index}/{len(phrases)}] "
            f"Génération de {phrase_id}",
            flush=True
        )

        # Construction du LaTeX

        tex_file.write_text(
            latex_document(phrase),
            encoding="utf-8"
        )

        print(
            " -> compilation LaTeX",
            flush=True
        )

        pdf_file = compile_latex(
            tex_file
        )

        print(
            " -> conversion PDF vers SVG",
            flush=True
        )

        convert_pdf_to_svg(
            pdf_file,
            svg_file
        )

        print(
            f" -> SVG créé : {svg_file.name}",
            flush=True
        )

        # Informations conservées dans le JSON

        manifest.append({

            "id": phrase_id,

            "category": phrase["category"],

            "source_line": phrase["source_line"],

            "text": phrase["text"],

            "subjects": phrase["subjects"],

            "verbs": phrase["verbs"],

            "targets": phrase["targets"],

            "svg": f"phrases_svg/{phrase_id}.svg",

        })

    # ----------------------------------------
    # Enregistrement du manifeste JSON
    # ----------------------------------------

    manifest_file = (
        OUTPUT_DIR / "phrases.json"
    )

    manifest_file.write_text(

        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2
        ) + "\n",

        encoding="utf-8"

    )

    # Copie du fichier source

    shutil.copy2(

        SOURCE_FILE,

        OUTPUT_DIR / "phrases.txt"

    )

    print()
    print("=" * 50)

    print(
        f"Terminé : {len(phrases)} SVG généré(s).",
        flush=True
    )

    print(
        f"Résultats : {OUTPUT_DIR}",
        flush=True
    )

    print(
        f"Manifest : {manifest_file}",
        flush=True
    )


# ============================================================
# POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":

    try:

        main()

    except Exception as error:

        print(
            f"\nERREUR : {error}",
            file=sys.stderr,
            flush=True
        )

        sys.exit(1)
