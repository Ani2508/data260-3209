import random

from database import Base, SessionLocal, engine
from models import Trial, TrialNote

SEED = 3209
random.seed(SEED)

SPONSORS = ["Stanford Medicine", "Mayo Clinic", "UCSF Health", "Johns Hopkins",
            "Cleveland Clinic", "Mass General", "Duke Health", "NYU Langone"]
STATUSES = ["Phase I", "Phase II", "Phase III", "Observational"]

Base.metadata.create_all(bind=engine)

db_session_basede26 = SessionLocal()

try:
    db_session_basede26.query(TrialNote).delete()
    db_session_basede26.query(Trial).delete()
    db_session_basede26.commit()

    trials = []
    for i in range(1, 5001):
        trials.append(Trial(
            trial_title=f"{random.choice(STATUSES)} Study #{i}",
            sponsor=random.choice(SPONSORS),
        ))
    db_session_basede26.add_all(trials)
    db_session_basede26.commit()

    trial_ids = [t.id for t in trials]

    notes = []
    for i in range(200):
        notes.append(TrialNote(
            trial_id=random.choice(trial_ids),
            note_text=f"Note {i + 1}: monitoring update for this trial.",
        ))
    db_session_basede26.add_all(notes)
    db_session_basede26.commit()

    print(f"Seeded {len(trials)} trials and {len(notes)} trial_notes (SEED={SEED}).")
finally:
    db_session_basede26.close()