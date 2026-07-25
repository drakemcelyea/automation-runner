#!/bin/bash

sudo pkill -f "/opt/automation-runner/run.py"
sudo pkill -f "uvicorn"

sleep 1

echo "=== Fixing permissions ==="
sudo chmod 777 -R /home/lcl_admin/

sudo rm -rf /opt/automation-runner/app/main.py
sudo rm -rf /opt/automation-runner/app/static/js/index.js
sudo rm -rf /opt/automation-runner/app/templates/index.html

sudo cp /home/lcl_admin/main.py /opt/automation-runner/app/
sudo cp /home/lcl_admin/index.js /opt/automation-runner/app/static/js/
sudo cp /home/lcl_admin/index.html /opt/automation-runner/app/templates/

sudo chown automationsvc:automationsvc /opt/automation-runner/app/main.py
sudo chown automationsvc:automationsvc /opt/automation-runner/app/static/js/index.js
sudo chown automationsvc:automationsvc /opt/automation-runner/app/templates/index.html
sudo chmod 644 /opt/automation-runner/app/main.py
sudo chmod 644 /opt/automation-runner/app/static/js/index.js
sudo chmod 644 /opt/automation-runner/app/templates/index.html

echo "=== Restarting service ==="

sudo systemctl restart automation-runner.service

echo "=== Verifying service ==="

sudo systemctl status automation-runner.service --no-pager

echo "=== Done ==="
