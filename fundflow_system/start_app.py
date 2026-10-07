import subprocess
import os

os.environ['STREAMLIT_BROWSER_GATHER_USAGE_STATS'] = 'false'
os.environ['STREAMLIT_FIRST_RUN'] = 'false'

script_path = os.path.join(os.path.dirname(__file__), 'dashboard.py')

for port in [8501, 8502, 8503, 8504, 8505]:
    cmd = ['python', '-m', 'streamlit', 'run', script_path, '--server.port', str(port), '--browser.gatherUsageStats', 'false']
    print(f"Trying port {port}...")
    try:
        subprocess.run(cmd, check=True)
        exit(0)
    except subprocess.CalledProcessError:
        continue

print("All ports 8501-8505 are in use. Please close other Streamlit processes and try again.")