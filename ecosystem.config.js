// PM2 Ecosystem Configuration
// =============================
//
// Start all:    pm2 start ecosystem.config.js
// Stop all:     pm2 stop all
// Logs:         pm2 logs
// Monitor:      pm2 monit
// Status:       pm2 status
// Restart:      pm2 restart all
//
// Architecture:
//   agent-daemon  (:8420)  — Background task processor + SSE events
//   agent-api     (:8000)  — Chat API + React UI (serves build)
//   email-digest            — Daily Outlook email digest at 08:00

const path = require("path");

module.exports = {
  apps: [
    // ─── 1. Agent Daemon ──────────────────────────────────
    // Background agent that picks up tasks and executes them
    // SSE events at :8420/events, task API at :8420/task
    {
      name: "agent-daemon",
      script: "daemon_v2.py",
      interpreter: "C:/Users/Στέφανος/AppData/Local/Programs/Python/Python313/python.exe",
      cwd: __dirname,

      env: {
        PYTHONUNBUFFERED: "1",
        AGENT_CHECK_INTERVAL: "300",    // 5 min between cycles
        AGENT_MAX_TASKS: "3",
        AGENT_API_PORT: "8420",
      },
      env_development: {
        AGENT_CHECK_INTERVAL: "60",     // 1 min (dev)
        AGENT_MAX_TASKS: "1",
      },
      env_production: {
        AGENT_CHECK_INTERVAL: "600",    // 10 min (prod)
        AGENT_MAX_TASKS: "5",
      },

      autorestart: true,
      watch: false,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,

      log_file: "./logs/daemon-combined.log",
      out_file: "./logs/daemon-out.log",
      error_file: "./logs/daemon-error.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      max_memory_restart: "500M",
      kill_timeout: 10000,
    },

    // ─── 2. API Server + React UI ─────────────────────────
    // Chat backend (Claude Agent SDK) + serves React build
    // http://localhost:8000 — full UI + API + daemon proxy
    {
      name: "agent-api",
      script: "api_server.py",
      interpreter: "C:/Users/Στέφανος/AppData/Local/Programs/Python/Python313/python.exe",
      cwd: __dirname,

      env: {
        PYTHONUNBUFFERED: "1",
        AGENT_API_PORT: "8000",
        AGENT_DAEMON_PORT: "8420",
      },

      autorestart: true,
      watch: false,
      max_restarts: 10,
      min_uptime: "5s",
      restart_delay: 3000,

      log_file: "./logs/api-combined.log",
      out_file: "./logs/api-out.log",
      error_file: "./logs/api-error.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      max_memory_restart: "300M",
      kill_timeout: 5000,
    },

    // ─── 3. Telegram Bot ─────────────────────────────────
    // Chat with the agent via Telegram (long-polling)
    {
      name: "telegram-bot",
      script: "telegram_bot.py",
      interpreter: "C:/Users/Στέφανος/AppData/Local/Programs/Python/Python313/python.exe",
      cwd: __dirname,

      env: {
        PYTHONUNBUFFERED: "1",
      },

      autorestart: true,
      watch: false,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,

      log_file: "./logs/telegram-combined.log",
      out_file: "./logs/telegram-out.log",
      error_file: "./logs/telegram-error.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      max_memory_restart: "300M",
      kill_timeout: 5000,
    },

    // ─── 4. Outlook Email Digest ──────────────────────────
    // Runs daily at 08:00, reads Outlook, sends summary to Gmail
    {
      name: "email-digest",
      script: path.join(
        ".Claude",
        "Skills",
        "outlook-email-digest",
        "scripts",
        "outlook_digest.py"
      ),
      args: "--schedule",
      interpreter: "C:/Users/Στέφανος/AppData/Local/Programs/Python/Python313/python.exe",
      cwd: path.resolve(__dirname, ".."),  // parent dir (AGENTI_SDK/aclaude)

      env: {
        PYTHONUNBUFFERED: "1",
      },

      autorestart: true,
      watch: false,
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 10000,

      log_file: "./proactive/logs/digest-combined.log",
      out_file: "./proactive/logs/digest-out.log",
      error_file: "./proactive/logs/digest-error.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      max_memory_restart: "200M",
    },
  ],
};
