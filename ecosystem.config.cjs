const path = require("path");

const appDir = __dirname;

module.exports = {
  apps: [
    {
      name: "assistant-api",
      cwd: appDir,
      script: path.join(appDir, "venv/bin/uvicorn"),
      args: "apps.api_gateway.main:app --host 0.0.0.0 --port 8000",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
    {
      name: "assistant-grpc",
      cwd: appDir,
      script: path.join(appDir, "venv/bin/python"),
      args: "-m apps.agent_runtime.grpc_runtime.server.server",
      interpreter: "none",
      autorestart: true,
      max_restarts: 10,
      env: {
        PYTHONUNBUFFERED: "1",
      },
    },
  ],
};
