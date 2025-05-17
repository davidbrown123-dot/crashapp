const notificationsDiv = document.getElementById('notifications');
const weatherInfoDiv = document.getElementById('weather-info');
const locationStatusP = document.getElementById('location-status');
const refreshWeatherBtn = document.getElementById('refresh-weather-btn');

// --- Configuration --- (Keep your ngrok URL placeholder - UPDATE MANUALLY LATER)
const NGROK_HTTPS_URL = 'https://c813-50-234-34-194.ngrok-free.app'; // <<<--- PASTE CURRENT NGROK URL HERE BEFORE BUILDING
const WEBSOCKET_URL = `wss://${NGROK_HTTPS_URL.replace(/^https?:\/\//, '')}/ws`;
const API_BASE_URL = NGROK_HTTPS_URL;

let ws;

// --- WebSocket Connection --- (Function remains the same)
function connectWebSocket() {
    console.log('Attempting WebSocket connection to:', WEBSOCKET_URL);
    ws = new WebSocket(WEBSOCKET_URL);
    ws.onopen = () => { console.log('WebSocket connection established.'); if (notificationsDiv.querySelector('p')?.textContent.includes('Waiting')) { notificationsDiv.innerHTML = '<p>Connected. Waiting for new crash alerts...</p>'; } };
    ws.onmessage = (event) => { console.log('Message received:', event.data); try { const message = JSON.parse(event.data); if (message.type === 'new_crash' && message.data) { addUserNotification(message.data); } } catch (error) { console.error('Failed to parse message:', error); } };
    ws.onerror = (error) => { console.error('WebSocket Error occurred:', error); addUserNotification({ video_filename: `WebSocket Conn Error to ${WEBSOCKET_URL}`, detection_timestamp: new Date().toISOString() }, true); };
    ws.onclose = (event) => { console.log(`WebSocket disconnected. Code: ${event.code}, Reason: "${event.reason}". Reconnecting...`); notificationsDiv.innerHTML = '<p>WebSocket disconnected. Attempting to reconnect...</p>'; setTimeout(connectWebSocket, 5000); };
}

// --- UI Updates --- (Function remains the same)
function addUserNotification(crashData, isError = false) {
    const item = document.createElement('div'); item.classList.add(isError ? 'notification-item-user-error' : 'notification-item-user'); const timestamp = crashData.detection_timestamp ? new Date(crashData.detection_timestamp).toLocaleString() : 'N/A'; item.innerHTML = `<strong>Alert:</strong> A crash detected.<br>Time: ${timestamp}<br>Ref: ${crashData.video_filename || 'N/A'}`; if (isError) { item.style.backgroundColor = '#f8d7da'; item.style.borderColor = '#f5c6cb'; item.innerHTML = `<strong>Connection Issue:</strong> ${crashData.video_filename || 'Unknown'}`; } const placeholder = notificationsDiv.querySelector('p'); if (placeholder && placeholder.textContent.includes('Waiting')) { notificationsDiv.innerHTML = ''; } notificationsDiv.prepend(item); const maxNotifications = 10; while (notificationsDiv.children.length > maxNotifications) { notificationsDiv.removeChild(notificationsDiv.lastChild); }
}

// --- Weather & Speed --- (Function remains the same)
async function fetchWeatherAndSpeed(latitude = null, longitude = null) {
    console.log(`Fetching weather from: ${API_BASE_URL}/api/weather_conditions with Lat: ${latitude}, Lon: ${longitude}`);
    weatherInfoDiv.innerHTML = '<p>Fetching weather data...</p>'; locationStatusP.textContent = 'Requesting weather...'; refreshWeatherBtn.disabled = true; let url = `${API_BASE_URL}/api/weather_conditions`; if (latitude !== null && longitude !== null) { url += `?lat=${latitude}&lon=${longitude}`; } else { locationStatusP.textContent = 'Using default location for weather.'; }
    try {
        const response = await fetch(url);
        if (!response.ok) { let errorDetail = `HTTP error! status: ${response.status}`; try { const errorJson = await response.json(); errorDetail += ` - ${errorJson.detail || JSON.stringify(errorJson)}`;} catch (e) { /* ignore */ } throw new Error(errorDetail); }
        const data = await response.json(); weatherInfoDiv.innerHTML = `<p><strong>Weather:</strong> ${data.weather_desc || 'N/A'}</p><p><strong>Visibility:</strong> ${data.visibility_km !== null ? data.visibility_km + ' km' : 'N/A'}</p><p><strong>Raining:</strong> ${data.is_raining ? 'Yes' : 'No'}</p><p><strong>Max Safe Speed:</strong> ${data.safe_speed_kmh} km/h</p>`; locationStatusP.textContent = `Weather based on: ${data.location_used}`;
    } catch (error) { console.error('Error fetching weather data:', error); weatherInfoDiv.innerHTML = `<p style="color: red;">Could not load weather data: ${error.message}</p>`; locationStatusP.textContent = 'Failed to get weather.';
    } finally { refreshWeatherBtn.disabled = false; }
}

// <<<--- Step 3: Add New Function using Capacitor Plugin --- >>>
async function requestLocationAndFetchWeather() {
    console.log("Requesting location via Capacitor plugin...");
    locationStatusP.textContent = 'Requesting location permission...';
    refreshWeatherBtn.disabled = true; // Disable button while requesting

    try {
        // Check if Geolocation plugin is available
        // Note: The import might make Geolocation directly available,
        // or sometimes Capacitor puts it under Capacitor.Plugins.Geolocation
        const GeolocationPlugin = (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins.Geolocation) ? Capacitor.Plugins.Geolocation : Geolocation;

        if (!GeolocationPlugin) {
             throw new Error("Geolocation plugin is not available. Check import/Capacitor setup.");
        }

        // 1. Request Permission
        const permStatus = await GeolocationPlugin.requestPermissions();
        console.log('Permission status:', permStatus);

        if (permStatus.location === 'granted' || permStatus.location === 'prompt-with-rationale') { // Treat prompt-with-rationale as potential grant
            locationStatusP.textContent = 'Permission granted. Getting position...';
            // 2. Get Current Position
            const position = await GeolocationPlugin.getCurrentPosition({
                enableHighAccuracy: false, // Set to true for GPS, false for faster/coarse
                timeout: 10000 // 10 seconds
            });
            console.log('Position acquired:', position);
            locationStatusP.textContent = 'Location acquired.';
            // 3. Fetch Weather with coordinates
            fetchWeatherAndSpeed(position.coords.latitude, position.coords.longitude);

        } else {
            // Permission denied
            console.warn('Location permission denied by user.');
            locationStatusP.textContent = 'Location permission denied. Using default location.';
            fetchWeatherAndSpeed(); // Use default
        }
    } catch (error) {
        // Handle errors
        console.error('Capacitor Geolocation Error:', error);
        locationStatusP.textContent = `Could not get location: ${error.message}. Using default.`;
        fetchWeatherAndSpeed(); // Use default
    } finally {
         // fetchWeatherAndSpeed re-enables the button in its finally block
    }
}


// --- Initial Setup ---
document.addEventListener('DOMContentLoaded', () => {
    connectWebSocket(); // Start WebSocket

    // <<<--- Step 4: Call the NEW location function --- >>>
    requestLocationAndFetchWeather(); // Use the plugin function on load

    // Add event listener for the refresh button to call the NEW function
    refreshWeatherBtn.addEventListener('click', requestLocationAndFetchWeather);
});