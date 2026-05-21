# Deploying to Wikimedia Toolforge

This guide deploys WikiTop100 as a **build service** container on Toolforge — the recommended approach. No code changes are needed beyond what's already committed.

## Prerequisites

- A [Toolforge account](https://wikitech.wikimedia.org/wiki/Help:Toolforge/Quickstart) with SSH access
- The tool name registered (e.g. `wikitop100`) via [toolsadmin](https://toolsadmin.wikimedia.org/)

## One-time Setup

### 1. Clone the repo on the Toolforge bastion

```bash
ssh <username>@login.toolforge.org
become wikitop100
git clone https://github.com/<your-org>/wikitop100.git $HOME
```

### 2. Build the container image

```bash
toolforge build start wikitop100
```

This reads `$HOME/Dockerfile`, installs dependencies (including the spaCy model), and pushes the image to Toolforge's internal registry.

Watch the build log with:
```bash
toolforge build log wikitop100 --follow
```

### 3. Create the service template

Write `$HOME/service.template`:

```yaml
# Toolforge webservice template for wikitop100
cpu: 500m
mem: 1Gi
type: buildservice
buildservice-image: docker-registry.tools.wmflabs.org/toolforge-python3.13:latest
health-check-path: /
```

1Gi memory is recommended because spaCy + graph assembly needs more than the default 512Mi.

### 4. Start the webservice

```bash
toolforge webservice --template=$HOME/service.template start
```

Your tool is now live at **https://wikitop100.toolforge.org**.

### 5. Set environment variables

```bash
toolforge envvars set WIKI_USER_AGENT="WikiTop100Viz/1.0 (contact: your-email@example.com)"
```

The User-Agent is required by Wikimedia API policy. You can also set `WIKI_MAX_CONCURRENT`, `WIKI_CACHE_DIR`, etc. (see `.env.example`).

## Updating

```bash
become wikitop100
cd $HOME
git pull
toolforge build start wikitop100
toolforge webservice restart
```

## Logs

```bash
toolforge webservice logs         # recent logs
toolforge webservice logs -f      # follow in real-time
```

## Troubleshooting

| Symptom | Likely fix |
|---------|-----------|
| Pod crashes on start | Check logs: `toolforge webservice logs`. Common cause: out of memory — bump `mem: 1Gi` in `service.template` |
| Build fails | `toolforge build log wikitop100 --follow` to see where it failed. Common cause: network timeout downloading spaCy model — retry the build |
| "No data for this date" in UI | The Hatnote API may not have data for that date yet, or the date format is wrong |
| 502 Bad Gateway | The container may be taking too long to start. Check `toolforge webservice status` and logs |
| Rate-limited by MW API | Set `WIKI_MAX_CONCURRENT=2` and a proper `WIKI_USER_AGENT` with your contact email |
