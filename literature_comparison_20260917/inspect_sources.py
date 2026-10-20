"""Read-only source inspection; writes only a new source-image QA derivative."""
from pathlib import Path
from pypdf import PdfReader
import pdfplumber
import json

root = Path(__file__).resolve().parent.parent
sources = root / 'literature_screen_20260917/sources'
dest = Path(__file__).resolve().parent / 'source_previews/aminzadeh_figure3_native.jpg'
if not dest.exists():
    PdfReader(sources / 'aminzadeh_2025_permeability.pdf').pages[4].images[0].image.save(dest)
ameen_dest = dest.parent / 'ameen_figure3_native.png'
if not ameen_dest.exists():
    for im in PdfReader(sources / 'ameen_2024_spheres.pdf').pages[8].images:
        if im.image.size == (1000, 652):
            im.image.save(ameen_dest)
with pdfplumber.open(sources / 'es2c09822_si_001.pdf') as pdf:
    p = pdf.pages[18]
    print('YU tick labels:', [(w['text'],w['x0'],w['top'],w['bottom']) for w in p.extract_words() if 420 < w['top'] < 565])
    print('YU missing point area:', [{k:o.get(k) for k in ['object_type','x0','x1','top','bottom','stroking_color','non_stroking_color','text']} for o in p.lines+p.curves+p.chars if 170 < o['x0'] < 176 and 440 < o['top'] < 535])
    print('YU table S1:', pdf.pages[4].extract_text())
for path in [root/'stage134_evaluations/sphere_combined_budget_refinement_20260916/independent_evaluation_01/results.json', root/'stage31_evaluations/stage31f_selected_replicated_cpd4_20260827/gpu_evaluation_02/evaluation.json']:
    d = json.loads(path.read_text())
    print(path.name, list(d))
    for key in ['paired_results','combined_budgets','observations','comparisons','summary']:
        if key in d:
            print(key, json.dumps(d[key])[:6000])
