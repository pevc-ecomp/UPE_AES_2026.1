"""Generate a synthetic CSV dataset for testing the Article Evaluator's CSV
batch mode against the "Cardiovascular ML" example research protocol.

Protocol (see data/article_presets.json -> "Exemplo - ML para Doencas Cardiovasculares"):

Inclusion criteria (logic: 1 AND 2 AND 3):
  1. Published between 2019 and 2024
  2. Uses machine learning / deep learning as the main approach
  3. Addresses diagnosis, classification or prediction of cardiovascular disease (CVD)

Exclusion criteria (any one excludes the article):
  1. Written in a language other than English or Portuguese
  2. Is a literature review/survey without proposing or validating its own model
  3. Does not report quantitative performance metrics for the model

Distribution (60 rows):
  - 6  (10%) fully inside the protocol  -> expected_group = in_protocol
  - 9  (15%) meet exactly 2/3 inclusion criteria, no exclusions -> maybe
  - 45 (75%) outside the protocol (fail >=2 inclusion criteria and/or
       trigger an exclusion criterion) -> out_of_protocol
"""

import csv
import random

random.seed(42)

CVD_TOPICS = [
    ("arrhythmia detection from ECG signals", "arrhythmia, ECG, cardiac signal classification"),
    ("heart failure prediction in hospitalized patients", "heart failure, risk prediction, cardiology"),
    ("acute myocardial infarction classification", "myocardial infarction, cardiac biomarkers, classification"),
    ("atrial fibrillation detection in ECG signals", "atrial fibrillation, ECG, arrhythmia"),
    ("coronary artery disease diagnosis", "coronary artery disease, diagnosis, cardiology"),
    ("cardiovascular risk prediction in hypertensive patients", "hypertension, cardiovascular risk, prediction"),
    ("cardiac arrest prediction in ICU patients", "cardiac arrest, ICU, early warning systems"),
    ("cardiovascular risk stratification in routine checkups", "risk stratification, cardiovascular disease, prevention"),
    ("heart sound classification via phonocardiogram", "heart sounds, phonocardiogram, classification"),
    ("hospital readmission prediction for cardiac patients", "readmission, heart disease, hospital data"),
    ("valve stenosis detection from echocardiograms", "valve stenosis, echocardiogram, diagnosis"),
    ("hypertrophic cardiomyopathy diagnosis", "cardiomyopathy, diagnosis, cardiac imaging"),
]

NON_CVD_TOPICS = [
    ("type 2 diabetes diagnosis from laboratory results", "diabetes, classification, clinical data"),
    ("lung cancer detection from CT images", "lung cancer, CT imaging, classification"),
    ("Parkinson's disease diagnosis from gait analysis", "Parkinson's disease, gait analysis, classification"),
    ("COVID-19 detection from chest X-rays", "COVID-19, chest X-ray, image classification"),
    ("Alzheimer's disease classification from MRI scans", "Alzheimer's disease, MRI, classification"),
    ("chronic kidney disease prediction", "chronic kidney disease, prediction, clinical data"),
    ("sepsis prediction in ICU patients", "sepsis, ICU, early prediction"),
    ("breast cancer detection from mammography images", "breast cancer, mammography, image classification"),
    ("diabetic retinopathy detection from fundus images", "diabetic retinopathy, fundus images, classification"),
    ("depression detection from social media posts", "depression, social media, NLP"),
]

ML_METHODS = [
    "A Convolutional Neural Network",
    "A Long Short-Term Memory (LSTM) Network",
    "A Random Forest",
    "An Ensemble of XGBoost and SVM",
    "A Transformer-Based Architecture",
    "A Pre-Trained Residual Neural Network (ResNet)",
]

SPANISH_ROWS = [
    (
        "Un Enfoque de Aprendizaje Profundo para la Deteccion de Arritmias Cardiacas",
        "Este articulo propone una red neuronal convolucional para la deteccion de arritmias "
        "cardiacas a partir de senales de ECG, entrenada y validada con una base de datos "
        "clinica recolectada entre 2021 y 2023. El modelo propuesto alcanzo una precision "
        "del 96%, una sensibilidad del 94% y un AUC de 0.97, superando a los metodos de "
        "referencia evaluados.",
        "arritmia, ECG, aprendizaje profundo",
        2022,
    ),
    (
        "Prediccion de Insuficiencia Cardiaca Mediante Modelos de Aprendizaje Automatico",
        "Este estudio presenta un modelo ensemble basado en XGBoost y SVM para predecir "
        "la insuficiencia cardiaca en pacientes hospitalizados, utilizando datos clinicos "
        "recolectados entre 2020 y 2023. El modelo alcanzo una precision del 93%, una "
        "sensibilidad del 90% y un AUC de 0.95.",
        "insuficiencia cardiaca, aprendizaje automatico, prediccion",
        2023,
    ),
    (
        "Clasificacion de Fibrilacion Auricular Utilizando Redes LSTM",
        "Este trabajo propone una red de memoria a largo y corto plazo (LSTM) para la "
        "clasificacion de fibrilacion auricular a partir de senales de ECG recolectadas "
        "entre 2019 y 2022. El modelo logro una precision del 95%, una sensibilidad del 92% "
        "y un AUC de 0.96, superando los metodos tradicionales.",
        "fibrilacion auricular, ECG, LSTM",
        2021,
    ),
    (
        "Diagnostico de Enfermedad Arterial Coronaria con Random Forest",
        "Este articulo presenta un clasificador de random forest para el diagnostico de "
        "enfermedad arterial coronaria, entrenado con datos clinicos de 2020 a 2024. El "
        "modelo alcanzo una precision del 91%, una sensibilidad del 89% y un AUC de 0.93.",
        "enfermedad arterial coronaria, random forest, diagnostico",
        2024,
    ),
    (
        "Estratificacion del Riesgo Cardiovascular Mediante Transformers",
        "Este estudio propone una arquitectura basada en transformers para la "
        "estratificacion del riesgo cardiovascular en chequeos rutinarios, utilizando "
        "datos recolectados entre 2021 y 2024. El modelo logro una precision del 94%, "
        "una sensibilidad del 91% y un AUC de 0.96.",
        "riesgo cardiovascular, transformers, estratificacion",
        2023,
    ),
]


def metrics_sentence() -> str:
    acc = random.randint(85, 98)
    sens = random.randint(80, 97)
    auc = round(random.uniform(0.85, 0.99), 2)
    return (
        f"The proposed model achieved an accuracy of {acc}%, a sensitivity of {sens}%, "
        f"and an AUC of {auc}, outperforming the baseline methods evaluated."
    )


def no_metrics_sentence() -> str:
    return (
        "The findings are discussed qualitatively, and no quantitative performance "
        "metrics for the model are reported."
    )


def stat_sentence() -> str:
    return (
        "This study applies traditional statistical analysis (logistic regression and "
        "chi-square hypothesis testing), without employing machine learning techniques, "
        "and reports odds ratios and significance levels (p < 0.05) for each risk factor."
    )


def title_for(method: str, topic_en: str, year: int) -> str:
    return f"{method} Approach for {topic_en.capitalize()} ({year})"


def review_title_for(topic_en: str) -> str:
    return f"Machine Learning for {topic_en.capitalize()}: A Systematic Literature Review"


def original_abstract(method: str, topic_en: str, year: int, metrics: bool) -> str:
    body = (
        f"This paper presents {method.lower()} for {topic_en}, trained and validated "
        f"using a clinical dataset collected between {year - 2} and {year}. "
    )
    body += metrics_sentence() if metrics else no_metrics_sentence()
    return body


def stat_abstract(topic_en: str, year: int) -> str:
    body = (
        f"This paper investigates {topic_en} using clinical data collected between "
        f"{year - 2} and {year}. "
    )
    body += stat_sentence()
    return body


def review_abstract(topic_en: str) -> str:
    return (
        f"This paper presents a systematic literature review of machine learning and "
        f"deep learning approaches for {topic_en}, synthesizing trends, open challenges "
        f"and future research directions, without proposing or validating a new model "
        f"of its own."
    )


rows: list[dict] = []

# ── Group A (6 rows, 10%) — fully inside the protocol ──────────────────────────
for i in range(6):
    topic_en, kw = CVD_TOPICS[i]
    method = ML_METHODS[i % len(ML_METHODS)]
    year = random.choice([2019, 2020, 2021, 2022, 2023, 2024])
    rows.append({
        "title": title_for(method, topic_en, year),
        "abstract": original_abstract(method, topic_en, year, metrics=True),
        "keywords": kw,
        "year": year,
        "expected_group": "in_protocol",
        "expected_notes": "Meets all 3 inclusion criteria; no exclusion criteria triggered.",
    })

# ── Group B1 (3 rows) — CVD + ML + metrics, but year out of range ──────────────
for i in range(3):
    topic_en, kw = CVD_TOPICS[(6 + i) % len(CVD_TOPICS)]
    method = ML_METHODS[(6 + i) % len(ML_METHODS)]
    year = random.choice([2015, 2016, 2017, 2018])
    rows.append({
        "title": title_for(method, topic_en, year),
        "abstract": original_abstract(method, topic_en, year, metrics=True),
        "keywords": kw,
        "year": year,
        "expected_group": "maybe",
        "expected_notes": "Meets inclusion criteria 2 and 3, but published before 2019 (fails criterion 1).",
    })

# ── Group B2 (3 rows) — CVD topic + statistical (non-ML), year in range ────────
for i in range(3):
    topic_en, kw = CVD_TOPICS[(9 + i) % len(CVD_TOPICS)]
    year = random.choice([2019, 2020, 2021, 2022, 2023, 2024])
    rows.append({
        "title": f"Statistical Risk Factor Analysis for {topic_en.capitalize()} ({year})",
        "abstract": stat_abstract(topic_en, year),
        "keywords": kw,
        "year": year,
        "expected_group": "maybe",
        "expected_notes": "Meets inclusion criteria 1 and 3, but does not use machine learning (fails criterion 2).",
    })

# ── Group B3 (3 rows) — non-CVD topic + ML + metrics, year in range ────────────
for i in range(3):
    topic_en, kw = NON_CVD_TOPICS[i]
    method = ML_METHODS[(2 + i) % len(ML_METHODS)]
    year = random.choice([2019, 2020, 2021, 2022, 2023, 2024])
    rows.append({
        "title": title_for(method, topic_en, year),
        "abstract": original_abstract(method, topic_en, year, metrics=True),
        "keywords": kw,
        "year": year,
        "expected_group": "maybe",
        "expected_notes": "Meets inclusion criteria 1 and 2, but does not address cardiovascular disease (fails criterion 3).",
    })

# ── Group C1 (10 rows) — literature reviews on CVD/ML topics (exclusion 2) ─────
for i in range(10):
    topic_en, kw = CVD_TOPICS[i % len(CVD_TOPICS)]
    rows.append({
        "title": review_title_for(topic_en),
        "abstract": review_abstract(topic_en),
        "keywords": kw,
        "year": random.choice([2020, 2021, 2022, 2023, 2024]),
        "expected_group": "out_of_protocol",
        "expected_notes": "Literature review without its own model -> triggers exclusion criterion 2.",
    })

# ── Group C2 (10 rows) — CVD + ML, original study, but no metrics (exclusion 3) ─
for i in range(10):
    topic_en, kw = CVD_TOPICS[i % len(CVD_TOPICS)]
    method = ML_METHODS[i % len(ML_METHODS)]
    year = random.choice([2019, 2020, 2021, 2022, 2023, 2024])
    rows.append({
        "title": title_for(method, topic_en, year),
        "abstract": original_abstract(method, topic_en, year, metrics=False),
        "keywords": kw,
        "year": year,
        "expected_group": "out_of_protocol",
        "expected_notes": "No quantitative performance metrics reported -> triggers exclusion criterion 3.",
    })

# ── Group C3 (5 rows) — CVD + ML + metrics, but written in Spanish (exclusion 1) ─
for title, abstract, kw, year in SPANISH_ROWS:
    rows.append({
        "title": title,
        "abstract": abstract,
        "keywords": kw,
        "year": year,
        "expected_group": "out_of_protocol",
        "expected_notes": "Written in Spanish -> triggers exclusion criterion 1.",
    })

# ── Group C4 (10 rows) — fail exactly 2 inclusion criteria, no exclusions ──────
# C4a: non-CVD + ML + metrics, year out of range (fails criteria 1 and 3)
for i in range(4):
    topic_en, kw = NON_CVD_TOPICS[(3 + i) % len(NON_CVD_TOPICS)]
    method = ML_METHODS[(1 + i) % len(ML_METHODS)]
    year = random.choice([2015, 2016, 2017, 2018])
    rows.append({
        "title": title_for(method, topic_en, year),
        "abstract": original_abstract(method, topic_en, year, metrics=True),
        "keywords": kw,
        "year": year,
        "expected_group": "out_of_protocol",
        "expected_notes": "Non-cardiovascular topic and published before 2019 -> fails criteria 1 and 3.",
    })

# C4b: CVD topic + statistical (non-ML), year out of range (fails criteria 1 and 2)
for i in range(3):
    topic_en, kw = CVD_TOPICS[(i + 3) % len(CVD_TOPICS)]
    year = random.choice([2015, 2016, 2017, 2018])
    rows.append({
        "title": f"Statistical Risk Factor Analysis for {topic_en.capitalize()} ({year})",
        "abstract": stat_abstract(topic_en, year),
        "keywords": kw,
        "year": year,
        "expected_group": "out_of_protocol",
        "expected_notes": "Non-ML statistical study published before 2019 -> fails criteria 1 and 2.",
    })

# C4c: non-CVD + statistical (non-ML), year in range (fails criteria 2 and 3)
for i in range(3):
    topic_en, kw = NON_CVD_TOPICS[(6 + i) % len(NON_CVD_TOPICS)]
    year = random.choice([2019, 2020, 2021, 2022, 2023, 2024])
    rows.append({
        "title": f"Statistical Risk Factor Analysis for {topic_en.capitalize()} ({year})",
        "abstract": stat_abstract(topic_en, year),
        "keywords": kw,
        "year": year,
        "expected_group": "out_of_protocol",
        "expected_notes": "Non-cardiovascular, non-ML statistical study -> fails criteria 2 and 3.",
    })

# ── Group C5 (10 rows) — fail all 3 inclusion criteria, no exclusions ──────────
for i in range(10):
    topic_en, kw = NON_CVD_TOPICS[i % len(NON_CVD_TOPICS)]
    year = random.choice([2014, 2015, 2016, 2017, 2018])
    rows.append({
        "title": f"Statistical Risk Factor Analysis for {topic_en.capitalize()} ({year})",
        "abstract": stat_abstract(topic_en, year),
        "keywords": kw,
        "year": year,
        "expected_group": "out_of_protocol",
        "expected_notes": "Non-cardiovascular, non-ML, published before 2019 -> fails all 3 inclusion criteria.",
    })

assert len(rows) == 60, f"Expected 60 rows, got {len(rows)}"

n_in = sum(1 for r in rows if r["expected_group"] == "in_protocol")
n_maybe = sum(1 for r in rows if r["expected_group"] == "maybe")
n_out = sum(1 for r in rows if r["expected_group"] == "out_of_protocol")
print(f"in_protocol={n_in} maybe={n_maybe} out_of_protocol={n_out} total={len(rows)}")

random.shuffle(rows)

with open("data/sample_articles_cardio_ml.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["title", "abstract", "keywords", "year", "expected_group", "expected_notes"],
    )
    writer.writeheader()
    writer.writerows(rows)

print("Wrote data/sample_articles_cardio_ml.csv")
