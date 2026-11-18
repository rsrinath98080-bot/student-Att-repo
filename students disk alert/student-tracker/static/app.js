/**
 * Student Attendance Tracking System - Vanilla Frontend Client
 * Handles modal alert dialog with focus trapping, clipboard copying,
 * asynchronous alert acknowledgment, and dark/light theme management.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Theme Management
  initTheme();

  // Alert Dialog Modal Management
  initModal();

  // Copy Guardian Message
  initCopyButton();
});

/**
 * Theme Switcher (Auto, Light, Dark)
 */
function initTheme() {
  const themeToggleBtn = document.getElementById("theme-toggle-btn");
  const themeIcon = document.getElementById("theme-icon");
  const themeLabel = document.getElementById("theme-label");

  function applyTheme(theme) {
    if (theme === "dark") {
      document.documentElement.setAttribute("data-theme", "dark");
      if (themeIcon) themeIcon.textContent = "🌙";
      if (themeLabel) themeLabel.textContent = "Dark";
    } else if (theme === "light") {
      document.documentElement.setAttribute("data-theme", "light");
      if (themeIcon) themeIcon.textContent = "☀️";
      if (themeLabel) themeLabel.textContent = "Light";
    } else {
      document.documentElement.removeAttribute("data-theme");
      if (themeIcon) themeIcon.textContent = "🌓";
      if (themeLabel) themeLabel.textContent = "Auto";
    }
  }

  const savedTheme = localStorage.getItem("student_tracker_theme") || "auto";
  applyTheme(savedTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      const current = localStorage.getItem("student_tracker_theme") || "auto";
      let next = "dark";
      if (current === "dark") next = "light";
      else if (current === "light") next = "auto";
      else next = "dark";

      localStorage.setItem("student_tracker_theme", next);
      applyTheme(next);
    });
  }
}

/**
 * Focus Trapping & Accessible Alert Dialog Modal
 */
let previouslyFocusedElement = null;

function initModal() {
  const modalBackdrop = document.getElementById("alert-modal-backdrop");
  if (!modalBackdrop) return;

  const bellBtn = document.getElementById("notification-bell-btn");
  const understandBtn = document.getElementById("modal-understand-btn");
  const copyBtn = document.getElementById("modal-copy-btn");

  // Focusable elements inside dialog
  const focusableSelector = 'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

  function openModal() {
    previouslyFocusedElement = document.activeElement;
    modalBackdrop.classList.add("open");
    modalBackdrop.setAttribute("aria-hidden", "false");

    // Focus the first action button
    const firstFocusable = modalBackdrop.querySelector(focusableSelector);
    if (firstFocusable) {
      setTimeout(() => firstFocusable.focus(), 50);
    }

    document.addEventListener("keydown", trapFocusAndHandleEsc);
  }

  function closeModal() {
    modalBackdrop.classList.remove("open");
    modalBackdrop.setAttribute("aria-hidden", "true");
    document.removeEventListener("keydown", trapFocusAndHandleEsc);

    if (previouslyFocusedElement && typeof previouslyFocusedElement.focus === "function") {
      previouslyFocusedElement.focus();
    }
  }

  function trapFocusAndHandleEsc(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      closeModal();
      return;
    }

    if (e.key === "Tab") {
      const focusables = Array.from(modalBackdrop.querySelectorAll(focusableSelector));
      if (focusables.length === 0) return;

      const first = focusables[0];
      const last = focusables[focusables.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    }
  }

  // Bell button opens modal
  if (bellBtn) {
    bellBtn.addEventListener("click", () => {
      openModal();
    });
  }

  // "I understand" button acknowledges alert and closes modal
  if (understandBtn) {
    understandBtn.addEventListener("click", async () => {
      const alertId = understandBtn.getAttribute("data-alert-id");
      closeModal();

      if (alertId) {
        try {
          const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
          await fetch("/api/alert/acknowledge", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Requested-With": "XMLHttpRequest",
            },
            body: JSON.stringify({ alert_id: parseInt(alertId, 10), csrf_token: csrfToken }),
          });
        } catch (err) {
          console.error("Failed to acknowledge alert:", err);
        }
      }
    });
  }

  // Auto-open if server flagged for load
  if (modalBackdrop.getAttribute("data-show-on-load") === "true") {
    openModal();
  }
}

/**
 * Copy Message to Clipboard with visible toast
 */
function initCopyButton() {
  const copyBtn = document.getElementById("modal-copy-btn");
  const messageBox = document.getElementById("modal-guardian-message");
  const copyToast = document.getElementById("modal-copy-toast");

  if (!copyBtn || !messageBox) return;

  copyBtn.addEventListener("click", async () => {
    const textToCopy = messageBox.value;
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(textToCopy);
      } else {
        messageBox.select();
        document.execCommand("copy");
      }

      if (copyToast) {
        copyToast.classList.add("show");
        setTimeout(() => copyToast.classList.remove("show"), 2500);
      }
    } catch (err) {
      console.warn("Clipboard API failed, selecting text instead", err);
      messageBox.select();
      if (copyToast) {
        copyToast.textContent = "Selected! Press Ctrl+C / Cmd+C to copy";
        copyToast.classList.add("show");
        setTimeout(() => copyToast.classList.remove("show"), 2500);
      }
    }
  });
}
