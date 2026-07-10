// Content script for Ceph Tracker pages
// Extracts tracker information and displays PR recommendations

console.log('Ceph Tracker Linker: Content script loaded for tracker page');

// Extract tracker ID from URL
function getTrackerIdFromURL() {
    const match = window.location.pathname.match(/\/issues\/(\d+)/);
    return match ? match[1] : null;
}

// Extract tracker information from the page
function extractTrackerInfo() {
    const trackerId = getTrackerIdFromURL();
    if (!trackerId) return null;

    // Extract title
    const titleElement = document.querySelector('.subject h3');
    const title = titleElement ? titleElement.textContent.trim() : 'Unknown';

    // Extract description
    const descElement = document.querySelector('.wiki');
    const description = descElement ? descElement.textContent.trim() : '';

    // Extract status
    const statusElement = document.querySelector('.status .value');
    const status = statusElement ? statusElement.textContent.trim() : 'Unknown';

    // Extract priority
    const priorityElement = document.querySelector('.priority .value');
    const priority = priorityElement ? priorityElement.textContent.trim() : 'Unknown';

    // Extract assignee
    const assigneeElement = document.querySelector('.assigned-to .value a');
    const assignee = assigneeElement ? assigneeElement.textContent.trim() : 'Unassigned';

    return {
        id: trackerId,
        title: title,
        description: description,
        status: status,
        priority: priority,
        assignee: assignee,
        url: window.location.href
    };
}

// Create sidebar HTML
function createSidebar() {
    const sidebar = document.createElement('div');
    sidebar.id = 'ceph-linker-sidebar';
    sidebar.innerHTML = `
    <div class="ceph-linker-header">
      <h2>🔗 PR Recommendations</h2>
      <button class="ceph-linker-toggle" title="Toggle sidebar">✕</button>
    </div>
    <div class="ceph-linker-content">
      <div class="ceph-linker-status loading">
        <span class="ceph-linker-spinner"></span>
        Checking API status...
      </div>
    </div>
  `;

    document.body.appendChild(sidebar);

    // Add toggle functionality
    const toggleBtn = sidebar.querySelector('.ceph-linker-toggle');
    toggleBtn.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
        toggleBtn.textContent = sidebar.classList.contains('collapsed') ? '☰' : '✕';
    });

    return sidebar;
}

// Update sidebar content
function updateSidebarContent(content) {
    const sidebar = document.getElementById('ceph-linker-sidebar');
    if (!sidebar) return;

    const contentDiv = sidebar.querySelector('.ceph-linker-content');
    contentDiv.innerHTML = content;
}

// Show loading state
function showLoading(message = 'Loading recommendations...') {
    updateSidebarContent(`
    <div class="ceph-linker-status loading">
      <span class="ceph-linker-spinner"></span>
      ${message}
    </div>
  `);
}

// Show error state
function showError(message, suggestion = '') {
    updateSidebarContent(`
    <div class="ceph-linker-status error">
      <strong>Error:</strong> ${message}
      ${suggestion ? `<br><small>${suggestion}</small>` : ''}
    </div>
  `);
}

// Show success state with recommendations
function showRecommendations(trackerInfo, recommendations) {
    if (!recommendations || recommendations.length === 0) {
        updateSidebarContent(`
      <div class="ceph-linker-current-item">
        <h3>Current Tracker</h3>
        <p><strong>#${trackerInfo.id}:</strong> ${trackerInfo.title}</p>
        <p><strong>Status:</strong> ${trackerInfo.status}</p>
      </div>
      <div class="ceph-linker-empty">
        <div class="ceph-linker-empty-icon">🔍</div>
        <p class="ceph-linker-empty-text">No matching PRs found</p>
      </div>
    `);
        return;
    }

    const recsHTML = recommendations.map(rec => {
        const similarity = (rec.similarity * 100).toFixed(1);
        const badgeClass = similarity >= 70 ? 'high' : similarity >= 50 ? 'medium' : 'low';

        return `
      <div class="ceph-linker-recommendation">
        <div class="ceph-linker-recommendation-header">
          <a href="${rec.pr_url}" target="_blank" class="ceph-linker-recommendation-title">
            PR #${rec.pr_number}: ${rec.pr_title}
          </a>
          <span class="ceph-linker-similarity-badge ${badgeClass}">${similarity}%</span>
        </div>
        <div class="ceph-linker-recommendation-meta">
          <strong>State:</strong> ${rec.pr_state} | 
          <strong>Author:</strong> ${rec.pr_author || 'Unknown'}
        </div>
        <div class="ceph-linker-recommendation-description">
          ${rec.pr_body ? rec.pr_body.substring(0, 150) + '...' : 'No description'}
        </div>
        <div class="ceph-linker-recommendation-actions">
          <a href="${rec.pr_url}" target="_blank" class="ceph-linker-btn ceph-linker-btn-primary">
            View PR
          </a>
          <button class="ceph-linker-btn" onclick="navigator.clipboard.writeText('${rec.pr_url}')">
            Copy Link
          </button>
        </div>
      </div>
    `;
    }).join('');

    updateSidebarContent(`
    <div class="ceph-linker-current-item">
      <h3>Current Tracker</h3>
      <p><strong>#${trackerInfo.id}:</strong> ${trackerInfo.title}</p>
      <p><strong>Status:</strong> ${trackerInfo.status} | <strong>Priority:</strong> ${trackerInfo.priority}</p>
    </div>
    <div class="ceph-linker-recommendations">
      <h3>Recommended PRs (${recommendations.length})</h3>
      ${recsHTML}
    </div>
  `);
}

// Fetch recommendations from API
async function fetchRecommendations(trackerInfo) {
    showLoading('Fetching recommendations...');

    try {
        const response = await chrome.runtime.sendMessage({
            type: 'GET_RECOMMENDATIONS',
            data: {
                type: 'tracker',
                id: trackerInfo.id
            }
        });

        if (!response.success) {
            showError(response.error, response.suggestion);
            return;
        }

        showRecommendations(trackerInfo, response.data.recommendations);
    } catch (error) {
        console.error('Error fetching recommendations:', error);
        showError('Failed to communicate with extension', 'Try reloading the page');
    }
}

// Check API health before proceeding
async function checkAPIHealth() {
    try {
        const response = await chrome.runtime.sendMessage({
            type: 'CHECK_API_STATUS'
        });

        return response.success;
    } catch (error) {
        console.error('API health check failed:', error);
        return false;
    }
}

// Initialize the extension
async function initialize() {
    console.log('Initializing Ceph Tracker Linker...');

    // Extract tracker info
    const trackerInfo = extractTrackerInfo();
    if (!trackerInfo) {
        console.log('Not a valid tracker page, skipping');
        return;
    }

    console.log('Tracker detected:', trackerInfo);

    // Create sidebar
    createSidebar();

    // Check API health
    showLoading('Checking API connection...');
    const apiHealthy = await checkAPIHealth();

    if (!apiHealthy) {
        showError(
            'Python API is not running',
            'Start the API: cd python_service && python api/app.py'
        );
        return;
    }

    // Fetch recommendations
    await fetchRecommendations(trackerInfo);
}

// Wait for page to be fully loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

// Made with Bob
