module.exports = {
  apps: [
    {
      name: 'timologia-api',
      cwd: './back',
      script: 'uvicorn',
      args: 'app:app --host 0.0.0.0 --port 8100',
      interpreter: 'python',
      env: { PYTHONPATH: '.' },
    },
    {
      name: 'timologia-worker',
      cwd: './back',
      script: 'worker.py',
      interpreter: 'python',
      env: { PYTHONPATH: '.' },
    },
  ],
};
