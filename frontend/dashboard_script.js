// frontend/dashboard_script.js

const notificationsDiv = document.getElementById('notifications');
const loadHistoryBtn = document.getElementById('load-history-btn');
const historyTbody = document.getElementById('history-tbody');
const historyStatus = document.getElementById('history-status');

// --- Configuration ---
// Ensure this matches the host and port where your backend is running
// Use 'ws://' for non-secure WebSocket, 'wss://' for secure (if you set that up later)
const WEBSOCKET_URL = 'ws://127.0.0.1:8000/ws';
const API_BASE_URL = 'http://127.0.0.1:8000'; // Base URL for API calls

let ws; // Variable to hold the WebSocket connection

// --- WebSocket Connection ---
function connectWebSocket() {
    console.log('Attempting to connect WebSocket...');
    ws = new WebSocket(WEBSOCKET_URL);

    ws.onopen = (event) => {
        console.log('WebSocket connection established.');
        // Clear initial message maybe?
        if (notificationsDiv.querySelector('p')?.textContent.includes('Waiting')) {
             notificationsDiv.innerHTML = '<p>Connected. Waiting for new crash alerts...</p>';
        }
    };

    ws.onmessage = (event) => {
        console.log('Message received from server:', event.data);
        try {
            const message = JSON.parse(event.data);

            // Check if it's a new crash notification
            if (message.type === 'new_crash' && message.data) {
                addNotification(message.data);
            }
            // Add handling for other message types if needed
        } catch (error) {
            console.error('Failed to parse message or invalid message format:', error);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket Error:', error);
        // Optionally update UI to show connection error
        addNotification({ video_filename: 'WebSocket Error', detection_timestamp: new Date().toISOString() }, true); // Indicate error
    };

    ws.onclose = (event) => {
        console.log('WebSocket connection closed:', event.reason, `Code: ${event.code}`);
        // Attempt to reconnect after a delay
        notificationsDiv.innerHTML = '<p>WebSocket disconnected. Attempting to reconnect in 5 seconds...</p>';
        setTimeout(connectWebSocket, 5000); // Reconnect after 5 seconds
    };
}

// --- UI Updates ---
function addNotification(crashData, isError = false) {
    const item = document.createElement('div');
    item.classList.add('notification-item');
    if (isError) {
        item.style.backgroundColor = '#f8d7da'; // Make errors red
        item.style.borderColor = '#f5c6cb';
    }

    // Format timestamp for readability
    const timestamp = crashData.detection_timestamp ?
        new Date(crashData.detection_timestamp).toLocaleString() : 'N/A';

    item.innerHTML = `
        <strong>Crash Alert!</strong><br>
        Video: ${crashData.video_filename || 'Unknown Video'}<br>
        Time: ${timestamp}
    `;

    // Remove placeholder if it exists
     const placeholder = notificationsDiv.querySelector('p');
     if (placeholder && placeholder.textContent.includes('Waiting')) {
         notificationsDiv.innerHTML = ''; // Clear placeholder
     }

    notificationsDiv.prepend(item); // Add newest notification at the top

    // Optional: Limit number of notifications shown
    const maxNotifications = 20;
    while (notificationsDiv.children.length > maxNotifications) {
        notificationsDiv.removeChild(notificationsDiv.lastChild);
    }
}

// --- History Fetching ---
async function fetchCrashHistory() {
    console.log('Fetching crash history...');
    historyStatus.textContent = 'Loading history...';
    historyTbody.innerHTML = ''; // Clear previous history
    loadHistoryBtn.disabled = true;

    try {
        const response = await fetch(`${API_BASE_URL}/api/crashes/history`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const historyData = await response.json();

        if (historyData.length === 0) {
            historyStatus.textContent = 'No crash history found.';
        } else {
            historyStatus.textContent = ''; // Clear status
            historyData.forEach(crash => {
                const row = historyTbody.insertRow();
                row.insertCell(0).textContent = crash.id;
                // Format dates for display
                row.insertCell(1).textContent = new Date(crash.detection_timestamp).toLocaleString();
                row.insertCell(2).textContent = crash.video_filename;
                row.insertCell(3).textContent = new Date(crash.created_at).toLocaleString();
            });
        }

    } catch (error) {
        console.error('Error fetching crash history:', error);
        historyStatus.textContent = `Error loading history: ${error.message}`;
    } finally {
         loadHistoryBtn.disabled = false; // Re-enable button
    }
}


// --- Initial Setup ---
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket(); // Start WebSocket connection when the page loads

    // Add event listener for the history button
    loadHistoryBtn.addEventListener('click', fetchCrashHistory);

    // Optional: Load history immediately on page load
    // fetchCrashHistory();
});