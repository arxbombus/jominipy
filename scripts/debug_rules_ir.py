from pathlib import Path
from pprint import pprint

from jominipy.rules import load_rules_paths

root = Path(__file__).resolve().parents[1]
path: Path = Path(root, "references/hoi4-rules/Config/common/technologies.cwt")

loaded = load_rules_paths([path])

pprint(loaded.ruleset)
