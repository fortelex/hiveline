import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getenv("PROJECT_PATH"))

from mongo.db import *
