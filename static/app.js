// Global state
let currentValidation = null;
let acceptedSuggestions = new Set();
let customModifications = {};
let currentUser = null;
let sessionId = null;
let pendingStatusChange = null; // Store pending status change data

// DOM elements
const form = document.getElementById('acatForm');
const validateBtn = document.getElementById('validateBtn');
const submitBtn = document.getElementById('submitBtn');
const addSecurityBtn = document.getElementById('addSecurity');
const resultsSection = document.getElementById('resultsSection');
const loadingOverlay = document.getElementById('loadingOverlay');

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    loadContraFirms();
    setupEventListeners();
    refreshACATList();
    checkAuth();
});

// Authentication functions
async function login() {
    const username = document.getElementById('usernameInput').value.trim();
    const password = document.getElementById('passwordInput').value;
    
    if (!username || !password) {
        alert('Please enter username and password');
        return;
    }
    
    try {
        const response = await fetch(`/api/auth/login?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Login failed');
        }
        
        const data = await response.json();
        sessionId = data.session_id;
        currentUser = data.user;
        
        // Hide login screen, show main app
        document.getElementById('loginScreen').style.display = 'none';
        document.getElementById('mainApp').style.display = 'block';
        
        updateAuthUI();
        refreshACATList();
        if (currentUser.role === 'full' || currentUser.role === 'owner') {
            loadLearningInsights();
        }
    } catch (error) {
        alert('Login failed: ' + error.message);
    }
}

function logout() {
    currentUser = null;
    sessionId = null;
    
    // Clear password field
    document.getElementById('passwordInput').value = '';
    document.getElementById('usernameInput').value = '';
    
    // Show login screen, hide main app
    document.getElementById('mainApp').style.display = 'none';
    document.getElementById('loginScreen').style.display = 'flex';
}

function updateAuthUI() {
    const loginScreen = document.getElementById('loginScreen');
    const userInfo = document.getElementById('userInfo');
    const currentUserSpan = document.getElementById('currentUser');
    
    if (currentUser) {
        loginScreen.style.display = 'none';
        if (userInfo) {
            userInfo.style.display = 'block';
            if (currentUserSpan) {
                currentUserSpan.textContent = `${currentUser.first_name} ${currentUser.last_name} (${currentUser.username}) - ${currentUser.role}`;
            }
        }
        updatePermissions();
    } else {
        loginScreen.style.display = 'flex';
        if (userInfo) {
            userInfo.style.display = 'none';
        }
    }
}

function updatePermissions() {
    const isReadOnly = currentUser && currentUser.role === 'read_only';
    
    // Disable form elements for read-only users
    const formElements = document.querySelectorAll('#acatForm input, #acatForm select, #acatForm textarea, #acatForm button');
    formElements.forEach(el => {
        el.disabled = isReadOnly;
    });
    
    // Hide form section for read-only users
    const formSection = document.querySelector('.form-section');
    if (formSection) {
        formSection.style.display = isReadOnly ? 'none' : 'block';
    }
    
    // Show learning analytics for full/owner users
    const learningSection = document.getElementById('learningSection');
    if (learningSection) {
        const canView = currentUser && (currentUser.role === 'full' || currentUser.role === 'owner');
        learningSection.style.display = canView ? 'block' : 'none';
        if (canView) {
            loadLearningInsights();
        }
    }
    
    // Show audit log button for admin/owner
    const auditLogBtn = document.getElementById('auditLogBtn');
    if (auditLogBtn) {
        auditLogBtn.style.display = (currentUser && (currentUser.role === 'full' || currentUser.role === 'owner')) ? 'inline-block' : 'none';
    }
    
    // Show approvals button for owner only
    const approvalsBtn = document.getElementById('approvalsBtn');
    if (approvalsBtn) {
        approvalsBtn.style.display = (currentUser && currentUser.role === 'owner') ? 'inline-block' : 'none';
    }
}

function checkAuth() {
    // Check if there's a stored session (for demo purposes)
    const storedSession = localStorage.getItem('acat_session');
    if (storedSession) {
        sessionId = storedSession;
        // In a real app, you'd validate the session with the server
        currentUser = { username: 'demo', role: 'full' };
        updateAuthUI();
    }
}

// Load contra firms from API
async function loadContraFirms() {
    try {
        const response = await fetch('/api/contra-firms');
        const contraFirms = await response.json();
        
        const select = document.getElementById('contraFirm');
        Object.entries(contraFirms).forEach(([code, name]) => {
            const option = document.createElement('option');
            option.value = code;
            option.textContent = `${code} - ${name}`;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('Failed to load contra firms:', error);
    }
}

// Setup event listeners
function setupEventListeners() {
    validateBtn.addEventListener('click', validateACAT);
    submitBtn.addEventListener('click', submitACAT);
    addSecurityBtn.addEventListener('click', addSecurityField);
    
    // Form validation
    form.addEventListener('input', function() {
        submitBtn.disabled = !currentValidation || !currentValidation.is_valid;
    });
}

// Validate ACAT data
async function validateACAT() {
    if (!validateForm()) {
        alert('Please fill in all required fields');
        return;
    }
    
    showLoading(true);
    
    try {
        const formData = getFormData();
        const response = await fetch('/api/validate-acat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(formData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const validation = await response.json();
        currentValidation = validation;
        displayValidationResults(validation);
        
    } catch (error) {
        console.error('Validation failed:', error);
        alert('Validation failed: ' + error.message);
    } finally {
        showLoading(false);
    }
}

// Submit ACAT data
async function submitACAT() {
    if (!currentValidation) {
        alert('Please validate the ACAT data first');
        return;
    }
    
    try {
        const formData = getFormData();
        const submissionData = {
            acat_data: formData,
            accepted_suggestions: Array.from(acceptedSuggestions),
            custom_modifications: customModifications
        };
        
        const response = await fetch('/api/submit-acat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(submissionData)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        alert(`ACAT submitted successfully!\nSubmission ID: ${result.submission_id}`);
        refreshACATList();
        
        // Reset form
        form.reset();
        resultsSection.style.display = 'none';
        currentValidation = null;
        acceptedSuggestions.clear();
        customModifications = {};
        submitBtn.disabled = true;
        
    } catch (error) {
        console.error('Submission failed:', error);
        alert('Submission failed: ' + error.message);
    }
}

// Get form data as JSON
function getFormData() {
    const formData = new FormData(form);
    const data = {};
    
    // Basic fields
    data.delivering_account = formData.get('delivering_account');
    data.receiving_account = formData.get('receiving_account');
    data.contra_firm = formData.get('contra_firm');
    data.transfer_type = formData.get('transfer_type');
    data.special_instructions = formData.get('special_instructions');
    
    // Customer information
    data.customer = {
        first_name: formData.get('customer.first_name'),
        last_name: formData.get('customer.last_name'),
        ssn: formData.get('customer.ssn'),
        tax_id: formData.get('customer.tax_id')
    };
    
    // Securities
    data.securities = [];
    const securityInputs = document.querySelectorAll('[name^="securities["]');
    const securityCount = Math.max(...Array.from(securityInputs).map(input => {
        const match = input.name.match(/securities\[(\d+)\]/);
        return match ? parseInt(match[1]) : 0;
    })) + 1;
    
    for (let i = 0; i < securityCount; i++) {
        const cusip = formData.get(`securities[${i}].cusip`);
        if (cusip) {
            data.securities.push({
                cusip: cusip,
                symbol: formData.get(`securities[${i}].symbol`) || null,
                description: formData.get(`securities[${i}].description`),
                quantity: parseInt(formData.get(`securities[${i}].quantity`)),
                asset_type: formData.get(`securities[${i}].asset_type`)
            });
        }
    }
    
    return data;
}

// Validate form
function validateForm() {
    const requiredFields = form.querySelectorAll('[required]');
    for (const field of requiredFields) {
        if (!field.value.trim()) {
            return false;
        }
    }
    return true;
}

// Display validation results
function displayValidationResults(validation) {
    resultsSection.style.display = 'block';
    
    // Validation status
    const statusDiv = document.getElementById('validationStatus');
    statusDiv.className = `validation-status ${validation.is_valid ? 'valid' : 'invalid'}`;
    
    const statusText = validation.is_valid ? '✓ Valid' : '✗ Issues Found';
    const probability = Math.round(validation.success_probability * 100);
    const probabilityClass = probability >= 80 ? 'high' : probability >= 60 ? 'medium' : 'low';
    
    statusDiv.innerHTML = `
        ${statusText}
        <span class="success-probability ${probabilityClass}">
            ${probability}% Success Probability
        </span>
    `;
    
    // Suggestions
    displaySuggestions(validation.suggestions);
    
    // Warnings
    displayWarnings(validation.warnings);
    
    // AI Analysis
    displayAIAnalysis(validation.ai_analysis);
    
    // Enable/disable submit button
    submitBtn.disabled = !validation.is_valid;
}

// Display suggestions
function displaySuggestions(suggestions) {
    const container = document.getElementById('suggestionsContainer');
    
    if (suggestions.length === 0) {
        container.innerHTML = '<p>No suggestions found. ACAT data looks good!</p>';
        return;
    }
    
    container.innerHTML = '<h3>AI Suggestions</h3>';
    
    suggestions.forEach((suggestion, index) => {
        const suggestionDiv = document.createElement('div');
        suggestionDiv.className = `suggestion-item ${suggestion.severity}`;
        suggestionDiv.innerHTML = `
            <div class="suggestion-header">
                <span class="suggestion-field">${suggestion.field}</span>
                <span class="suggestion-severity ${suggestion.severity}">${suggestion.severity}</span>
            </div>
            <div class="suggestion-details">
                <p><strong>Current:</strong> <span class="suggestion-current">${suggestion.current_value}</span></p>
                <p><strong>Suggested:</strong> <span class="suggestion-suggested">${suggestion.suggested_value}</span></p>
                <p class="suggestion-reason">${suggestion.reason}</p>
                <p><strong>Confidence:</strong> ${Math.round(suggestion.confidence * 100)}%</p>
            </div>
            <div class="suggestion-actions">
                <button class="accept-suggestion" onclick="acceptSuggestion('${suggestion.field}', '${suggestion.suggested_value}')">
                    Accept
                </button>
                <button class="reject-suggestion" onclick="rejectSuggestion('${suggestion.field}')">
                    Reject
                </button>
            </div>
        `;
        container.appendChild(suggestionDiv);
    });
}

// Display warnings
function displayWarnings(warnings) {
    const container = document.getElementById('warningsContainer');
    
    if (warnings.length === 0) {
        container.innerHTML = '';
        return;
    }
    
    container.innerHTML = '<h3>Warnings</h3>';
    
    warnings.forEach(warning => {
        const warningDiv = document.createElement('div');
        warningDiv.className = 'warning-item';
        warningDiv.textContent = warning;
        container.appendChild(warningDiv);
    });
}

// Display AI analysis
function displayAIAnalysis(analysis) {
    const container = document.getElementById('aiAnalysis');
    container.innerHTML = `
        <h4>AI Analysis Summary</h4>
        <p>${analysis}</p>
    `;
}

// Accept suggestion
function acceptSuggestion(field, suggestedValue) {
    acceptedSuggestions.add(field);
    customModifications[field] = suggestedValue;
    
    // Update the form field if it exists
    const fieldElement = document.querySelector(`[name="${field}"]`);
    if (fieldElement) {
        fieldElement.value = suggestedValue;
    }
    
    // Update UI
    updateSuggestionUI(field, true);
}

// Reject suggestion
function rejectSuggestion(field) {
    acceptedSuggestions.delete(field);
    delete customModifications[field];
    
    // Update UI
    updateSuggestionUI(field, false);
}

// Update suggestion UI
function updateSuggestionUI(field, accepted) {
    const suggestionItems = document.querySelectorAll('.suggestion-item');
    suggestionItems.forEach(item => {
        const fieldSpan = item.querySelector('.suggestion-field');
        if (fieldSpan && fieldSpan.textContent === field) {
            const actions = item.querySelector('.suggestion-actions');
            if (accepted) {
                actions.innerHTML = '<span style="color: #28a745; font-weight: bold;">✓ Accepted</span>';
            } else {
                actions.innerHTML = `
                    <button class="accept-suggestion" onclick="acceptSuggestion('${field}', '${item.querySelector('.suggestion-suggested').textContent}')">
                        Accept
                    </button>
                    <button class="reject-suggestion" onclick="rejectSuggestion('${field}')">
                        Reject
                    </button>
                `;
            }
        }
    });
}

// Add security field
function addSecurityField() {
    const container = document.getElementById('securitiesContainer');
    const securityCount = container.children.length;
    
    const securityDiv = document.createElement('div');
    securityDiv.className = 'security-item';
    securityDiv.innerHTML = `
        <div class="form-grid">
            <div class="form-group">
                <label>CUSIP *</label>
                <input type="text" name="securities[${securityCount}].cusip" required maxlength="9">
            </div>
            <div class="form-group">
                <label>Symbol</label>
                <input type="text" name="securities[${securityCount}].symbol" maxlength="10">
            </div>
            <div class="form-group">
                <label>Description *</label>
                <input type="text" name="securities[${securityCount}].description" required>
            </div>
            <div class="form-group">
                <label>Quantity *</label>
                <input type="number" name="securities[${securityCount}].quantity" required min="1">
            </div>
            <div class="form-group">
                <label>Asset Type *</label>
                <select name="securities[${securityCount}].asset_type" required>
                    <option value="">Select type...</option>
                    <option value="equity">Equity</option>
                    <option value="mutual_fund">Mutual Fund</option>
                    <option value="bond">Bond</option>
                    <option value="option">Option</option>
                    <option value="cash">Cash</option>
                </select>
            </div>
        </div>
    `;
    
    container.appendChild(securityDiv);
}

// Show/hide loading overlay
function showLoading(show) {
    loadingOverlay.style.display = show ? 'flex' : 'none';
}

// --- Ongoing ACATs List ---
async function refreshACATList() {
    try {
        const res = await fetch('/api/tracking');
        if (!res.ok) return;
        const acats = await res.json();
        renderStatusSummary(acats);
        renderACATList(acats);
    } catch (e) {
        console.error('Failed to load ACAT list', e);
    }
}

// Calculate business days between two dates
function calculateBusinessDays(startDate, endDate) {
    const start = new Date(startDate);
    const end = new Date(endDate);
    let count = 0;
    let current = new Date(start);
    
    while (current <= end) {
        const dayOfWeek = current.getDay();
        if (dayOfWeek !== 0 && dayOfWeek !== 6) { // Not weekend
            count++;
        }
        current.setDate(current.getDate() + 1);
    }
    return count;
}

// Render status summary dashboard
function renderStatusSummary(acats) {
    const container = document.getElementById('statusSummary');
    if (!container) return;
    
    const total = acats.length;
    if (total === 0) {
        container.innerHTML = '<p>No ACATs to display</p>';
        return;
    }
    
    // Status order: workflow progression
    const statusOrder = [
        'new', 'submitted', 'pending_review', 'pending_client', 
        'pending_delivering', 'pending_receiving', 'completed', 'rejected', 'cancelled'
    ];
    
    const statusLabels = {
        'new': 'New',
        'submitted': 'Submitted',
        'pending_review': 'Review',
        'pending_client': 'Client',
        'pending_delivering': 'Delivering',
        'pending_receiving': 'Receiving',
        'rejected': 'Rejected',
        'cancelled': 'Cancelled',
        'completed': 'Completed'
    };
    
    const statusColors = {
        'completed': '#10b981',
        'submitted': '#3b82f6',
        'pending_review': '#3b82f6',
        'pending_client': '#f59e0b',
        'pending_delivering': '#f59e0b',
        'pending_receiving': '#f59e0b',
        'new': '#8b5cf6',
        'rejected': '#ef4444',
        'cancelled': '#ef4444'
    };
    
    // Count by status
    const statusCounts = {};
    acats.forEach(acat => {
        statusCounts[acat.status] = (statusCounts[acat.status] || 0) + 1;
    });
    
    // Calculate metrics
    const completed = statusCounts['completed'] || 0;
    const failed = (statusCounts['rejected'] || 0) + (statusCounts['cancelled'] || 0);
    const inProgress = total - completed - failed;
    const successRate = total > 0 ? Math.round((completed / total) * 100) : 0;
    
    // Overview cards
    const overview = `
        <div class="status-overview">
            <div class="summary-card">
                <div class="summary-card-value" style="color: #1e3a8a">${total}</div>
                <div class="summary-card-label">Total ACATs</div>
            </div>
            <div class="summary-card">
                <div class="summary-card-value" style="color: ${inProgress > 0 ? '#f59e0b' : '#64748b'}">${inProgress}</div>
                <div class="summary-card-label">In Progress</div>
            </div>
            <div class="summary-card">
                <div class="summary-card-value" style="color: #10b981">${successRate}%</div>
                <div class="summary-card-label">Success Rate</div>
            </div>
        </div>
    `;
    
    // Distribution bar
    const distributionSegments = statusOrder
        .filter(status => statusCounts[status] > 0)
        .map(status => {
            const count = statusCounts[status];
            const percentage = (count / total) * 100;
            return `
                <div class="distribution-segment" 
                     style="width: ${percentage}%; background: ${statusColors[status]}" 
                     title="${statusLabels[status]}: ${count}">
                    ${percentage >= 8 ? count : ''}
                </div>
            `;
        }).join('');
    
    const legend = statusOrder
        .filter(status => statusCounts[status] > 0)
        .map(status => `
            <div class="legend-item">
                <div class="legend-color" style="background: ${statusColors[status]}"></div>
                <span>${statusLabels[status]}: ${statusCounts[status]}</span>
            </div>
        `).join('');
    
    const distribution = `
        <div class="status-distribution">
            <h3>Status Distribution</h3>
            <div class="distribution-bar">${distributionSegments}</div>
            <div class="distribution-legend">${legend}</div>
        </div>
    `;
    
    // Status cards in logical order
    const cards = statusOrder
        .filter(status => statusCounts[status] > 0)
        .map(status => `
            <div class="status-card" style="border-left-color: ${statusColors[status]}">
                <div class="status-card-count" style="color: ${statusColors[status]}">${statusCounts[status]}</div>
                <div class="status-card-label">${statusLabels[status]}</div>
            </div>
        `).join('');
    
    container.innerHTML = `
        ${overview}
        ${distribution}
        <div class="status-grid">
            ${cards}
        </div>
    `;
}

function renderACATList(acats) {
    const container = document.getElementById('acatList');
    if (!container) return;
    if (!acats || acats.length === 0) {
        container.innerHTML = '<p>No ongoing ACATs yet.</p>';
        return;
    }
    const now = new Date();
    const rows = acats.map(a => {
        const createdDate = new Date(a.created_at);
        const formattedDate = createdDate.toLocaleDateString();
        const businessDays = calculateBusinessDays(createdDate, now);
        let daysClass = 'days-normal';
        if (businessDays > 10) daysClass = 'days-critical';
        else if (businessDays > 5) daysClass = 'days-warning';
        
        return `
        <tr>
            <td>${a.id.substring(0, 8)}...</td>
            <td>${a.acat_data.delivering_account}</td>
            <td>${a.acat_data.receiving_account}</td>
            <td>${formattedDate}<br><span class="days-elapsed ${daysClass}">${businessDays} business days</span></td>
            <td>
                ${renderStatusActions(a)}
            </td>
        </tr>
        `;
    }).join('');
    container.innerHTML = `
        <table class="table">
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Delivering</th>
                    <th>Receiving</th>
                    <th>Submitted / Days Elapsed</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
    `;
}

function renderStatusActions(record) {
    const isReadOnly = currentUser && currentUser.role === 'read_only';
    
    if (isReadOnly) {
        return `<span class="status-display">${record.status}</span>`;
    }
    
    const statuses = [
        'new','submitted','pending_review','pending_client','pending_delivering','pending_receiving','rejected','cancelled','completed'
    ];
    const options = statuses.map(s => `<option value="${s}" ${record.status===s?'selected':''}>${s}</option>`).join('');
    return `
        <select onchange="showStatusUpdateModal('${record.id}', this.value)">
            ${options}
        </select>
    `;
}

function showStatusUpdateModal(recordId, newStatus) {
    // Store pending status change data
    pendingStatusChange = {
        recordId: recordId,
        newStatus: newStatus
    };
    
    // Show status change modal
    document.getElementById('newStatusDisplay').textContent = newStatus;
    document.getElementById('statusChangeReason').value = '';
    document.getElementById('passwordVerification').value = '';
    document.getElementById('statusChangeModal').style.display = 'flex';
    document.getElementById('statusChangeReason').focus();
}

async function updateRecordStatus(id, status, reason) {
    if (!currentUser) {
        alert('Please login first');
        return;
    }
    
    try {
        const updateRequest = {
            status: status,
            reason: reason,
            updated_by: currentUser.username
        };
        
        const res = await fetch(`/api/tracking/${id}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateRequest)
        });
        
        if (!res.ok) throw new Error('Failed to update status');
        await refreshACATList();
        
        // Refresh learning insights after status change
        if (currentUser.role === 'full') {
            loadLearningInsights();
        }
    } catch (e) {
        alert(e.message);
    }
}

// Status change modal functions
function cancelStatusChange() {
    document.getElementById('statusChangeModal').style.display = 'none';
    pendingStatusChange = null;
}

async function confirmStatusChange() {
    const reason = document.getElementById('statusChangeReason').value.trim();
    const password = document.getElementById('passwordVerification').value;
    
    if (!reason) {
        alert('Please enter a reason for the status change');
        document.getElementById('statusChangeReason').focus();
        return;
    }
    
    if (!password) {
        alert('Please enter your password');
        document.getElementById('passwordVerification').focus();
        return;
    }
    
    try {
        // Verify password first
        const verifyResponse = await fetch(`/api/auth/verify-password?session_id=${sessionId}&password=${encodeURIComponent(password)}`, {
            method: 'POST'
        });
        
        if (!verifyResponse.ok) {
            alert('Invalid password. Please try again.');
            document.getElementById('passwordVerification').value = '';
            document.getElementById('passwordVerification').focus();
            return;
        }
        
        // Update status with password verification
        const response = await fetch(`/api/tracking/${pendingStatusChange.recordId}/status`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                status: pendingStatusChange.newStatus,
                reason: reason,
                updated_by: currentUser.username,
                password: password,
                session_id: sessionId
            })
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to update status');
        }
        
        const updatedRecord = await response.json();
        
        // Close modal and refresh
        const newStatus = pendingStatusChange.newStatus;
        document.getElementById('statusChangeModal').style.display = 'none';
        pendingStatusChange = null;
        refreshACATList();
        
        // Refresh learning insights after status change
        if (currentUser.role === 'full' || currentUser.role === 'owner') {
            loadLearningInsights();
        }
        
        // Show success message
        const successMsg = document.createElement('div');
        successMsg.style.cssText = 'position: fixed; top: 20px; right: 20px; background: #10b981; color: white; padding: 16px 24px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); z-index: 10000;';
        successMsg.textContent = `✓ Status updated to ${newStatus}`;
        document.body.appendChild(successMsg);
        setTimeout(() => successMsg.remove(), 3000);
        
    } catch (error) {
        alert('Failed to update status: ' + error.message);
    }
}

// --- Learning Analytics ---

async function loadLearningInsights() {
    try {
        const res = await fetch('/api/learning/insights');
        if (!res.ok) return;
        const insights = await res.json();
        renderLearningInsights(insights);
    } catch (e) {
        console.error('Failed to load learning insights', e);
    }
}

function renderLearningInsights(insights) {
    const container = document.getElementById('learningInsights');
    if (!container) return;
    
    if (!insights.learning_active) {
        container.innerHTML = '<p>No learning data available yet. Submit some ACATs to start learning!</p>';
        return;
    }
    
    const successRate = Math.round(insights.overall_success_rate * 100);
    const problematicFirms = insights.problematic_firms.map(f => 
        `${f.firm} (${Math.round(f.success_rate * 100)}% success, ${f.total_submissions} submissions)`
    ).join('<br>');
    
    const commonIssues = insights.most_common_issues.map(([field, count]) => 
        `${field}: ${count} occurrences`
    ).join('<br>');
    
    container.innerHTML = `
        <div class="learning-stats">
            <h3>Overall Statistics</h3>
            <p><strong>Total Firms:</strong> ${insights.total_firms}</p>
            <p><strong>Total Submissions:</strong> ${insights.total_submissions}</p>
            <p><strong>Overall Success Rate:</strong> ${successRate}%</p>
        </div>
        <div class="learning-issues">
            <h3>Most Common Issues</h3>
            <p>${commonIssues || 'No common issues identified yet'}</p>
        </div>
        <div class="learning-problematic">
            <h3>Firms Needing Attention</h3>
            <p>${problematicFirms || 'All firms performing well!'}</p>
        </div>
    `;
}

// User Creation Functions
async function createUserAccount() {
    const form = document.getElementById('userCreationForm');
    const formData = new FormData(form);
    
    const userData = {
        username: document.getElementById('newUsername').value,
        first_name: document.getElementById('newFirstName').value,
        last_name: document.getElementById('newLastName').value,
        email: document.getElementById('newEmail').value,
        phone_number: document.getElementById('newPhoneNumber').value || null,
        role: document.getElementById('userRole').value
    };
    
    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(userData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }
        
        const result = await response.json();
        alert('Account created successfully! You can now log in.');
        showOnboardingStep('setupComplete');
        
    } catch (error) {
        console.error('Registration failed:', error);
        alert('Registration failed: ' + error.message);
    }
}

// --- Signup Flow ---
let currentSignupStep = 1;

function showSignupFromLogin() {
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('mainApp').style.display = 'block';
    document.getElementById('signupFlow').style.display = 'block';
    currentSignupStep = 1;
    updateSignupProgress();
}

function showSignup() {
    document.querySelector('.main-content').style.display = 'none';
    document.getElementById('signupFlow').style.display = 'block';
    currentSignupStep = 1;
    updateSignupProgress();
}

function showLoginFromSignup() {
    document.getElementById('signupFlow').style.display = 'none';
    document.getElementById('mainApp').style.display = 'none';
    document.getElementById('loginScreen').style.display = 'flex';
}

function nextSignupStep() {
    // Validate current step
    const form = document.getElementById('signupForm');
    if (!form.checkValidity()) {
        form.reportValidity();
        return;
    }
    
    // Validate password match
    const password = document.getElementById('signupPassword').value;
    const passwordConfirm = document.getElementById('signupPasswordConfirm').value;
    
    if (password !== passwordConfirm) {
        alert('Passwords do not match');
        return;
    }
    
    currentSignupStep = 2;
    updateSignupProgress();
}

function prevSignupStep() {
    currentSignupStep = 1;
    updateSignupProgress();
}

function updateSignupProgress() {
    // Update progress dots
    document.querySelectorAll('.progress-dot').forEach((dot, index) => {
        if (index + 1 === currentSignupStep) {
            dot.classList.add('active');
        } else {
            dot.classList.remove('active');
        }
    });
    
    // Update step visibility
    document.querySelectorAll('.signup-step').forEach((step, index) => {
        if (index + 1 === currentSignupStep) {
            step.classList.add('active');
        } else {
            step.classList.remove('active');
        }
    });
}

async function completeSignup() {
    const selectedRole = document.querySelector('input[name="userRole"]:checked');
    if (!selectedRole) {
        alert('Please select a permission level');
        return;
    }
    
    const userData = {
        username: document.getElementById('signupUsername').value,
        password: document.getElementById('signupPassword').value,
        first_name: document.getElementById('signupFirstName').value,
        last_name: document.getElementById('signupLastName').value,
        email: document.getElementById('signupEmail').value,
        phone_number: document.getElementById('signupPhone').value || null,
        role: selectedRole.value
    };
    
    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(userData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Registration failed');
        }
        
        const isOwner = selectedRole.value === 'owner';
        if (isOwner) {
            alert('Owner account created successfully! You have immediate access. Please log in with your username and password.');
        } else {
            alert('Account created successfully! Your account is pending approval by an owner. You will be able to log in once approved.');
        }
        showLoginFromSignup();
        
        // Reset form
        document.getElementById('signupForm').reset();
        document.querySelectorAll('input[name="userRole"]').forEach(r => r.checked = false);
        currentSignupStep = 1;
    } catch (error) {
        alert('Signup failed: ' + error.message);
    }
}

// Add click handlers for role selection
document.addEventListener('click', function(e) {
    if (e.target.closest('.role-option')) {
        const option = e.target.closest('.role-option');
        document.querySelectorAll('.role-option').forEach(opt => opt.classList.remove('selected'));
        option.classList.add('selected');
        option.querySelector('input[type="radio"]').checked = true;
    }
});

// --- ACAT Creation Wizard ---
let currentACATStep = 1;
const totalACATSteps = 3;

function startACATCreation() {
    if (!currentUser) {
        alert('Please log in first');
        return;
    }
    
    if (currentUser.role === 'read_only') {
        alert('You need full access permissions to create ACATs');
        return;
    }
    
    // Hide main content, show wizard
    document.querySelector('.main-content').style.display = 'none';
    document.getElementById('acatCreationFlow').style.display = 'block';
    
    // Set audit username
    document.getElementById('creatorUsername').textContent = currentUser.username;
    
    // Reset wizard to step 1
    currentACATStep = 1;
    updateACATWizardProgress();
    
    // Load contra firms
    loadCreateContraFirms();
    
    // Initialize with one security
    addCreateSecurity();
}

function cancelACATCreation() {
    document.getElementById('acatCreationFlow').style.display = 'none';
    document.querySelector('.main-content').style.display = 'flex';
    
    // Reset form
    document.querySelectorAll('#acatCreationFlow input, #acatCreationFlow select, #acatCreationFlow textarea').forEach(el => el.value = '');
    document.getElementById('createSecuritiesContainer').innerHTML = '';
    currentACATStep = 1;
}

function nextACATStep() {
    // Validate current step
    let isValid = true;
    const currentStepEl = document.getElementById(`acatStep${currentACATStep}`);
    const requiredFields = currentStepEl.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            isValid = false;
            field.style.borderColor = '#ef4444';
        } else {
            field.style.borderColor = '#cbd5e1';
        }
    });
    
    if (!isValid) {
        alert('Please fill in all required fields');
        return;
    }
    
    if (currentACATStep < totalACATSteps) {
        currentACATStep++;
        updateACATWizardProgress();
    }
}

function prevACATStep() {
    if (currentACATStep > 1) {
        currentACATStep--;
        updateACATWizardProgress();
    }
}

function updateACATWizardProgress() {
    // Update progress steps
    document.querySelectorAll('.wizard-progress .progress-step').forEach((step, index) => {
        if (index + 1 === currentACATStep) {
            step.classList.add('active');
        } else {
            step.classList.remove('active');
        }
    });
    
    // Update step visibility
    for (let i = 1; i <= totalACATSteps; i++) {
        const stepEl = document.getElementById(`acatStep${i}`);
        if (i === currentACATStep) {
            stepEl.classList.add('active');
            stepEl.style.display = 'block';
        } else {
            stepEl.classList.remove('active');
            stepEl.style.display = 'none';
        }
    }
    
    // Update button visibility
    document.getElementById('createPrevBtn').style.display = currentACATStep > 1 ? 'block' : 'none';
    document.getElementById('createNextBtn').style.display = currentACATStep < totalACATSteps ? 'block' : 'none';
    document.getElementById('createSubmitBtn').style.display = currentACATStep === totalACATSteps ? 'block' : 'none';
}

async function loadCreateContraFirms() {
    try {
        const response = await fetch('/api/contra-firms');
        const firms = await response.json();
        const select = document.getElementById('createContraFirm');
        select.innerHTML = '<option value="">Select contra firm...</option>' + 
            firms.map(f => `<option value="${f.id}">${f.name} (${f.id})</option>`).join('');
    } catch (error) {
        console.error('Failed to load contra firms:', error);
    }
}

function addCreateSecurity() {
    const container = document.getElementById('createSecuritiesContainer');
    const index = container.children.length;
    
    const securityDiv = document.createElement('div');
    securityDiv.className = 'security-item';
    securityDiv.style.marginBottom = '16px';
    securityDiv.innerHTML = `
        <div class="field-row">
            <div class="field-item">
                <label class="field-label">CUSIP *</label>
                <input type="text" class="field-value security-cusip" required>
            </div>
            <div class="field-item">
                <label class="field-label">Symbol *</label>
                <input type="text" class="field-value security-symbol" required>
            </div>
        </div>
        <div class="field-row">
            <div class="field-item">
                <label class="field-label">Description *</label>
                <input type="text" class="field-value security-description" required>
            </div>
            <div class="field-item">
                <label class="field-label">Quantity *</label>
                <input type="number" class="field-value security-quantity" required min="1">
            </div>
        </div>
        <div class="field-item">
            <label class="field-label">Asset Type *</label>
            <select class="field-value security-assettype" required>
                <option value="">Select type...</option>
                <option value="equity">Equity</option>
                <option value="mutual_fund">Mutual Fund</option>
                <option value="bond">Bond</option>
            </select>
        </div>
        ${index > 0 ? '<button type="button" class="btn-secondary" onclick="this.parentElement.remove()" style="margin-top: 12px;">Remove</button>' : ''}
    `;
    container.appendChild(securityDiv);
}

async function submitNewACAT() {
    if (!currentUser) {
        alert('Please log in first');
        return;
    }
    
    // Gather customer data
    const customer = {
        first_name: document.getElementById('createFirstName').value,
        last_name: document.getElementById('createLastName').value,
        ssn: document.getElementById('createSSN').value,
        tax_id: document.getElementById('createTaxID').value || null
    };
    
    // Gather account/firm data
    const acatData = {
        delivering_account: document.getElementById('createDeliveringAccount').value,
        receiving_account: document.getElementById('createReceivingAccount').value,
        contra_firm: document.getElementById('createContraFirm').value,
        transfer_type: document.getElementById('createTransferType').value,
        customer: customer,
        securities: [],
        special_instructions: document.getElementById('createInstructions').value || null
    };
    
    // Gather securities
    const securityItems = document.querySelectorAll('#createSecuritiesContainer .security-item');
    securityItems.forEach(item => {
        const cusip = item.querySelector('.security-cusip').value;
        const symbol = item.querySelector('.security-symbol').value;
        const description = item.querySelector('.security-description').value;
        const quantity = item.querySelector('.security-quantity').value;
        const assetType = item.querySelector('.security-assettype').value;
        
        if (cusip && symbol && description && quantity && assetType) {
            acatData.securities.push({
                cusip: cusip,
                symbol: symbol,
                description: description,
                quantity: parseInt(quantity),
                asset_type: assetType
            });
        }
    });
    
    // Validate
    if (!acatData.customer.first_name || !acatData.customer.last_name || !acatData.customer.ssn) {
        alert('Please fill in all required customer information');
        return;
    }
    
    if (!acatData.delivering_account || !acatData.receiving_account || !acatData.contra_firm) {
        alert('Please fill in all required account information');
        return;
    }
    
    if (acatData.securities.length === 0) {
        alert('Please add at least one security');
        return;
    }
    
    try {
        // Submit the ACAT
        const response = await fetch('/api/submit', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                acat_data: acatData,
                accepted_suggestions: [],
                custom_modifications: {}
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to submit ACAT');
        }
        
        const result = await response.json();
        alert(`ACAT created successfully!\nSubmission ID: ${result.submission_id}`);
        
        // Return to dashboard
        cancelACATCreation();
        refreshACATList();
    } catch (error) {
        alert('Failed to create ACAT: ' + error.message);
    }
}

// --- About Screen ---
function showAbout() {
    document.querySelector('.main-content').style.display = 'none';
    document.getElementById('aboutScreen').style.display = 'block';
}

function closeAbout() {
    document.getElementById('aboutScreen').style.display = 'none';
    document.querySelector('.main-content').style.display = 'flex';
}

// --- Audit Log Screen ---
async function showAuditLog() {
    if (!currentUser || currentUser.role === 'read_only') {
        alert('Access denied');
        return;
    }
    
    document.querySelector('.main-content').style.display = 'none';
    document.getElementById('auditLogScreen').style.display = 'block';
    
    // Load audit log
    try {
        const response = await fetch(`/api/audit/changes?session_id=${sessionId}`);
        if (!response.ok) throw new Error('Failed to load audit log');
        
        const auditEntries = await response.json();
        renderAuditLog(auditEntries);
    } catch (error) {
        document.getElementById('auditLogContent').innerHTML = '<p>Failed to load audit log</p>';
    }
}

function closeAuditLog() {
    document.getElementById('auditLogScreen').style.display = 'none';
    document.querySelector('.main-content').style.display = 'flex';
}

function renderAuditLog(entries) {
    const container = document.getElementById('auditLogContent');
    
    if (!entries || entries.length === 0) {
        container.innerHTML = '<p>No audit entries found</p>';
        return;
    }
    
    const rows = entries.map(entry => {
        const date = new Date(entry.performed_at);
        const actionType = entry.action === 'status_change' ? 'Status Change' : 
                          entry.action === 'create' ? 'ACAT Created' :
                          entry.action === 'approve_user' ? 'User Approved' :
                          entry.action === 'reject_user' ? 'User Rejected' : entry.action;
        
        let details = '';
        if (entry.action === 'status_change') {
            details = `${entry.details.from_status} → ${entry.details.to_status}`;
        } else if (entry.action === 'create') {
            details = `Account: ${entry.details.delivering_account} → ${entry.details.receiving_account}`;
        } else if (entry.action === 'approve_user' || entry.action === 'reject_user') {
            details = `User: ${entry.entity_id}`;
        }
        
        return `
            <tr>
                <td>${date.toLocaleString()}</td>
                <td><span class="action-badge action-${entry.action}">${actionType}</span></td>
                <td>${entry.entity_type.toUpperCase()}</td>
                <td>${entry.entity_id.substring(0, 8)}...</td>
                <td>${details}</td>
                <td>${entry.details.reason || entry.details.approved_by || entry.details.rejected_by || 'N/A'}</td>
                <td><strong>${entry.performed_by}</strong></td>
            </tr>
        `;
    }).join('');
    
    container.innerHTML = `
        <table class="table">
            <thead>
                <tr>
                    <th>Timestamp</th>
                    <th>Action</th>
                    <th>Entity Type</th>
                    <th>Entity ID</th>
                    <th>Details</th>
                    <th>Reason/Info</th>
                    <th>Performed By</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
    `;
}

// --- Pending Approvals Screen (Owner Only) ---
async function showPendingApprovals() {
    if (!currentUser || currentUser.role !== 'owner') {
        alert('Owner access required');
        return;
    }
    
    document.querySelector('.main-content').style.display = 'none';
    document.getElementById('approvalsScreen').style.display = 'block';
    
    // Load pending approvals
    try {
        const response = await fetch(`/api/admin/pending-users?session_id=${sessionId}`);
        if (!response.ok) throw new Error('Failed to load pending approvals');
        
        const pendingUsers = await response.json();
        renderPendingApprovals(pendingUsers);
    } catch (error) {
        document.getElementById('pendingApprovalsContent').innerHTML = '<p>Failed to load pending approvals</p>';
    }
}

function closePendingApprovals() {
    document.getElementById('approvalsScreen').style.display = 'none';
    document.querySelector('.main-content').style.display = 'flex';
}

function renderPendingApprovals(users) {
    const container = document.getElementById('pendingApprovalsContent');
    
    if (!users || users.length === 0) {
        container.innerHTML = '<p>No pending user approvals</p>';
        return;
    }
    
    const rows = users.map(user => `
        <tr>
            <td>${user.username}</td>
            <td>${user.first_name} ${user.last_name}</td>
            <td>${user.email}</td>
            <td>${user.phone_number || 'N/A'}</td>
            <td><span class="status-${user.role}">${user.role}</span></td>
            <td>${new Date(user.created_at).toLocaleDateString()}</td>
            <td>
                <button class="btn-success" onclick="approveUser('${user.id}')" style="margin-right: 8px;">Approve</button>
                <button class="btn-secondary" onclick="rejectUser('${user.id}')" style="background: #ef4444;">Reject</button>
            </td>
        </tr>
    `).join('');
    
    container.innerHTML = `
        <table class="table">
            <thead>
                <tr>
                    <th>Username</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Phone</th>
                    <th>Requested Role</th>
                    <th>Requested On</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
    `;
}

async function approveUser(userId) {
    if (!confirm('Are you sure you want to approve this user?')) return;
    
    try {
        const response = await fetch(`/api/admin/approve-user/${userId}?session_id=${sessionId}`, {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Failed to approve user');
        
        alert('User approved successfully');
        showPendingApprovals(); // Refresh list
    } catch (error) {
        alert('Failed to approve user: ' + error.message);
    }
}

async function rejectUser(userId) {
    if (!confirm('Are you sure you want to reject this user? This will delete their account.')) return;
    
    try {
        const response = await fetch(`/api/admin/reject-user/${userId}?session_id=${sessionId}`, {
            method: 'POST'
        });
        
        if (!response.ok) throw new Error('Failed to reject user');
        
        alert('User rejected and account deleted');
        showPendingApprovals(); // Refresh list
    } catch (error) {
        alert('Failed to reject user: ' + error.message);
    }
}

// Setup event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Existing event listeners...
    loadContraFirms();
    setupEventListeners();
    refreshACATList();
    checkAuth();
    
    // Add user creation form listener
    const userCreationForm = document.getElementById('userCreationForm');
    if (userCreationForm) {
        userCreationForm.addEventListener('submit', function(e) {
            e.preventDefault();
            createUserAccount();
        });
    }
});

