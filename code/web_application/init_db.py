from sqlalchemy import inspect

import models  # noqa: F401  (registers the tables)
from database import Base, engine

Base.metadata.create_all(bind=engine)
print("Tables in s3209_rel:", inspect(engine).get_table_names())