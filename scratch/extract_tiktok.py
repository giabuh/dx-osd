import sys, re, json
sys.stdout.reconfigure(encoding='utf-8')
f = open(r'C:\Users\ASUS\.gemini\antigravity-cli\brain\0755ef5a-a058-44e9-94cd-642246088fd0\.system_generated\steps\3383\content.md', 'r', encoding='utf-8', errors='ignore').read()
m = re.search(r'<script[^>]*id=\"VideoObject\"[^>]*>(.*?)</script>', f, re.DOTALL)
if m:
    data = json.loads(m.group(1))
    print(json.dumps(data, indent=2, ensure_ascii=False))
