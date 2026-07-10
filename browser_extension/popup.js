// Popup script for Ceph Tracker Linker extension

document.addEventListener('DOMContentLoaded', async () => {
    console.log('Popup loaded');

    // Check API status
    await checkAPIStatus();

    // Get current page info
    await getCurrentPageInfo();

    // Set up event listeners
    setupEventListeners();
});

// Check if Python API is running
async function checkAPIStatus() {
    const statusDiv = document.getElementById('status');
    const infoDiv = document.getElementById('info');

    try {
        const response = await chrome.runtime.sendMessage({
            type: 'CHECK_API_STATUS'
        });

        if (response.success) {
            statusDiv.className = 'status success';
            statusDiv.innerHTML = '✓ API is running';
            infoDiv.style.display = 'block';

            document.getElementById('api-status').textContent = 'Online';
            document.getElementById('api-url').textContent = 'localhost:5001';
        } else {
            throw new Error(response.error);
        }
    } catch (error) {
        statusDiv.className = 'status error';
        statusDiv.innerHTML = `
      <strong>API Not Running</strong><br>
      <small>Start with: cd python_service && python api/app.py</small>
    `;
        infoDiv.style.display = 'none';
    }
}

// Get information about the current page
async function getCurrentPageInfo() {
    try {
        const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

        if (!tab || !tab.url) {
            document.getElementById('page-type').textContent = 'Unknown';
            return;
        }

        const url = tab.url;

        // Check if it's a Ceph tracker page
        const trackerMatch = url.match(/tracker\.ceph\.com\/issues\/(\d+)/);
        if (trackerMatch) {
            document.getElementById('page-type').textContent = 'Ceph Tracker';
            document.getElementById('page-id').textContent = `#${trackerMatch[1]}`;
            return;
        }

        // Check if it's a GitHub PR page
        const prMatch = url.match(/github\.com\/ceph\/ceph\/pull\/(\d+)/);
        if (prMatch) {
            document.getElementById('page-type').textContent = 'GitHub PR';
            document.getElementById('page-id').textContent = `#${prMatch[1]}`;
            return;
        }

        // Not a supported page
        document.getElementById('page-type').textContent = 'Not supported';
        document.getElementById('page-id').textContent = 'N/A';
    } catch (error) {
        console.error('Error getting page info:', error);
        document.getElementById('page-type').textContent = 'Error';
    }
}

// Set up button event listeners
function setupEventListeners() {
    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', async () => {
        const btn = document.getElementById('refresh-btn');
        btn.disabled = true;
        btn.textContent = 'Refreshing...';

        try {
            // Reload the current tab to refresh recommendations
            const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
            await chrome.tabs.reload(tab.id);

            setTimeout(() => {
                btn.disabled = false;
                btn.textContent = 'Refresh Recommendations';
            }, 1000);
        } catch (error) {
            console.error('Error refreshing:', error);
            btn.disabled = false;
            btn.textContent = 'Refresh Recommendations';
        }
    });

    // Settings button (placeholder for future functionality)
    document.getElementById('settings-btn').addEventListener('click', () => {
        alert('Settings coming soon!\n\nFor now, configure the API in python_service/.env');
    });
}

// Made with Bob
