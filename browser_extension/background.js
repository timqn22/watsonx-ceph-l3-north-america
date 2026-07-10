// Background service worker for Ceph Tracker Linker extension
// Handles API communication and state management

const API_BASE_URL = 'http://localhost:5001';

// Listen for messages from content scripts
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log('Background received message:', request.type);

    if (request.type === 'GET_RECOMMENDATIONS') {
        handleGetRecommendations(request.data, sendResponse);
        return true; // Keep channel open for async response
    }

    if (request.type === 'GET_TRACKER_INFO') {
        handleGetTrackerInfo(request.trackerId, sendResponse);
        return true;
    }

    if (request.type === 'GET_PR_INFO') {
        handleGetPRInfo(request.prNumber, sendResponse);
        return true;
    }

    if (request.type === 'CHECK_API_STATUS') {
        handleCheckAPIStatus(sendResponse);
        return true;
    }
});

// Get recommendations for a tracker or PR
async function handleGetRecommendations(data, sendResponse) {
    try {
        const endpoint = data.type === 'tracker'
            ? `${API_BASE_URL}/api/recommendations/tracker/${data.id}`
            : `${API_BASE_URL}/api/recommendations/pr/${data.number}`;

        console.log('Fetching recommendations from:', endpoint);

        const response = await fetch(endpoint, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            throw new Error(`API returned ${response.status}: ${response.statusText}`);
        }

        const result = await response.json();
        console.log('Recommendations received:', result);

        sendResponse({ success: true, data: result });
    } catch (error) {
        console.error('Error fetching recommendations:', error);
        sendResponse({
            success: false,
            error: error.message,
            suggestion: 'Make sure Python API is running on localhost:5001'
        });
    }
}

// Get detailed tracker information
async function handleGetTrackerInfo(trackerId, sendResponse) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/trackers/${trackerId}`);

        if (!response.ok) {
            throw new Error(`API returned ${response.status}`);
        }

        const result = await response.json();
        sendResponse({ success: true, data: result });
    } catch (error) {
        console.error('Error fetching tracker info:', error);
        sendResponse({ success: false, error: error.message });
    }
}

// Get detailed PR information
async function handleGetPRInfo(prNumber, sendResponse) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/prs/${prNumber}`);

        if (!response.ok) {
            throw new Error(`API returned ${response.status}`);
        }

        const result = await response.json();
        sendResponse({ success: true, data: result });
    } catch (error) {
        console.error('Error fetching PR info:', error);
        sendResponse({ success: false, error: error.message });
    }
}

// Check if Python API is running
async function handleCheckAPIStatus(sendResponse) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/health`, {
            method: 'GET',
            signal: AbortSignal.timeout(3000) // 3 second timeout
        });

        if (!response.ok) {
            throw new Error('API not healthy');
        }

        const result = await response.json();
        sendResponse({ success: true, data: result });
    } catch (error) {
        console.error('API health check failed:', error);
        sendResponse({
            success: false,
            error: 'Python API is not running',
            suggestion: 'Start the API with: cd python_service && python api/app.py'
        });
    }
}

// Extension installation handler
chrome.runtime.onInstalled.addListener((details) => {
    if (details.reason === 'install') {
        console.log('Ceph Tracker Linker extension installed');

        // Set default settings
        chrome.storage.sync.set({
            apiUrl: API_BASE_URL,
            autoLoad: true,
            minSimilarity: 0.5
        });
    }
});

console.log('Ceph Tracker Linker background service worker loaded');

// Made with Bob
