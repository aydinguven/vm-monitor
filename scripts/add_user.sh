#!/bin/bash
# Add User Script - Create additional dashboard users
# Usage: sudo /opt/vm-monitor/scripts/add_user.sh

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

INSTALL_DIR="/opt/vm-monitor"

if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}Error: VM Monitor not found at $INSTALL_DIR${NC}"
    exit 1
fi

echo -e "${GREEN}VM Monitor - Add User${NC}"
echo "=============================="
echo ""

# Get username
while true; do
    read -p "Username: " username
    if [ -z "$username" ]; then
        echo -e "${YELLOW}Username cannot be empty.${NC}"
        continue
    fi
    break
done

# Get password (hidden input)
while true; do
    read -sp "Password: " password
    echo ""
    
    if [ ${#password} -lt 6 ]; then
        echo -e "${YELLOW}Password must be at least 6 characters.${NC}"
        continue
    fi
    
    read -sp "Confirm password: " password_confirm
    echo ""
    
    if [ "$password" != "$password_confirm" ]; then
        echo -e "${YELLOW}Passwords do not match. Try again.${NC}"
        continue
    fi
    break
done

# Create user
cd "$INSTALL_DIR"
sudo ./venv/bin/python3 -c "
from app import app, db
from models import User

with app.app_context():
    # Check if user exists
    existing = User.query.filter_by(username='$username').first()
    if existing:
        print('Error: User already exists')
        exit(1)
    
    # Create user
    user = User(username='$username')
    user.set_password('$password')
    db.session.add(user)
    db.session.commit()
    print(f'✓ User \"{username}\" created successfully')
"

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}User added successfully!${NC}"
else
    echo ""
    echo -e "${RED}Failed to create user.${NC}"
    exit 1
fi
