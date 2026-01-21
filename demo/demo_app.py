#!/usr/bin/env python3
"""
Demo App Wrapper for VM Monitor.
Wraps the main dashboard app and injects a demo banner.
This keeps demo code completely separate from production.
"""

import os
import sys

# Add dashboard to path
DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), '..', 'dashboard')
sys.path.insert(0, DASHBOARD_DIR)

# Set working directory to dashboard for template loading
os.chdir(DASHBOARD_DIR)

# Import the main app
from app import app

# Demo banner HTML to inject
DEMO_BANNER = '''
<div id="demo-banner" style="
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    text-align: center;
    padding: 12px 20px;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 9999;
    box-shadow: 0 2px 10px rgba(0,0,0,0.3);
">
    <strong>🎮 DEMO MODE</strong> — This is a demonstration with simulated data. 
    <a href="https://github.com/aydinguven/vm-monitor" target="_blank" 
       style="color: #ffe066; text-decoration: underline; margin-left: 10px;">
       Get the real thing →
    </a>
</div>
<style>
    /* Push content down to account for fixed banner */
    body { padding-top: 50px !important; }
</style>
'''

@app.after_request
def inject_demo_banner(response):
    """Inject demo banner into HTML responses."""
    if response.content_type and 'text/html' in response.content_type:
        try:
            html = response.get_data(as_text=True)
            # Inject banner after <body> tag
            if '<body' in html:
                html = html.replace('<body>', f'<body>{DEMO_BANNER}', 1)
                # Also replace any <body ...> with attributes
                import re
                html = re.sub(r'(<body[^>]*>)', rf'\1{DEMO_BANNER}', html, count=1)
                response.set_data(html)
        except Exception as e:
            # If injection fails, just return original response
            pass
    return response


if __name__ == '__main__':
    print("🎮 Starting VM Monitor DEMO")
    print("   Banner injection enabled")
    print("")
    app.run(host='0.0.0.0', port=5000, debug=False)
