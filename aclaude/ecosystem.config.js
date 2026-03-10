// PM2 Ecosystem Configuration — AgelClaw VPS
// =============================================
//
// Start:    pm2 start ecosystem.config.js
// Stop:     pm2 stop all
// Logs:     pm2 logs
// Monitor:  pm2 monit
// Status:   pm2 status
//
// Runs agent_run.py which starts all services:
//   daemon  (:8420), api_server (:8000), telegram_bot

module.exports = {
  apps: [
    {
      name: "agelclaw",
      script: "proactive/src/agelclaw/agent_run.py",
      interpreter: "python3",
      cwd: __dirname,

      env: {
        PYTHONUNBUFFERED: "1",
        AGENT_API_PORT: "8000",
        AGENT_DAEMON_PORT: "8420",
        AGENT_CHECK_INTERVAL: "300",
        AGENT_MAX_CONCURRENT: "5",
        CLAUDE_CODE_MAX_OUTPUT_TOKENS: "0",
      },

      autorestart: true,
      watch: false,
      max_restarts: 10,
      min_uptime: "10s",
      restart_delay: 5000,

      log_file: "./logs/agelclaw-combined.log",
      out_file: "./logs/agelclaw-out.log",
      error_file: "./logs/agelclaw-error.log",
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      merge_logs: true,
      max_memory_restart: "1G",
      kill_timeout: 10000,
    },
  ],
};
