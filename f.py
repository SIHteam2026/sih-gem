import sys
for i, line in enumerate(open('backend/app/services/contradiction_service.py', 'r')):
    if 'EVD-PRIMITIVE' in line:
        print(f'{i+1}: {line.strip()}')
