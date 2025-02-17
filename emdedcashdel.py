import shutil
import os

cache_dir = os.path.join(os.path.expanduser("~"), ".cache", "torch")
if os.path.exists(cache_dir):
    shutil.rmtree(cache_dir)