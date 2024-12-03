#!/bin/bash

# Create conf directory if it doesn't exist
mkdir -p conf

# Set password
echo "conf passw test_password"
hummingbot_conf_path="conf" hummingbot_password="test_password" python3 -c "
from hummingbot.client.config.security import Security;
Security.login(input('conf passw '), input('conf path '));
"

# Set password again (sometimes needed)
echo "conf passw test_password"
hummingbot_conf_path="conf" hummingbot_password="test_password" python3 -c "
from hummingbot.client.config.security import Security;
Security.login(input('conf passw '), input('conf path '));
"

# Set environment variables
export BIRDEYE_API_KEY="YOUR-API-KEY-HERE"  # Replace with actual API key if needed
export PYTHONPATH=/backend-api:$PYTHONPATH