#!/bin/bash
echo "Avvio della Piattaforma Strategica Auxilium..."

# Install requirements if not already installed
echo "Installazione dipendenze backend..."
pip3 install -r backend/requirements.txt

# Start backend in the background
echo "Avvio Backend (FastAPI) su porta 8005..."
python3 backend/main.py &
BACKEND_PID=$!

# Start frontend in the foreground
echo "Avvio Frontend su http://localhost:8080..."
cd frontend
python3 -m http.server 8080 &
FRONTEND_PID=$!

echo "=================================================="
echo " Piattaforma Strategica Attiva!"
echo " Backend API: http://localhost:8005"
echo " Frontend App: http://localhost:8080"
echo "=================================================="
echo "Premi Ctrl+C per fermare tutti i server"

# Wait for Ctrl+C
trap "kill $BACKEND_PID $FRONTEND_PID" SIGINT
wait
