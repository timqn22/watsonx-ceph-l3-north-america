// Content script for GitHub PR pages
// Extracts PR information and displays tracker recommendations

console.log('Ceph Tracker Linker: Content script loaded for GitHub PR page');

// Extract PR number from URL
function getPRNumberFromURL() {
    const match = window.location.pathname.match(/\/pull\/(\d+)/);
    return match ? match[1] : null;
}

// Extract PR information from the page
function extractPRInfo() {
    const prNumber = getPRNumberFromURL();
    if (!prNumber) return null;

    // Extract title
    const titleElement = document.querySelector('.js-issue-title');
    const title = titleElement ? titleElement.textContent.trim() : 'Unknown';

    // Extract description/body
    const bodyElement = document.querySelector('.comment-body');
    const body = bodyElement ? bodyElement.textContent.trim() : '';

    // Extract state (open/closed/merged)
    const stateElement = document.querySelector('.State');
    let state = 'unknown';
    if (stateElement) {
        if (stateElement.classList.contains('State--open')) state = 'open';
        else if (stateElement.classList.contains('State--closed')) state = 'closed';
        else if (stateElement.classList.contains('State--merged')) state = 'merged';
    }

    // Extract author
    const authorElement = document.querySelector('.author');
    const author = authorElement ? authorElement.textContent.trim() : 'Unknown';

    // Extract labels
    const labelElements = document.querySelectorAll('.js-issue-labels .IssueLabel');
    const labels = Array.from(labelElements).map(el => el.textContent.trim());

    return {
        number: prNumber,
        title: title,
        body: body,
        state: state,
        author: author,
        labels: labels,
        url: window.location.href
    };
}

// Create sidebar HTML
function createSidebar() {
    const sidebar = document.createElement('div');
    sidebar.id = 'ceph-linker-sidebar';
    sidebar.innerHTML = `
    <div class="ceph-linker-header">
      <h2>🔗 Tracker Recommendations</h2>
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
function showRecommendations(prInfo, recommendations) {
    if (!recommendations || recommendations.length === 0) {
        updateSidebarContent(`
      <div class="ceph-linker-current-item">
        <h3>Current Pull Request</h3>
        <p><strong>PR #${prInfo.number}:</strong> ${prInfo.title}</p>
        <p><strong>State:</strong> ${prInfo.state} | <strong>Author:</strong> ${prInfo.author}</p>
      </div>
      <div class="ceph-linker-empty">
        <div class="ceph-linker-empty-icon">🔍</div>
        <p class="ceph-linker-empty-text">No matching trackers found</p>
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
          <a href="${rec.tracker_url}" target="_blank" class="ceph-linker-recommendation-title">
            Tracker #${rec.tracker_id}: ${rec.tracker_subject}
          </a>
          <span class="ceph-linker-similarity-badge ${badgeClass}">${similarity}%</span>
        </div>
        <div class="ceph-linker-recommendation-meta">
          <strong>Status:</strong> ${rec.tracker_status} | 
          <strong>Priority:</strong> ${rec.tracker_priority || 'Normal'}
        </div>
        <div class="ceph-linker-recommendation-description">
          ${rec.tracker_description ? rec.tracker_description.substring(0, 150) + '...' : 'No description'}
        </div>
        <div class="ceph-linker-recommendation-actions">
          <a href="${rec.tracker_url}" target="_blank" class="ceph-linker-btn ceph-linker-btn-primary">
            View Tracker
          </a>
          <button class="ceph-linker-btn" onclick="navigator.clipboard.writeText('${rec.tracker_url}')">
            Copy Link
          </button>
        </div>
      </div>
    `;
    }).join('');

    updateSidebarContent(`
    <div class="ceph-linker-current-item">
      <h3>Current Pull Request</h3>
      <p><strong>PR #${prInfo.number}:</strong> ${prInfo.title}</p>
      <p><strong>State:</strong> ${prInfo.state} | <strong>Author:</strong> ${prInfo.author}</p>
      ${prInfo.labels.length > 0 ? `<p><strong>Labels:</strong> ${prInfo.labels.join(', ')}</p>` : ''}
    </div>
    <div class="ceph-linker-recommendations">
      <h3>Recommended Trackers (${recommendations.length})</h3>
      ${recsHTML}
    </div>
  `);
}

// Fetch recommendations from API
async function fetchRecommendations(prInfo) {
    showLoading('Fetching recommendations...');

    try {
        const response = await chrome.runtime.sendMessage({
            type: 'GET_RECOMMENDATIONS',
            data: {
                type: 'pr',
                number: prInfo.number
            }
        });

        if (!response.success) {
            showError(response.error, response.suggestion);
            return;
        }

        showRecommendations(prInfo, response.data.recommendations);
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
    console.log('Initializing Ceph Tracker Linker for GitHub...');

    // Extract PR info
    const prInfo = extractPRInfo();
    if (!prInfo) {
        console.log('Not a valid PR page, skipping');
        return;
    }

    console.log('PR detected:', prInfo);

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
    await fetchRecommendations(prInfo);
}

// Wait for page to be fully loaded
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initialize);
} else {
    initialize();
}

// Handle GitHub's dynamic page loading (turbo/pjax)
document.addEventListener('turbo:load', initialize);
document.addEventListener('pjax:end', initialize);

// Made with Bob
