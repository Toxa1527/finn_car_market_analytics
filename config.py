# finn_project/config.py

###
import os
###

BASE_URL = "https://www.finn.no/mobility/search/car?last_search=false&registration_class=1"

DB_DIR = os.path.join(os.path.dirname(__file__), "database")
DB_PATH = os.path.join(DB_DIR, "cars.db")

update_interval = 3600
