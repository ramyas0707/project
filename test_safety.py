import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from app.main import clean_path

def test_clean_path_accepts_normal_file():
    assert clean_path("src/main.py") == "src/main.py"

def test_clean_path_blocks_traversal():
    try:
        clean_path("../secret.txt")
        assert False
    except ValueError:
        assert True

def test_clean_path_blocks_env():
    try:
        clean_path(".env")
        assert False
    except ValueError:
        assert True
