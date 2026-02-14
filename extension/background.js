const API_BASE = "http://localhost:8000";
let authToken = null;

// Load token from storage on startup
chrome.storage.local.get(['authToken'], (result) => {
  if (result.authToken) {
    authToken = result.authToken;
    console.log("[AUTH] Loaded auth token from storage");
  }
});

async function apiFetch(path, options = {}) {
  const url = `${API_BASE}${path}`;
  
  // Add Authorization header if we have a token
  const headers = options.headers || {};
  if (authToken) {
    headers['Authorization'] = `Bearer ${authToken}`;
  }
  
  options.headers = headers;
  
  console.log("[API] Fetch:", url, options);
  
  const res = await fetch(url, options);
  
  // Handle 401 Unauthorized - clear token and notify user
  if (res.status === 401) {
    authToken = null;
    chrome.storage.local.remove('authToken');
    throw new Error("Authentication expired. Please login again.");
  }
  
  if (res.status >= 400) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status} on ${url}: ${text}`);
  }
  
  return res.json();
}

// Listen for messages from extension
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  console.log("[MESSAGE] Background got message:", msg);
  
  const { type, payload } = msg;
  
  // --- Auth Success ---
  if (type === "AUTH_SUCCESS") {
    authToken = msg.token;
    chrome.storage.local.set({ 
      authToken: msg.token,
      userEmail: msg.email 
    });
    console.log("[AUTH] Authentication successful");
    sendResponse({ success: true });
    return true;
  }
  
  // --- Check Auth ---
  if (type === "CHECK_AUTH") {
    (async () => {
      try {
        if (!authToken) {
          sendResponse({ authenticated: false, message: "No token" });
          return;
        }
        
        const data = await apiFetch("/auth/me");
        sendResponse({ authenticated: true, user: data });
      } catch (err) {
        sendResponse({ authenticated: false, error: err.toString() });
      }
    })();
    return true;
  }
  
  // --- Logout ---
  if (type === "LOGOUT") {
    authToken = null;
    chrome.storage.local.clear();
    sendResponse({ success: true });
    return true;
  }
  
  // --- Add Task ---
  if (type === "ADD_TASK") {
    (async () => {
      try {
        const data = await apiFetch("/tasks/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        sendResponse(data);
      } catch (err) {
        sendResponse({ error: err.toString() });
      }
    })();
    return true;
  }
  
  // --- Get Tasks ---
  if (type === "GET_TASKS") {
    (async () => {
      try {
        const data = await apiFetch("/tasks/");
        sendResponse(data);
      } catch (err) {
        sendResponse({ error: err.toString() });
      }
    })();
    return true;
  }
  
  // --- Schedule ---
  if (type === "SCHEDULE") {
    (async () => {
      try {
        const data = await apiFetch("/scheduler/", { method: "POST" });
        sendResponse(data);
      } catch (err) {
        sendResponse({ error: err.toString() });
      }
    })();
    return true;
  }
  
  // --- Get Settings ---
  if (type === "GET_SETTINGS") {
    (async () => {
      try {
        const data = await apiFetch("/settings/");
        sendResponse(data);
      } catch (err) {
        sendResponse({ error: err.toString() });
      }
    })();
    return true;
  }
  
  // --- Save Settings ---
  if (type === "SAVE_SETTINGS") {
    (async () => {
      try {
        const data = await apiFetch("/settings/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        sendResponse(data);
      } catch (err) {
        sendResponse({ error: err.toString() });
      }
    })();
    return true;
  }
  
  // --- Delete Task ---
  if (type === "DELETE_TASK") {
    (async () => {
      try {
        console.log(`[DELETE] Deleting task ${payload.id}`);
        
        const deleteResult = await apiFetch(`/tasks/${payload.id}`, { 
          method: "DELETE" 
        });
        
        console.log("[DELETE] Delete result:", deleteResult);
        
        await new Promise(resolve => setTimeout(resolve, 1000));
        
        console.log("[SYNC] Syncing calendar...");
        await apiFetch("/sync/", { method: "POST" });
        
        console.log("[TASKS] Fetching updated tasks...");
        const tasks = await apiFetch("/tasks/");
        
        sendResponse(tasks);
      } catch (err) {
        console.error("[ERROR] Delete task error:", err);
        sendResponse({ error: err.toString() });
      }
    })();
    return true;
  }
  
  // --- Sync & Get Tasks ---
  if (type === "SYNC_AND_GET_TASKS") {
    (async () => {
      try {
        await apiFetch("/sync/", { method: "POST" });
        const tasks = await apiFetch("/tasks/");
        sendResponse(tasks);
      } catch (err) {
        sendResponse({ error: err.toString() });
      }
    })();
    return true;
  }
});
