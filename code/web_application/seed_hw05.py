"""HW5 seed: rebuilds sponsors / trials / trial_notes with the new schema.

Users and sessions are kept. Run once after pulling the HW5 code:
    python seed_hw05.py
"""
import random

from sqlalchemy import inspect

from database import Base, SessionLocal, engine
from models import TRIAL_STATUSES, Sponsor, Trial, TrialNote

SEED = 3209
random.seed(SEED)

SPONSORS = [
    ("Stanford Medicine", "USA", "trials@stanfordmed.org"),
    ("Mayo Clinic", "USA", "research@mayoclinic.org"),
    ("UCSF Health", "USA", "ctsi@ucsfhealth.org"),
    ("Johns Hopkins Medicine", "USA", "trials@jhmi.edu"),
    ("Charite Berlin", "Germany", "studien@charite.de"),
    ("Tata Memorial Centre", "India", "crc@tmc.gov.in"),
    ("University of Toronto", "Canada", "trials@utoronto.ca"),
    ("Karolinska Institutet", "Sweden", "trials@ki.se"),
]
CONDITIONS = ["Type 2 Diabetes", "Hypertension", "Breast Cancer", "Asthma",
              "Alzheimer's Disease", "Rheumatoid Arthritis", "Migraine",
              "Chronic Kidney Disease", "Major Depression", "Psoriasis"]
PHASES = ["Phase I", "Phase II", "Phase III", "Observational"]
N_TRIALS = 40

# Old (HW4) trial tables have a different shape -> drop and recreate them.
tables = [TrialNote.__table__, Trial.__table__, Sponsor.__table__]
Base.metadata.drop_all(bind=engine, tables=tables)
Base.metadata.create_all(bind=engine)

db = SessionLocal()
try:
    sponsors = [Sponsor(name=n, country=c, contact_email=e) for n, c, e in SPONSORS]
    db.add_all(sponsors)
    db.commit()

    used = set()
    trials = []
    for i in range(1, N_TRIALS + 1):
        nct = f"NCT{random.randint(10_000_000, 99_999_999)}"
        while nct in used:
            nct = f"NCT{random.randint(10_000_000, 99_999_999)}"
        used.add(nct)
        status = random.choice(TRIAL_STATUSES)
        slots = random.randint(5, 300) if status == "Recruiting" else 0
        trials.append(Trial(
            trial_title=f"{random.choice(PHASES)} Study of Drug {chr(65 + i % 26)}-{i} "
                        f"in {random.choice(CONDITIONS)}",
            nct_id=nct, enrollment_slots=slots, status=status,
            sponsor_id=random.choice(sponsors).id,
        ))
    db.add_all(trials)
    db.commit()

    notes = [TrialNote(trial_id=random.choice(trials).id,
                       note_text=f"Note {i + 1}: monitoring update for this trial.")
             for i in range(40)]
    db.add_all(notes)
    db.commit()

    print(f"Seeded {len(sponsors)} sponsors, {len(trials)} trials, "
          f"{len(notes)} trial_notes (SEED={SEED}).")
    print("Tables:", inspect(engine).get_table_names())
finally:
    db.close()
