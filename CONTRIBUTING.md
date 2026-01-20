# Contributing

Hey! 👋

This is my first open source project. If you're reading this, I'm already grateful you're here.

## Want to Help?

Go wild. Seriously.

- **Found a bug?** Open an issue.
- **Have an idea?** Open an issue.
- **Want to refactor my spaghetti code?** Please do.
- **Just want to chat?** Shoot me a message.

## How I Work

I move fast and break things (then fix them in patch releases 😅). No strict processes here - just make your changes and submit a PR. I'll review it when I can.

## What Would Help

- Bug fixes
- Documentation (install guides for different OSes)
- UI/UX improvements  
- New SMS providers
- Tests (there are none... yet)
- Feedback on what sucks

## Dev Setup

```bash
# Dashboard
cd dashboard
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py

# Agent (run on a test VM)
python agent/agent.py
```

## No Rules

There's no linting, no CI, no code review checklist. Just write code that works and isn't obviously terrible.

---

Thanks for being here. 🙏
