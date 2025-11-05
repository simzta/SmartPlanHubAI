/*  SmartPlanHub — minimal front-end shell
    This file wires up:
      1) A tiny hash-based router for "pages" (no network, no framework)
      2) A simple Chat dock toggle (UI-only, no AI/plumbing yet)

    Notes:
    - We use URL fragments (e.g. #/dashboard) to determine which view to show.
    - There is no persistence or API usage in this starter—purely presentational.
*/

/** -------------------------------------------------------------------------
 * Utilities
 * --------------------------------------------------------------------------
 */

/**
 * Shorthand query selector.
 * @param {string} sel - CSS selector string
 * @param {ParentNode} [ctx=document] - Optional parent context
 * @returns {Element|null}
 */
const $ = (sel, ctx = document) => ctx.querySelector(sel);

/**
 * Render a string of HTML into a given target element.
 * (Keeps things simple for this scaffold—no diffing/VDOM/etc.)
 * @param {Element} target
 * @param {string} html
 */
function render(target, html) {
  target.innerHTML = html.trim();
}

/**
 * Helper to create a standard subtitle paragraph with consistent styling.
 * This keeps our view templates tidy and enforces a uniform look.
 * @param {string} text
 * @returns {string} HTML string
 */
function fmtSubtitle(text) {
  return `<p class="page-subtitle">${text}</p>`;
}

/** -------------------------------------------------------------------------
 * View templates (static, placeholder content)
 * Each key in the Views object is a function that returns HTML for a "page".
 * No data fetching here—just structure to be replaced later.
 * --------------------------------------------------------------------------
 */
const Views = {
  /**
   * Dashboard: high-level overview area
   * Later this could aggregate upcoming deadlines, progress charts, etc.
   */
  dashboard() {
    return `
      <section class="panel">
        <h1 class="page-title">Dashboard</h1>
        ${fmtSubtitle("Overview of deadlines & progress (placeholder)")}
        <div class="empty">
          <h3>No data yet</h3>
          <p>Connect your calendar and documents to see assignments here.</p>
        </div>
      </section>
    `;
  },

  /**
   * Assignments: list of work items with status and progress indicators.
   * For now, we hard-code a few example cards as placeholders.
   */
  assignments() {
    return `
      <section class="panel">
        <h1 class="page-title">Assignments</h1>
        ${fmtSubtitle("Track deadlines and status")}
        <div class="grid">
          ${[1,2,3].map(i => `
            <div class="panel">
              <!-- Card header: title + due date + status pill -->
              <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">
                <div>
                  <div style="font-weight:600;">Sample Assignment ${i}</div>
                  <div class="page-subtitle" style="margin:2px 0 0 0;">Due: Nov 15, 2025</div>
                </div>
                <span style="background:#eef2ff;color:#3730a3;padding:4px 8px;border-radius:999px;font-size:12px;">Not started</span>
              </div>

              <!-- Progress bar (purely visual for now) -->
              <div style="margin-top:10px;display:flex;align-items:center;gap:8px;">
                <div style="height:8px;width:120px;border-radius:8px;background:#e5e7eb;overflow:hidden;">
                  <div style="height:8px;width:0%;background:#4c6bff;"></div>
                </div>
                <span style="font-size:12px;color:#6b7280;">0%</span>
              </div>
            </div>
          `).join("")}
        </div>
      </section>
    `;
  },

  /**
   * Planner: an at-a-glance, day-based scaffold.
   * Later this could show scheduled blocks, suggested study windows, etc.
   */
  planner() {
    return `
      <section class="panel">
        <h1 class="page-title">Planner</h1>
        ${fmtSubtitle("Auto-generated plan (placeholder)")}
        <div class="grid">
          ${Array.from({length:8}).map((_,i) => `
            <div class="panel">
              <div style="font-size:12px;color:#6b7280;">Day ${i+1}</div>
              <div style="margin-top:8px;height:64px;border-radius:8px;background:#f3f4f6;border:1px solid #e5e7eb;"></div>
            </div>
          `).join("")}
        </div>
      </section>
    `;
  },

  /**
   * Projects: eventually a place to show detected documents and project context.
   */
  projects() {
    return `
      <section class="panel">
        <h1 class="page-title">Projects</h1>
        ${fmtSubtitle("Documents & detected work")}
        <ul style="list-style:none;padding:0;margin:0;display:grid;gap:12px;">
          <li class="panel">
            <div style="font-weight:600;">Sample Project</div>
            <div class="page-subtitle">No documents linked yet.</div>
          </li>
        </ul>
      </section>
    `;
  },

  /**
   * Settings: space for user preferences and integrations (calendar, drive, API keys).
   */
  settings() {
    return `
      <section class="panel">
        <h1 class="page-title">Settings</h1>
        ${fmtSubtitle("Connections & preferences")}
        <div class="panel" style="margin-top:12px;">
          Coming soon (calendar & drive connections, OpenAI key, etc.).
        </div>
      </section>
    `;
  },

  /**
   * Fallback view if a route is not recognized.
   */
  notFound() {
    return `
      <section class="panel">
        <h1 class="page-title">Page not found</h1>
        ${fmtSubtitle("The page you requested doesn’t exist.")}
      </section>
    `;
  }
};

/** -------------------------------------------------------------------------
 * Router (very small, hash-based)
 *
 * How it works:
 * - We use URL hash fragments like "#/dashboard".
 * - On load or when the hash changes, we look up the view function for that path
 *   and inject its HTML into <main id="app">.
 * - If the path isn't registered, we render the NotFound view.
 * - "Navigation" links in index.html have href="#/route" and a [data-route] attr.
 * - highlightActiveLinks() gives basic visual feedback for the active route.
 * --------------------------------------------------------------------------
 */

/** Map path strings to view functions */
const ROUTES = {
  "/dashboard": Views.dashboard,
  "/assignments": Views.assignments,
  "/planner": Views.planner,
  "/projects": Views.projects,
  "/settings": Views.settings
};

/**
 * Compute the current route path from the hash.
 * Defaults to "/dashboard" when there is no hash.
 * @returns {string}
 */
function getPath() {
  // strip leading '#' from the fragment (e.g. "#/dashboard" -> "/dashboard")
  const raw = window.location.hash.replace(/^#/, "");
  return raw || "/dashboard";
}

/**
 * Main navigation handler:
 *  - Determines the path
 *  - Selects the appropriate view
 *  - Renders it into the app container
 *  - Updates active link styles
 */
function navigate() {
  const path = getPath();
  const view = ROUTES[path] || Views.notFound;
  const app = $("#app");
  if (!app) return; // Defensive: if #app is missing, do nothing
  render(app, view());
  highlightActiveLinks(path);
}

/**
 * Highlight the active route in the header/sidebar nav.
 * We look for elements with [data-route], compare their href to the current path,
 * and add/remove styling/aria-current accordingly.
 * @param {string} path - current route path, like "/assignments"
 */
function highlightActiveLinks(path) {
  document.querySelectorAll("[data-route]").forEach(a => {
    const href = a.getAttribute("href") || "";
    // Convert a hash link like "#/planner" to "/planner" for comparison.
    const route = href.startsWith("#") ? href.slice(1) : href;

    if (route === path) {
      a.setAttribute("aria-current", "page");   // Accessibility hint
      a.style.background = "#eef2ff";           // Simple visual highlight
    } else {
      a.removeAttribute("aria-current");
      a.style.background = "";
    }
  });
}

/** Listen for changes to the hash (user clicks a nav link, or uses back/forward) */
window.addEventListener("hashchange", navigate);
/** Also run once on initial page load so we render the correct view immediately */
window.addEventListener("DOMContentLoaded", navigate);

/** -------------------------------------------------------------------------
 * Chat dock (UI-only for now)
 *
 * Behavior:
 * - Clicking the floating "Chat" button toggles visibility of the dock.
 * - Clicking the "×" close button, outside the dock, or pressing Escape hides it.
 * - We flip the "hidden" attribute and adjust aria-modal for basic accessibility.
 * --------------------------------------------------------------------------
 */
(function setupChatDock(){
  const toggle = $("#chat-toggle");  // Floating button labeled "Chat"
  const dock = $("#chat-dock");      // The chat panel <section>
  const closeBtn = $("#chat-close"); // The "×" button inside the dock

  // If any required element is missing, abort gracefully.
  if (!toggle || !dock || !closeBtn) return;

  /** Open the chat panel: show + set aria */
  function open() {
    dock.hidden = false;                 // Makes the <section> visible
    dock.setAttribute("aria-modal", "true");
  }

  /** Close the chat panel: hide + set aria */
  function close() {
    dock.hidden = true;                  // Hides the <section>
    dock.setAttribute("aria-modal", "false");
  }

  /** Toggle open/close when clicking the floating button */
  toggle.addEventListener("click", () => {
    const isHidden = dock.hidden;
    if (isHidden) open(); else close();
  });

  /** Close when clicking the "×" in the chat header */
  closeBtn.addEventListener("click", close);

  /**
   * Close when clicking outside the dock:
   * - Ignores clicks on the toggle button itself (so it can reopen).
   * - Only runs if the dock is open.
   */
  document.addEventListener("click", (e) => {
    if (dock.hidden) return; // No action if already closed
    const withinDock = dock.contains(e.target);
    const clickedToggle = toggle.contains(e.target);
    if (!withinDock && !clickedToggle) close();
  });

  /** Close the dock when the user presses Escape (common dialog behavior) */
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") close();
  });
})();
