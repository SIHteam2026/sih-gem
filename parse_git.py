import zlib
import os
def get_object(sha):
    path = os.path.join('.git', 'objects', sha[:2], sha[2:])
    if not os.path.exists(path): return None
    with open(path, 'rb') as f:
        return zlib.decompress(f.read())

def get_tree(sha):
    obj = get_object(sha)
    if not obj: return {}
    type_end = obj.find(b'\x00')
    content = obj[type_end+1:]
    entries = {}
    while content:
        mode_end = content.find(b' ')
        mode = content[:mode_end].decode()
        name_end = content.find(b'\x00', mode_end)
        name = content[mode_end+1:name_end].decode()
        entry_sha = content[name_end+1:name_end+21].hex()
        entries[name] = (mode, entry_sha)
        content = content[name_end+21:]
    return entries

def find_file_sha(commit_sha, filepath):
    obj = get_object(commit_sha)
    type_end = obj.find(b'\x00')
    content = obj[type_end+1:].decode()
    tree_sha = [line.split(' ')[1] for line in content.split('\n') if line.startswith('tree')][0]
    
    parts = filepath.split('/')
    curr_sha = tree_sha
    for part in parts:
        tree = get_tree(curr_sha)
        if part not in tree: return None
        mode, curr_sha = tree[part]
    return curr_sha

remote_sha = '391a9d31e3239840e9b2cb970a26f4621eb0d40d'
file_sha = find_file_sha(remote_sha, 'backend/app/services/claim_extraction_service.py')
if file_sha:
    content = get_object(file_sha)
    type_end = content.find(b'\x00')
    print("REMOTE FILE FOUND")
    # print(content[type_end+1:].decode())
    with open('remote_file.txt', 'wb') as f:
        f.write(content[type_end+1:])
else:
    print("FILE NOT FOUND IN REMOTE")
