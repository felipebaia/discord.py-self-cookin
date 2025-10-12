# create and activate a virtual environment, then install dependencies
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -r requirements.txt

# running the local server
echo "Initializing local server..."
python3 src/local_server.py &
sleep 2

# running the local server
echo "Creating multi tabs..."
python3 src/test_multi_tabs.py &
sleep 2

# running selfbot
echo "Starting selfbot..."
python3 src/selfbot_monitor.py