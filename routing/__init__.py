import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.getenv("PROJECT_PATH"))

from routing.resource_loader import create_place_resources
from routing.otp_builder import build_graph
from routing.vc_router_wrapper import route_virtual_commuters