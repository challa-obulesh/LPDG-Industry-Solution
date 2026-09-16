LPDG INNOVATION HUB - SELECTION CHALLENGE 2026
==============================================

## Live Demo and Video Presentation

[Open the live Streamlit dashboard](https://lpdg-industry-solutionutmsource.streamlit.app/)

Face-to-face video presentation for the NEXORA 2026 — LPDG x RGMCET Challenge:

[Watch the Video](https://drive.google.com/file/d/194BmJCXJXUrbrouhyy7fZ5r_dRVATwVu/view?usp=drivesdk)

WHAT TO DO FIRST

  1. Read 01-Challenge-Brief.pdf. That is the whole task: what to build, which
     area to pick, what mistakes cost, and what to hand in.

  2. Read 02-Data-Dictionary.pdf. It explains every file and column in the data.

  3. Download 03-challenge-data.zip and unzip it. You will get a folder called
     "data". Keep that name - the brief and both scripts expect it.

WHAT IS IN HERE

  01-Challenge-Brief.pdf    The brief. Read this first.
  02-Data-Dictionary.pdf    Every file, every column, and how to load them.
  03-challenge-data.zip     The data. 70 MB to download, 105 MB unzipped.
  baseline_3sigma.py        A baseline that works. You may build on it as it is.
  validate_submission.py    Checks your predictions.csv before you hand in.
  README.txt                This file.

PART 1 QUICK START

  python -m pip install -r requirements.txt
  python baseline_3sigma.py --data 03-challenge-data/data --out predictions.csv
  python validate_submission.py predictions.csv

Part 1 uses the unchanged official 3-sigma baseline. The verified output is
120 rows across eight weeks, with exactly 15 ranked gateways per week.

If we invite you to a live session afterwards, we will hand you a month of data
nobody has seen, ask your thing to run on it while we watch, and ask you to make
one change live in the area you picked. If you picked machine learning, that means
improving your model on that month. Section "If we invite you to a live session"
in the brief has the detail. Build so that you can change it with people watching.

The data is for this exercise only. Please do not pass it on or publish it.

## Part 2 research reproducibility

Part 2 is a historical proxy-label research evaluation. It does not change the
official baseline, original challenge data, or `predictions.csv`, and it must not
be described as hidden-ground-truth performance.

Install the Part 2 dependencies from the repository root:

```powershell
python -m pip install -r requirements-part2.txt
```

Run the frozen Part 2 evaluation from the repository root:

```powershell
python run_part2.py
```

Final model: Logistic Regression.

The controlled model-selection record tested Logistic Regression, Random Forest,
Extra Trees and HistGradientBoosting under the same chronological splits,
eligible gateway population, top-15 selection, and cost formula. They produced
identical measured operational results, so Logistic Regression was retained for
simplicity, interpretability, computational efficiency, and reproducibility.

The verified forward comparison is EUR 329,400 for the unchanged 3-sigma
baseline and EUR 270,600 for Logistic Regression, a EUR 58,800 lower historical
proxy-label cost across eight weeks. This is not confirmed real-world savings.
These results are based on historical proxy labels and should not be presented
as official hidden-groundtruth performance. The separate unseen-gateway result
is documented in the Part 2 reports and is not an official challenge score.

Part 2 does not replace the Part 1 submission. It does not modify the official
baseline, original challenge data, or `predictions.csv`.

## Presentation dashboard

The read-only Streamlit dashboard presents both parts using the existing
predictions, reports, and artifacts. It does not retrain the model or regenerate
evaluation outputs.

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

Questions go to the address in your invitation email, by the dates in the
brief. Every answer goes to everyone.
