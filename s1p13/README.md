# SaaS Revenue Retention - Your Business Dashboard

## What this is
Your private business analytics dashboard. It shows you what's happening in your business, helps you decide what to do about it, and tracks whether you're on target - all in one place.

## Your 3 sections
**UNDERSTAND** - See your key numbers, charts, and any unusual patterns
**DECIDE** - Read insights and recommendations written in plain English
**MONITOR** - Track forecasts, set targets, and get alerts automatically

Plus an **Interactive explorer** (click any bar to filter everything) and a **User manual**.

## New here? Start with the User Manual tab
Click "User manual" in the sidebar. It explains every section in plain English.

## Deployment Checklist
- [ ] npm install (run once - generates package-lock.json)
- [ ] wrangler.toml: name = "s1p13", main before [site], bucket = "./dist"
- [ ] npm run build -> check the dist/ folder was created
- [ ] npx wrangler deploy -> note the live URL
- [ ] (optional) wrangler secret put FORECAST_LOOKUP -> paste the contents of forecast_lookup.json (without it the Worker reads the forecast from the deployed data file)
- [ ] Test: open the live URL -> dashboard loads with data
- [ ] Test: open the live URL /mcp -> MCP manifest appears

## How to run locally
1. npm install
2. npm run dev -> open http://localhost:5173

## How to deploy
1. npm run build
2. npx wrangler deploy
-> Live at: https://s1p13.<your-account>.workers.dev (Cloudflare shows the exact address after deploy)

## MCP Integration (for Claude)
Add this URL to Claude as an MCP connector (read-only):
https://s1p13.<your-account>.workers.dev/mcp
Claude can then read your live business data directly.

## How to update your dashboard
1. Run the pipeline: python main.py
2. Then: python export_for_frontend.py
3. Copy the new output/ folder into public/data/ (or rerun generate_react_frontend.py)
4. Then: npm run build && npx wrangler deploy

## Access control
No login screens are built in. Protect the site with Cloudflare Zero Trust (Access) in your Cloudflare dashboard.

## Support
Contact the analyst who set this up for you.
