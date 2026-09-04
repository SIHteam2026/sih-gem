import zlib
import os
import glob
def get_object(sha):
    path = os.path.join('.git', 'objects', sha[:2], sha[2:])
    if not os.path.exists(path): return None
    with open(path, 'rb') as f:
        return zlib.decompress(f.read())
print(get_object('391a9d31e3239840e9b2cb970a26f4621eb0d40d')[:100])
