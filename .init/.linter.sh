#!/bin/bash
cd /home/kavia/workspace/code-generation/event-planner-pro-207444-207453/event_backend
source venv/bin/activate
flake8 .
LINT_EXIT_CODE=$?
if [ $LINT_EXIT_CODE -ne 0 ]; then
  exit 1
fi

