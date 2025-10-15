// Global state
let currentValidation = null;
let acceptedSuggestions = new Set();
let customModifications = {};
let currentUser = null;
let sessionId = null;

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
    if (!username) {
        alert('Please enter a username');
        return;
    }
    
    try {
        const response = await fetch(`/api/auth/login?username=${encodeURIComponent(username)}`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Login failed');
        }
        
        const data = await response.json();
        sessionId = data.session_id;
        currentUser = data.user;
        
        // Open new window with authenticated interface
        const newWindow = window.open('', '_blank', 'width=1200,height=800,scrollbars=yes,resizable=yes');
        
        if (newWindow) {
            // Write the authenticated interface HTML to the new window
            newWindow.document.write(`
                <!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>ACAT Correction Service - ${currentUser.first_name} ${currentUser.last_name}</title>
                    <link rel="stylesheet" href="/styles.css">
                </head>
                <body>
                    <div class="container">
                        <header>
                            <h1>ACAT Correction Service</h1>
                            <p>AI-powered validation and correction for DTCC ACAT transfers</p>
                            <div id="authSection">
                                <div id="userInfo" style="display: block;">
                                    <span id="currentUser">${currentUser.first_name} ${currentUser.last_name} (${currentUser.username}) - ${currentUser.role}</span>
                                    <button onclick="logout()">Logout</button>
                                </div>
                            </div>
                        </header>

                        <div class="main-content">
                            <!-- ACAT Creation Wizard -->
                            <div id="acatCreationWizard">
                                <div class="wizard-container">
                                    <div class="wizard-header">
                                        <h2>Create New ACAT Request</h2>
                                        <div class="wizard-progress">
                                            <div class="progress-step active" data-step="1">Account Info</div>
                                            <div class="progress-step" data-step="2">Customer Info</div>
                                            <div class="progress-step" data-step="3">Securities</div>
                                            <div class="progress-step" data-step="4">Review</div>
                                        </div>
                                    </div>

                                    <form id="acatWizardForm">
                                        <!-- Step 1: Account Information -->
                                        <div class="wizard-step" id="step1">
                                            <h3>Account Information</h3>
                                            <div class="form-grid">
                                                <div class="form-group">
                                                    <label for="wizDeliveringAccount">Delivering Account *</label>
                                                    <input type="text" id="wizDeliveringAccount" name="delivering_account" required>
                                                </div>
                                                <div class="form-group">
                                                    <label for="wizReceivingAccount">Receiving Account *</label>
                                                    <input type="text" id="wizReceivingAccount" name="receiving_account" required>
                                                </div>
                                                <div class="form-group">
                                                    <label for="wizContraFirm">Contra Firm *</label>
                                                    <select id="wizContraFirm" name="contra_firm" required>
                                                        <option value="">Select contra firm...</option>
                                                    </select>
                                                </div>
                                                <div class="form-group">
                                                    <label for="wizTransferType">Transfer Type *</label>
                                                    <select id="wizTransferType" name="transfer_type" required>
                                                        <option value="">Select transfer type...</option>
                                                        <option value="full">Full Transfer</option>
                                                        <option value="partial">Partial Transfer</option>
                                                    </select>
                                                </div>
                                            </div>
                                        </div>

                                        <!-- Step 2: Customer Information -->
                                        <div class="wizard-step" id="step2" style="display: none;">
                                            <h3>Customer Information</h3>
                                            <div class="form-grid">
                                                <div class="form-group">
                                                    <label for="wizFirstName">First Name *</label>
                                                    <input type="text" id="wizFirstName" name="first_name" required>
                                                </div>
                                                <div class="form-group">
                                                    <label for="wizLastName">Last Name *</label>
                                                    <input type="text" id="wizLastName" name="last_name" required>
                                                </div>
                                                <div class="form-group">
                                                    <label for="wizSSN">SSN *</label>
                                                    <input type="text" id="wizSSN" name="ssn" required placeholder="123-45-6789">
                                                </div>
                                                <div class="form-group">
                                                    <label for="wizTaxId">Tax ID</label>
                                                    <input type="text" id="wizTaxId" name="tax_id" placeholder="Optional">
                                                </div>
                                            </div>
                                        </div>

                                        <!-- Step 3: Securities -->
                                        <div class="wizard-step" id="step3" style="display: none;">
                                            <h3>Securities</h3>
                                            <div id="wizSecuritiesContainer">
                                                <div class="security-item">
                                                    <div class="form-grid">
                                                        <div class="form-group">
                                                            <label>CUSIP *</label>
                                                            <input type="text" name="cusip" required>
                                                        </div>
                                                        <div class="form-group">
                                                            <label>Symbol *</label>
                                                            <input type="text" name="symbol" required>
                                                        </div>
                                                        <div class="form-group">
                                                            <label>Description *</label>
                                                            <input type="text" name="description" required>
                                                        </div>
                                                        <div class="form-group">
                                                            <label>Quantity *</label>
                                                            <input type="number" name="quantity" required min="1">
                                                        </div>
                                                        <div class="form-group">
                                                            <label>Asset Type *</label>
                                                            <select name="asset_type" required>
                                                                <option value="">Select type...</option>
                                                                <option value="equity">Equity</option>
                                                                <option value="mutual_fund">Mutual Fund</option>
                                                                <option value="bond">Bond</option>
                                                            </select>
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                            <button type="button" onclick="addWizardSecurity()" class="btn-secondary">Add Another Security</button>
                                        </div>

                                        <!-- Step 4: Review -->
                                        <div class="wizard-step" id="step4" style="display: none;">
                                            <h3>Review & Submit</h3>
                                            <div id="wizReviewContent"></div>
                                        </div>

                                        <div class="wizard-actions">
                                            <button type="button" onclick="prevStep()" id="wizPrevBtn" style="display: none;" class="btn-secondary">Previous</button>
                                            <button type="button" onclick="nextStep()" id="wizNextBtn" class="btn-primary">Next</button>
                                            <button type="submit" id="wizSubmitBtn" style="display: none;" class="btn-success">Create ACAT Request</button>
                                        </div>
                                    </form>
                                </div>
                            </div>

                            <!-- Ongoing ACATs -->
                            <div class="results-section">
                                <h2>Ongoing ACATs</h2>
                                <div id="acatList">
                                    <p>Loading ACATs...</p>
                                </div>
                            </div>
                        </div>

                        <!-- Learning Analytics (for full users) -->
                        <div id="learningAnalytics" style="display: none;">
                            <div class="results-section">
                                <h2>Learning Analytics</h2>
                                <div id="learningInsights">
                                    <p>Loading analytics...</p>
                                </div>
                            </div>
                        </div>
                    </div>

                    <script>
                        // Global variables
                        let currentUser = ${JSON.stringify(currentUser)};
                        let sessionId = '${sessionId}';
                        let currentWizardStep = 1;
                        const totalWizardSteps = 4;

                        // Initialize the authenticated interface
                        document.addEventListener('DOMContentLoaded', function() {
                            loadContraFirms();
                            refreshACATList();
                            if (currentUser.role === 'full') {
                                document.getElementById('learningAnalytics').style.display = 'block';
                                loadLearningInsights();
                            }
                        });

                        // Include all the necessary functions from the main app.js
                        // (This would include all the functions like loadContraFirms, refreshACATList, etc.)
                    </script>
                    <script src="/app.js"></script>
                </body>
                </html>
            `);
            newWindow.document.close();
            
            // Close the current window after a short delay
            setTimeout(() => {
                window.close();
            }, 1000);
        } else {
            // Fallback if popup was blocked
            alert('Please allow popups for this site to use the login feature');
            updateAuthUI();
            refreshACATList();
        }
    } catch (error) {
        alert('Login failed: ' + error.message);
    }
}

function logout() {
    currentUser = null;
    sessionId = null;
    updateAuthUI();
    refreshACATList();
}

function updateAuthUI() {
    const loginForm = document.getElementById('loginForm');
    const userInfo = document.getElementById('userInfo');
    const currentUserSpan = document.getElementById('currentUser');
    
    if (currentUser) {
        loginForm.style.display = 'none';
        userInfo.style.display = 'block';
        currentUserSpan.textContent = `${currentUser.first_name} ${currentUser.last_name} (${currentUser.username}) - ${currentUser.role}`;
        updatePermissions();
    } else {
        loginForm.style.display = 'block';
        userInfo.style.display = 'none';
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
    
    // Show learning analytics for full users
    const learningSection = document.getElementById('learningSection');
    if (learningSection) {
        learningSection.style.display = currentUser && currentUser.role === 'full' ? 'block' : 'none';
        if (currentUser && currentUser.role === 'full') {
            loadLearningInsights();
        }
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
    
    // Count by status
    const statusCounts = {};
    const statusLabels = {
        'new': 'New',
        'submitted': 'Submitted',
        'pending_review': 'Pending Review',
        'pending_client': 'Pending Client',
        'pending_delivering': 'Pending Delivering',
        'pending_receiving': 'Pending Receiving',
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
    
    acats.forEach(acat => {
        statusCounts[acat.status] = (statusCounts[acat.status] || 0) + 1;
    });
    
    const cards = Object.entries(statusCounts).map(([status, count]) => `
        <div class="status-card">
            <div class="status-card-count" style="color: ${statusColors[status]}">${count}</div>
            <div class="status-card-label" style="background: ${statusColors[status]}">${statusLabels[status]}</div>
        </div>
    `).join('');
    
    container.innerHTML = cards || '<p>No ACATs to display</p>';
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
    const reason = prompt(`Enter reason for changing status to "${newStatus}":`);
    if (reason && reason.trim()) {
        updateRecordStatus(recordId, newStatus, reason.trim());
    }
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
