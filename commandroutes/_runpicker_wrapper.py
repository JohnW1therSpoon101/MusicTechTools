import sys, subprocess, os
outf = r"/Users/jaydenstern/Documents/GitHub/youtube2audaisplitter/commandroutes/_selected_path.txt"
p = subprocess.run([sys.executable, r"/Users/jaydenstern/Documents/GitHub/youtube2audaisplitter/plumming/getaudiofile1.py"], capture_output=True, text=True)
if p.stdout.strip():
    with open(outf, "w", encoding="utf-8") as f:
        f.write(p.stdout.strip())
