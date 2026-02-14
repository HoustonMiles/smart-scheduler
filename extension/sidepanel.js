const API_BASE = "http://localhost:8000";

// ===========================
// TOAST SYSTEM
// ===========================
function showToast(message, isError = false) {
  const toastContainer = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${isError ? 'error' : 'success'}`;
  
  toast.innerHTML = `
    <div class="toast-content">
      <div>${message}</div>
    </div>
    <button class="toast-close" onclick="this.parentElement.remove()">×</button>
  `;
  
  toastContainer.appendChild(toast);
  
  setTimeout(() => {
    toast.classList.add('removing');
    setTimeout(() => {
      if (toast.parentElement) {
        toast.remove();
      }
    }, 300);
  }, 3000);
}

// ===========================
// Authentication
// ===========================
async function checkAuthStatus() {
  console.log("Checking auth status...");
  
  return new Promise((resolve) => {
    chrome.storage.local.get(['authToken', 'userEmail'], async (result) => {
      if (result.authToken) {
        try {
          const response = await fetch(`${API_BASE}/auth/me`, {
            headers: {
              'Authorization': `Bearer ${result.authToken}`,
              'Content-Type': 'application/json'
            }
          });
          
          if (response.ok) {
            const user = await response.json();
            document.getElementById('userEmail').textContent = user.email;
            showMainApp();
            resolve(true);
          } else {
            chrome.storage.local.clear();
            showLoginScreen();
            resolve(false);
          }
        } catch (error) {
          console.error("Auth check failed:", error);
          showLoginScreen();
          resolve(false);
        }
      } else {
        showLoginScreen();
        resolve(false);
      }
    });
  });
}

function showLoginScreen() {
  document.getElementById('loginScreen').classList.remove('hidden');
  document.getElementById('mainApp').classList.remove('visible');
}

function showMainApp() {
  document.getElementById('loginScreen').classList.add('hidden');
  document.getElementById('mainApp').classList.add('visible');
  loadTasks();
  loadSettings();
  loadSchedule();
}

// ===========================
// Login Handler
// ===========================
document.getElementById("loginBtn").addEventListener("click", () => {
  const sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
  const loginUrl = `${API_BASE}/login?session_id=${sessionId}`;
  
  chrome.tabs.create({ url: loginUrl }, (tab) => {
    if (chrome.runtime.lastError) {
      showToast("Failed to open login page", true);
      return;
    }
    
    const loginTabId = tab.id;
    showToast("Login window opened");
    
    let pollCount = 0;
    const maxPolls = 60;
    
    const checkInterval = setInterval(async () => {
      pollCount++;
      
      try {
        const response = await fetch(`${API_BASE}/auth/poll/${sessionId}`);
        const data = await response.json();
        
        if (data.authenticated && data.token) {
          clearInterval(checkInterval);
          
          await new Promise((resolve) => {
            chrome.storage.local.set({
              authToken: data.token,
              userEmail: data.email
            }, resolve);
          });
          
          showToast("Login successful!");
          document.getElementById('userEmail').textContent = data.email;
          
          chrome.tabs.remove(loginTabId);
          
          setTimeout(() => {
            showMainApp();
          }, 100);
        }
      } catch (error) {
        console.error("Poll error:", error);
      }
      
      if (pollCount >= maxPolls) {
        clearInterval(checkInterval);
        showToast("Login timeout", true);
      }
    }, 2000);
  });
});

document.getElementById("logoutBtn").addEventListener("click", () => {
  if (confirm("Are you sure you want to logout?")) {
    chrome.storage.local.clear(() => {
      showLoginScreen();
      showToast("Logged out");
    });
  }
});

// ===========================
// API Calls
// ===========================
async function authenticatedFetch(path, options = {}) {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get(['authToken'], async (result) => {
      if (!result.authToken) {
        showToast("Please login first", true);
        showLoginScreen();
        reject(new Error("Not authenticated"));
        return;
      }
      
      const headers = options.headers || {};
      headers['Authorization'] = `Bearer ${result.authToken}`;
      headers['Content-Type'] = 'application/json';
      
      options.headers = headers;
      
      try {
        const response = await fetch(`${API_BASE}${path}`, options);
        
        if (response.status === 401) {
          chrome.storage.local.clear();
          showLoginScreen();
          reject(new Error("Session expired"));
          return;
        }
        
        if (!response.ok) {
          const text = await response.text();
          reject(new Error(`HTTP ${response.status}: ${text}`));
          return;
        }
        
        const data = await response.json();
        resolve(data);
      } catch (error) {
        console.error("Fetch error:", error);
        reject(error);
      }
    });
  });
}

async function loadTasks() {
  console.log("[loadTasks] Starting...");
  try {
    const tasks = await authenticatedFetch("/tasks/");
    console.log("[loadTasks] Fetched tasks:", tasks);
    renderTasks(tasks);
    console.log("[loadTasks] Rendered tasks");
  } catch (error) {
    console.error("[loadTasks] Failed:", error);
    showToast("Failed to load tasks", true);
  }
}

async function loadSettings() {
  try {
    const response = await authenticatedFetch("/settings/");
    const settings = response.data || response;
    document.getElementById("minHour").value = settings.min_hour || 9;
    document.getElementById("maxHour").value = settings.max_hour || 18;
    document.getElementById("bufferMinutes").value = settings.buffer_minutes || 60;
  } catch (error) {
    console.error("Failed to load settings:", error);
  }
}

async function loadSchedule() {
  console.log("=== Loading Schedule ===");
  
  try {
    // Show loading state
    document.getElementById('scheduleView').innerHTML = 
      '<div class="empty-state"><span class="loading">⟳</span> Loading schedule...</div>';
    
    const tasks = await authenticatedFetch("/tasks/");
    console.log("Loaded tasks:", tasks);
    
    if (!Array.isArray(tasks) || tasks.length === 0) {
      document.getElementById('scheduleView').innerHTML = 
        '<div class="empty-state">No tasks yet. Add tasks and click "Schedule All Tasks"</div>';
      return;
    }
    
    // Fetch sessions for all tasks
    const allSessions = [];
    let hasErrors = false;
    
    for (const task of tasks) {
      try {
        console.log(`Fetching sessions for task ${task.id} (${task.title})...`);
        const response = await authenticatedFetch(`/tasks/${task.id}/sessions`);
        console.log(`Response for task ${task.id}:`, response);
        
        // Handle StandardResponse format
        let sessions = [];
        
        if (response && response.success && response.data && response.data.sessions) {
          sessions = response.data.sessions;
          console.log(`✓ Found ${sessions.length} sessions in response.data.sessions`);
        } else if (response && response.data && Array.isArray(response.data)) {
          sessions = response.data;
          console.log(`✓ Found ${sessions.length} sessions in response.data (array)`);
        } else if (response && Array.isArray(response.sessions)) {
          sessions = response.sessions;
          console.log(`✓ Found ${sessions.length} sessions in response.sessions`);
        } else if (Array.isArray(response)) {
          sessions = response;
          console.log(`✓ Found ${sessions.length} sessions in response (array)`);
        } else {
          console.warn(`⚠ Unexpected response format for task ${task.id}:`, response);
        }
        
        // Add sessions with task info
        if (sessions && sessions.length > 0) {
          console.log(`Processing ${sessions.length} sessions for task ${task.title}...`);
          
          sessions.forEach((session, idx) => {
            console.log(`  Session ${idx + 1}:`, {
              start: session.start,
              end: session.end,
              taskTitle: session.taskTitle,
              priority: session.priority
            });
            
            if (session.start && session.end) {
              const sessionData = {
                taskTitle: session.taskTitle || task.title,
                taskId: session.taskId || task.id,
                priority: session.priority !== undefined ? session.priority : task.priority,
                start: session.start,
                end: session.end,
                duration: session.duration_minutes || 
                         Math.round((new Date(session.end) - new Date(session.start)) / 60000)
              };
              
              console.log(`  ✓ Adding session:`, sessionData);
              allSessions.push(sessionData);
            } else {
              console.warn(`  ✗ Session missing start/end:`, session);
            }
          });
        } else {
          console.log(`No sessions found for task ${task.id}`);
        }
      } catch (error) {
        console.error(`Failed to load sessions for task ${task.id}:`, error);
        hasErrors = true;
      }
    }
    
    console.log("=== Collection Complete ===");
    console.log(`Total sessions collected: ${allSessions.length}`);
    console.log("All sessions:", allSessions);
    
    if (allSessions.length === 0) {
      if (hasErrors) {
        document.getElementById('scheduleView').innerHTML = 
          '<div class="empty-state">Error loading some sessions. Check console for details.</div>';
      } else {
        document.getElementById('scheduleView').innerHTML = 
          '<div class="empty-state">No scheduled sessions yet. Click "Schedule All Tasks" to create your schedule!</div>';
      }
      return;
    }
    
    console.log("Calling renderSchedule with", allSessions.length, "sessions");
    renderSchedule(allSessions);
    console.log("renderSchedule completed");
    
    const scheduleDiv = document.getElementById('scheduleView'); 
    console.log("scheduleView element:", scheduleDiv);
    console.log("scheduleView innerHTML length:", scheduleDiv?.innerHTML?.length);
    console.log("scheduleView is visible?", scheduleDiv?.offsetHeight > 0);

    const scheduleTab = document.getElementById('schedule');
    console.log("schedule tab-content:", scheduleTab);
    console.log("schedule has 'active' class?", scheduleTab?.classList.contains('active'));
    console.log("schedule display style:", window.getComputedStyle(scheduleTab).display);
    
  } catch (error) {
    console.error("Failed to load schedule:", error);
    document.getElementById('scheduleView').innerHTML = 
      '<div class="empty-state">Error loading schedule: ' + error.message + '</div>';
  }
}

function renderSchedule(sessions) {
  console.log("=== Rendering Schedule ===");
  console.log("Sessions to render:", sessions.length);
  
  if (!sessions || sessions.length === 0) {
    document.getElementById('scheduleView').innerHTML = 
      '<div class="empty-state">No sessions to display</div>';
    return;
  }
  
  // Group sessions by day
  const sessionsByDay = {};
  
  sessions.forEach(session => {
    if (!session.start) {
      console.warn("Session missing start time:", session);
      return;
    }
    
    const date = new Date(session.start);
    if (isNaN(date.getTime())) {
      console.error("Invalid date for session:", session);
      return;
    }
    
    const dayKey = date.toISOString().split('T')[0]; // YYYY-MM-DD
    
    if (!sessionsByDay[dayKey]) {
      sessionsByDay[dayKey] = [];
    }
    
    sessionsByDay[dayKey].push(session);
  });
  
  console.log("Sessions grouped by day:", Object.keys(sessionsByDay).length, "days");
  
  // Sort sessions within each day by start time
  Object.keys(sessionsByDay).forEach(day => {
    sessionsByDay[day].sort((a, b) => new Date(a.start) - new Date(b.start));
  });
  
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  // Render Google Calendar-style day cards
  const scheduleHTML = Object.keys(sessionsByDay)
    .sort()
    .map(dayKey => {
      const date = new Date(dayKey + 'T00:00:00');
      const isToday = date.getTime() === today.getTime();
      const sessions = sessionsByDay[dayKey];
      
      return `
        <div class="gcal-day ${isToday ? 'gcal-day-today' : ''}">
          <div class="gcal-day-header">
            <div>
              <span class="gcal-date">${formatDayHeader(date)}</span>
              ${isToday ? '<span class="gcal-today-badge">TODAY</span>' : ''}
            </div>
            <span class="gcal-count">${sessions.length} session${sessions.length !== 1 ? 's' : ''}</span>
          </div>
          <div class="gcal-events">
            ${sessions.map(session => `
              <div class="gcal-event">
                <div class="gcal-event-color" style="background: ${getPriorityColor(session.priority)}"></div>
                <div class="gcal-event-content">
                  <div class="gcal-event-title">${escapeHtml(session.taskTitle)}</div>
                  <div class="gcal-event-time">
                    ${formatTime(session.start)} - ${formatTime(session.end)} 
                    (${session.duration} min)
                  </div>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    })
    .join('');
  
  console.log("Rendered HTML for", Object.keys(sessionsByDay).length, "days");
  
  // ADD THIS LINE TO DEBUG:
  console.log("HTML length:", scheduleHTML.length, "characters");
  console.log("First 500 chars of HTML:", scheduleHTML.substring(0, 500));
  
  if (scheduleHTML) {
    document.getElementById('scheduleView').innerHTML = scheduleHTML;
    console.log("Schedule rendered successfully!");
  } else {
    document.getElementById('scheduleView').innerHTML = 
      '<div class="empty-state">No sessions to display</div>';
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function getPriorityColor(priority) {
  const colors = {
    1: '#ea4335',  // Red - highest priority
    2: '#fbbc04',  // Yellow
    3: '#4285f4',  // Blue
    4: '#34a853',  // Green
    5: '#34a853'   // Green - lowest priority
  };
  return colors[priority] || '#4285f4';
}

function formatDayHeader(date) {
  const options = { weekday: 'long', month: 'long', day: 'numeric' };
  return date.toLocaleDateString('en-US', options);
}

function formatTime(isoString) {
  // Backend returns times like "2025-11-17T09:00:00+00:00"
  // but they're actually in local time, not UTC
  // So we strip the timezone and parse as local
  
  // Remove timezone info (+00:00 or Z)
  const localString = isoString.replace(/\+00:00$/, '').replace(/Z$/, '');
  
  // Parse as local time
  const date = new Date(localString);
  
  return date.toLocaleTimeString('en-US', { 
    hour: 'numeric', 
    minute: '2-digit',
    hour12: true 
  });
}

function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { 
    month: 'short', 
    day: 'numeric', 
    year: 'numeric' 
  });
}

async function deleteTask(id) {
  try {
    await authenticatedFetch(`/tasks/${id}`, { method: 'DELETE' });
    showToast("Task deleted successfully");
    loadTasks();
    loadSchedule();
  } catch (error) {
    showToast("Failed to delete task", true);
  }
}

// ===========================
// Form Validation
// ===========================
function validateTaskForm() {
  const title = document.getElementById("title").value.trim();
  const duration = parseInt(document.getElementById("duration").value);
  const minSession = parseInt(document.getElementById("minSession").value);
  const maxSession = parseInt(document.getElementById("maxSession").value);
  const deadline = document.getElementById("deadline").value;
  const priority = parseInt(document.getElementById("priority").value);

  if (!title) {
    showToast("Please enter a task title", true);
    return false;
  }

  if (!deadline) {
    showToast("Please select a deadline", true);
    return false;
  }

  const deadlineDate = new Date(deadline);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  
  if (deadlineDate < today) {
    showToast("Deadline cannot be in the past", true);
    return false;
  }

  if (!duration || duration <= 0) {
    showToast("Duration must be greater than 0", true);
    return false;
  }

  if (!minSession || minSession <= 0) {
    showToast("Min session must be greater than 0", true);
    return false;
  }

  if (!maxSession || maxSession <= 0) {
    showToast("Max session must be greater than 0", true);
    return false;
  }

  if (minSession > maxSession) {
    showToast("Min session cannot be greater than max session", true);
    return false;
  }

  if (duration < minSession) {
    showToast("Total duration cannot be less than min session", true);
    return false;
  }

  if (!priority || priority < 1 || priority > 5) {
    showToast("Priority must be between 1 and 5", true);
    return false;
  }

  return true;
}

// ===========================
// Task Rendering
// ===========================
function renderTasks(tasks) {
  const list = document.getElementById("taskList");
  
  if (!Array.isArray(tasks)) {
    list.innerHTML = '<div class="empty-state">Error loading tasks</div>';
    return;
  }

  if (tasks.length === 0) {
    list.innerHTML = '<div class="empty-state">No tasks yet. Add your first task above!</div>';
    return;
  }

  list.innerHTML = tasks.map(t => `
    <li data-id="${t.id}" data-priority="${t.priority}">
      <strong>${escapeHtml(t.title)}</strong>
      <small>
        Due: ${formatDate(t.due_date)}<br>
        Duration: ${t.total_duration} minutes<br>
        Sessions: ${t.min_session}-${t.max_session} min<br>
        Priority: ${t.priority} | Status: ${t.status}
      </small>
      <button class="delete-btn" data-id="${t.id}">Delete</button>
    </li>
  `).join("");

  document.querySelectorAll(".delete-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      if (confirm(`Delete "${tasks.find(t => t.id == e.target.dataset.id).title}"?`)) {
        deleteTask(e.target.dataset.id);
      }
    });
  });
}

function formatTime(isoString) {
  // The backend returns times like "2025-11-17T09:00:00+00:00" (UTC)
  // But they should be displayed in the user's local timezone
  
  // Parse the ISO string as UTC
  const date = new Date(isoString);
  
  // Display in user's local timezone
  return date.toLocaleTimeString('en-US', { 
    hour: 'numeric', 
    minute: '2-digit',
    hour12: true,
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone
  });
}

// ===========================
// Event Listeners
// ===========================
document.getElementById("add").addEventListener("click", async () => {
  if (!validateTaskForm()) return;

  const btn = document.getElementById("add");
  const originalText = btn.textContent;
  btn.innerHTML = 'Adding...';
  btn.disabled = true;

  const payload = {
    title: document.getElementById("title").value.trim(),
    due_date: document.getElementById("deadline").value,
    total_duration: parseInt(document.getElementById("duration").value),
    min_session: parseInt(document.getElementById("minSession").value),
    max_session: parseInt(document.getElementById("maxSession").value),
    priority: parseInt(document.getElementById("priority").value),
    allow_overlap: document.getElementById("allowOverlap").checked,
    once_per_day: document.getElementById("oncePerDay").checked
  };

  try {
    await authenticatedFetch("/tasks/", {
      method: 'POST',
      body: JSON.stringify(payload)
    });
    
    showToast("Task added successfully!");
    
    // Clear form
    document.getElementById("title").value = "";
    document.getElementById("duration").value = "";
    document.getElementById("minSession").value = "";
    document.getElementById("maxSession").value = "";
    document.getElementById("priority").value = "";
    document.getElementById("allowOverlap").checked = false;
    document.getElementById("oncePerDay").checked = false;
    
    loadTasks();
  } catch (error) {
    showToast("Failed to add task", true);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
});

document.getElementById("scheduleButton").addEventListener("click", async () => {
  const btn = document.getElementById("scheduleButton");
  const originalText = btn.textContent;
  btn.innerHTML = 'Scheduling...';
  btn.disabled = true;

  try {
    const result = await authenticatedFetch("/scheduler/", { method: 'POST' });
    showToast(result.message || "Tasks scheduled successfully!");
    
    // Reload tasks
    await loadTasks();
    
    // Switch to Schedule tab FIRST
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    document.querySelector('[data-tab="schedule"]').classList.add("active");
    document.getElementById("schedule").classList.add("active");
    
    // Then load schedule (now that tab is visible)
    await loadSchedule();
    
  } catch (error) {
    showToast("Scheduling failed: " + error.message, true);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
});

document.getElementById("refreshSchedule").addEventListener("click", () => {
  loadSchedule();
  showToast("Schedule refreshed");
});

document.getElementById("saveSettings").addEventListener("click", async () => {
  const minHour = parseInt(document.getElementById("minHour").value);
  const maxHour = parseInt(document.getElementById("maxHour").value);
  const bufferMinutes = parseInt(document.getElementById("bufferMinutes").value);

  if (isNaN(minHour) || minHour < 0 || minHour > 23) {
    showToast("Min hour must be between 0 and 23", true);
    return;
  }

  if (isNaN(maxHour) || maxHour < 0 || maxHour > 23) {
    showToast("Max hour must be between 0 and 23", true);
    return;
  }

  if (minHour >= maxHour) {
    showToast("Min hour must be less than max hour", true);
    return;
  }

  if (isNaN(bufferMinutes) || bufferMinutes < 0) {
    showToast("Buffer must be 0 or greater", true);
    return;
  }

  const btn = document.getElementById("saveSettings");
  const originalText = btn.textContent;
  btn.innerHTML = 'Saving...';
  btn.disabled = true;

  const settings = { min_hour: minHour, max_hour: maxHour, buffer_minutes: bufferMinutes };
  
  try {
    await authenticatedFetch("/settings/", {
      method: 'POST',
      body: JSON.stringify(settings)
    });
    showToast("Settings saved successfully!");
  } catch (error) {
    showToast("Failed to save settings", true);
  } finally {
    btn.textContent = originalText;
    btn.disabled = false;
  }
});

// Tab switching
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    tab.classList.add("active");
    document.getElementById(tab.dataset.tab).classList.add("active");
    
    // Refresh schedule when switching to it
    if (tab.dataset.tab === 'schedule') {
      loadSchedule();
    }
  });
});

// Initialize
document.addEventListener("DOMContentLoaded", () => {
  const today = new Date().toISOString().split('T')[0];
  document.getElementById("deadline").setAttribute('min', today);
  checkAuthStatus();
});
