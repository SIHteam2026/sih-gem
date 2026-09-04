import difflib
with open('remote_file.txt', 'r') as f:
    remote = f.readlines()
with open('backend/app/services/claim_extraction_service.py', 'r') as f:
    local = f.readlines()
for line in difflib.unified_diff(remote, local, fromfile='remote', tofile='local'):
    if not line.startswith('---') and not line.startswith('+++') and not line.startswith('@@') and (line.startswith('+') or line.startswith('-')):
        print(line, end='')
